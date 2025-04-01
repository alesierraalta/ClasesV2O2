#!/bin/bash
echo "===== LIMPIEZA DE ARCHIVOS REDUNDANTES ====="
echo ""

# Verificar si estamos en el directorio correcto
if [ ! -f "run.sh" ]; then
    echo "ERROR: Este script debe ejecutarse en el directorio principal de la aplicacion."
    echo ""
    echo "Por favor, ejecute este script desde el directorio donde se encuentra run.sh"
    exit 1
fi

echo "Eliminando archivos de script temporales y redundantes..."
rm -f create-new-repo.bat push-changes.bat push-updates.bat commit-changes.bat create_db.py push-cleanup.bat
rm -f *.bat.bak

echo ""
echo "Eliminando archivos de registro temporales..."
rm -f import_debug.log import_errors.log notifications.log
rm -f *.pyc
rm -rf __pycache__

echo ""
echo "Limpiando archivos temporales de Python..."
find . -name "*.pyc" -delete
find . -name "__pycache__" -exec rm -rf {} +
find . -name ".DS_Store" -delete

echo ""
echo "Agregando archivos temporales a .gitignore..."
grep -q "create_db.py" .gitignore || echo "create_db.py" >> .gitignore
grep -q "*.log" .gitignore || echo "*.log" >> .gitignore
grep -q "*.pyc" .gitignore || echo "*.pyc" >> .gitignore
grep -q "__pycache__/" .gitignore || echo "__pycache__/" >> .gitignore
grep -q "notification_lock.txt" .gitignore || echo "notification_lock.txt" >> .gitignore
grep -q ".DS_Store" .gitignore || echo ".DS_Store" >> .gitignore

echo ""
echo "¡Limpieza completada con éxito!"
echo ""
echo "Nota: Los archivos esenciales para la aplicacion se han conservado."
echo "Los archivos de datos (como la base de datos) no se han eliminado."
echo ""

read -p "Presiona Enter para continuar..." 