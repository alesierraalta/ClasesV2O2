@echo off
setlocal enabledelayedexpansion

:: Configuracion de colores para la consola
set "GREEN=[92m"
set "YELLOW=[93m"
set "CYAN=[96m"
set "RESET=[0m"

:: Activar el entorno virtual
echo %CYAN%Activando entorno virtual...%RESET%
call venv\Scripts\activate

:: Establecer variables de entorno para pruebas
set FLASK_ENV=testing
set NOTIFICATION_PHONE_NUMBER=+5555555555

echo %CYAN%Ejecutando pruebas del modulo de notificaciones...%RESET%
echo.

:: Ejecutar las pruebas de notificaciones con reporte detallado
pytest --cov=notifications --cov-report=term-missing tests/test_notifications.py -v

echo.
echo %GREEN%Pruebas de notificaciones completadas.%RESET%
echo.
echo %YELLOW%Presiona cualquier tecla para salir...%RESET%
pause
