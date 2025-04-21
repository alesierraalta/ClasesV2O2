#!/bin/bash
echo "===== ACTUALIZADOR DE APP ClasesO2 ====="
echo ""

# Verificar si estamos en el directorio correcto
if [ ! -f "run.sh" ]; then
    echo "ERROR: Este script debe ejecutarse en el directorio principal de la aplicacion."
    echo "El archivo run.sh no se encontro en el directorio actual."
    echo ""
    echo "Por favor, ejecute este script desde el directorio donde se encuentra run.sh"
    exit 1
fi

# Verificar si git está instalado
if ! command -v git &> /dev/null; then
    echo "ERROR: Git no esta instalado en este sistema."
    echo "Por favor, instale Git e intente nuevamente."
    echo "En macOS puede instalarlo con 'brew install git'"
    exit 1
fi

echo "Obteniendo cambios del repositorio..."
git reset --hard HEAD
git pull origin main

echo ""
echo "Activando entorno virtual..."
source venv/bin/activate

echo ""
echo "Actualizando dependencias..."
pip install -r requirements.txt

echo ""
echo "¡Actualización completada con éxito!"
echo ""
echo "Para iniciar la aplicación, ejecute: ./run.sh"
echo ""

read -p "Presiona Enter para continuar..." 