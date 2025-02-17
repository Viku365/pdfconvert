import streamlit as st
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.ai.language.conversations import ConversationAnalysisClient
from azure.ai.textanalytics import TextAnalyticsClient
from pymongo import MongoClient
import openai
import os
import time
import json
from dotenv import load_dotenv


# 🔹 Cargar variables de entorno
load_dotenv()

# 🔹 Configuración de Azure Document Intelligence
pdf_endpoint = st.secrets.get("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "")
pdf_api_key = st.secrets.get("AZURE_DOCUMENT_INTELLIGENCE_KEY", "")

pdf_client = DocumentAnalysisClient(endpoint=pdf_endpoint, credential=AzureKeyCredential(pdf_api_key))

# 🔹 Configuración de Azure Conversational Service
azure_endpoint = st.secrets.get("AZURE_LANGUAGE_ENDPOINT", "")
azure_key = st.secrets.get("AZURE_LANGUAGE_KEY", "")

conv_client = ConversationAnalysisClient(azure_endpoint, AzureKeyCredential(azure_key))

# 🔹 Configuración de Azure Named Entity Recognition (NER)
text_analytics_client = TextAnalyticsClient(endpoint=azure_endpoint, credential=AzureKeyCredential(azure_key))

# 🔹 Configuración de MongoDB
MONGO_URI = st.secrets.get("MONGO_URI", "")

mongo_client = MongoClient(MONGO_URI)
db = mongo_client["ordenadores_db"]
collection = db["ordenadores"]

# 🔹 Configuración de OpenAI en Azure
openai.api_type = "azure"
openai.api_base = st.secrets.get("AZURE_OPENAI_ENDPOINT", "")
openai.api_key = st.secrets.get("AZURE_OPENAI_KEY", "")
openai.api_version = "2024-07-01-preview"
DEPLOYMENT_NAME = st.secrets.get("DEPLOYMENT_NAME", "")

# 🔹 URL base de Blob Storage para los PDF
BLOB_STORAGE_URL = "https://tajamarstorage.blob.core.windows.net/articles/"

# 🔹 Variables de estado en session_state
if "compra_realizada" not in st.session_state:
    st.session_state.compra_realizada = False
if "mensaje_compra" not in st.session_state:
    st.session_state.mensaje_compra = None
if "ordenadores_recomendados" not in st.session_state:
    st.session_state.ordenadores_recomendados = []
if "user_input" not in st.session_state:
    st.session_state.user_input = ""
if "pdf_procesado" not in st.session_state:
    st.session_state.pdf_procesado = None
if "ordenador_extraido" not in st.session_state:
    st.session_state.ordenador_extraido = None

# 🔹 Función para extraer texto de PDF
def extraer_texto_de_pdf(pdf_bytes):
    """Extrae texto de un PDF usando Azure Document Intelligence."""
    try:
        from io import BytesIO
        pdf_stream = BytesIO(pdf_bytes)

        poller = pdf_client.begin_analyze_document("prebuilt-document", pdf_stream)
        result = poller.result()

        if not result.pages:
            return "Error: No se encontró texto en el documento."

        texto_extraido = "\n".join([line.content for page in result.pages for line in page.lines])
        return texto_extraido.strip()
    except Exception as e:
        return f"Error al procesar PDF: {str(e)}"


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

# 🔹 Función para obtener entidades con Custom Named Entity Recognition (NER)
def obtener_entidades_custom_ner(texto):
    """Obtiene entidades usando Custom Named Entity Recognition (NER) en Azure Language Service."""
    try:
        poller = text_analytics_client.begin_recognize_custom_entities(
            [texto],
            project_name="Ordenador-Entidades",
            deployment_name="production"
        )
        result = poller.result()

        entidades = {}
        for doc in result:
            if not doc.is_error:
                for entity in doc.entities:
                    category = entity.category
                    if category not in entidades:
                        entidades[category] = []
                    entidades[category].append({
                        "text": entity.text,
                        "confidence": entity.confidence_score
                    })
            else:
                return {"Error": f"Azure NER Error: {doc.error.code} - {doc.error.message}"}

        return entidades
    except Exception as e:
        return {"Error": str(e)}

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


# 🔹 Función para formatear las especificaciones del ordenador extraído
def seleccionar_entidad_mas_confiable(entidades, categoria):
    """Devuelve el texto de la entidad con mayor confidence_score dentro de una categoría."""
    if categoria in entidades and entidades[categoria]:
        # Ordena las entidades por confidence_score en orden descendente y devuelve la de mayor confianza
        entidad_mas_confiable = max(entidades[categoria], key=lambda x: x.get("confidence", 0))
        return entidad_mas_confiable.get("text", "Desconocido")
    return "Desconocido"

def formatear_ordenador_extraido(entidades):
    """Genera un texto con las especificaciones del ordenador extraído del PDF, seleccionando la entidad con mayor confianza."""
    specs = "🖥 **Especificaciones del ordenador detectado:**\n\n"
    specs += f"💻 **Marca:** {seleccionar_entidad_mas_confiable(entidades, 'Marca')}\n"
    specs += f"🖥 **Modelo:** {seleccionar_entidad_mas_confiable(entidades, 'Modelo')}\n"
    specs += f"⚡ **Procesador:** {seleccionar_entidad_mas_confiable(entidades, 'Procesador')}\n"
    specs += f"💾 **Memoria RAM:** {seleccionar_entidad_mas_confiable(entidades, 'Memoria RAM')}\n"
    specs += f"🎮 **Gráfica:** {seleccionar_entidad_mas_confiable(entidades, 'Grafica')}\n"

    return specs


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
        specs = f"🖥 **{ordenador.get('json_data', {}).get('Marca', [{}])[0].get('text', 'Desconocido')}** "
        specs += f"{ordenador.get('json_data', {}).get('Modelo', [{}])[0].get('text', 'Desconocido')}\n"
        specs += f"💾 RAM: {ordenador.get('json_data', {}).get('Memoria RAM', [{}])[0].get('text', 'Desconocido')}\n"
        specs += f"⚡ Procesador: {ordenador.get('json_data', {}).get('Procesador', [{}])[0].get('text', 'Desconocido')}\n"
        specs += f"🎮 Gráfica: {ordenador.get('json_data', {}).get('Grafica', [{}])[0].get('text', 'Desconocida')}\n"
        pdf_link = BLOB_STORAGE_URL + ordenador.get("document_id", "")

        respuestas.append((specs, pdf_link, str(ordenador["_id"])))

    return respuestas

# 🔹 Función para realizar la compra
def realizar_compra():
    """Marca la compra como realizada y limpia el chat."""
    st.session_state.compra_realizada = True
    st.session_state.mensaje_compra = "✅ Compra realizada con éxito."
    st.session_state.ordenadores_recomendados = []
    st.session_state.user_input = ""
    st.session_state.ordenador_extraido = None
    st.rerun()

# ---------- INTERFAZ CON STREAMLIT ----------
st.title("💻 Chatbot - Búsqueda y Compra de Ordenadores")

# 🔹 Subir PDF y extraer entidades
uploaded_file = st.file_uploader("📂 Sube un archivo PDF", type=["pdf"])
if uploaded_file is not None:
    with st.spinner("📄 Procesando PDF..."):
        pdf_bytes = uploaded_file.read()
        texto_extraido = extraer_texto_de_pdf(pdf_bytes)
        if texto_extraido:
            entidades_extraidas = obtener_entidades_custom_ner(texto_extraido)
            if entidades_extraidas:
                st.session_state.ordenador_extraido = entidades_extraidas
                specs_text = formatear_ordenador_extraido(entidades_extraidas)
                st.success("✅ Ordenador detectado con las siguientes especificaciones:")
                st.write(specs_text)
                # 🔹 Imprimir JSON por consola
                print("🔍 JSON de entidades extraídas del PDF:")
                print(json.dumps(entidades_extraidas, indent=4, ensure_ascii=False))
                if st.button("🛍️ Comprar este ordenador"):
                    realizar_compra()
        else:
            st.error("❌ No se pudo extraer texto del PDF.")

# 🔹 Chatbot para búsqueda manual
if not st.session_state.compra_realizada:
    st.session_state.user_input = st.text_input("📝 Escribe tu consulta aquí...", value=st.session_state.user_input)

    if st.button("🔍 Buscar"):
        if st.session_state.user_input:
            intent, entidades = get_intent_and_entities(st.session_state.user_input)

            if intent in ["Order_Computer", "Search_Computer"]:
                # 🔹 Buscar ordenadores en la base de datos
                ordenadores_encontrados, _ = buscar_ordenador(entidades)

                if ordenadores_encontrados:
                    st.session_state.ordenadores_recomendados = formatear_respuesta_ordenador(ordenadores_encontrados)
                else:
                    st.warning("❌ No se encontraron ordenadores con esas características.")

            elif intent == "General_Information":
                # 🔹 Verifica si la consulta es sobre ordenadores antes de llamar a OpenAI
                keywords = ["ordenador", "pc", "portátil", "cpu", "gpu", "ram", "procesador", "gráfica", "tarjeta gráfica"]
                if any(word in st.session_state.user_input.lower() for word in keywords):
                    respuesta = generar_respuesta_openai(st.session_state.user_input)
                    st.write(respuesta)
                else:
                    st.warning("❌ No puedo responder preguntas que no sean sobre ordenadores.")

            else:
                # 🔹 Mensaje para preguntas fuera de contexto
                st.warning("❌ No puedo responderte eso ahora mismo.")

# 🔹 Mostrar ordenadores recomendados
if not st.session_state.compra_realizada and st.session_state.ordenadores_recomendados:
    st.success("🛒 Te recomendamos estos ordenadores:")
    for specs, pdf_link, ordenador_id in st.session_state.ordenadores_recomendados:
        st.write(specs)
        st.markdown(f"📄 [Ver ficha completa]({pdf_link})", unsafe_allow_html=True)
        if st.button(f"🛍️ Comprar", key=f"comprar_{ordenador_id}"):  # 🔹 Agregar clave única
            realizar_compra()


if st.session_state.compra_realizada:
    st.success(st.session_state.mensaje_compra)
    if st.button("🔄 Nueva búsqueda"):
        st.session_state.compra_realizada = False
        st.session_state.mensaje_compra = None
        st.rerun()
