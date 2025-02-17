from pymongo import MongoClient
import os
from dotenv import load_dotenv
from collections import defaultdict

# Cargar variables de entorno
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

# Conectar a MongoDB
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["ordenadores_db"]
collection = db["ordenadores"]

def obtener_resumen_entidades():
    """Consulta MongoDB y agrupa los datos por entidad."""
    entidad_contador = defaultdict(set)

    # Buscar todos los documentos en la colección
    documentos = collection.find({}, {"json_data": 1})

    for doc in documentos:
        json_data = doc.get("json_data", {})
        
        for entidad, valores in json_data.items():
            if isinstance(valores, list) and valores:  # Verifica si hay datos en la entidad
                for valor in valores:
                    entidad_contador[entidad].add(valor.get("text", "Desconocido"))

    # Convertir a diccionario estándar
    resultado = {entidad: list(valores) for entidad, valores in entidad_contador.items()}
    return resultado

# Ejecutar la consulta y mostrar los datos agrupados
resumen = obtener_resumen_entidades()

# Mostrar los resultados
for entidad, valores in resumen.items():
    print(f"📌 {entidad}: {valores}")
