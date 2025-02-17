import streamlit as st
from azure.core.credentials import AzureKeyCredential
from azure.ai.language.conversations import ConversationAnalysisClient
from pymongo import MongoClient
import openai
import os
from dotenv import load_dotenv

# 🔹 Cargar variables de entorno
load_dotenv()

# 🔹 Configuración de Azure Language Service (Conversational)
azure_endpoint = os.getenv("AZURE_LANGUAGE_ENDPOINT")
azure_key = os.getenv("AZURE_LANGUAGE_KEY")

# 🔹 Configuración de MongoDB
MONGO_URI = os.getenv("MONGO_URI")
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["ordenadores_db"]
collection = db["ordenadores"]

# 🔹 Configuración de OpenAI en Azure
openai.api_type = "azure"
openai.api_base = os.getenv("AZURE_OPENAI_ENDPOINT")
openai.api_key = os.getenv("AZURE_OPENAI_KEY")
openai.api_version = "2024-07-01-preview"
DEPLOYMENT_NAME = "gpt-4o-mini"  # ⚠️ Reemplázalo con el nombre real de tu deployment en Azure OpenAI

# 🔹 URL base de Blob Storage para los PDF
BLOB_STORAGE_URL = "https://tajamarstorage.blob.core.windows.net/articles/"

# 🔹 Inicializar cliente de Azure para Conversational Service
conv_client = ConversationAnalysisClient(azure_endpoint, AzureKeyCredential(azure_key))

# 🔹 Función para obtener el intent y las entidades
def get_intent_and_entities(text):
    """Obtiene el Intent y Entidades de Azure Conversational Service."""
    try:
        response = conv_client.analyze_conversation(
            task={
                "kind": "Conversation",
                "analysisInput": {"conversationItem": {"id": "1", "participantId": "user", "text": text}},
                "parameters": {"projectName": "Ordenador-conversational", "deploymentName": "production"}
            }
        )

        # Extraer intent y entidades
        intent = response["result"]["prediction"]["topIntent"]
        entities = {entity["category"]: entity["text"] for entity in response["result"]["prediction"]["entities"]}

        print(f"🔍 Intent detectado: {intent}")
        print(f"📌 Entidades detectadas: {entities}")

        return intent, entities
    except Exception as e:
        st.error(f"Error en Conversational Service: {str(e)}")
        return "None", {}

# 🔹 Función para buscar ordenadores en MongoDB
def buscar_ordenador(criterios):
    """Busca ordenadores en MongoDB basándose en las entidades detectadas."""
    if not criterios:
        return [], []

    query_exact = {"$and": []}
    query_relajada = {"$or": []}
    entidades_no_encontradas = []

    # Crear consulta exacta y relajada
    for key, value in criterios.items():
        query_exact["$and"].append({f"json_data.{key}.text": {"$regex": f"^{value}$", "$options": "i"}})
        query_relajada["$or"].append({f"json_data.{key}.text": {"$regex": f".*{value}.*", "$options": "i"}})

    print(f"🧐 Query Exacta para MongoDB: {query_exact}")  # Debug
    print(f"🧐 Query Relajada para MongoDB: {query_relajada}")  # Debug

    # Buscar coincidencia exacta
    resultados_exactos = list(collection.find(query_exact))
    
    if resultados_exactos:
        print(f"✅ Se encontró una coincidencia exacta: {len(resultados_exactos)}")
        return resultados_exactos, []

    # Si no hay coincidencias exactas, buscar coincidencias parciales
    resultados_relajados = list(collection.find(query_relajada))

    if resultados_relajados:
        print(f"⚠️ No se encontró una coincidencia exacta, pero sí {len(resultados_relajados)} coincidencias parciales.")
        return resultados_relajados, entidades_no_encontradas

    # Si no encontró nada, indicar qué entidades no coincidieron
    entidades_no_encontradas = list(criterios.keys())
    print(f"❌ No se encontró ningún ordenador con las siguientes entidades: {entidades_no_encontradas}")

    return [], entidades_no_encontradas


# 🔹 Función para generar respuesta de OpenAI
def generar_respuesta_openai(mensaje):
    """Llama a OpenAI para obtener respuestas naturales."""
    try:
        respuesta = openai.ChatCompletion.create(
            engine=DEPLOYMENT_NAME,
            messages=[
                {"role": "system", "content": "Eres un asistente experto en ordenadores. Responde con información concisa y útil."},
                {"role": "user", "content": mensaje}
            ],
            temperature=0.7,
            max_tokens=150  # ⚠️ Limitamos a 150 tokens para respuestas más cortas
        )
        return respuesta['choices'][0]['message']['content']
    except Exception as e:
        return f"❌ Error en OpenAI: {str(e)}"

# 🔹 Función para formatear la respuesta con especificaciones
def formatear_respuesta_ordenador(ordenadores):
    """Genera una respuesta con las especificaciones de múltiples ordenadores."""
    respuestas = []
    
    for ordenador in ordenadores:
        specs = f"🖥 **{ordenador.get('json_data', {}).get('Marca', [{}])[0].get('text', 'Desconocido')}** {ordenador.get('json_data', {}).get('Modelo', [{}])[0].get('text', 'Desconocido')}\n"
        specs += f"💾 RAM: {ordenador.get('json_data', {}).get('Memoria RAM', [{}])[0].get('text', 'Desconocido')}\n"
        specs += f"⚡ Procesador: {ordenador.get('json_data', {}).get('Procesador', [{}])[0].get('text', 'Desconocido')}\n"
        specs += f"🎮 Gráfica: {ordenador.get('json_data', {}).get('Grafica', [{}])[0].get('text', 'Desconocida')}\n"
        specs += f"💾 Disco Duro: {ordenador.get('json_data', {}).get('Disco Duro', [{}])[0].get('text', 'Desconocido')}\n"
        specs += f"🖥 Pantalla: {ordenador.get('json_data', {}).get('Pantalla', [{}])[0].get('text', 'Desconocida')}\n"
        pdf_link = BLOB_STORAGE_URL + ordenador["document_id"]

        respuestas.append((specs, pdf_link))

    return respuestas  # Retorna una lista de tuplas (especificaciones, link)


# ---------- INTERFAZ CON STREAMLIT ----------
st.title("💬 Chatbot - Búsqueda de Ordenadores")

user_input = st.text_input("Escribe tu consulta aquí...", "")

if st.button("Buscar"):
    if user_input:
        st.info("🔍 Procesando tu consulta...")

        # Obtener intent y entidades del usuario
        intent, entidades = get_intent_and_entities(user_input)

        if intent == "None" or intent == "General_Information":
            respuesta = generar_respuesta_openai(user_input)
            st.success("🤖 Respuesta de OpenAI:")
            st.write(respuesta)

        elif intent == "Search_Computer":
            ordenadores_encontrados, entidades_no_encontradas = buscar_ordenador(entidades)

            if ordenadores_encontrados:
                st.success("🎯 Hemos encontrado estos ordenadores que se adaptan a tu búsqueda:")
                
                respuestas = formatear_respuesta_ordenador(ordenadores_encontrados)

                for specs, pdf_link in respuestas:
                    st.write(specs)
                    st.markdown(f"📄 [Ver ficha completa]({pdf_link})", unsafe_allow_html=True)

            else:
                if entidades_no_encontradas:
                    st.warning(f"❌ No encontramos un ordenador con {' y '.join(entidades_no_encontradas)}, pero estos modelos podrían interesarte:")

                    
                    # Buscar alternativas eliminando las entidades no encontradas
                    entidades_parciales = {k: v for k, v in entidades.items() if k not in entidades_no_encontradas}
                    ordenadores_similares, _ = buscar_ordenador(entidades_parciales)

                    if ordenadores_similares:
                        respuestas_similares = formatear_respuesta_ordenador(ordenadores_similares)
                        for specs, pdf_link in respuestas_similares:
                            st.write(specs)
                            st.markdown(f"📄 [Ver ficha completa]({pdf_link})", unsafe_allow_html=True)
                    else:
                        st.warning("⚠️ No encontramos ningún ordenador con especificaciones similares.")

                else:
                    st.warning("❌ No encontramos un ordenador que coincida con tu búsqueda.")

        elif intent == "Price_Information":
            ordenadores_encontrados, _ = buscar_ordenador(entidades)
            if ordenadores_encontrados:
                for ordenador in ordenadores_encontrados:
                    precio = ordenador.get('json_data', {}).get('precio', [{}])[0].get('text', 'No disponible')
                    st.success(f"💰 El precio del {ordenador['json_data']['Marca'][0]['text']} {ordenador['json_data']['Modelo'][0]['text']} es de {precio}")
            else:
                st.warning("❌ No encontramos información de precios para tu búsqueda.")

        else:
            st.warning("⚠️ No entendí tu consulta, intenta de nuevo.")
    else:
        st.warning("⚠️ Por favor, ingresa un mensaje.")