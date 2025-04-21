#!/bin/bash

echo "Configurando Git..."
echo "Por favor, ingresa tu email de GitHub:"
read email_github
echo "Por favor, ingresa tu nombre de usuario de GitHub:"
read nombre_usuario

git config --global user.email "$email_github"
git config --global user.name "$nombre_usuario"

# Aumentar el buffer para repositorios grandes
git config --global http.postBuffer 524288000

echo "Verificando el estado actual de requirements.txt..."
git status requirements.txt

echo "¿Quieres agregar requirements.txt a los cambios? (y/n)"
read respuesta

if [ "$respuesta" = "y" ] || [ "$respuesta" = "Y" ]; then
    echo "Agregando requirements.txt..."
    git add requirements.txt
    
    echo "Haciendo commit con mensaje: 'Actualización de dependencias en requirements.txt'"
    git commit -m "Actualización de dependencias en requirements.txt"
    
    echo "Subiendo cambios al repositorio remoto..."
    git push origin master
    
    if [ $? -eq 0 ]; then
        echo "¡Cambios subidos con éxito!"
    else
        echo "Error al hacer push. Por favor, verifica tus credenciales."
        echo "Recuerda: GitHub requiere un token personal de acceso (PAT) en lugar de contraseña:"
        echo "1. Ve a GitHub -> Settings -> Developer settings -> Personal access tokens"
        echo "2. Genera un nuevo token con permisos de 'repo'"
        echo "3. Usa este token como contraseña cuando se solicite"
    fi
else
    echo "Operación cancelada."
fi 