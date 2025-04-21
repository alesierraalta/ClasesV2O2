# Instrucciones para Actualizar el Sistema de Notificaciones

Para permitir la configuración manual de las horas de notificación, necesitas modificar tres archivos en tu proyecto:

## 1. Actualización del archivo `notifications.py`

Busca el archivo `notifications.py` y modifica/añade el siguiente código:

```python
# Al inicio del archivo, añade estas constantes:
# Horas de notificación predeterminadas
DEFAULT_NOTIFICATION_HOUR_1 = "13:30"
DEFAULT_NOTIFICATION_HOUR_2 = "20:30"

# Modificar la variable scheduler para que sea global
scheduler_initialized = False
scheduler = None  # Añadir esta variable global
```

También necesitas añadir estas dos funciones nuevas:

```python
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
            
            logger.info(f"Horarios de notificación actualizados: {hour1} y {hour2}")
            return True
        except Exception as e:
            logger.error(f"Error al configurar nuevos horarios de notificación: {str(e)}")
            return False
    
    return False
```

Y necesitas reemplazar la función `setup_notification_scheduler` por esta versión:

```python
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
        
        # Iniciar el scheduler
        scheduler.start()
        scheduler_initialized = True
        logger.info(f"Scheduler de notificaciones iniciado con horarios: {hour1} y {hour2}")
    except Exception as e:
        logger.error(f"Error al configurar horarios de notificación: {str(e)}")
        # Intentar configurar con valores predeterminados
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
        
        scheduler.start()
        scheduler_initialized = True
        logger.info("Scheduler de notificaciones iniciado con horarios predeterminados: 13:30 y 20:30")
```

## 2. Actualización de la función en `app.py`

Reemplaza la función `configuracion_notificaciones` en tu archivo `app.py` con esta versión:

```python
@app.route('/configuracion/notificaciones', methods=['GET', 'POST'])
def configuracion_notificaciones():
    """Configuración de notificaciones y alertas"""
    from notifications import check_and_notify_unregistered_classes, send_whatsapp_notification, is_notification_locked
    from notifications import update_notification_schedule, DEFAULT_NOTIFICATION_HOUR_1, DEFAULT_NOTIFICATION_HOUR_2

    if request.method == 'POST':
        # Guardar la configuración del número de teléfono
        telefono = request.form.get('telefono_notificaciones', '').strip()
        hora_notificacion_1 = request.form.get('hora_notificacion_1', DEFAULT_NOTIFICATION_HOUR_1).strip()
        hora_notificacion_2 = request.form.get('hora_notificacion_2', DEFAULT_NOTIFICATION_HOUR_2).strip()
        
        # Validar que el número tenga el formato correcto
        if not telefono:
            flash('Ingrese un número de teléfono válido', 'danger')
        elif not telefono.startswith('+'):
            flash('El número debe incluir el código del país con el prefijo "+" (por ejemplo, +34612345678)', 'warning')
            telefono = '+' + telefono  # Intentar arreglarlo añadiendo el +
        
        # Validar el formato de las horas (HH:MM)
        import re
        hora_formato_valido = re.compile(r'^([01]?[0-9]|2[0-3]):([0-5][0-9])$')
        
        if not hora_formato_valido.match(hora_notificacion_1):
            flash('El formato de la primera hora de notificación debe ser HH:MM (por ejemplo, 13:30)', 'warning')
            hora_notificacion_1 = DEFAULT_NOTIFICATION_HOUR_1
            
        if not hora_formato_valido.match(hora_notificacion_2):
            flash('El formato de la segunda hora de notificación debe ser HH:MM (por ejemplo, 20:30)', 'warning')
            hora_notificacion_2 = DEFAULT_NOTIFICATION_HOUR_2
        
        if telefono:
            # Guardar en el archivo de configuración como variable de entorno permanente
            try:
                # Actualizar run.bat con el nuevo número y horas
                run_bat_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'run.bat')
                if os.path.exists(run_bat_path):
                    with open(run_bat_path, 'r', encoding='utf-8') as file:
                        content = file.read()
                    
                    # Reemplazar la línea con el número de teléfono
                    content = content.replace(
                        'set NOTIFICATION_PHONE_NUMBER=+numero_a_notificar_aqui', 
                        f'set NOTIFICATION_PHONE_NUMBER={telefono}'
                    )
                    
                    # Si ya hay un número configurado, reemplazarlo también
                    import re
                    pattern = r'set NOTIFICATION_PHONE_NUMBER=\+[0-9]+'
                    content = re.sub(pattern, f'set NOTIFICATION_PHONE_NUMBER={telefono}', content)
                    
                    # Agregar o actualizar las horas de notificación
                    if 'set NOTIFICATION_HOUR_1=' in content:
                        content = re.sub(r'set NOTIFICATION_HOUR_1=[0-9:]+', f'set NOTIFICATION_HOUR_1={hora_notificacion_1}', content)
                    else:
                        content += f'\nset NOTIFICATION_HOUR_1={hora_notificacion_1}'
                        
                    if 'set NOTIFICATION_HOUR_2=' in content:
                        content = re.sub(r'set NOTIFICATION_HOUR_2=[0-9:]+', f'set NOTIFICATION_HOUR_2={hora_notificacion_2}', content)
                    else:
                        content += f'\nset NOTIFICATION_HOUR_2={hora_notificacion_2}'
                    
                    with open(run_bat_path, 'w', encoding='utf-8') as file:
                        file.write(content)
            except Exception as e:
                app.logger.error(f"Error al actualizar run.bat: {str(e)}")
            
            # Guardar en las variables actuales
            os.environ['NOTIFICATION_PHONE_NUMBER'] = telefono
            os.environ['NOTIFICATION_HOUR_1'] = hora_notificacion_1
            os.environ['NOTIFICATION_HOUR_2'] = hora_notificacion_2
            
            app.config['NOTIFICATION_PHONE_NUMBER'] = telefono
            app.config['NOTIFICATION_HOUR_1'] = hora_notificacion_1
            app.config['NOTIFICATION_HOUR_2'] = hora_notificacion_2
            
            # Actualizar el scheduler con las nuevas horas
            update_notification_schedule(app)
            
            flash(f'Configuración de notificaciones actualizada. Número configurado: {telefono}', 'success')
            flash(f'Horarios de notificación configurados: {hora_notificacion_1} y {hora_notificacion_2}', 'success')
            
            # Probar la notificación si se solicitó
            if 'enviar_prueba' in request.form:
                # Verificar si ya hay un envío en progreso
                if is_notification_locked():
                    flash('Hay un envío de notificación en progreso. Por favor, espere unos minutos antes de intentar nuevamente.', 'warning')
                else:
                    try:
                        # Enviar un mensaje de prueba directamente
                        mensaje_prueba = f" Mensaje de prueba desde AppClases\n\nEste es un mensaje de prueba para verificar la configuración del sistema de notificaciones. La hora actual es: {datetime.now().strftime('%H:%M:%S')}"
                        
                        # Ejecutar el envío en un proceso independiente para evitar bloqueos
                        sent = send_whatsapp_notification(mensaje_prueba, telefono)
                        if sent:
                            flash('Notificación de prueba enviada. Verifica tu WhatsApp.', 'success')
                        else:
                            flash('No se pudo enviar la notificación de prueba. Revisa los logs para más detalles.', 'warning')
                    except Exception as e:
                        flash(f'Error al enviar notificación de prueba: {str(e)}', 'danger')
                    
        return redirect(url_for('configuracion_notificaciones'))
        
    # Obtener la configuración actual
    current_phone = app.config.get('NOTIFICATION_PHONE_NUMBER', os.environ.get('NOTIFICATION_PHONE_NUMBER', ''))
    current_hour_1 = app.config.get('NOTIFICATION_HOUR_1', os.environ.get('NOTIFICATION_HOUR_1', DEFAULT_NOTIFICATION_HOUR_1))
    current_hour_2 = app.config.get('NOTIFICATION_HOUR_2', os.environ.get('NOTIFICATION_HOUR_2', DEFAULT_NOTIFICATION_HOUR_2))
    
    return render_template('configuracion/notificaciones.html', 
                          telefono_actual=current_phone,
                          hora_notificacion_1=current_hour_1,
                          hora_notificacion_2=current_hour_2)
```

## 3. Actualización de la plantilla `templates/configuracion/notificaciones.html`

Reemplaza el contenido de la plantilla con el siguiente código:

```html
{% extends 'base.html' %}

{% block title %}Configuración de Notificaciones{% endblock %}

{% block content %}
<div class="container mt-4">
    <div class="row">
        <div class="col-12">
            <h1 class="mb-4">Configuración de Notificaciones</h1>
            
            <div class="card shadow mb-4">
                <div class="card-header py-3">
                    <h6 class="m-0 font-weight-bold text-primary">Notificaciones de WhatsApp para Clases No Registradas</h6>
                </div>
                <div class="card-body">
                    <p>
                        Configure el número de teléfono al que se enviarán notificaciones de WhatsApp 
                        cuando haya clases que no se han registrado. Las notificaciones se enviarán 
                        de acuerdo a los horarios que usted configure:
                    </p>
                </div>
            </div>
            
            <div class="card mt-4">
                <div class="card-header">
                    <h5>Notificaciones WhatsApp</h5>
                </div>
                <div class="card-body">
                    <form method="POST" action="{{ url_for('configuracion_notificaciones') }}">
                        <div class="form-group mb-3">
                            <label for="telefono_notificaciones">Número de teléfono para notificaciones:</label>
                            <input type="text" class="form-control" id="telefono_notificaciones" name="telefono_notificaciones" placeholder="+56912345678" value="{{ telefono_actual }}">
                            <small class="form-text text-muted">
                                Ingrese el número completo incluyendo el código del país (ej: +56912345678)
                            </small>
                        </div>
                        
                        <div class="row">
                            <div class="col-md-6">
                                <div class="form-group mb-3">
                                    <label for="hora_notificacion_1">Primera notificación diaria:</label>
                                    <input type="time" class="form-control" id="hora_notificacion_1" name="hora_notificacion_1" value="{{ hora_notificacion_1 }}">
                                    <small class="form-text text-muted">
                                        Hora de la primera notificación (formato 24h)
                                    </small>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="form-group mb-3">
                                    <label for="hora_notificacion_2">Segunda notificación diaria:</label>
                                    <input type="time" class="form-control" id="hora_notificacion_2" name="hora_notificacion_2" value="{{ hora_notificacion_2 }}">
                                    <small class="form-text text-muted">
                                        Hora de la segunda notificación (formato 24h)
                                    </small>
                                </div>
                            </div>
                        </div>
                        
                        <button type="submit" class="btn btn-primary">Guardar configuración</button>
                        <button type="submit" name="enviar_prueba" class="btn btn-info">Guardar y enviar notificación de prueba</button>
                    </form>
                    
                    <div class="alert alert-info mt-4">
                        <h5>Requisitos para las notificaciones por WhatsApp</h5>
                        <ul>
                            <li>El sistema envía notificaciones usando PyWhatKit, que requiere una sesión de WhatsApp Web activa</li>
                            <li>El equipo debe tener un navegador web instalado</li>
                            <li>La primera vez que envíe una notificación, deberá escanear el código QR para iniciar sesión en WhatsApp Web</li>
                            <li>No cierre la ventana de WhatsApp Web mientras se procesa el envío</li>
                            <li>Para evitar problemas, el sistema limita los envíos a uno cada 15 minutos</li>
                            <li>Si la aplicación se cierra durante un envío, reinicie la aplicación y use el script <code>verify_notifications.py</code> para limpiar los bloqueos</li>
                        </ul>
                    </div>
                    
                    <div class="alert alert-warning mt-4">
                        <h5>Solución de problemas</h5>
                        <p>Si las notificaciones no funcionan correctamente:</p>
                        <ol>
                            <li>Verifique que el número de teléfono sea correcto e incluya el código del país (ej: +34612345678)</li>
                            <li>Asegúrese de tener una sesión de WhatsApp Web activa</li>
                            <li>Si nota que los mensajes se están enviando repetidamente, detenga la aplicación</li>
                            <li>Ejecute <code>python verify_notifications.py</code> para limpiar cualquier bloqueo</li>
                            <li>Reinicie la aplicación con <code>run.bat</code></li>
                        </ol>
                        <p><strong>Si los mensajes no se envían completamente</strong> (aparecen en la ventana de WhatsApp pero no se presiona Enviar):</p>
                        <ul>
                            <li>Utilice el método alternativo con: <code>python send_whatsapp_manual.py</code></li>
                            <li>Este método utiliza una biblioteca adicional (pyautogui) para simular la pulsación de Enter</li>
                            <li>Durante el envío, no mueva el mouse ni use el teclado</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %} 