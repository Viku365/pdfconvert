import streamlit as st
from pymongo import MongoClient
import os
from dotenv import load_dotenv

# 🔹 Cargar variables de entorno
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

# 🔹 Conectar a MongoDB
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["ordenadores_db"]
collection = db["ordenadores"]

# 🔹 URL base de Blob Storage para los PDF
BLOB_STORAGE_URL = "https://tajamarstorage.blob.core.windows.net/articles/"

# 🔹 Función para formatear la respuesta con especificaciones y botón de compra
def formatear_respuesta_ordenador(ordenadores):
    """Genera una respuesta con las especificaciones de múltiples ordenadores y añade el botón de compra."""
    respuestas = []
    
    for ordenador in ordenadores:
        specs = f"🖥 **{ordenador.get('json_data', {}).get('Marca', [{}])[0].get('text', 'Desconocido')}** {ordenador.get('json_data', {}).get('Modelo', [{}])[0].get('text', 'Desconocido')}\n"
        specs += f"💾 RAM: {ordenador.get('json_data', {}).get('Memoria RAM', [{}])[0].get('text', 'Desconocido')}\n"
        specs += f"⚡ Procesador: {ordenador.get('json_data', {}).get('Procesador', [{}])[0].get('text', 'Desconocido')}\n"
        specs += f"🎮 Gráfica: {ordenador.get('json_data', {}).get('Grafica', [{}])[0].get('text', 'Desconocida')}\n"
        specs += f"💾 Disco Duro: {ordenador.get('json_data', {}).get('Disco Duro', [{}])[0].get('text', 'Desconocido')}\n"
        specs += f"🖥 Pantalla: {ordenador.get('json_data', {}).get('Pantalla', [{}])[0].get('text', 'Desconocida')}\n"
        pdf_link = BLOB_STORAGE_URL + ordenador["document_id"]

        with st.container():
            st.write(specs)
            st.markdown(f"📄 [Ver ficha completa]({pdf_link})", unsafe_allow_html=True)
            
            # Agregar un botón de compra
            if st.button(f"🛒 Comprar {ordenador.get('json_data', {}).get('Modelo', [{}])[0].get('text', 'Desconocido')}", key=ordenador["_id"]):
                st.session_state["compra_realizada"] = ordenador.get('json_data', {}).get('Modelo', [{}])[0].get('text', 'Desconocido')

    return respuestas  # Retorna una lista de tuplas (especificaciones, link)


# 🔹 Verificar si se realizó una compra
if "compra_realizada" in st.session_state and st.session_state["compra_realizada"]:
    st.success(f"✅ Compra realizada con éxito para el modelo: {st.session_state['compra_realizada']} 🎉")
    st.session_state["compra_realizada"] = None  # Resetear el estado después de mostrar el mensaje

