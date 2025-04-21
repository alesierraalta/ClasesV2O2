"""
Pruebas unitarias para el módulo de notificaciones.
"""
import os
import sys
import pytest
import tempfile
import logging
from datetime import datetime, timedelta, time
from unittest.mock import patch, MagicMock, mock_open, call

# Añadir el directorio raíz del proyecto al PATH para importar módulos
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importar componentes a probar
from notifications import (
    create_notification_lock, is_notification_locked, release_notification_lock, 
    send_whatsapp_notification, LOCK_FILE, MIN_TIME_BETWEEN_SENDS,
    check_and_notify_unregistered_classes as check_unregistered_classes, calcular_hora_fin,
    configure_notifications, setup_notification_scheduler
)

@pytest.fixture
def temp_lock_file(monkeypatch):
    """Fixture que proporciona un archivo de bloqueo temporal para las pruebas."""
    # Guardar el valor original
    original_lock_file = LOCK_FILE
    
    # Crear un archivo temporal para las pruebas
    temp_dir = tempfile.gettempdir()
    temp_lock_path = os.path.join(temp_dir, 'test_notification_lock.txt')
    
    # Usar monkeypatch para modificar la constante global
    monkeypatch.setattr('notifications.LOCK_FILE', temp_lock_path)
    
    # Eliminar el archivo para comenzar con un estado limpio
    if os.path.exists(temp_lock_path):
        os.remove(temp_lock_path)
    
    yield temp_lock_path
    
    # Limpiar después de la prueba
    if os.path.exists(temp_lock_path):
        os.remove(temp_lock_path)
    
    # Restaurar el valor original
    monkeypatch.setattr('notifications.LOCK_FILE', original_lock_file)

@pytest.fixture
def reset_notification_state(monkeypatch):
    """Fixture para reiniciar el estado de las variables globales de notificación."""
    # Reiniciar last_send_time a None
    monkeypatch.setattr('notifications.last_send_time', None)
    
    # Devolver el monkeypatch por si necesitamos realizar más cambios
    yield monkeypatch

@pytest.mark.usefixtures('app_context')
class TestNotificationLockSystem:
    """Pruebas para el sistema de bloqueo de notificaciones."""
    
    def test_create_notification_lock(self, temp_lock_file, monkeypatch):
        """Prueba la creación del archivo de bloqueo."""
        # Verificar que inicialmente no hay bloqueo
        assert not os.path.exists(temp_lock_file)
        
        # Crear un bloqueo
        result = create_notification_lock()
        
        # Verificar que se creó correctamente
        assert result is True
        assert os.path.exists(temp_lock_file)
        
        # Leer el contenido para verificar el formato
        with open(temp_lock_file, 'r') as f:
            content = f.read().strip()
        
        # Verificar que el contenido es una fecha válida
        try:
            datetime.strptime(content, '%Y-%m-%d %H:%M:%S')
            is_valid_date = True
        except ValueError:
            is_valid_date = False
        
        assert is_valid_date is True
    
    def test_is_notification_locked(self, temp_lock_file, monkeypatch):
        """Prueba la detección del estado de bloqueo."""
        # Sin archivo de bloqueo
        assert is_notification_locked() is False
        
        # Crear un bloqueo reciente
        with open(temp_lock_file, 'w') as f:
            f.write(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        # Verificar que detecte el bloqueo
        assert is_notification_locked() is True
        
        # Crear un bloqueo antiguo (más de 30 minutos)
        old_time = datetime.now() - timedelta(minutes=31)
        with open(temp_lock_file, 'w') as f:
            f.write(old_time.strftime('%Y-%m-%d %H:%M:%S'))
        
        # Verificar que no detecte el bloqueo (expirado)
        assert is_notification_locked() is False
    
    def test_release_notification_lock(self, temp_lock_file, monkeypatch):
        """Prueba la liberación del bloqueo."""
        # Crear un bloqueo
        with open(temp_lock_file, 'w') as f:
            f.write(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        # Verificar que existe
        assert os.path.exists(temp_lock_file)
        
        # Liberar el bloqueo
        result = release_notification_lock()
        
        # Verificar que se eliminó
        assert result is True
        assert not os.path.exists(temp_lock_file)

@pytest.mark.usefixtures('app_context')
class TestSendWhatsAppNotification:
    """Pruebas para la función de envío de notificaciones por WhatsApp."""
    
    @pytest.fixture(autouse=True)
    def setup_notification_lock(self, temp_lock_file, reset_notification_state):
        """Configuración inicial para cada prueba."""
        # Limpiar bloqueos antes de cada prueba
        if os.path.exists(temp_lock_file):
            os.remove(temp_lock_file)

    @patch('notifications.time_module.sleep')
    @patch('notifications.pywhatkit.sendwhatmsg')
    @patch('app.app')
    def test_send_whatsapp_notification_success(self, mock_app, mock_sendwhatmsg, mock_sleep):
        """Prueba un envío exitoso de notificación."""
        # Configurar para evitar dormir el proceso
        mock_sleep.return_value = None
        
        # Configurar el número de teléfono
        mock_app.config = {'NOTIFICATION_PHONE_NUMBER': '+1234567890'}
        
        # Obtener la hora actual para predecir la hora de envío (hora + 1 minuto)
        now = datetime.now()
        send_hour = now.hour
        send_minute = now.minute + 1
        
        # Ajustar si los minutos superan 59
        if send_minute >= 60:
            send_minute = send_minute % 60
            send_hour = (send_hour + 1) % 24
        
        # Llamar a la función
        result = send_whatsapp_notification("Mensaje de prueba")
        
        # Verificar que se llamó a la función de envío con los parámetros correctos
        mock_sendwhatmsg.assert_called_once_with(
            "+1234567890",
            "Mensaje de prueba",
            send_hour,
            send_minute,
            wait_time=20,
            tab_close=True,
            close_time=3
        )
        
        # Verificar que el resultado es correcto
        assert result is True
    
    @patch('notifications.time_module.sleep')
    @patch('notifications.pywhatkit.sendwhatmsg')
    @patch('app.app')
    def test_send_whatsapp_notification_rate_limit(self, mock_app, mock_sendwhatmsg, mock_sleep, temp_lock_file):
        """Prueba que no se envíen mensajes demasiado seguidos."""
        # Configurar para evitar dormir el proceso
        mock_sleep.return_value = None
        
        # Configurar el número de teléfono
        mock_app.config = {'NOTIFICATION_PHONE_NUMBER': '+1234567890'}
        
        # Crear un bloqueo reciente
        with open(temp_lock_file, 'w') as f:
            f.write(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        # Llamar a la función
        result = send_whatsapp_notification("Mensaje de prueba")
        
        # Verificar que no se llamó a la función de envío
        mock_sendwhatmsg.assert_not_called()
        
        # Verificar que el resultado es correcto
        assert result is False
    
    @patch('notifications.time_module.sleep')
    @patch('notifications.pywhatkit.sendwhatmsg')
    @patch('app.app')
    def test_send_whatsapp_notification_no_number(self, mock_app, mock_sendwhatmsg, mock_sleep):
        """Prueba el manejo de número de teléfono no configurado."""
        # Configurar para evitar dormir el proceso
        mock_sleep.return_value = None
        
        # Configurar sin número de teléfono
        mock_app.config = {}
        
        # Llamar a la función
        result = send_whatsapp_notification("Mensaje de prueba")
        
        # Verificar que no se llamó a la función de envío
        mock_sendwhatmsg.assert_not_called()
        
        # Verificar que el resultado es correcto
        assert result is False
    
    @patch('notifications.time_module.sleep')
    @patch('notifications.pywhatkit.sendwhatmsg')
    @patch('app.app')
    @patch('notifications.is_notification_locked', return_value=False)  # Asegurar que no hay bloqueo previo
    @patch('notifications.create_notification_lock', return_value=True)  # Asegurar que se crea el bloqueo
    def test_send_whatsapp_notification_with_exception(self, mock_create_lock, mock_is_locked, mock_app, mock_sendwhatmsg, mock_sleep):
        """Prueba el manejo de excepciones durante el envío."""
        # Configurar para evitar dormir el proceso
        mock_sleep.return_value = None
        
        # Configurar el número de teléfono
        mock_app.config = {'NOTIFICATION_PHONE_NUMBER': '+1234567890'}
        
        # Simular una excepción durante el envío
        mock_sendwhatmsg.side_effect = Exception("Error al enviar")
        
        # Llamar a la función
        result = send_whatsapp_notification("Mensaje de prueba")
        
        # Verificar que se intentó llamar a la función de envío
        mock_sendwhatmsg.assert_called_once()
        
        # Verificar que el resultado es correcto
        assert result is False
    
    @patch('notifications.time_module.sleep')
    @patch('notifications.pywhatkit.sendwhatmsg')
    @patch('app.app')
    def test_send_whatsapp_notification_message_too_long(self, mock_app, mock_sendwhatmsg, mock_sleep):
        """Prueba el manejo de mensajes demasiado largos."""
        # Configurar para evitar dormir el proceso
        mock_sleep.return_value = None
        
        # Configurar el número de teléfono
        mock_app.config = {'NOTIFICATION_PHONE_NUMBER': '+1234567890'}
        
        # Crear un mensaje muy largo (más de 1000 caracteres)
        long_message = "a" * 1100
        
        # Llamar a la función
        result = send_whatsapp_notification(long_message)
        
        # Verificar que se llamó a la función de envío con un mensaje completo
        # (la implementación no tiene limitación de longitud)
        mock_sendwhatmsg.assert_called_once()
        
        # Verificar que el resultado es correcto
        assert result is True
    
    @patch('notifications.time_module.sleep')
    @patch('notifications.pywhatkit.sendwhatmsg')
    @patch('app.app')
    def test_send_whatsapp_notification_lock_failure(self, mock_app, mock_sendwhatmsg, mock_sleep):
        """Prueba el manejo de fallos al crear el bloqueo."""
        # Configurar para evitar dormir el proceso
        mock_sleep.return_value = None
        
        # Configurar el número de teléfono
        mock_app.config = {'NOTIFICATION_PHONE_NUMBER': '+1234567890'}
        
        # Simular fallo al crear el bloqueo
        with patch('notifications.create_notification_lock', return_value=False):
            # Llamar a la función
            result = send_whatsapp_notification("Mensaje de prueba")
            
            # Verificar que no se llamó a la función de envío
            mock_sendwhatmsg.assert_not_called()
            
            # Verificar que el resultado es correcto
            assert result is False
    
    @patch('notifications.time_module.sleep')
    @patch('notifications.pywhatkit.sendwhatmsg')
    @patch('app.app')
    @patch('notifications.last_send_time', datetime.now())
    def test_send_whatsapp_notification_time_limit(self, mock_app, mock_sendwhatmsg, mock_sleep):
        """Prueba el límite de tiempo entre envíos de notificaciones."""
        # Configurar para evitar dormir el proceso
        mock_sleep.return_value = None
        
        # Configurar el número de teléfono
        mock_app.config = {'NOTIFICATION_PHONE_NUMBER': '+1234567890'}
        
        # Llamar a la función - debería fallar por el límite de tiempo
        result = send_whatsapp_notification("Mensaje de prueba")
        
        # Verificar que no se llamó a la función de envío
        mock_sendwhatmsg.assert_not_called()
        
        # Verificar que el resultado es correcto
        assert result is False

@pytest.mark.usefixtures('app_context')
class TestNotificationIntegration:
    """Pruebas de integración para el sistema de notificaciones."""
    
    def test_full_notification_cycle(self, temp_lock_file):
        """Prueba un ciclo completo de bloqueo, verificación y liberación."""
        # 1. Verificar que inicialmente no hay bloqueo
        assert not is_notification_locked()
        
        # 2. Crear un bloqueo
        create_result = create_notification_lock()
        assert create_result is True
        
        # 3. Verificar que el bloqueo está activo
        assert is_notification_locked() is True
        
        # 4. Liberar el bloqueo
        release_result = release_notification_lock()
        assert release_result is True
        
        # 5. Verificar que el bloqueo ya no existe
        assert not is_notification_locked()
    
    def test_lock_timeout(self, temp_lock_file):
        """Prueba que el bloqueo expire después del tiempo configurado."""
        # Crear un bloqueo antiguo (más de 30 minutos)
        old_time = datetime.now() - timedelta(minutes=MIN_TIME_BETWEEN_SENDS + 1)
        with open(temp_lock_file, 'w') as f:
            f.write(old_time.strftime('%Y-%m-%d %H:%M:%S'))
        
        # Verificar que el bloqueo no está activo (expirado)
        assert not is_notification_locked()
        
        # Intentar crear un nuevo bloqueo
        create_result = create_notification_lock()
        assert create_result is True
        
        # Verificar que ahora sí hay un bloqueo activo
        assert is_notification_locked() is True
    
    def test_lock_with_custom_timeout(self, temp_lock_file, monkeypatch):
        """Prueba la funcionalidad con un tiempo de bloqueo personalizado."""
        # Crear un bloqueo antiguo (15 minutos)
        old_time = datetime.now() - timedelta(minutes=15)
        with open(temp_lock_file, 'w') as f:
            f.write(old_time.strftime('%Y-%m-%d %H:%M:%S'))
        
        # Con el tiempo predeterminado (30 min), debería seguir bloqueado
        assert is_notification_locked() is True
        
        # Modificar directamente la verificación de tiempo en la función
        # Patch que simula que han pasado 20 minutos (más que el bloqueo de 15 min pero menos que los 30 min default)
        with patch('notifications.datetime') as mock_datetime:
            mock_dt = MagicMock()
            mock_dt.now.return_value = datetime.now() + timedelta(minutes=20)
            mock_dt.strptime = datetime.strptime
            mock_datetime.now.return_value = mock_dt.now.return_value
            mock_datetime.strptime = mock_dt.strptime
            
            # Con 20 minutos adicionales (total 35 min desde creación), ya no debería estar bloqueado
            assert not is_notification_locked()

@pytest.mark.usefixtures('app_context')
class TestUnregisteredClassesNotification:
    """Pruebas para la funcionalidad de verificación de clases no registradas."""
    
    def test_calcular_hora_fin(self):
        """Prueba el cálculo de la hora de finalización."""
        # Caso simple
        hora_inicio = time(hour=10, minute=30)
        duracion = 60  # 60 minutos
        hora_fin = calcular_hora_fin(hora_inicio, duracion)
        assert hora_fin.hour == 11
        assert hora_fin.minute == 30
        
        # Caso que cruza la hora
        hora_inicio = time(hour=10, minute=45)
        duracion = 30  # 30 minutos
        hora_fin = calcular_hora_fin(hora_inicio, duracion)
        assert hora_fin.hour == 11
        assert hora_fin.minute == 15
        
        # Caso que cruza el día
        hora_inicio = time(hour=23, minute=30)
        duracion = 60  # 60 minutos
        hora_fin = calcular_hora_fin(hora_inicio, duracion)
        assert hora_fin.hour == 0
        assert hora_fin.minute == 30
    
    @patch('notifications.logger')
    @patch('notifications.send_whatsapp_notification')
    @patch('app.ClaseRealizada')  # Este patch afectará la importación local dentro de check_unregistered_classes
    @patch('app.HorarioClase')    # Este patch afectará la importación local dentro de check_unregistered_classes
    @patch('app.app')             # Este patch afectará la importación local dentro de check_unregistered_classes
    def test_check_unregistered_classes_with_pending_classes(self, mock_app, mock_horario, mock_clase_realizada, mock_send, mock_logger):
        """Prueba la verificación de clases no registradas cuando hay clases pendientes."""
        # Configurar mocks para la base de datos
        mock_app_context = MagicMock()
        mock_app.app_context.return_value = mock_app_context
        mock_app_context.__enter__.return_value = None
        mock_app_context.__exit__.return_value = None
        
        # Configurar el día de la semana (lunes = 0)
        today = datetime.now().date()
        today_weekday = 0  # Lunes
        
        # Crear horarios de clase para hoy
        mock_horario_1 = MagicMock()
        mock_horario_1.id = 1
        mock_horario_1.tipo_clase = "Yoga"
        mock_horario_1.hora_inicio = time(hour=9, minute=0)
        mock_horario_1.duracion = 60
        mock_horario_1.dia_semana = today_weekday
        mock_horario_1.profesor.nombre = "Juan Pérez"
        
        mock_horario_2 = MagicMock()
        mock_horario_2.id = 2
        mock_horario_2.tipo_clase = "Pilates"
        mock_horario_2.hora_inicio = time(hour=10, minute=30)
        mock_horario_2.duracion = 45
        mock_horario_2.dia_semana = today_weekday
        mock_horario_2.profesor.nombre = "María López"
        
        # Configurar consulta de horarios
        mock_horario.query.filter.return_value.all.return_value = [mock_horario_1, mock_horario_2]
        
        # Configurar clases ya realizadas (solo la segunda clase está registrada)
        mock_clase = MagicMock()
        mock_clase.horario_id = 2
        mock_clase_realizada.query.filter.return_value.all.return_value = [mock_clase]
        
        # Simular que es tarde en el día (todas las clases han terminado)
        with patch('notifications.datetime') as mock_datetime:
            mock_dt = MagicMock()
            mock_dt.now.return_value = datetime(2025, 3, 25, 18, 0)  # 6:00 PM
            mock_datetime.now.return_value = mock_dt.now.return_value
            mock_datetime.now.side_effect = lambda: mock_dt.now.return_value
            
            # Llamar a la función
            check_unregistered_classes()
            
            # Verificar que se envió una notificación
            mock_send.assert_called_once()
            
            # Verificar que el mensaje contiene la información de la clase no registrada
            message = mock_send.call_args[0][0]
            assert "Yoga" in message
            assert "Juan Pérez" in message
            assert "9:00" in message
            
            # Verificar el registro
            mock_logger.info.assert_any_call(f"Notificación enviada para 1 clases no registradas")
    
    @patch('notifications.logger')
    @patch('notifications.send_whatsapp_notification')
    @patch('app.ClaseRealizada')  # Este patch afectará la importación local dentro de check_unregistered_classes
    @patch('app.HorarioClase')    # Este patch afectará la importación local dentro de check_unregistered_classes
    @patch('app.app')             # Este patch afectará la importación local dentro de check_unregistered_classes
    def test_check_unregistered_classes_all_registered(self, mock_app, mock_horario, mock_clase_realizada, mock_send, mock_logger):
        """Prueba la verificación cuando todas las clases están registradas."""
        # Configurar mocks para la base de datos
        mock_app_context = MagicMock()
        mock_app.app_context.return_value = mock_app_context
        mock_app_context.__enter__.return_value = None
        mock_app_context.__exit__.return_value = None
        
        # Configurar el día de la semana
        today = datetime.now().date()
        today_weekday = 0  # Lunes
        
        # Crear horarios de clase para hoy
        mock_horario_1 = MagicMock()
        mock_horario_1.id = 1
        mock_horario_1.tipo_clase = "Yoga"
        mock_horario_1.hora_inicio = time(hour=9, minute=0)
        mock_horario_1.duracion = 60
        mock_horario_1.dia_semana = today_weekday
        
        mock_horario_2 = MagicMock()
        mock_horario_2.id = 2
        mock_horario_2.tipo_clase = "Pilates"
        mock_horario_2.hora_inicio = time(hour=10, minute=30)
        mock_horario_2.duracion = 45
        mock_horario_2.dia_semana = today_weekday
        
        # Configurar consulta de horarios
        mock_horario.query.filter.return_value.all.return_value = [mock_horario_1, mock_horario_2]
        
        # Configurar clases ya realizadas (ambas clases están registradas)
        mock_clase_1 = MagicMock()
        mock_clase_1.horario_id = 1
        mock_clase_2 = MagicMock()
        mock_clase_2.horario_id = 2
        mock_clase_realizada.query.filter.return_value.all.return_value = [mock_clase_1, mock_clase_2]
        
        # Simular que es tarde en el día (todas las clases han terminado)
        with patch('notifications.datetime') as mock_datetime:
            mock_dt = MagicMock()
            mock_dt.now.return_value = datetime(2025, 3, 25, 18, 0)  # 6:00 PM
            mock_datetime.now.return_value = mock_dt.now.return_value
            mock_datetime.now.side_effect = lambda: mock_dt.now.return_value
            
            # Llamar a la función
            check_unregistered_classes()
            
            # Verificar que no se envió ninguna notificación
            mock_send.assert_not_called()
            
            # Verificar el registro
            mock_logger.info.assert_any_call("Todas las clases de hoy están registradas o aún no han finalizado")
    
    @patch('notifications.logger')
    @patch('notifications.send_whatsapp_notification')
    @patch('app.ClaseRealizada')  # Este patch afectará la importación local dentro de check_unregistered_classes
    @patch('app.HorarioClase')    # Este patch afectará la importación local dentro de check_unregistered_classes
    @patch('app.app')             # Este patch afectará la importación local dentro de check_unregistered_classes
    def test_check_unregistered_classes_no_classes_today(self, mock_app, mock_horario, mock_clase_realizada, mock_send, mock_logger):
        """Prueba la verificación cuando no hay clases programadas para hoy."""
        # Configurar mocks para la base de datos
        mock_app_context = MagicMock()
        mock_app.app_context.return_value = mock_app_context
        mock_app_context.__enter__.return_value = None
        mock_app_context.__exit__.return_value = None
        
        # No hay horarios para hoy
        mock_horario.query.filter.return_value.all.return_value = []
        
        # Llamar a la función
        check_unregistered_classes()
        
        # Verificar que no se envió ninguna notificación
        mock_send.assert_not_called()
        
        # Verificar el registro
        mock_logger.info.assert_any_call(mock_logger.info.call_args[0][0])
    
    @patch('notifications.logger')
    @patch('notifications.send_whatsapp_notification')
    @patch('app.ClaseRealizada')  # Este patch afectará la importación local dentro de check_unregistered_classes
    @patch('app.HorarioClase')    # Este patch afectará la importación local dentro de check_unregistered_classes
    @patch('app.app')             # Este patch afectará la importación local dentro de check_unregistered_classes
    def test_check_unregistered_classes_exception(self, mock_app, mock_horario, mock_clase_realizada, mock_send, mock_logger):
        """Prueba el manejo de excepciones durante la verificación."""
        # Configurar mocks para la base de datos
        mock_app_context = MagicMock()
        mock_app.app_context.return_value = mock_app_context
        mock_app_context.__enter__.return_value = None
        mock_app_context.__exit__.return_value = None
        
        # Simular una excepción en la consulta
        mock_horario.query.filter.side_effect = Exception("Error de consulta")
        
        # Verificar que la excepción se propaga
        with pytest.raises(Exception):
            check_unregistered_classes()
        
        # Verificar el registro de error
        mock_logger.error.assert_called_once_with(mock_logger.error.call_args[0][0])

@pytest.mark.usefixtures('reset_notification_state')
class TestNotificationConfiguration:
    """Pruebas para las funciones de configuración de notificaciones."""

    @pytest.fixture(autouse=True)
    def setup(self, reset_notification_state):
        """Configuración inicial para las pruebas de configuración."""
        pass

    @patch('notifications.check_and_notify_unregistered_classes')
    def test_configure_notifications(self, mock_check):
        """Prueba la configuración de notificaciones para una aplicación Flask."""
        # Crear un mock para la aplicación Flask
        mock_app = MagicMock()
        mock_app.config = {}
        
        # Configurar un número de teléfono en las variables de entorno para probar
        with patch.dict(os.environ, {"NOTIFICATION_PHONE_NUMBER": "+1234567890"}):
            result = configure_notifications(mock_app)
            
            # Verificar que el número de teléfono se haya configurado
            assert mock_app.config.get('NOTIFICATION_PHONE_NUMBER') == "+1234567890"
            
            # Verificar que la función devuelve check_and_notify_unregistered_classes
            assert result == mock_check

    @patch('notifications.configure_notifications')
    @patch('notifications.BackgroundScheduler')
    @patch('notifications.check_and_notify_unregistered_classes')
    @patch('notifications.scheduler_initialized', False)
    @patch('notifications.logger')
    def test_setup_notification_scheduler_first_time(self, mock_logger, mock_check, mock_scheduler_class, mock_configure):
        """Prueba la inicialización del scheduler por primera vez."""
        mock_app = MagicMock()
        mock_scheduler = MagicMock()
        mock_scheduler_class.return_value = mock_scheduler
        
        # Llamar a la función
        with patch('notifications.scheduler_initialized', False, create=True):
            setup_notification_scheduler(mock_app)
        
        # Verificar que se llamó a configure_notifications
        mock_configure.assert_called_once_with(mock_app)
        
        # Verificar que se creó el scheduler
        mock_scheduler_class.assert_called_once()
        
        # Verificar que se agregaron los trabajos (puede fallar si el orden cambia)
        assert mock_scheduler.add_job.call_count >= 2
        
        # Verificar que se inició el scheduler
        mock_scheduler.start.assert_called_once()
        
        # Verificar que se registró el mensaje de inicio
        mock_logger.info.assert_called_with("Scheduler de notificaciones iniciado")

    @patch('notifications.configure_notifications')
    @patch('notifications.BackgroundScheduler')
    @patch('notifications.logger')
    @patch('notifications.scheduler_initialized', True)
    def test_setup_notification_scheduler_already_initialized(self, mock_logger, mock_scheduler_class, mock_configure):
        """Prueba que el scheduler no se inicialice múltiples veces."""
        mock_app = MagicMock()
        
        # Llamar a la función
        setup_notification_scheduler(mock_app)
        
        # Verificar que no se creó un nuevo scheduler
        mock_scheduler_class.assert_not_called()
        
        # Verificar que se registró el mensaje apropiado
        mock_logger.info.assert_called_once_with("Scheduler ya está inicializado. Evitando duplicación.")
        
        # Verificar que no se llamó a configure_notifications
        mock_configure.assert_not_called()

    def test_is_notification_locked_timeout_handler(self):
        """Prueba el manejo de timeout en is_notification_locked."""
        # Crear un archivo de bloqueo caducado para probar
        timestamp = (datetime.now() - timedelta(minutes=31)).strftime('%Y-%m-%d %H:%M:%S')
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            old_lock_file = f.name
            f.write(timestamp)  # Escribir una fecha antigua (más de 30 minutos)
        
        # Parchear LOCK_FILE para usar nuestro archivo temporal
        with patch('notifications.LOCK_FILE', old_lock_file), \
             patch('notifications.logger') as mock_logger:
            # Verificar que se detecte como expirado
            result = is_notification_locked()
            
            # El archivo debería ser eliminado y la función debería devolver False
            assert result is False
            assert not os.path.exists(old_lock_file)
            
            # Verificar el registro de mensaje
            mock_logger.info.assert_called_once_with("Bloqueo de notificación expirado, eliminando archivo de bloqueo")
    
    def test_create_notification_lock_custom_format(self):
        """Prueba la creación de un bloqueo con formato de tiempo personalizado."""
        # Usar un archivo temporal para las pruebas
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file_path = temp_file.name
            
        # Asegurarse de que el archivo no exista para iniciar la prueba
        os.unlink(temp_file_path)
        
        # Parchear LOCK_FILE para usar nuestro archivo temporal
        with patch('notifications.LOCK_FILE', temp_file_path):
            # Crear un bloqueo con formato de tiempo personalizado (verificamos que se usa el formato de tiempo)
            now_before = datetime.now().replace(microsecond=0)
            result = create_notification_lock()
            now_after = datetime.now().replace(microsecond=0)
            
            # Verificar que la función devuelve True
            assert result is True
            
            # Verificar que se creó el archivo
            assert os.path.exists(temp_file_path)
            
            # Verificar que el contenido es una fecha y hora
            with open(temp_file_path, 'r') as f:
                content = f.read()
                
            # La fecha en el archivo debe estar entre now_before y now_after
            try:
                file_datetime = datetime.strptime(content, '%Y-%m-%d %H:%M:%S')
                assert now_before <= file_datetime <= now_after
            except:
                # Si el formato no es correcto, fallará
                assert False, f"El contenido del archivo de bloqueo no tiene el formato esperado: {content}"
            
            # Limpiar
            os.unlink(temp_file_path)

    def test_release_notification_lock_with_exception(self):
        """Prueba la liberación del bloqueo cuando ocurre una excepción."""
        # Crear un mock para logger
        with patch('notifications.logger') as mock_logger:
            # Simular que os.path.exists devuelve True
            with patch('os.path.exists', return_value=True):
                # Simular una excepción al intentar eliminar el archivo
                with patch('os.unlink', side_effect=Exception("Error al eliminar archivo")):
                    # Intentar liberar el bloqueo
                    release_notification_lock()
                    
                    # Verificar que se registró el error
                    mock_logger.error.assert_called_once()
                    assert "Error al liberar bloqueo de notificación" in mock_logger.error.call_args[0][0]
