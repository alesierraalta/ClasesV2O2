@echo off
echo Creando directorio temporal...
mkdir temp_repo
cd temp_repo

echo Clonando repositorio...
git clone https://github.com/alesierraalta/AppClasesO2.git
cd AppClasesO2

echo Copiando los archivos modificados...
copy "..\..\run.bat" .
copy "..\..\requirements.txt" .

echo Configurando Git...
git config --global user.email "alejandrosa2000@gmail.com"
git config --global user.name "alesierraalta"

echo Añadiendo archivos...
git add run.bat requirements.txt

echo Haciendo commit...
git commit -m "Arreglo en run.bat para inicializar la base de datos y añadir pandas a requirements.txt"

echo Subiendo cambios...
git push

echo Limpiando...
cd ..\..
rmdir /s /q temp_repo

echo ¡Cambios subidos con éxito! 