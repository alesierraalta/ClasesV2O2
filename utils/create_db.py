import sqlite3
import os
import sys

# Configuración de paths
utils_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(utils_dir)
sys.path.append(root_dir)
os.chdir(root_dir)

# Ahora podemos importar app
from app import app, db

try:
    with app.app_context():
        db.create_all()
    print('Base de datos inicializada correctamente (metodo 1)')
except Exception as e1:
    try:
        conn = sqlite3.connect('gimnasio.db')
        print('Base de datos creada correctamente (metodo 2)')
        conn.close()
    except Exception as e2:
        print(f'Error al crear la base de datos: {e1}\n{e2}')
