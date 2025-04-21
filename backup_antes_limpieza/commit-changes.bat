@echo off
echo Configurando Git...
git config --global user.email "alejandrosa2000@gmail.com"
git config --global user.name "alesierraalta"

echo Añadiendo archivos...
git add run.bat requirements.txt

echo Haciendo commit...
git commit -m "Arreglo en run.bat para inicializar la base de datos y añadir pandas a requirements.txt"

echo Sincronizando con el repositorio remoto...
git fetch origin
git branch -M main
git pull origin main --allow-unrelated-histories

echo Subiendo cambios...
git push -u origin main 