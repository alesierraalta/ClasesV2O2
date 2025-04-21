@echo off
setlocal

REM Cambiamos al directorio raíz del proyecto
cd %~dp0
cd ..

echo === PRUEBAS DE NOTIFICACIONES ===
echo.
echo Este script ejecutará las pruebas relacionadas con las notificaciones.
echo.

REM Ejecutar pruebas relacionadas con notificaciones
python -m pytest tests/test_notifications.py -v

echo.
echo Pruebas completadas.
pause
