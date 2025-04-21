@echo off
echo ===== ACTUALIZADOR DE APP ClasesO2 =====
echo.

:: Verificar si estamos en el directorio correcto
if not exist run.bat (
    echo ERROR: Este script debe ejecutarse en el directorio principal de la aplicacion.
    echo El archivo run.bat no se encontro en el directorio actual.
    echo.
    echo Por favor, ejecute este script desde el directorio donde se encuentra run.bat
    goto :end
)

:: Verificar si git está instalado
git --version > nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Git no esta instalado en este sistema.
    echo Por favor, instale Git desde https://git-scm.com/ e intente nuevamente.
    goto :end
)

echo Obteniendo cambios del repositorio...
git reset --hard HEAD
git pull origin main

echo.
echo Activando entorno virtual...
call venv\Scripts\activate

echo.
echo Actualizando dependencias...
pip install -r requirements.txt

echo.
echo ¡Actualización completada con éxito!
echo.
echo Para iniciar la aplicación, ejecute: run.bat
echo.

:end
pause 