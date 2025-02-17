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
azure_endpoint = st.secrets["AZURE_LANGUAGE_ENDPOINT"]
azure_key = st.secrets["AZURE_LANGUAGE_KEY"]

# 🔹 Configuración de MongoDB
MONGO_URI = st.secrets["MONGO_URI"]
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["ordenadores_db"]
collection = db["ordenadores"]

# 🔹 Configuración de OpenAI en Azure
openai.api_type = "azure"
openai.api_base = st.secrets["AZURE_OPENAI_ENDPOINT"]
openai.api_key = st.secrets["AZURE_OPENAI_KEY"]
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

        respuestas.append((specs, pdf_link, ordenador["_id"]))

    return respuestas  # Retorna una lista de tuplas (especificaciones, link, ID)

# ---------- INTERFAZ CON STREAMLIT ----------
st.title("Chatbot - Búsqueda de Ordenadores")

user_input = st.text_input("Escribe tu consulta aquí...", "")

if st.button("Buscar"):
    if user_input:
        loading_message = st.empty()  
        loading_message.info("🔍 Procesando tu consulta...")  

        intent, entidades = get_intent_and_entities(user_input)

        loading_message.empty()

        if intent == "Order_Computer":
            ordenadores_encontrados, _ = buscar_ordenador(entidades)

            if ordenadores_encontrados:
                st.success("🛒 Te recomendamos este ordenador para tu compra:")
                respuestas = formatear_respuesta_ordenador(ordenadores_encontrados)

                for specs, pdf_link, ordenador_id in respuestas:
                    st.write(specs)
                    st.markdown(f"📄 [Ver ficha completa]({pdf_link})", unsafe_allow_html=True)
                    
                    if st.button(f"🛍️ Comprar", key=ordenador_id):
                        st.success("✅ Compra realizada con éxito.")

            else:
                st.warning("❌ No encontramos un ordenador con esas especificaciones disponibles para compra.")

        elif intent == "Search_Computer":
            ordenadores_encontrados, entidades_no_encontradas = buscar_ordenador(entidades)

            if ordenadores_encontrados:
                st.success("🎯 Hemos encontrado estos ordenadores que se adaptan a tu búsqueda:")
                respuestas = formatear_respuesta_ordenador(ordenadores_encontrados)

                for specs, pdf_link, _ in respuestas:
                    st.write(specs)
                    st.markdown(f"📄 [Ver ficha completa]({pdf_link})", unsafe_allow_html=True)

        else:
            st.warning("⚠️ No entendí tu consulta, intenta de nuevo.")

    else:
        st.warning("⚠️ Por favor, ingresa un mensaje.")
