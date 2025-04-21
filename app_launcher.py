import os
import sys
import webbrowser
import threading
import time
from app import app, db

def open_browser():
    """Abrir el navegador después de un pequeño retraso"""
    time.sleep(1.5)
    webbrowser.open('http://localhost:5000')

def run_app():
    """Inicializar la BD y ejecutar la aplicación"""
    # Verificar si la BD existe y crearla si no
    if not os.path.exists('gimnasio.db'):
        with app.app_context():
            db.create_all()
            print("Base de datos inicializada correctamente.")
    
    # Abrir el navegador en un hilo separado
    threading.Thread(target=open_browser).start()
    
    # Ejecutar la aplicación
    app.run(debug=False)

if __name__ == '__main__':
    run_app() 