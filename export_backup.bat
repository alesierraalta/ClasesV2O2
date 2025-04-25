@echo off
echo Utilidad de Exportación de Base de Datos a Excel

REM Activar entorno virtual
call venv\Scripts\activate

REM Verificar si existe el entorno virtual
if not exist venv\Scripts\python.exe (
    echo ERROR: No se encontró el entorno virtual.
    echo Por favor, ejecute primero run.bat para configurar el entorno.
    pause
    exit /b 1
)

echo Exportando datos a Excel...
echo.

REM Ejecutar el script de exportación
venv\Scripts\python export_to_excel.py

echo.
echo Exportación completada.
echo Los archivos están en la carpeta "backups".
echo.

pause 