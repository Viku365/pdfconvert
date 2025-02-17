from dotenv import load_dotenv
import os
import json
from azure.core.credentials import AzureKeyCredential
from azure.ai.textanalytics import TextAnalyticsClient
from save_to_mongo import save_pdf_and_json_to_db  # Función para guardar en MongoDB

def main():
    try:
        # Get Configuration Settings
        load_dotenv()
        ai_endpoint = os.getenv('LANGUAGE_SERVICE_ENDPOINT')
        ai_key = os.getenv('LANGUAGE_SERVICE_KEY')
        project_name = "Ordenador-Entidades"
        deployment_name = "production"

        # Create client using endpoint and key
        credential = AzureKeyCredential(ai_key)
        ai_client = TextAnalyticsClient(endpoint=ai_endpoint, credential=credential)

        # Carpeta que contiene los archivos PDF
        pdf_folder = r"C:\Users\Alumno_AI\Documents\Viku\PDFRecognizer\pdf"  # Carpeta de archivos PDF
        json_folder = r"C:\Users\Alumno_AI\Documents\Viku\PDFRecognizer\json"  # Carpeta de archivos JSON
        pdf_files = os.listdir(pdf_folder)
        json_files = os.listdir(json_folder)

        # Verificar si hay archivos PDF
        if not pdf_files:
            print(f"No se encontraron archivos PDF en la carpeta: {pdf_folder}")
            return  # Salir si no hay archivos PDF

        # Procesar archivos PDF y JSON
        for file_name in pdf_files:
            if file_name.endswith('.pdf'):
                print(f"Procesando archivo PDF: {file_name}")  # Imprimir el archivo que estamos procesando
                pdf_file_path = os.path.join(pdf_folder, file_name)

                # Leer los contenidos del archivo PDF (deberías tener una función para extraer texto del PDF)
                text = extract_text_from_pdf(pdf_file_path)  # Debes implementar la función para extraer texto del PDF

                # Verificar si el archivo tiene texto
                if not text.strip():
                    print(f"El archivo {file_name} está vacío.")
                    continue  # Salta al siguiente archivo si está vacío

                # Extraer entidades del texto
                operation = ai_client.begin_recognize_custom_entities(
                    [text],  # Batched documents
                    project_name=project_name,
                    deployment_name=deployment_name
                )

                document_results = operation.result()

                # Preparar un diccionario para almacenar todas las entidades
                file_entities = {}

                for custom_entities_result in document_results:
                    if custom_entities_result.kind == "CustomEntityRecognition":
                        for entity in custom_entities_result.entities:
                            category = entity.category
                            if category not in file_entities:
                                file_entities[category] = []

                            # Agregar detalles de la entidad a la categoría correspondiente
                            file_entities[category].append({
                                "text": entity.text,
                                "confidence_score": entity.confidence_score
                            })
                    elif custom_entities_result.is_error is True:
                        file_entities["error"] = {
                            "code": custom_entities_result.error.code,
                            "message": custom_entities_result.error.message
                        }

                # Buscar el archivo JSON correspondiente para vincularlo
                json_file_name = file_name.replace('.pdf', '.json')
                if json_file_name in json_files:
                    json_file_path = os.path.join(json_folder, json_file_name)

                    # Leer el archivo JSON
                    with open(json_file_path, 'r', encoding='utf-8') as file:
                        json_data = json.load(file)

                    # Guardar los archivos PDF y JSON junto con las entidades en MongoDB
                    save_pdf_and_json_to_db(file_name, json_data)

    except Exception as ex:
        print(ex)

# Función para extraer el texto de un archivo PDF (a implementar)
def extract_text_from_pdf(pdf_file_path):
    # Aquí usarías una librería como PyPDF2 o pdfplumber para extraer el texto del archivo PDF.
    # Este es solo un ejemplo:
    try:
        with open(pdf_file_path, "rb") as f:
            # Aquí implementas la lógica para extraer el texto del PDF
            # Como ejemplo, supongamos que estamos extrayendo el texto
            text = "Texto extraído del PDF"  # Reemplaza con el código real de extracción
        return text
    except Exception as e:
        print(f"Error al extraer texto del archivo {pdf_file_path}: {str(e)}")
        return ""

if __name__ == "__main__":
    main()
