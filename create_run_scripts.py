#!/usr/bin/env python3
"""
Script para regenerar los scripts de ejecución después de la reorganización.
Crea scripts adecuados para Windows y macOS.
"""
import os
import stat

def create_windows_scripts():
    """Crear scripts para Windows."""
    # Script para ejecutar la aplicación
    with open('run_windows.bat', 'w') as f:
        f.write('@echo off\n')
        f.write('echo Ejecutando la aplicación desde scripts/windows...\n')
        f.write('cd scripts\\windows\n')
        f.write('call run.bat\n')
        f.write('cd ../..\n')
        f.write('pause\n')
    
    # Script para ejecutar tests
    with open('run_tests_windows.bat', 'w') as f:
        f.write('@echo off\n')
        f.write('echo Ejecutando pruebas...\n')
        f.write('cd tests\n')
        f.write('call run_tests.bat\n')
        f.write('cd ..\n')
        f.write('pause\n')

def create_mac_scripts():
    """Crear scripts para macOS."""
    # Script para ejecutar la aplicación
    with open('run_mac.sh', 'w') as f:
        f.write('#!/bin/bash\n')
        f.write('echo "Ejecutando la aplicación desde scripts/mac..."\n')
        f.write('cd "$(dirname "$0")"\n')  # Cambia al directorio del script
        f.write('bash scripts/mac/run.sh\n')
    
    # Dar permisos de ejecución
    os.chmod('run_mac.sh', os.stat('run_mac.sh').st_mode | stat.S_IEXEC)
    
    # Script para ejecutar tests
    with open('run_tests_mac.sh', 'w') as f:
        f.write('#!/bin/bash\n')
        f.write('echo "Ejecutando pruebas..."\n')
        f.write('cd "$(dirname "$0")"\n')  # Cambia al directorio del script
        f.write('cd tests\n')
        f.write('python run_tests.py\n')
        f.write('cd ..\n')
    
    # Dar permisos de ejecución
    os.chmod('run_tests_mac.sh', os.stat('run_tests_mac.sh').st_mode | stat.S_IEXEC)

def main():
    """Función principal."""
    print("Regenerando scripts de ejecución...")
    
    create_windows_scripts()
    create_mac_scripts()
    
    print("Scripts regenerados correctamente.")
    print("\nPara Windows:")
    print("  - run_windows.bat: Ejecutar la aplicación")
    print("  - run_tests_windows.bat: Ejecutar pruebas")
    print("\nPara macOS:")
    print("  - run_mac.sh: Ejecutar la aplicación")
    print("  - run_tests_mac.sh: Ejecutar pruebas")

if __name__ == "__main__":
    main() 