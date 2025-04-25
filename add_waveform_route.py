from app import app
from flask import render_template
from audio_utils import audio_bp

# Register the blueprint
app.register_blueprint(audio_bp)

@app.route('/asistencia/waveform')
def control_asistencia_waveform():
    """Same as control_asistencia but with waveform visualization"""
    # Copy the logic from your existing control_asistencia route
    from app import datetime, HorarioClase, ClaseRealizada, os
    
    # Mostrar las clases programadas para hoy que no tienen registro de asistencia
    hoy = datetime.now().date()
    dia_semana = hoy.weekday()
    
    # Horarios programados para hoy
    horarios_hoy = HorarioClase.query.filter_by(dia_semana=dia_semana).order_by(HorarioClase.hora_inicio).all()
    
    # Clases ya registradas hoy
    clases_realizadas_hoy = ClaseRealizada.query.filter_by(fecha=hoy).all()
    
    # IDs de horarios que ya tienen clases realizadas registradas hoy
    horarios_ya_registrados = [c.horario_id for c in clases_realizadas_hoy]
    
    # Horarios pendientes (que no tienen registro aún)
    horarios_pendientes = [h for h in horarios_hoy if h.id not in horarios_ya_registrados]
    
    # Verificar si hay archivos de audio temporales para clases pendientes
    temp_audio_files = {}
    for horario in horarios_pendientes:
        for ext in ['mp3', 'wav', 'ogg']:
            audio_path = os.path.join(app.config['UPLOAD_FOLDER'], f'temp_horario_{horario.id}.{ext}')
            if os.path.exists(audio_path):
                temp_audio_files[horario.id] = True
                break
    
    return render_template('asistencia/control_with_waveform.html', 
                          horarios_pendientes=horarios_pendientes,
                          clases_realizadas=clases_realizadas_hoy,
                          temp_audio_files=temp_audio_files,
                          hoy=hoy)

# Add a route that uses the fixed template
@app.route('/asistencia/fixed')
def control_asistencia_fixed():
    """Fixed version of control_asistencia"""
    from app import datetime, HorarioClase, ClaseRealizada, os
    
    hoy = datetime.now().date()
    dia_semana = hoy.weekday()
    
    horarios_hoy = HorarioClase.query.filter_by(dia_semana=dia_semana).order_by(HorarioClase.hora_inicio).all()
    clases_realizadas_hoy = ClaseRealizada.query.filter_by(fecha=hoy).all()
    horarios_ya_registrados = [c.horario_id for c in clases_realizadas_hoy]
    horarios_pendientes = [h for h in horarios_hoy if h.id not in horarios_ya_registrados]
    
    temp_audio_files = {}
    for horario in horarios_pendientes:
        for ext in ['mp3', 'wav', 'ogg']:
            audio_path = os.path.join(app.config['UPLOAD_FOLDER'], f'temp_horario_{horario.id}.{ext}')
            if os.path.exists(audio_path):
                temp_audio_files[horario.id] = True
                break
    
    # Use the fixed template
    return render_template('asistencia/control_fixed.html', 
                          horarios_pendientes=horarios_pendientes,
                          clases_realizadas=clases_realizadas_hoy,
                          temp_audio_files=temp_audio_files,
                          hoy=hoy)

print("Waveform route and fixed control route added successfully!")