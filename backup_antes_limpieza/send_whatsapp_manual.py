"""
Script alternativo para enviar mensajes WhatsApp utilizando pyautogui para presionar Enter
Este script puede usarse si el método normal no está enviando los mensajes correctamente
"""
import os
import sys
import time
from datetime import datetime

try:
    import pywhatkit
    import pyautogui
except ImportError:
    print("Instalando dependencias necesarias...")
    os.system("pip install pywhatkit pyautogui")
    import pywhatkit
    import pyautogui

def send_whatsapp_with_enter(phone_number, message):
    """
    Envía un mensaje de WhatsApp y presiona Enter automáticamente
    usando pyautogui para simular la pulsación de tecla.
    """
    if not phone_number.startswith("+"):
        phone_number = "+" + phone_number
        
    print(f"Enviando mensaje a {phone_number}...")
    
    # Formatear el número sin el +
    formatted_phone = phone_number.replace('+', '').replace(' ', '')
    
    try:
        # Usar el método instantáneo que abre WhatsApp Web inmediatamente
        wait_time = 30  # 30 segundos para cargar WhatsApp Web
        print(f"Abriendo WhatsApp Web (espera de {wait_time} segundos)...")
        
        # No cerrar la pestaña automáticamente para poder presionar Enter manualmente
        pywhatkit.sendwhatmsg_instantly(
            f"+{formatted_phone}",
            message,
            wait_time=wait_time,
            tab_close=False,
            close_time=3
        )
        
        # Esperar a que se cargue la página y el mensaje esté listo
        print("Esperando 5 segundos adicionales...")
        time.sleep(5)
        
        # Presionar Enter para enviar el mensaje
        print("Presionando Enter para enviar el mensaje...")
        pyautogui.press('enter')
        
        # Esperar para confirmar que se envió
        time.sleep(3)
        print("Mensaje enviado con éxito")
        return True
        
    except Exception as e:
        print(f"Error al enviar el mensaje: {str(e)}")
        return False

def main():
    print("=== ENVÍO MANUAL DE MENSAJES WHATSAPP ===")
    
    # Verificar si hay parámetros en línea de comandos
    if len(sys.argv) > 2:
        phone = sys.argv[1]
        message = sys.argv[2]
    else:
        # Solicitar datos manualmente
        phone = input("Ingrese el número de teléfono (con código de país, ej: +584244461682): ")
        message = input("Ingrese el mensaje a enviar: ")
        if not message:
            message = f"Este es un mensaje de prueba enviado el {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    
    # Confirmar antes de enviar
    print("\n=== DATOS DEL ENVÍO ===")
    print(f"Número: {phone}")
    print(f"Mensaje:\n{message}\n")
    
    confirm = input("¿Desea enviar este mensaje? (s/n): ")
    if confirm.lower() in ('s', 'si', 'sí', 'y', 'yes'):
        print("\nPreparando para enviar mensaje...")
        print("IMPORTANTE: No mueva el mouse ni use el teclado durante el proceso")
        print("La ventana de WhatsApp Web se abrirá automáticamente\n")
        
        # Cuenta regresiva para que el usuario se prepare
        for i in range(5, 0, -1):
            print(f"Comenzando en {i} segundos...", end="\r")
            time.sleep(1)
        print("\n")
        
        # Enviar el mensaje
        result = send_whatsapp_with_enter(phone, message)
        
        if result:
            print("\n✅ Mensaje enviado correctamente")
        else:
            print("\n❌ Error al enviar el mensaje")
    else:
        print("Envío cancelado")

if __name__ == "__main__":
    main()
