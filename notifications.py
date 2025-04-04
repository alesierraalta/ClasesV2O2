import os
import logging
import time as time_module
from datetime import datetime, time, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import pywhatkit
from flask import current_app
from sqlalchemy import and_, func

# Configuración del logger
def setup_logger():
    """Configurar logger para notificaciones"""
    # No usar basicConfig para evitar duplicación
    # logging.basicConfig(level=logging.INFO, 
    #                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    logger = logging.getLogger('notifications')
    logger.setLevel(logging.INFO)
    
    # Limpiar handlers existentes para evitar duplicación
    if logger.handlers:
        logger.handlers.clear()
    
    # Agregar manejadores
    # Manejador para archivo
    file_handler = logging.FileHandler('notifications.log')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)
    
    # Manejador para consola
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)
    
    # Establecer propagación a False para evitar que los mensajes se propaguen a handlers raíz
    logger.propagate = False
    
    return logger

# Inicialización
logger = setup_logger()

# Variable para almacenar el número de teléfono para notificaciones
NOTIFICATION_PHONE_NUMBER = None  # Será obtenido dinámicamente de la configuración

# Horas de notificación predeterminadas
DEFAULT_NOTIFICATION_HOUR_1 = "13:30"
DEFAULT_NOTIFICATION_HOUR_2 = "20:30"

# Variable global para controlar si el scheduler ya está iniciado
scheduler_initialized = False
scheduler = None

# Variable global para almacenar el último tiempo de envío
last_send_time = None
# Tiempo mínimo entre envíos (en segundos) - 15 minutos para evitar spam accidental
MIN_TIME_BETWEEN_SENDS = 15 * 60

# Tiempo mínimo para bloqueo (en segundos) - 30 minutos por defecto
MIN_LOCK_TIME = 30 * 60

# Ruta del archivo de bloqueo para prevenir envíos múltiples
LOCK_FILE = 'notification_lock.txt'

def is_notification_locked():
    """Verificar si existe un bloqueo de notificación activo"""
    try:
        if os.path.exists(LOCK_FILE):
            # Verificar si el bloqueo ha expirado (30 minutos)
            lock_time_str = open(LOCK_FILE, 'r').read().strip()
            try:
                lock_time = datetime.strptime(lock_time_str, '%Y-%m-%d %H:%M:%S')
                current_time = datetime.now()
                # Si el bloqueo tiene más de 30 minutos, considerarlo expirado
                if (current_time - lock_time).total_seconds() > 30 * 60:
                    logger.info("Bloqueo de notificación expirado, eliminando archivo de bloqueo")
                    os.remove(LOCK_FILE)
                    return False
                else:
                    return True
            except ValueError:
                # Si hay error al leer la fecha, eliminar el archivo y crear uno nuevo
                os.remove(LOCK_FILE)
                return False
        return False
    except Exception as e:
        logger.error(f"Error al verificar bloqueo de notificación: {str(e)}")
        # En caso de error, asumir que no hay bloqueo
        return False

def create_notification_lock():
    """Crear un archivo de bloqueo para prevenir envíos múltiples"""
    try:
        with open(LOCK_FILE, 'w') as f:
            f.write(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        return True
    except Exception as e:
        logger.error(f"Error al crear bloqueo de notificación: {str(e)}")
        return False

def release_notification_lock():
    """Liberar el bloqueo de notificación"""
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
        return True
    except Exception as e:
        logger.error(f"Error al liberar bloqueo de notificación: {str(e)}")
        return False

def setup_notification_config(app):
    """Configurar valores desde la aplicación Flask"""
    global NOTIFICATION_PHONE_NUMBER
    
    # Obtener valores de la configuración de la aplicación si existen
    NOTIFICATION_PHONE_NUMBER = app.config.get('NOTIFICATION_PHONE_NUMBER', os.environ.get('NOTIFICATION_PHONE_NUMBER', None))

def check_and_notify_unregistered_classes():
    """Verificar clases no registradas y enviar notificación"""
    from app import app, HorarioClase, ClaseRealizada, db, DIAS_SEMANA
    
    # Usar un contexto de aplicación para trabajar con la base de datos
    with app.app_context():
        try:
            logger.info("Verificando clases no registradas...")
            
            # Obtener la fecha actual
            hoy = datetime.now().date()
            dia_semana_hoy = hoy.weekday()  # 0 es lunes, 6 es domingo
            
            # Obtener todos los horarios programados para hoy
            horarios_hoy = HorarioClase.query.filter(
                HorarioClase.dia_semana == dia_semana_hoy
            ).all()
            
            if not horarios_hoy:
                # Convertir DIAS_SEMANA a un diccionario para obtener el nombre del día
                dias_dict = dict(DIAS_SEMANA)
                logger.info(f"No hay clases programadas para hoy ({dias_dict.get(dia_semana_hoy, 'Desconocido')})")
                return
            
            # Verificar qué clases ya han sido registradas hoy
            clases_realizadas_hoy = ClaseRealizada.query.filter(
                ClaseRealizada.fecha == hoy
            ).all()
            
            # IDs de horarios ya registrados hoy
            ids_registrados = {cr.horario_id for cr in clases_realizadas_hoy}
            
            # Identificar clases no registradas hasta ahora
            hora_actual = datetime.now().time()
            clases_pendientes = []
            
            for horario in horarios_hoy:
                # Calcular la hora de finalización de la clase
                hora_fin = calcular_hora_fin(horario.hora_inicio, horario.duracion)
                
                # Si la clase ya terminó y no está registrada, agregarla a pendientes
                if hora_fin < hora_actual and horario.id not in ids_registrados:
                    # Asegurarse de que existen los atributos necesarios
                    profesor_nombre = getattr(horario.profesor, 'nombre', 'Sin profesor asignado') if hasattr(horario, 'profesor') and horario.profesor else 'Sin profesor asignado'
                    
                    clases_pendientes.append({
                        'id': horario.id,
                        'tipo': getattr(horario, 'tipo_clase', 'N/A'),
                        'hora': horario.hora_inicio.strftime('%H:%M'),
                        'profesor': profesor_nombre
                    })
            
            if not clases_pendientes:
                logger.info("Todas las clases de hoy están registradas o aún no han finalizado")
                return
            
            # Construir mensaje
            mensaje = f"⚠️ ALERTA: {len(clases_pendientes)} clase(s) no registrada(s) hoy ({hoy.strftime('%d/%m/%Y')}):\n\n"
            
            for i, clase in enumerate(clases_pendientes, 1):
                mensaje += f"{i}. Clase de {clase['tipo']} a las {clase['hora']} con {clase['profesor']}\n"
            
            mensaje += "\nPor favor, registre estas clases lo antes posible."
            
            # Enviar notificación
            sent = send_whatsapp_notification(mensaje)
            
            if sent:
                logger.info(f"Notificación enviada para {len(clases_pendientes)} clases no registradas")
            else:
                logger.error("No se pudo enviar la notificación")
                
        except Exception as e:
            logger.error(f"Error al verificar clases no registradas: {str(e)}")
            raise Exception(f"Error al verificar clases no registradas: {str(e)}")  # Re-lanzar una excepción válida

def calcular_hora_fin(hora_inicio, duracion):
    """Calcula la hora de finalización de una clase"""
    minutos_totales = hora_inicio.hour * 60 + hora_inicio.minute + duracion
    horas, minutos = divmod(minutos_totales, 60)
    horas = horas % 24  # Manejar casos donde la clase termina después de la medianoche
    return time(hour=horas, minute=minutos)

def send_whatsapp_notification(message, phone_number=None):
    """Enviar notificación por WhatsApp usando PyWhatKit"""
    from app import app
    global last_send_time
    
    # Verificar si hay un bloqueo activo (envío en progreso)
    if is_notification_locked():
        logger.warning("Hay un envío de notificación en progreso. No se enviará otro mensaje.")
        return False
    
    # Control para evitar envíos múltiples accidentales
    current_time = datetime.now()
    if last_send_time is not None:
        time_diff = (current_time - last_send_time).total_seconds()
        if time_diff < MIN_TIME_BETWEEN_SENDS:
            logger.warning(f"Intento de envío múltiple detectado. Último envío hace {time_diff:.1f} segundos (mínimo {MIN_TIME_BETWEEN_SENDS} segundos). Se ignorará esta solicitud.")
            return False
    
    # Crear un bloqueo para evitar envíos simultáneos
    if not create_notification_lock():
        logger.error("No se pudo crear bloqueo para envío de notificación")
        return False
    
    try:
        # Si no se proporciona un número, intentar obtenerlo de la configuración
        if not phone_number:
            with app.app_context():
                phone_number = app.config.get('NOTIFICATION_PHONE_NUMBER', os.environ.get('NOTIFICATION_PHONE_NUMBER'))
        
        # Verificar que tengamos un número válido
        if not phone_number or phone_number == '+numero_a_notificar_aqui':
            logger.error("No se ha configurado un número de teléfono válido para notificaciones")
            release_notification_lock()
            return False
        
        # Formatear el número de teléfono (eliminar el + y cualquier espacio)
        formatted_phone = phone_number.replace('+', '').replace(' ', '')
        
        # Registro detallado para depuración
        logger.info(f"Enviando mensaje WhatsApp al número: +{formatted_phone}")
        
        # Intentar importar pyautogui para automatizar la pulsación de Enter
        try:
            import pyautogui
            have_pyautogui = True
            logger.info("Módulo pyautogui disponible para automatizar el envío")
        except ImportError:
            have_pyautogui = False
            logger.warning("Módulo pyautogui no disponible. El mensaje podría quedar pendiente de enviar.")
        
        # Configuración específica para asegurar el envío
        wait_time = 25  # Tiempo de espera para que cargue WhatsApp Web (aumentado)
        
        # Método alternativo: usar directamente pywhatkit.sendwhatmsg_instantly
        try:
            # Usamos el método instantáneo pero sin cerrar la pestaña
            logger.info("Usando método instantáneo con pestaña abierta...")
            pywhatkit.sendwhatmsg_instantly(
                f"+{formatted_phone}", 
                message,
                wait_time=wait_time,  # Tiempo de espera mayor para carga
                tab_close=False,  # No cerrar la pestaña para poder presionar Enter
                close_time=5
            )
            logger.info("Mensaje preparado correctamente en WhatsApp Web")
            
            # Esperar unos segundos adicionales para asegurar que la interfaz esté lista
            logger.info("Esperando 5 segundos adicionales...")
            time_module.sleep(5)
            
            # Presionar Enter para enviar el mensaje si tenemos pyautogui
            if have_pyautogui:
                logger.info("Presionando Enter para enviar el mensaje...")
                pyautogui.press('enter')
                time_module.sleep(3)  # Esperar confirmación de envío
                logger.info("Tecla Enter presionada correctamente")
            else:
                # Si no tenemos pyautogui, esperar más tiempo con la esperanza de que el usuario vea el mensaje
                logger.warning("No se puede presionar Enter automáticamente. El mensaje está pendiente de envío manual.")
                time_module.sleep(30)  # Esperar 30 segundos para dar tiempo al usuario a ver el mensaje
            
            # Presionar Alt+F4 para cerrar la ventana si tenemos pyautogui
            if have_pyautogui:
                logger.info("Cerrando ventana de WhatsApp Web...")
                pyautogui.hotkey('alt', 'f4')
                time_module.sleep(1)
                
        except Exception as e:
            logger.error(f"Error al enviar mensaje instantáneo: {str(e)}")
            return False
        
        # Actualizar el último tiempo de envío
        last_send_time = datetime.now()
        
        logger.info(f"Mensaje enviado a +{formatted_phone}")
        return True
    except Exception as e:
        logger.error(f"Error al enviar notificación por WhatsApp: {str(e)}")
        return False
    finally:
        # Siempre liberar el bloqueo al finalizar
        release_notification_lock()

def configure_notifications(app):
    """Configurar notificaciones para una aplicación Flask"""
    # No es necesario usar global aquí, ya que siempre obtendremos el valor de app.config
    
    # Configurar la instancia de aplicación
    app.config.setdefault('NOTIFICATION_PHONE_NUMBER', os.environ.get('NOTIFICATION_PHONE_NUMBER'))
    app.config.setdefault('NOTIFICATION_HOUR_1', os.environ.get('NOTIFICATION_HOUR_1', DEFAULT_NOTIFICATION_HOUR_1))
    app.config.setdefault('NOTIFICATION_HOUR_2', os.environ.get('NOTIFICATION_HOUR_2', DEFAULT_NOTIFICATION_HOUR_2))
    
    # Registrar la función para verificar clases no registradas
    return check_and_notify_unregistered_classes

def update_notification_schedule(app):
    """Actualizar el scheduler con nuevas horas de notificación"""
    global scheduler
    
    if scheduler and not scheduler.shutdown:
        # Eliminar trabajos existentes
        try:
            scheduler.remove_job('notification_afternoon')
            scheduler.remove_job('notification_evening')
            logger.info("Trabajos de notificación anteriores eliminados")
        except Exception as e:
            logger.warning(f"No se pudieron eliminar trabajos anteriores: {str(e)}")
        
        # Obtener horas configuradas
        hour1 = app.config.get('NOTIFICATION_HOUR_1', DEFAULT_NOTIFICATION_HOUR_1)
        hour2 = app.config.get('NOTIFICATION_HOUR_2', DEFAULT_NOTIFICATION_HOUR_2)
        
        try:
            # Convertir formato "HH:MM" a horas y minutos
            hour1_hour, hour1_minute = map(int, hour1.split(':'))
            hour2_hour, hour2_minute = map(int, hour2.split(':'))
            
            # Programar verificación para la primera hora
            scheduler.add_job(
                check_and_notify_unregistered_classes,
                'cron',
                hour=hour1_hour,
                minute=hour1_minute,
                id='notification_afternoon'
            )
            
            # Programar verificación para la segunda hora
            scheduler.add_job(
                check_and_notify_unregistered_classes,
                'cron',
                hour=hour2_hour,
                minute=hour2_minute,
                id='notification_evening'
            )
            
            # Agregar trabajo de prueba para verificar funcionamiento (para depuración)
            current_time = datetime.now()
            test_minute = (current_time.minute + 2) % 60  # 2 minutos en el futuro
            test_hour = current_time.hour
            if current_time.minute >= 58:  # Ajustar la hora si los minutos dan la vuelta
                test_hour = (test_hour + 1) % 24
                
            scheduler.add_job(
                check_and_notify_unregistered_classes,
                'cron',
                hour=test_hour,
                minute=test_minute,
                id='notification_test'
            )
            
            logger.info(f"Horarios de notificación actualizados: {hour1} y {hour2}")
            logger.info(f"Trabajo de prueba programado para: {test_hour}:{test_minute}")
            return True
        except Exception as e:
            logger.error(f"Error al configurar nuevos horarios de notificación: {str(e)}")
            return False
    else:
        logger.error("El scheduler no está inicializado o está apagado.")
        return False

def setup_notification_scheduler(app):
    """Configurar el scheduler para las notificaciones"""
    global scheduler_initialized, scheduler
    
    # Evitar inicializar múltiples veces
    if scheduler_initialized:
        logger.info("Scheduler ya está inicializado. Evitando duplicación.")
        return
        
    configure_notifications(app)
    
    # Inicializar el scheduler
    scheduler = BackgroundScheduler()
    
    # Obtener horas configuradas
    hour1 = app.config.get('NOTIFICATION_HOUR_1', DEFAULT_NOTIFICATION_HOUR_1)
    hour2 = app.config.get('NOTIFICATION_HOUR_2', DEFAULT_NOTIFICATION_HOUR_2)
    
    try:
        # Convertir formato "HH:MM" a horas y minutos
        hour1_hour, hour1_minute = map(int, hour1.split(':'))
        hour2_hour, hour2_minute = map(int, hour2.split(':'))
        
        # Programar verificación para la primera hora
        scheduler.add_job(
            check_and_notify_unregistered_classes,
            'cron',
            hour=hour1_hour,
            minute=hour1_minute,
            id='notification_afternoon'
        )
        
        # Programar verificación para la segunda hora
        scheduler.add_job(
            check_and_notify_unregistered_classes,
            'cron',
            hour=hour2_hour,
            minute=hour2_minute,
            id='notification_evening'
        )
        
        # Agregar un trabajo de prueba que se ejecute cada minuto (solo para verificación)
        scheduler.add_job(
            lambda: logger.info("Ejecución de verificación del scheduler - cada minuto"),
            'cron',
            minute='*',
            id='scheduler_heartbeat'
        )
        
        # Programar trabajo de prueba inmediato para 2 minutos después
        current_time = datetime.now()
        test_minute = (current_time.minute + 2) % 60
        test_hour = current_time.hour
        if current_time.minute >= 58:
            test_hour = (test_hour + 1) % 24
            
        scheduler.add_job(
            check_and_notify_unregistered_classes,
            'cron',
            hour=test_hour,
            minute=test_minute,
            id='notification_test_immediate'
        )
        
        # Iniciar el scheduler
        scheduler.start()
        scheduler_initialized = True
        logger.info(f"Scheduler de notificaciones iniciado con horarios: {hour1} y {hour2}")
        logger.info(f"Trabajo de prueba inmediato programado para: {test_hour}:{test_minute}")
    except Exception as e:
        logger.error(f"Error al configurar horarios de notificación: {str(e)}")
        # Intentar configurar con valores predeterminados
        try:
            scheduler.add_job(
                check_and_notify_unregistered_classes,
                'cron',
                hour=13,
                minute=30,
                id='notification_afternoon'
            )
            
            scheduler.add_job(
                check_and_notify_unregistered_classes,
                'cron',
                hour=20,
                minute=30,
                id='notification_evening'
            )
            
            # Agregar el heartbeat también en caso de recuperación
            scheduler.add_job(
                lambda: logger.info("Ejecución de verificación del scheduler - cada minuto (modo recuperación)"),
                'cron',
                minute='*',
                id='scheduler_heartbeat'
            )
            
            scheduler.start()
            scheduler_initialized = True
            logger.info("Scheduler de notificaciones iniciado con horarios predeterminados: 13:30 y 20:30")
        except Exception as inner_e:
            logger.error(f"Error crítico al inicializar scheduler: {str(inner_e)}")
            return False
            
    return True
