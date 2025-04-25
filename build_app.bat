@echo off
echo Iniciando entorno virtual...
if not exist venv (
    echo Creando entorno virtual...
    python -m venv venv
)

call venv\Scripts\activate

echo Instalando dependencias...
pip install -r requirements.txt

echo Creando carpeta static (para recursos estáticos)...
if not exist static (
    mkdir static
)

echo Limpiando compilaciones anteriores...
if exist dist (
    rmdir /s /q dist
)
if exist build (
    rmdir /s /q build
)

echo Compilando la aplicación con PyInstaller...
pyinstaller --clean gym_app.spec

echo.
echo Aplicación compilada. Ahora encontrarás el ejecutable en la carpeta "dist"
echo Para ejecutar la aplicación, haz doble clic en "dist\GymManager.exe"
echo.
echo IMPORTANTE: El ejecutable ahora incluye todas las dependencias en un solo archivo.
echo Si aún ves errores, intenta ejecutar el archivo como administrador.

pause 