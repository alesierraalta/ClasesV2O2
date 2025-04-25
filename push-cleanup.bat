@echo off
echo Creando directorio temporal...
mkdir temp_repo
cd temp_repo

echo Clonando repositorio...
git clone https://github.com/alesierraalta/ClasesO2.git
cd ClasesO2

echo Copiando archivo de limpieza...
copy "..\..\cleanup.bat" .

echo Actualizando .gitignore...
:: Verificar primero si ya contiene estas entradas
findstr /c:"create_db.py" .gitignore >nul
if %errorlevel% neq 0 (
    echo create_db.py >> .gitignore
)
findstr /c:"notification_lock.txt" .gitignore >nul
if %errorlevel% neq 0 (
    echo notification_lock.txt >> .gitignore
)

echo Configurando Git...
git config --global user.email "alejandrosa2000@gmail.com"
git config --global user.name "alesierraalta"

echo Añadiendo archivos...
git add cleanup.bat .gitignore

echo Haciendo commit...
git commit -m "Agrega script de limpieza para eliminar archivos temporales y redundantes"

echo Subiendo cambios...
git push

echo Limpiando...
cd ..\..
rmdir /s /q temp_repo

echo ¡Cambios subidos con éxito! 