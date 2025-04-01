"""
Script de prueba para enviar una notificación usando la función actualizada
que usa pyautogui para asegurar que el mensaje se envíe correctamente.
"""
from app import app
import logging
import time
import os
import sys

# Configurar logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logger = logging.getLogger('test_notification')

def check_dependencies():
    """Verifica que todas las dependencias necesarias estén instaladas."""
    missing_deps = []
    
    print("Verificando dependencias necesarias...")
    
    try:
        import pywhatkit
        print("✓ pywhatkit está instalado correctamente")
    except ImportError:
        print("✗ Error: pywhatkit no está instalado")
        missing_deps.append("pywhatkit")
    
    try:
        import pyautogui
        print("✓ pyautogui está instalado correctamente")
    except ImportError:
        print("✗ Error: pyautogui no está instalado")
        missing_deps.append("pyautogui")
    
    if missing_deps:
        print("\n⚠️ Faltan las siguientes dependencias:")
        for dep in missing_deps:
            print(f"  - {dep}")
        
        print("\nPuede instalarlas con los siguientes comandos:")
        print("pip install pywhatkit pyautogui")
        
        proceed = input("\n¿Desea continuar de todas formas? (s/n): ")
        if proceed.lower() not in ('s', 'si', 'sí', 'y', 'yes'):
            print("Prueba cancelada.")
            sys.exit(1)
    
    return True

def test_send_notification():
    """Prueba el envío de una notificación por WhatsApp."""
    # Importar aquí para evitar errores si faltan dependencias
    from notifications import send_whatsapp_notification
    
    with app.app_context():
        # Obtener el número de teléfono de la configuración o usar uno de prueba
        phone = app.config.get('NOTIFICATION_PHONE_NUMBER', os.environ.get('NOTIFICATION_PHONE_NUMBER'))
        
        if not phone:
            print("No hay un número de teléfono configurado. Solicitando número...")
            phone = input("Ingrese el número de teléfono (con código de país, ej: +584244461682): ")
            
            # Guardar temporalmente en la configuración
            app.config['NOTIFICATION_PHONE_NUMBER'] = phone
            
            # Preguntar si desea guardar en run.bat
            save = input("¿Desea guardar este número de teléfono para futuras notificaciones? (s/n): ")
            if save.lower() in ('s', 'si', 'sí', 'y', 'yes'):
                try:
                    run_bat_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'run.bat')
                    if os.path.exists(run_bat_path):
                        with open(run_bat_path, 'r', encoding='utf-8') as file:
                            content = file.read()
                        
                        # Actualizar el número de teléfono
                        import re
                        pattern = r'set NOTIFICATION_PHONE_NUMBER=(\+[0-9]+|[^"\n\r]*)'
                        content = re.sub(pattern, f'set NOTIFICATION_PHONE_NUMBER={phone}', content)
                        
                        with open(run_bat_path, 'w', encoding='utf-8') as file:
                            file.write(content)
                            
                        print(f"Número guardado en {run_bat_path}")
                    else:
                        print(f"No se encontró el archivo run.bat en {run_bat_path}")
                except Exception as e:
                    print(f"Error al guardar el número: {str(e)}")
        
        # Construir un mensaje de prueba
        test_message = f"""
⚠️ MENSAJE DE PRUEBA

Este es un mensaje de prueba del sistema de notificaciones.
Hora actual: {time.strftime('%H:%M:%S')}

Por favor confirme si recibió este mensaje.
"""
        
        print(f"\nEnviando mensaje de prueba a {phone}...")
        print("NOTA: No mueva el mouse ni use el teclado durante el proceso.")
        print("El envío usará pyautogui para presionar Enter automáticamente.\n")
        
        # Cuenta regresiva
        for i in range(5, 0, -1):
            print(f"Comenzando en {i} segundos...", end="\r")
            time.sleep(1)
        print("\n")
        
        # Enviar la notificación
        try:
            result = send_whatsapp_notification(test_message, phone)
            
            if result:
                print("\n✅ Mensaje enviado correctamente")
            else:
                print("\n❌ Error al enviar el mensaje")
                print("Revise el archivo notifications.log para más detalles.")
                
            return result
        except Exception as e:
            print(f"\n❌ Error grave al enviar la notificación: {str(e)}")
            print("Este error puede deberse a problemas con WhatsApp Web o el navegador.")
            print("Sugerencias:")
            print("1. Asegúrese de tener WhatsApp Web configurado y accesible")
            print("2. Verifique su conexión a internet")
            print("3. Cierre todas las pestañas de WhatsApp Web y vuelva a intentarlo")
            return False

if __name__ == "__main__":
    print("=== PRUEBA DE ENVÍO DE NOTIFICACIÓN ===\n")
    
    # Verificar dependencias
    check_dependencies()
    
    # Ejecutar prueba
    test_send_notification()
    
    print("\n=== FIN DE LA PRUEBA ===")
    input("Presione Enter para salir...") 