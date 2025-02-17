import streamlit as st
from azure.core.credentials import AzureKeyCredential
from azure.ai.language.conversations import ConversationAnalysisClient
from pymongo import MongoClient
import openai
import os
from dotenv import load_dotenv
import time  

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
DEPLOYMENT_NAME = "gpt-4o-mini"

# 🔹 URL base de Blob Storage para los PDF
BLOB_STORAGE_URL = "https://tajamarstorage.blob.core.windows.net/articles/"

# 🔹 Inicializar cliente de Azure para Conversational Service
conv_client = ConversationAnalysisClient(azure_endpoint, AzureKeyCredential(azure_key))

# 🔹 Variables de estado en `session_state`
if "compra_realizada" not in st.session_state:
    st.session_state.compra_realizada = False
if "mensaje_compra" not in st.session_state:
    st.session_state.mensaje_compra = None
if "ordenadores_recomendados" not in st.session_state:
    st.session_state.ordenadores_recomendados = []
if "user_input" not in st.session_state:
    st.session_state.user_input = ""

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

    query_relajada = {"$or": []}

    for key, value in criterios.items():
        query_relajada["$or"].append({f"json_data.{key}.text": {"$regex": f".*{value}.*", "$options": "i"}})

    print(f"🧐 Query Relajada para MongoDB: {query_relajada}")

    resultados = list(collection.find(query_relajada))

    if resultados:
        print(f"✅ Se encontraron {len(resultados)} coincidencias parciales.")
        return resultados, []
    
    print(f"❌ No se encontró ningún ordenador con las especificaciones buscadas.")
    return [], list(criterios.keys())

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
            max_tokens=150
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
        pdf_link = BLOB_STORAGE_URL + ordenador["document_id"]

        respuestas.append((specs, pdf_link, str(ordenador["_id"])))

    return respuestas

# 🔹 Función para realizar la compra
def realizar_compra(ordenador_id):
    """Marca la compra como realizada y limpia el chat."""
    st.session_state.compra_realizada = True
    st.session_state.mensaje_compra = f"✅ Compra realizada con éxito."
    st.session_state.ordenadores_recomendados = []
    st.session_state.user_input = ""
    st.rerun()

# ---------- INTERFAZ CON STREAMLIT ----------
st.title("💻 Chatbot - Búsqueda y Compra de Ordenadores")

if not st.session_state.compra_realizada:
    st.session_state.user_input = st.text_input("Escribe tu consulta aquí...", value=st.session_state.user_input)

    if st.button("Buscar"):
        if st.session_state.user_input:
            # 🔹 LIMPIAR ANTERIOR CONSULTA ANTES DE PROCESAR UNA NUEVA
            st.session_state.ordenadores_recomendados = []
            st.session_state.mensaje_compra = None

            loading_message = st.empty()  
            loading_message.info("🔍 Consultando...")

            time.sleep(1.5)

            intent, entidades = get_intent_and_entities(st.session_state.user_input)

            loading_message.empty()  # 🔹 Borra el mensaje de carga una vez obtenido el resultado

            if intent in ["None", "General_Information"]:
                respuesta = generar_respuesta_openai(st.session_state.user_input)
                st.write(respuesta)

            elif intent in ["Order_Computer", "Search_Computer"]:
                ordenadores_encontrados, _ = buscar_ordenador(entidades)

                if ordenadores_encontrados:
                    st.session_state.ordenadores_recomendados = formatear_respuesta_ordenador(ordenadores_encontrados)

            else:
                # 🔹 Mensaje para consultas fuera de contexto
                st.warning("❌ No puedo responderte eso ahora mismo.")

if not st.session_state.compra_realizada and st.session_state.ordenadores_recomendados:
    st.success("🛒 Te recomendamos estos ordenadores:")
    for specs, pdf_link, ordenador_id in st.session_state.ordenadores_recomendados:
        st.write(specs)
        st.markdown(f"📄 [Ver ficha completa]({pdf_link})", unsafe_allow_html=True)
        if st.button(f"🛍️ Comprar", key=f"comprar_{ordenador_id}"):
            realizar_compra(ordenador_id)

if st.session_state.compra_realizada:
    st.success(st.session_state.mensaje_compra)
    if st.button("🔄 Nueva búsqueda"):
        st.session_state.compra_realizada = False
        st.session_state.mensaje_compra = None
        st.rerun()
