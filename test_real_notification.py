"""
Script para probar el formato real de una notificación de clases no registradas
"""
from app import app, HorarioClase
from notifications import send_whatsapp_notification
from datetime import datetime

# Mensaje de ejemplo con el formato exacto usado en notificaciones reales
def crear_mensaje_ejemplo():
    """Crear un mensaje de ejemplo con el formato exacto que se usa en notificaciones reales"""
    
    # Datos de ejemplo de clases no registradas (similar a las clases reales en la base de datos)
    clases_pendientes = [
        {
            'id': 1,
            'tipo_clase': 'MOVE',
            'hora_inicio': '09:30',
            'hora_fin': '10:15',
            'profesor': 'Juan Pérez',
            'dia': 'Lunes',
            'fecha': datetime.now().strftime('%d/%m/%Y')
        },
        {
            'id': 2,
            'tipo_clase': 'RIDE',
            'hora_inicio': '11:00',
            'hora_fin': '11:45',
            'profesor': 'María García',
            'dia': 'Lunes',
            'fecha': datetime.now().strftime('%d/%m/%Y')
        },
        {
            'id': 3,
            'tipo_clase': 'BOX',
            'hora_inicio': '15:45',
            'hora_fin': '16:30',
            'profesor': 'Carlos Rodríguez',
            'dia': 'Lunes',
            'fecha': datetime.now().strftime('%d/%m/%Y')
        }
    ]
    
    # Obtener la fecha actual
    fecha_hoy = datetime.now().strftime('%d/%m/%Y')
    
    # Construir el mensaje como se hace en la función original
    mensaje = f"⚠️ ALERTA: {len(clases_pendientes)} clase(s) no registrada(s) hoy ({fecha_hoy}):\n\n"
    
    for i, clase in enumerate(clases_pendientes, 1):
        mensaje += f"{i}. Clase de {clase['tipo_clase']} a las {clase['hora_inicio']} con {clase['profesor']}\n"
    
    mensaje += "\nPor favor, registre estas clases lo antes posible."
    
    return mensaje

def mostrar_menu():
    """Mostrar menú de opciones para probar diferentes ejemplos de mensajes"""
    print("\n===== PRUEBA DE NOTIFICACIONES DE WHATSAPP =====")
    print("1. Ver ejemplo de mensaje de clases no registradas")
    print("2. Enviar mensaje de prueba de clases no registradas")
    print("3. Enviar mensaje de prueba simple")
    print("0. Salir")
    
    opcion = input("\nSeleccione una opción: ")
    return opcion

if __name__ == "__main__":
    with app.app_context():
        while True:
            opcion = mostrar_menu()
            
            if opcion == "1":
                # Solo mostrar el mensaje de ejemplo
                mensaje = crear_mensaje_ejemplo()
                print("\n=== EJEMPLO DE MENSAJE DE CLASES NO REGISTRADAS ===")
                print(mensaje)
                print("==================================================")
                input("\nPresione Enter para continuar...")
                
            elif opcion == "2":
                # Enviar mensaje de ejemplo de clases no registradas
                mensaje = crear_mensaje_ejemplo()
                print("\n=== ENVIANDO MENSAJE DE EJEMPLO ===")
                print(mensaje)
                print("==================================")
                
                confirmacion = input("\n¿Está seguro de enviar este mensaje? (s/n): ")
                if confirmacion.lower() in ('s', 'si', 'sí', 'y', 'yes'):
                    print("Enviando mensaje...")
                    resultado = send_whatsapp_notification(mensaje)
                    if resultado:
                        print("Mensaje enviado correctamente. Revise WhatsApp.")
                    else:
                        print("No se pudo enviar el mensaje. Revise los logs.")
                else:
                    print("Envío cancelado.")
                
                input("\nPresione Enter para continuar...")
                
            elif opcion == "3":
                # Enviar mensaje simple de prueba
                mensaje = f"✅ Esta es una prueba simple de WhatsApp desde AppClases\nHora: {datetime.now().strftime('%H:%M:%S')}"
                print("\n=== ENVIANDO MENSAJE SIMPLE ===")
                print(mensaje)
                print("==============================")
                
                confirmacion = input("\n¿Está seguro de enviar este mensaje? (s/n): ")
                if confirmacion.lower() in ('s', 'si', 'sí', 'y', 'yes'):
                    print("Enviando mensaje...")
                    resultado = send_whatsapp_notification(mensaje)
                    if resultado:
                        print("Mensaje enviado correctamente. Revise WhatsApp.")
                    else:
                        print("No se pudo enviar el mensaje. Revise los logs.")
                else:
                    print("Envío cancelado.")
                
                input("\nPresione Enter para continuar...")
                
            elif opcion == "0":
                print("Saliendo...")
                break
                
            else:
                print("Opción no válida. Intente de nuevo.")
