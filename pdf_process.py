import os
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential

# Configura la clave y el endpoint
endpoint = "https://viku-pdf-recognizer.cognitiveservices.azure.com/"
api_key = "BQN3nVPOTDAOXqvnxlJY2WbBWLJNOZNvRw7tm3CvzRcV7ZRmiRNsJQQJ99BBACYeBjFXJ3w3AAALACOGSY9L"

# Crea el cliente
client = DocumentAnalysisClient(endpoint=endpoint, credential=AzureKeyCredential(api_key))

# Ruta completa de la carpeta que contiene los PDFs
pdf_folder = "C:\\Users\\Alumno_AI\\Documents\\Viku\\PDFRecognizer\\pdf"  # Asegúrate de que esta ruta sea correcta

# Verifica si la carpeta contiene archivos PDF
if not os.path.exists(pdf_folder):
    print(f"Error: La carpeta {pdf_folder} no existe.")
    exit()

# Obtén todos los archivos PDF en la carpeta
pdf_files = [f for f in os.listdir(pdf_folder) if f.endswith('.pdf')]

# Verifica si se encontraron archivos PDF
if not pdf_files:
    print("No se encontraron archivos PDF en la carpeta.")
    exit()

# Procesa cada archivo PDF
for pdf_file in pdf_files:
    pdf_path = os.path.join(pdf_folder, pdf_file)
    
    print(f"Procesando el archivo: {pdf_file}...")
    
    try:
        # Abre el archivo PDF
        with open(pdf_path, "rb") as f:
            poller = client.begin_analyze_document("prebuilt-document", f)
            result = poller.result()

        # Generar el nombre del archivo de salida (txt)
        txt_file_name = pdf_file.replace('.pdf', '.txt')
        txt_file_path = os.path.join(pdf_folder, txt_file_name)

        # Escribir el texto extraído en el archivo txt
        with open(txt_file_path, 'w', encoding='utf-8') as txt_file:
            for page in result.pages:
                txt_file.write(f"Página número: {page.page_number}\n")
                for line in page.lines:
                    txt_file.write(f"{line.content}\n")
        
        print(f"Texto extraído y guardado en: {txt_file_path}")
    except Exception as e:
        print(f"Error al procesar el archivo {pdf_file}: {str(e)}")
