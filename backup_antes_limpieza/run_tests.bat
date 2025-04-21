@echo off
setlocal enabledelayedexpansion

:: -------------------------------------------------------
:: MENÚ DE PRUEBAS PARA APPCLASES
:: (Soluciona "The syntax of the command is incorrect"
::  escapando la barra vertical o usando comillas)
:: -------------------------------------------------------

:: Pequeña pausa al inicio (opcional)
echo Iniciando script de pruebas para appClases...
pause

:menu
cls
echo +======================================================+
echo ^|           MENU DE PRUEBAS - APP CLASES               ^|
echo +======================================================+
echo.
echo  1. Ejecutar todas las pruebas
echo  2. Ejecutar pruebas del modulo de notificaciones
echo  3. Ejecutar pruebas de la API
echo  4. Ejecutar pruebas de integracion
echo  5. Ejecutar pruebas unitarias
echo  6. Generar reporte HTML detallado
echo  7. Ejecutar pruebas con cobertura especifica de modulo
echo  8. Ejecutar pruebas con modo verbose
echo  9. Salir
echo.
echo Digite el numero de la opcion deseada:
set /p option="> "

if "%option%"=="1" goto all_tests
if "%option%"=="2" goto notification_tests
if "%option%"=="3" goto api_tests
if "%option%"=="4" goto integration_tests
if "%option%"=="5" goto unit_tests
if "%option%"=="6" goto html_report
if "%option%"=="7" goto specific_coverage
if "%option%"=="8" goto verbose_tests
if "%option%"=="9" goto end

echo Opcion invalida. Intente nuevamente.
timeout /t 2 >nul
goto menu

:all_tests
cls
echo Ejecutando todas las pruebas con cobertura...
:: Aquí el comando real de pytest con cobertura:
pytest --cov=. tests/ -v
echo.
echo Pruebas completadas.
pause
goto menu

:notification_tests
cls
echo Ejecutando pruebas del modulo de notificaciones...
pytest --cov=notifications --cov-report=term-missing tests/test_notifications.py -v
echo.
echo Pruebas completadas.
pause
goto menu

:api_tests
cls
echo Ejecutando pruebas de la API...
pytest -m api --cov=api_routes --cov=app tests/ -v
echo.
echo Pruebas completadas.
pause
goto menu

:integration_tests
cls
echo Ejecutando pruebas de integracion...
pytest -m integration --cov=. tests/ -v
echo.
echo Pruebas completadas.
pause
goto menu

:unit_tests
cls
echo Ejecutando pruebas unitarias...
pytest -m unit --cov=. tests/ -v
echo.
echo Pruebas completadas.
pause
goto menu

:html_report
cls
echo Generando reporte HTML detallado de cobertura...
pytest --cov=. --cov-report=html tests/
echo.
echo Reporte generado en la carpeta htmlcov.
echo Abriendo el reporte en el navegador...
start htmlcov\index.html
pause
goto menu

:specific_coverage
cls
echo Modulos disponibles:
echo  1. notifications
echo  2. app
echo  3. models
echo  4. api_routes
echo  5. audio_routes
echo  0. Volver al menu principal
echo.
echo Seleccione el modulo para analizar su cobertura:
set /p module="> "

if "%module%"=="1" (
    set module_name=notifications
    goto run_specific_module
)
if "%module%"=="2" (
    set module_name=app
    goto run_specific_module
)
if "%module%"=="3" (
    set module_name=models
    goto run_specific_module
)
if "%module%"=="4" (
    set module_name=api_routes
    goto run_specific_module
)
if "%module%"=="5" (
    set module_name=audio_routes
    goto run_specific_module
)
if "%module%"=="0" goto menu

echo Opcion invalida. Intente nuevamente.
timeout /t 2 >nul
goto specific_coverage

:run_specific_module
cls
echo Ejecutando pruebas y analisis de cobertura para el modulo !module_name!...
pytest --cov=!module_name! --cov-report=term-missing tests/ -v
echo.
echo Analisis completado.
pause
goto menu

:verbose_tests
cls
echo Ejecutando pruebas en modo verbose detallado...
pytest -vv tests/
echo.
echo Pruebas completadas.
pause
goto menu

:end
echo Saliendo del programa de pruebas...
pause
endlocal
exit /b 0
