"""
Script para verificar el estado actual del sistema de notificaciones
y limpiar cualquier bloqueo que pueda haber quedado.
"""
import os
import sys
from datetime import datetime

# Comprobar si existe un archivo de bloqueo
LOCK_FILE = 'notification_lock.txt'

def check_lock_file():
    """Verificar si existe un archivo de bloqueo de notificación y su estado"""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                lock_time_str = f.read().strip()
            
            try:
                lock_time = datetime.strptime(lock_time_str, '%Y-%m-%d %H:%M:%S')
                current_time = datetime.now()
                time_diff = (current_time - lock_time).total_seconds()
                
                print(f"🔒 Archivo de bloqueo encontrado:")
                print(f"   - Fecha/hora del bloqueo: {lock_time_str}")
                print(f"   - Tiempo transcurrido: {time_diff:.1f} segundos")
                
                if time_diff > 30 * 60:  # 30 minutos
                    print("   - Estado: EXPIRADO (más de 30 minutos)")
                else:
                    print("   - Estado: ACTIVO")
                
                return True
            except ValueError:
                print("🔒 Archivo de bloqueo encontrado pero con formato de fecha inválido")
                return True
        except Exception as e:
            print(f"❌ Error al leer el archivo de bloqueo: {str(e)}")
            return True
    else:
        print("✅ No se encontró ningún archivo de bloqueo activo")
        return False

def delete_lock_file():
    """Eliminar el archivo de bloqueo si existe"""
    if os.path.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
            print("✅ Archivo de bloqueo eliminado correctamente")
            return True
        except Exception as e:
            print(f"❌ Error al eliminar el archivo de bloqueo: {str(e)}")
            return False
    else:
        print("⚠️ No hay archivo de bloqueo para eliminar")
        return False

def check_notification_config():
    """Verificar la configuración actual del número de teléfono para notificaciones"""
    notification_number = os.environ.get('NOTIFICATION_PHONE_NUMBER')
    
    if not notification_number:
        print("⚠️ No se encontró ningún número de teléfono configurado en las variables de entorno")
    else:
        print(f"📱 Número de teléfono configurado: {notification_number}")
    
    # Verificar archivo run.bat
    run_bat_path = 'run.bat'
    if os.path.exists(run_bat_path):
        try:
            with open(run_bat_path, 'r') as f:
                content = f.read()
            
            import re
            pattern = r'set NOTIFICATION_PHONE_NUMBER=(.*)'
            match = re.search(pattern, content)
            
            if match:
                number_in_bat = match.group(1)
                print(f"📱 Número configurado en run.bat: {number_in_bat}")
                
                if notification_number and number_in_bat != notification_number:
                    print("⚠️ El número en run.bat es diferente al de las variables de entorno")
            else:
                print("⚠️ No se encontró configuración de número en run.bat")
        except Exception as e:
            print(f"❌ Error al leer run.bat: {str(e)}")

def show_menu():
    """Mostrar menú de opciones"""
    print("\n==== VERIFICADOR DE SISTEMA DE NOTIFICACIONES ====")
    print("1. Verificar estado de archivos de bloqueo")
    print("2. Eliminar archivo de bloqueo (si existe)")
    print("3. Verificar configuración de número de teléfono")
    print("4. Ejecutar todas las verificaciones")
    print("0. Salir")
    
    option = input("\nSeleccione una opción: ")
    return option

if __name__ == "__main__":
    # Si hay argumentos en línea de comandos, ejecutar acciones directamente
    if len(sys.argv) > 1:
        if sys.argv[1] == "clean":
            print("Modo limpieza: eliminando archivos de bloqueo")
            delete_lock_file()
            sys.exit(0)
        elif sys.argv[1] == "check":
            print("Modo verificación: comprobando estado")
            check_lock_file()
            check_notification_config()
            sys.exit(0)
    
    # Modo interactivo
    while True:
        option = show_menu()
        
        if option == "1":
            check_lock_file()
            input("\nPresione Enter para continuar...")
        elif option == "2":
            delete_lock_file()
            input("\nPresione Enter para continuar...")
        elif option == "3":
            check_notification_config()
            input("\nPresione Enter para continuar...")
        elif option == "4":
            check_lock_file()
            check_notification_config()
            input("\nPresione Enter para continuar...")
        elif option == "0":
            print("Saliendo...")
            break
        else:
            print("Opción no válida")
