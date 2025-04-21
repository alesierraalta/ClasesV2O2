@echo off
echo Ejecutando pruebas de notificaciones desde su nueva ubicación...
cd tests
call run_notification_tests.bat
cd ..
pause 