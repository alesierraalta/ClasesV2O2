@echo off
echo Iniciando entorno virtual...
call venv\Scripts\activate

echo Instalando dependencias de prueba si no existen...
pip install pytest pytest-cov

if "%1"=="" (
    echo Error: Debes especificar un tipo de prueba a ejecutar.
    echo Uso: run_specific_tests.bat [unit^|integration^|api^|file] [nombre_archivo]
    echo Ejemplos:
    echo   run_specific_tests.bat unit      - Ejecuta todas las pruebas unitarias
    echo   run_specific_tests.bat integration - Ejecuta todas las pruebas de integración
    echo   run_specific_tests.bat api       - Ejecuta todas las pruebas de API
    echo   run_specific_tests.bat file test_notifications.py - Ejecuta todas las pruebas en ese archivo
    goto :end
)

set TEST_TYPE=%1

if "%TEST_TYPE%"=="unit" (
    echo Ejecutando pruebas unitarias...
    pytest -m unit --cov=. -v
) else if "%TEST_TYPE%"=="integration" (
    echo Ejecutando pruebas de integración...
    pytest -m integration --cov=. -v
) else if "%TEST_TYPE%"=="api" (
    echo Ejecutando pruebas de API...
    pytest -m api --cov=. -v
) else if "%TEST_TYPE%"=="file" (
    if "%2"=="" (
        echo Error: Debes especificar un nombre de archivo para las pruebas de archivo.
        goto :end
    )
    echo Ejecutando pruebas en archivo %2...
    pytest tests/%2 --cov=. -v
) else (
    echo Tipo de prueba no reconocido: %TEST_TYPE%
    echo Tipos válidos: unit, integration, api, file
)

:end
echo.
echo Presiona cualquier tecla para salir...
pause
