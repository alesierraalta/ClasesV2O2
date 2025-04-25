from app import app
from notifications import scheduler, scheduler_initialized
import logging

# Configurar logging para ver mensajes en consola
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logger = logging.getLogger('scheduler_checker')

def verificar_scheduler():
    """
    Verifica el estado del programador de notificaciones y muestra sus trabajos configurados.
    """
    print("Verificando el estado del programador de notificaciones...\n")
    
    # Verificar si el scheduler está inicializado
    print(f"Scheduler inicializado: {scheduler_initialized}")
    
    if scheduler is None:
        print("ERROR: El scheduler no está definido.")
        return False
    
    # Verificar si el scheduler está activo
    if scheduler.shutdown:
        print("ERROR: El scheduler está apagado.")
        return False
    else:
        print("El scheduler está activo.")
    
    # Obtener los trabajos programados
    jobs = scheduler.get_jobs()
    
    print(f"\nTrabajos programados ({len(jobs)}):")
    if not jobs:
        print("No hay trabajos programados.")
    else:
        for job in jobs:
            print(f"  - ID: {job.id}")
            print(f"    Función: {job.func.__name__ if hasattr(job.func, '__name__') else job.func}")
            print(f"    Trigger: {job.trigger}")
            print(f"    Próxima ejecución: {job.next_run_time}")
            print()
    
    # Verificar la configuración actual
    with app.app_context():
        phone = app.config.get('NOTIFICATION_PHONE_NUMBER', 'No configurado')
        hour1 = app.config.get('NOTIFICATION_HOUR_1', 'No configurado')
        hour2 = app.config.get('NOTIFICATION_HOUR_2', 'No configurado')
        
        print("\nConfiguración actual:")
        print(f"Teléfono: {phone}")
        print(f"Hora notificación 1: {hour1}")
        print(f"Hora notificación 2: {hour2}")
    
    return True

if __name__ == "__main__":
    verificar_scheduler()
    print("\nVerificación completa.") 