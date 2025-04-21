from app import app
import os
import re

def configure_notifications():
    """
    Script para configurar permanentemente las notificaciones WhatsApp.
    Guarda la configuración en run.bat y variables de entorno.
    """
    # Número de teléfono a configurar (cambia esto por tu número real)
    telefono = "+584244461682"  # Reemplaza con el número que usaste en la prueba
    hora1 = "13:30"  # Primera notificación diaria (13:30)
    hora2 = "20:30"  # Segunda notificación diaria (20:30)
    
    print(f"Configurando notificaciones WhatsApp con:")
    print(f"Teléfono: {telefono}")
    print(f"Horas de notificación: {hora1} y {hora2}")
    
    # Guardar en variables de entorno (para la sesión actual)
    os.environ['NOTIFICATION_PHONE_NUMBER'] = telefono
    os.environ['NOTIFICATION_HOUR_1'] = hora1
    os.environ['NOTIFICATION_HOUR_2'] = hora2
    
    # Guardar en la configuración de la aplicación
    app.config['NOTIFICATION_PHONE_NUMBER'] = telefono
    app.config['NOTIFICATION_HOUR_1'] = hora1
    app.config['NOTIFICATION_HOUR_2'] = hora2
    
    print("Configuración aplicada a la sesión actual.")
    
    # Guardar en run.bat para que sea permanente
    try:
        run_bat_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'run.bat')
        if os.path.exists(run_bat_path):
            with open(run_bat_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Actualizar o agregar el número de teléfono
            if 'set NOTIFICATION_PHONE_NUMBER=' in content:
                pattern = r'set NOTIFICATION_PHONE_NUMBER=(\+[0-9]+|[^"\n\r]*)'
                content = re.sub(pattern, f'set NOTIFICATION_PHONE_NUMBER={telefono}', content)
            else:
                content += f'\nset NOTIFICATION_PHONE_NUMBER={telefono}'
            
            # Actualizar o agregar horas de notificación
            if 'set NOTIFICATION_HOUR_1=' in content:
                content = re.sub(r'set NOTIFICATION_HOUR_1=[0-9:]+', f'set NOTIFICATION_HOUR_1={hora1}', content)
            else:
                content += f'\nset NOTIFICATION_HOUR_1={hora1}'
                
            if 'set NOTIFICATION_HOUR_2=' in content:
                content = re.sub(r'set NOTIFICATION_HOUR_2=[0-9:]+', f'set NOTIFICATION_HOUR_2={hora2}', content)
            else:
                content += f'\nset NOTIFICATION_HOUR_2={hora2}'
            
            # Guardar cambios
            with open(run_bat_path, 'w', encoding='utf-8') as file:
                file.write(content)
                
            print(f"Configuración guardada en {run_bat_path}")
            print("Las notificaciones funcionarán correctamente después de reiniciar la aplicación.")
        else:
            print(f"No se encontró el archivo run.bat en {run_bat_path}")
    except Exception as e:
        print(f"Error al guardar la configuración: {str(e)}")
        
    return True

if __name__ == "__main__":
    configure_notifications() 