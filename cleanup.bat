@echo off
echo ===== LIMPIEZA DE ARCHIVOS REDUNDANTES =====
echo.

:: Verificar si estamos en el directorio correcto
if not exist run.bat (
    echo ERROR: Este script debe ejecutarse en el directorio principal de la aplicacion.
    echo.
    echo Por favor, ejecute este script desde el directorio donde se encuentra run.bat
    goto :end
)

echo Eliminando archivos de script temporales y redundantes...
if exist create-new-repo.bat del /q create-new-repo.bat
if exist push-changes.bat del /q push-changes.bat
if exist push-updates.bat del /q push-updates.bat
if exist commit-changes.bat del /q commit-changes.bat
if exist create_db.py del /q create_db.py

echo.
echo Eliminando archivos de registro temporales...
if exist import_debug.log del /q import_debug.log
if exist import_errors.log del /q import_errors.log
if exist *.pyc del /q *.pyc
if exist __pycache__ rd /s /q __pycache__

echo.
echo Limpiando archivos temporales de Python...
if exist *.pyc del /q *.pyc
if exist __pycache__ rd /s /q __pycache__

echo.
echo Agregando archivos temporales a .gitignore...
echo create_db.py >> .gitignore
echo *.log >> .gitignore
echo *.pyc >> .gitignore
echo __pycache__/ >> .gitignore
echo notification_lock.txt >> .gitignore

echo.
echo ¡Limpieza completada con éxito!
echo.
echo Nota: Los archivos esenciales para la aplicacion se han conservado.
echo Los archivos de datos (como la base de datos) no se han eliminado.
echo.

:end
pause 