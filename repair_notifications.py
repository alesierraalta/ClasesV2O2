from app import app
from notifications import setup_notification_scheduler, check_and_notify_unregistered_classes
from notifications import update_notification_schedule, scheduler, scheduler_initialized
from notifications import DEFAULT_NOTIFICATION_HOUR_1, DEFAULT_NOTIFICATION_HOUR_2
import logging
import os
import re

# Configurar logging para ver mensajes en consola
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logger = logging.getLogger('notification_repair')

def configurar_notificaciones():
    """Configura las notificaciones con valores predeterminados si no están configurados"""
    # Verificar la configuración actual
    with app.app_context():
        phone = app.config.get('NOTIFICATION_PHONE_NUMBER', None)
        hour1 = app.config.get('NOTIFICATION_HOUR_1', None)
        hour2 = app.config.get('NOTIFICATION_HOUR_2', None)
        
        print("Configuración actual:")
        print(f"Teléfono: {phone}")
        print(f"Hora notificación 1: {hour1}")
        print(f"Hora notificación 2: {hour2}")
        
        # Solicitar o configurar el número de teléfono si no está configurado
        if not phone:
            telefono = input("\nIngrese el número de teléfono para notificaciones (ej: +584244461682): ")
            if not telefono:
                print("No se ingresó un número, usando un valor de ejemplo.")
                telefono = "+584244461682"  # Reemplaza esto con un número real
        else:
            telefono = phone
            
        # Configurar horas si no están definidas
        if not hour1:
            hora1 = DEFAULT_NOTIFICATION_HOUR_1
            print(f"Usando hora predeterminada para notificación 1: {hora1}")
        else:
            hora1 = hour1
            
        if not hour2:
            hora2 = DEFAULT_NOTIFICATION_HOUR_2
            print(f"Usando hora predeterminada para notificación 2: {hora2}")
        else:
            hora2 = hour2
        
        # Guardar configuración en variables de entorno
        os.environ['NOTIFICATION_PHONE_NUMBER'] = telefono
        os.environ['NOTIFICATION_HOUR_1'] = hora1
        os.environ['NOTIFICATION_HOUR_2'] = hora2
        
        # Guardar en la configuración de la aplicación
        app.config['NOTIFICATION_PHONE_NUMBER'] = telefono
        app.config['NOTIFICATION_HOUR_1'] = hora1
        app.config['NOTIFICATION_HOUR_2'] = hora2
        
        print("\nNueva configuración:")
        print(f"Teléfono: {app.config['NOTIFICATION_PHONE_NUMBER']}")
        print(f"Hora notificación 1: {app.config['NOTIFICATION_HOUR_1']}")
        print(f"Hora notificación 2: {app.config['NOTIFICATION_HOUR_2']}")
        
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
            else:
                print(f"Advertencia: No se encontró el archivo run.bat en {run_bat_path}")
        except Exception as e:
            print(f"Error al guardar la configuración: {str(e)}")
    
    return True

def inicializar_scheduler():
    """Inicializa el scheduler si no está ya inicializado"""
    print("\nInicializando scheduler...")
    with app.app_context():
        setup_notification_scheduler(app)
    
    # Verificar estado
    print(f"Scheduler inicializado: {scheduler_initialized}")
    if scheduler is None:
        print("ERROR: El scheduler no está definido después de la inicialización.")
        return False
    
    # Verificar si el scheduler está activo
    if hasattr(scheduler, 'shutdown') and scheduler.shutdown:
        print("ERROR: El scheduler está apagado.")
        return False
    else:
        print("El scheduler está activo.")
    
    return True

def verificar_y_actualizar_scheduler():
    """Verifica y actualiza la configuración del scheduler"""
    if not scheduler_initialized or scheduler is None:
        print("El scheduler no está inicializado. Inicializando...")
        inicializar_scheduler()
    
    print("\nActualizando configuración del scheduler...")
    with app.app_context():
        result = update_notification_schedule(app)
        if result:
            print("Scheduler actualizado correctamente.")
        else:
            print("No se pudo actualizar el scheduler.")
    
    # Mostrar trabajos programados
    if scheduler:
        jobs = scheduler.get_jobs()
        print(f"\nTrabajos programados ({len(jobs)}):")
        if not jobs:
            print("No hay trabajos programados.")
        else:
            for job in jobs:
                print(f"  - ID: {job.id}")
                print(f"    Función: {job.func.__name__ if hasattr(job.func, '__name__') else job.func}")
                print(f"    Trigger: {job.trigger}")
                if hasattr(job, 'next_run_time'):
                    print(f"    Próxima ejecución: {job.next_run_time}")
                print()
    
    return True

def verificar_clases_pendientes():
    """Verifica si hay clases pendientes de registrar"""
    print("\nVerificando clases no registradas...")
    with app.app_context():
        try:
            result = check_and_notify_unregistered_classes()
            print("Verificación completada.")
            return True
        except Exception as e:
            print(f"Error al verificar clases no registradas: {str(e)}")
            return False

if __name__ == "__main__":
    print("=== REPARACIÓN Y CONFIGURACIÓN DE NOTIFICACIONES ===\n")
    
    # Paso 1: Configurar notificaciones
    configurar_notificaciones()
    
    # Paso 2: Inicializar scheduler
    inicializar_scheduler()
    
    # Paso 3: Verificar y actualizar scheduler
    verificar_y_actualizar_scheduler()
    
    # Paso 4: Verificar clases pendientes
    verificar_clases_pendientes()
    
    print("\n=== PROCESO COMPLETADO ===")
    print("El sistema de notificaciones debería estar funcionando correctamente.")
    print("Para que los cambios sean permanentes, reinicie la aplicación con run.bat.") 