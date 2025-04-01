from app import app, HorarioClase, ClaseRealizada
from notifications import check_and_notify_unregistered_classes, update_notification_schedule, logger, send_whatsapp_notification
from datetime import datetime
import logging
import os

# Configurar logging adicional para ver los mensajes en consola
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)
logger.setLevel(logging.DEBUG)

print("Verificando clases no registradas...")

with app.app_context():
    try:
        # Verificar la configuración del scheduler
        print("--- CONFIGURACIÓN ACTUAL ---")
        phone = app.config.get('NOTIFICATION_PHONE_NUMBER', 'No configurado')
        hour1 = app.config.get('NOTIFICATION_HOUR_1', 'No configurado')
        hour2 = app.config.get('NOTIFICATION_HOUR_2', 'No configurado')
        
        print(f"Teléfono: {phone}")
        print(f"Hora notificación 1: {hour1}")
        print(f"Hora notificación 2: {hour2}")
        
        # Solicitar el número de teléfono al usuario
        print("\nNecesita configurar un número de teléfono para recibir notificaciones")
        telefono = input("Ingrese su número de teléfono con código de país (ej: +56912345678): ")
        
        if not telefono:
            print("No se ingresó un número de teléfono. Usando uno de prueba...")
            telefono = "+123456789"  # Número de prueba
        
        # Guardar el número en la configuración
        app.config['NOTIFICATION_PHONE_NUMBER'] = telefono
        os.environ['NOTIFICATION_PHONE_NUMBER'] = telefono
        
        # Configurar horas de notificación si no están configuradas
        if hour1 == 'No configurado':
            app.config['NOTIFICATION_HOUR_1'] = "13:30"
            os.environ['NOTIFICATION_HOUR_1'] = "13:30"
            print("Hora de notificación 1 configurada a 13:30")
        
        if hour2 == 'No configurado':
            app.config['NOTIFICATION_HOUR_2'] = "20:30"
            os.environ['NOTIFICATION_HOUR_2'] = "20:30"
            print("Hora de notificación 2 configurada a 20:30")
        
        # Mostrar la nueva configuración
        print("\n--- NUEVA CONFIGURACIÓN ---")
        print(f"Teléfono: {app.config.get('NOTIFICATION_PHONE_NUMBER')}")
        print(f"Hora notificación 1: {app.config.get('NOTIFICATION_HOUR_1')}")
        print(f"Hora notificación 2: {app.config.get('NOTIFICATION_HOUR_2')}")
        
        # Obtener la fecha actual
        hoy = datetime.now().date()
        dia_semana_hoy = hoy.weekday()  # 0 es lunes, 6 es domingo
        
        print(f"\nFecha actual: {hoy}, día de la semana: {dia_semana_hoy}")
        
        # Obtener todos los horarios programados para hoy
        horarios_hoy = HorarioClase.query.filter(
            HorarioClase.dia_semana == dia_semana_hoy
        ).all()
        
        if not horarios_hoy:
            print(f"No hay clases programadas para hoy (día {dia_semana_hoy})")
        else:
            print(f"Hay {len(horarios_hoy)} clases programadas para hoy:")
            for h in horarios_hoy:
                print(f"  - ID: {h.id}, Tipo: {h.tipo_clase}, Hora: {h.hora_inicio}, Profesor: {h.profesor.nombre if h.profesor else 'Sin profesor'}")
        
        # Verificar qué clases ya han sido registradas hoy
        clases_realizadas_hoy = ClaseRealizada.query.filter(
            ClaseRealizada.fecha == hoy
        ).all()
        
        print(f"Clases ya registradas hoy: {len(clases_realizadas_hoy)}")
        for cr in clases_realizadas_hoy:
            print(f"  - ID: {cr.id}, Horario ID: {cr.horario_id}, Profesor: {cr.profesor.nombre if cr.profesor else 'Sin profesor'}")
        
        # IDs de horarios ya registrados hoy
        ids_registrados = {cr.horario_id for cr in clases_realizadas_hoy}
        
        # Identificar clases no registradas hasta ahora
        hora_actual = datetime.now().time()
        print(f"Hora actual: {hora_actual}")
        
        clases_pendientes = []
        
        for horario in horarios_hoy:
            if horario.id not in ids_registrados:
                print(f"Clase pendiente detectada: ID {horario.id}, Tipo: {horario.tipo_clase}, Hora: {horario.hora_inicio}")
                
                # Calcular la hora de finalización aproximada (hora inicio + duración)
                minutos_totales = horario.hora_inicio.hour * 60 + horario.hora_inicio.minute + horario.duracion
                horas_fin, minutos_fin = divmod(minutos_totales, 60)
                horas_fin = horas_fin % 24  # Manejar casos donde la clase termina después de la medianoche
                print(f"  Hora fin aproximada: {horas_fin:02d}:{minutos_fin:02d}")
                
                # Si la clase ya terminó según la hora de finalización
                if (hora_actual.hour > horas_fin or (hora_actual.hour == horas_fin and hora_actual.minute >= minutos_fin)):
                    print(f"  ALERTA: Esta clase ya terminó y no ha sido registrada!")
                    clases_pendientes.append(horario)
            else:
                print(f"Clase ya registrada: ID {horario.id}")
        
        if clases_pendientes:
            print(f"\nHay {len(clases_pendientes)} clases sin registrar que ya terminaron:")
            
            # Construir mensaje
            mensaje = f"⚠️ ALERTA: {len(clases_pendientes)} clase(s) no registrada(s) hoy ({hoy.strftime('%d/%m/%Y')}):\n\n"
            
            for i, clase in enumerate(clases_pendientes, 1):
                profesor_nombre = getattr(clase.profesor, 'nombre', 'Sin profesor asignado') if hasattr(clase, 'profesor') and clase.profesor else 'Sin profesor asignado'
                mensaje += f"{i}. Clase de {clase.tipo_clase} a las {clase.hora_inicio.strftime('%H:%M')} con {profesor_nombre}\n"
                print(f"  {i}. Clase de {clase.tipo_clase} a las {clase.hora_inicio.strftime('%H:%M')} con {profesor_nombre}")
            
            mensaje += "\nPor favor, registre estas clases lo antes posible."
            
            print("\nMensaje que se enviaría:")
            print(mensaje)
            
            # Preguntar si desea forzar el envío de la notificación
            forzar_envio = input("\n¿Desea forzar el envío de la notificación ahora? (s/n): ")
            if forzar_envio.lower() == 's':
                print("Enviando notificación forzada...")
                sent = send_whatsapp_notification(mensaje, telefono)
                if sent:
                    print(f"Notificación enviada correctamente para {len(clases_pendientes)} clases no registradas")
                else:
                    print("No se pudo enviar la notificación. Revise los logs para más detalles.")
        else:
            print("No hay clases pendientes por registrar que ya hayan terminado.")
            
        # Actualizar la configuración permanente
        print("\n¿Desea guardar esta configuración para la aplicación? (s/n): ")
        guardar_config = input()
        if guardar_config.lower() == 's':
            try:
                # Actualizar run.bat con el nuevo número y horas
                run_bat_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'run.bat')
                if os.path.exists(run_bat_path):
                    with open(run_bat_path, 'r', encoding='utf-8') as file:
                        content = file.read()
                    
                    # Reemplazar la línea con el número de teléfono
                    import re
                    
                    # Para el teléfono
                    if 'set NOTIFICATION_PHONE_NUMBER=' in content:
                        pattern = r'set NOTIFICATION_PHONE_NUMBER=(\+[0-9]+|[^"\n\r]*)'
                        content = re.sub(pattern, f'set NOTIFICATION_PHONE_NUMBER={telefono}', content)
                    else:
                        content += f'\nset NOTIFICATION_PHONE_NUMBER={telefono}'
                    
                    # Para las horas si no estaban configuradas
                    hour1 = app.config.get('NOTIFICATION_HOUR_1')
                    hour2 = app.config.get('NOTIFICATION_HOUR_2')
                    
                    if 'set NOTIFICATION_HOUR_1=' in content:
                        content = re.sub(r'set NOTIFICATION_HOUR_1=[0-9:]+', f'set NOTIFICATION_HOUR_1={hour1}', content)
                    else:
                        content += f'\nset NOTIFICATION_HOUR_1={hour1}'
                        
                    if 'set NOTIFICATION_HOUR_2=' in content:
                        content = re.sub(r'set NOTIFICATION_HOUR_2=[0-9:]+', f'set NOTIFICATION_HOUR_2={hour2}', content)
                    else:
                        content += f'\nset NOTIFICATION_HOUR_2={hour2}'
                    
                    with open(run_bat_path, 'w', encoding='utf-8') as file:
                        file.write(content)
                    
                    print(f"Configuración guardada en run.bat")
                    print("Recuerde reiniciar la aplicación para que los cambios surtan efecto.")
                else:
                    print(f"No se encontró el archivo run.bat en {run_bat_path}")
            except Exception as e:
                print(f"Error al guardar la configuración: {str(e)}")
            
    except Exception as e:
        print(f"Error al verificar clases no registradas: {str(e)}")
        import traceback
        traceback.print_exc()

print("\nVerificación completa.") 