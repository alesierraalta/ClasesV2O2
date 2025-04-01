import os
import sys
import time
import webview
import threading
import logging
from app import app, db
from flask import request

# Configurar registro de logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("gymmanager.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("GymManager")

@app.route('/asistencia/upload_audio/<int:horario_id>', methods=['POST'])
def upload_audio(horario_id):
    if 'audio' not in request.files:
        return 'No file part', 400
    file = request.files['audio']
    if file.filename == '':
        return 'No selected file', 400
    # Save the file logic here
    file.save(os.path.join('uploads', file.filename))
    return 'File uploaded successfully', 200

def start_server():
    """Iniciar el servidor Flask en segundo plano"""
    try:
        # Verificar si la BD existe y crearla si no
        if not os.path.exists('gimnasio.db'):
            with app.app_context():
                db.create_all()
                logger.info("Base de datos inicializada correctamente.")
        
        # Configurar la aplicación para producción
        app.config['ENV'] = 'production'
        app.config['DEBUG'] = False
        app.config['TESTING'] = False
        
        # Ejecutar la aplicación Flask
        logger.info("Iniciando servidor Flask en http://127.0.0.1:5000")
        app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Error al iniciar el servidor: {str(e)}")
        raise

def run_app():
    """Ejecutar la aplicación como ventana de escritorio"""
    try:
        logger.info("Iniciando aplicación GymManager...")
        
        # Iniciar el servidor Flask en un hilo separado
        t = threading.Thread(target=start_server)
        t.daemon = True
        t.start()
        
        # Esperar a que el servidor esté listo
        time.sleep(2)
        
        # Crear y mostrar la ventana de la aplicación
        logger.info("Abriendo ventana de la aplicación...")
        webview.create_window(
            title='GymManager - Sistema de Gestión de Clases', 
            url='http://localhost:5000',
            width=1200,
            height=800,
            resizable=True,
            min_size=(800, 600),
            text_select=True,
            confirm_close=True,
            background_color='#FFFFFF'
        )
        webview.start(debug=False)
    except Exception as e:
        logger.error(f"Error en la aplicación: {str(e)}")
        input("Presiona Enter para salir...")
        sys.exit(1)

if __name__ == '__main__':
    run_app() 