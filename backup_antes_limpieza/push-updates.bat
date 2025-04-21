@echo off
echo Creando directorio temporal...
mkdir temp_repo
cd temp_repo

echo Clonando repositorio...
git clone https://github.com/alesierraalta/ClasesO2.git
cd ClasesO2

echo Copiando los archivos modificados...
copy "..\..\run.bat" .
copy "..\..\requirements.txt" .
copy "..\..\notifications.py" .
copy "..\..\update_app.bat" .

echo Configurando Git...
git config --global user.email "alejandrosa2000@gmail.com"
git config --global user.name "alesierraalta"

echo Añadiendo archivos...
git add run.bat requirements.txt notifications.py update_app.bat

echo Haciendo commit...
git commit -m "Agrega script de actualización para facilitar despliegue en múltiples computadoras"

echo Subiendo cambios...
git push

echo Limpiando...
cd ..\..
rmdir /s /q temp_repo

echo ¡Cambios subidos con éxito! 