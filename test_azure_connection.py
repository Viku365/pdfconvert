import requests
import os

# 🔹 Configuración de Azure Document Intelligence (Form Recognizer)
FORM_RECOGNIZER_ENDPOINT = "https://viku-pdf-recognizer.cognitiveservices.azure.com/"
FORM_RECOGNIZER_KEY = "BQN3nVPOTDAOXqvnxlJY2WbBWLJNOZNvRw7tm3CvzRcV7ZRmiRNsJQQJ99BBACYeBjFXJ3w3AAALACOGSY9L"

# 📂 Ruta del PDF (ajusta según sea necesario)
pdf_path = "pdf/16Z90R-E.AD78B.pdf"

# 🔗 URL de la API de Azure Document Intelligence
url = f"{FORM_RECOGNIZER_ENDPOINT}/formrecognizer/documentModels/prebuilt-document:analyze?api-version=2023-07-31"

# 📤 Leer el archivo PDF en modo binario
with open(pdf_path, "rb") as f:
    pdf_bytes = f.read()

# 📡 Realizar la solicitud a Azure
headers = {
    "Ocp-Apim-Subscription-Key": FORM_RECOGNIZER_KEY,
    "Content-Type": "application/pdf"
}

print(f"📤 Enviando PDF a: {url}")

response = requests.post(url, headers=headers, data=pdf_bytes)

# 📥 Imprimir la respuesta de Azure
print(f"🔄 Código de respuesta: {response.status_code}")
print(f"📄 Respuesta de Azure: {response.text}")

# ✅ Verificar si la solicitud fue exitosa
if response.status_code == 202:
    print("✅ El PDF fue enviado correctamente. Revisa el resultado en Azure Portal.")
elif response.status_code == 400:
    print("❌ Error 400: Archivo no compatible o dañado.")
elif response.status_code == 401:
    print("❌ Error 401: Clave API incorrecta o no autorizada.")
elif response.status_code == 404:
    print("❌ Error 404: Endpoint incorrecto.")
else:
    print("⚠️ Error desconocido. Revisa los logs de Azure.")

