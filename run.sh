#!/bin/bash
echo "Iniciando entorno virtual..."
if [ ! -d "venv" ]; then
    echo "Creando entorno virtual..."
    python3 -m venv venv
fi

# Activar el entorno virtual
source venv/bin/activate

# Establecer variables de entorno
export FLASK_APP=app.py
export FLASK_ENV=development
# NO MODIFICAR MANUALMENTE - ESTE VALOR SE ACTUALIZARÁ AUTOMÁTICAMENTE
export NOTIFICATION_PHONE_NUMBER=+584244461682
# Nota: Reemplazar +numero_a_notificar_aqui con el número completo incluyendo el código del país
# por ejemplo: +56912345678 para Chile o +34612345678 para España (sin espacios)

echo "Instalando dependencias principales..."
pip install -r requirements.txt

# Instalación de dependencias adicionales que podrían faltar
echo "Verificando dependencias adicionales..."
pip install flask-login

# No eliminamos la base de datos para mantener persistencia
# del gimnasio.db
echo "Inicializando la base de datos..."
# Crear un script Python temporal para inicializar la base de datos
cat > create_db.py << 'EOL'
import sqlite3
try:
    import os
    from app import app, db
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
EOL

# Ejecutar el script
python create_db.py

echo "Iniciando la aplicación..."
# Añadimos la opción para ignorar errores y continuar
flask run --host=0.0.0.0 --port=5000 || (
    echo "Ha ocurrido un error al iniciar Flask."
    echo "Asegúrate de tener todas las dependencias instaladas."
    echo ""
    echo "Intentando método alternativo con app_launcher.py..."
    python app_launcher.py || (
        echo "Intentando ejecutar app.py directamente..."
        python app.py
    )
    read -p "Presiona Enter para continuar..."
) 