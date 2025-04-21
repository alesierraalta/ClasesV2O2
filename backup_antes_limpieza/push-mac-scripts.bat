@echo off
echo Creando directorio temporal...
mkdir temp_repo
cd temp_repo

echo Clonando repositorio...
git clone https://github.com/alesierraalta/ClasesO2.git
cd ClasesO2

echo Copiando scripts para macOS...
copy "..\..\run.sh" .
copy "..\..\update_app.sh" .
copy "..\..\cleanup.sh" .

echo Configurando Git...
git config --global user.email "alejandrosa2000@gmail.com"
git config --global user.name "alesierraalta"

echo Añadiendo archivos...
git add run.sh update_app.sh cleanup.sh

echo Haciendo commit...
git commit -m "Agrega scripts equivalentes para macOS/Unix"

echo Subiendo cambios...
git push

echo Limpiando...
cd ..\..
rmdir /s /q temp_repo

echo ¡Cambios subidos con éxito! 