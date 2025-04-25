@echo off
echo Iniciando entorno virtual...
if not exist venv (
    echo Creando entorno virtual...
    python -m venv venv
)

:: Activar el entorno virtual
call venv\Scripts\activate

:: Establecer variables de entorno
set FLASK_APP=app.py
set FLASK_ENV=development
:: NO MODIFICAR MANUALMENTE - ESTE VALOR SE ACTUALIZARÁ AUTOMÁTICAMENTE
set NOTIFICATION_PHONE_NUMBER=+584244461682
:: Nota: Reemplazar +numero_a_notificar_aqui con el número completo incluyendo el código del país
:: por ejemplo: +56912345678 para Chile o +34612345678 para España (sin espacios)

echo Instalando dependencias principales...
pip install -r requirements.txt

:: Instalación de dependencias adicionales que podrían faltar
echo Verificando dependencias adicionales...
pip install flask-login

:: No eliminamos la base de datos para mantener persistencia
:: del gimnasio.db
echo Inicializando la base de datos...
:: Usando un enfoque de script separado para evitar problemas con comandos multilinea
echo import sqlite3 > create_db.py
echo try: >> create_db.py
echo     import os >> create_db.py
echo     from app import app, db >> create_db.py
echo     with app.app_context(): >> create_db.py
echo         db.create_all() >> create_db.py
echo     print('Base de datos inicializada correctamente (metodo 1)') >> create_db.py
echo except Exception as e1: >> create_db.py
echo     try: >> create_db.py
echo         conn = sqlite3.connect('gimnasio.db') >> create_db.py
echo         print('Base de datos creada correctamente (metodo 2)') >> create_db.py
echo         conn.close() >> create_db.py
echo     except Exception as e2: >> create_db.py
echo         print(f'Error al crear la base de datos: {e1}\\n{e2}') >> create_db.py

:: Ejecutar el script
python create_db.py

echo Iniciando la aplicación...
:: Añadimos la opción para ignorar errores y continuar
flask run --host=0.0.0.0 --port=5000 || (
    echo Ha ocurrido un error al iniciar Flask.
    echo Asegúrate de tener todas las dependencias instaladas.
    echo.
    echo Intentando método alternativo con app_launcher.py...
    python app_launcher.py || (
        echo Intentando ejecutar app.py directamente...
        python app.py
    )
    pause
)