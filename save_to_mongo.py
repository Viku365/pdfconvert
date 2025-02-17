import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Función para guardar solo el archivo JSON y el document_id en MongoDB
def save_pdf_and_json_to_db(file_name, json_data):
    # Cargar las variables de entorno
    load_dotenv()
    MONGO_URI = os.getenv("MONGO_URI")  # Conectar con MongoDB
    client = MongoClient(MONGO_URI)
    db = client["ordenadores_db"]
    collection = db["ordenadores"]

    # Guardar solo el document_id y el json_data en MongoDB
    document = {
        "document_id": file_name,  # Guardar el nombre del archivo (document_id)
        "json_data": json_data  # Guardar el contenido del archivo JSON
    }

    try:
        result = collection.insert_one(document)
        print(f"Documento insertado con ID: {result.inserted_id}")
    except Exception as e:
        print(f"Error al insertar el archivo {file_name} en MongoDB: {str(e)}")
