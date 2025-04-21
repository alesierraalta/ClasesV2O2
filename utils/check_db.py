import sqlite3
import os
import sys

# Agregar directorio raíz al path
utils_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(utils_dir)
sys.path.append(root_dir)
os.chdir(root_dir)  # Cambiar al directorio raíz

# Listar archivos .db para encontrar la base de datos
print("Archivos .db en el directorio:")
for file in os.listdir('.'):
    if file.endswith('.db'):
        print(f"- {file}")

# Intentar con gimnasio.db
try:
    conn = sqlite3.connect('gimnasio.db')
    cursor = conn.cursor()
    cursor.execute('PRAGMA table_info(clase_realizada)')
    columns = cursor.fetchall()
    print('\nColumnas de clase_realizada en gimnasio.db:')
    for col in columns:
        print(col)
    conn.close()
except Exception as e:
    print(f"Error al conectar a gimnasio.db: {e}")

# Buscar en el código app.py la configuración de la base de datos
print("\nBuscando configuración de base de datos en app.py:")
with open('app.py', 'r') as file:
    for i, line in enumerate(file):
        if 'SQLALCHEMY_DATABASE_URI' in line:
            print(f"Línea {i+1}: {line.strip()}") 