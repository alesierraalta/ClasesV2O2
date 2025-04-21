#!/bin/bash

echo "Configurando Git..."
echo "Por favor, ingresa tu email de GitHub:"
read email_github
echo "Por favor, ingresa tu nombre de usuario de GitHub:"
read nombre_usuario

git config --global user.email "$email_github"
git config --global user.name "$nombre_usuario"

echo "Verificando el estado actual del repositorio..."
git status

echo "¿Quieres agregar todos los cambios? (y/n)"
read respuesta

if [ "$respuesta" = "y" ] || [ "$respuesta" = "Y" ]; then
    echo "Agregando todos los cambios..."
    git add .
    
    echo "Escribe un mensaje para el commit:"
    read mensaje_commit
    
    if [ -z "$mensaje_commit" ]; then
        mensaje_commit="Actualización de dependencias y corrección de errores"
    fi
    
    echo "Haciendo commit con mensaje: $mensaje_commit"
    git commit -m "$mensaje_commit"
    
    echo "Subiendo cambios al repositorio remoto (https://github.com/alesierraalta/ClasesO2.git)..."
    git push origin master
    
    if [ $? -eq 0 ]; then
        echo "¡Cambios subidos con éxito!"
    else
        echo "Error al hacer push. Por favor verifica tus credenciales y permisos."
        echo "Si es la primera vez que haces push, es posible que necesites generar un token personal:"
        echo "1. Ve a GitHub -> Settings -> Developer settings -> Personal access tokens"
        echo "2. Genera un nuevo token con permisos de 'repo'"
        echo "3. Usa este token como contraseña cuando se solicite"
    fi
else
    echo "Operación cancelada."
fi 