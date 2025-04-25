@echo off
echo Configurando datos de usuario Git...
git config --global user.email "alejandrosa2000@gmail.com"
git config --global user.name "alesierraalta"

echo Eliminando cualquier origen remoto existente...
git remote remove origin

echo Inicializando nuevo repositorio...
git init

echo Creando README.md...
echo # ClasesO2 > README.md
echo Un sistema completo de gestión para academias de fitness y gimnasios. >> README.md
echo >> README.md
echo ## Características >> README.md
echo - Gestión de horarios de clases >> README.md
echo - Control de asistencia de profesores >> README.md
echo - Registro de alumnos en clases >> README.md
echo - Informes y estadísticas >> README.md
echo - Importación/exportación de datos >> README.md
echo >> README.md
echo ## Instalación >> README.md
echo 1. Clonar el repositorio >> README.md
echo 2. Ejecutar run.bat para instalar dependencias e iniciar la aplicación >> README.md

echo Añadiendo todos los archivos...
git add --all

echo Realizando commit inicial...
git commit -m "first commit"

echo Configurando rama principal...
git branch -M main

echo Añadiendo repositorio remoto...
git remote add origin https://github.com/alesierraalta/ClasesO2.git

echo Subiendo código al repositorio remoto...
git push -f -u origin main

echo ¡Proceso completado! El código se ha subido a https://github.com/alesierraalta/ClasesO2
pause 