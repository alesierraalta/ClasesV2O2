import os
import logging
import traceback
import re  # para expresiones regulares
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort, send_file, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, date, time
from werkzeug.utils import secure_filename
import calendar
from flask_wtf.csrf import CSRFProtect, generate_csrf
import pandas as pd
import numpy as np
import io
import re
import click
import functools
import glob
import shutil

import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Necesario para generar gráficos sin interfaz gráfica
import librosa
import librosa.display
import io
import base64
import time as time_module  # Renamed to avoid conflict with datetime.time

# Importar el blueprint de API
from api_routes import api

# Importar el blueprint de audio
from audio_routes import audio_bp

# Importar módulo de notificaciones
from notifications import setup_notification_scheduler, check_and_notify_unregistered_classes, send_whatsapp_notification, is_notification_locked

# Definir extensiones permitidas para archivos Excel
ALLOWED_EXTENSIONS_EXCEL = {'xlsx', 'xls'}

# Definir extensiones permitidas para archivos de audio
ALLOWED_EXTENSIONS_AUDIO = {'mp3', 'wav', 'ogg', 'webm', 'm4a'}

# Función para verificar si un archivo tiene una extensión permitida
def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

# Inicializar la aplicación Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu-clave-secreta'
csrf = CSRFProtect(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gimnasio.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# Configuración para notificaciones WhatsApp
app.config['NOTIFICATION_PHONE_NUMBER'] = os.environ.get('NOTIFICATION_PHONE_NUMBER')

# Añade esto después de crear tu aplicación Flask en app.py
# Nota: SOLO PARA DESARROLLO, no usar en producción
app.config['WTF_CSRF_ENABLED'] = False

# Configuración para PyWhatKit
app.config['WHATSAPP_NUMBER'] = os.environ.get('WHATSAPP_NUMBER')
app.config['WHATSAPP_MESSAGE'] = os.environ.get('WHATSAPP_MESSAGE')

# Configurar logging para depuración
try:
    logger = logging.getLogger('import_debug')
    if not logger.handlers:
        # Crear handler de archivo
        log_file = logging.FileHandler('import_debug.log', 'w', encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        log_file.setFormatter(formatter)
        logger.addHandler(log_file)
        logger.setLevel(logging.DEBUG)
        
        # Crear archivo de errores
        with open('import_errors.log', 'w', encoding='utf-8') as f:
            f.write("Registro de errores de importación\n\n")
except Exception as e:
    print(f"Error al configurar logging: {e}")

# Decorador para rutas inaccesibles
def ruta_inaccesible(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        abort(404)  # Retornar error 404 Not Found
    return decorated_function

# Registrar filtro personalizado para divmod
@app.template_filter('divmod')
def divmod_filter(value, arg):
    return divmod(value, arg)

# Filtro para obtener el timestamp actual
@app.template_filter('now')
def now_filter():
    return datetime.now()

# Inicializar la base de datos
db = SQLAlchemy(app)
# Exempt certain routes from CSRF
csrf.exempt('/import/asistencia')
csrf.exempt('/import/clases')
csrf.exempt('/import/horarios')
csrf.exempt('/import/profesores')
# Añadir esta línea para eximir la ruta de carga de audio
csrf.exempt('/asistencia/upload_audio/<int:horario_id>')

# Create database tables if they don't exist
with app.app_context():
    db.create_all()

# Función para convertir un valor decimal de Excel a objeto time
def excel_time_to_time(excel_time):
    if pd.isna(excel_time):
        return None
        
    # Si ya es un objeto time, devolverlo directamente
    if isinstance(excel_time, time):
        return excel_time
    
    # Si es datetime, extraer la hora
    if isinstance(excel_time, datetime):
        return excel_time.time()
        
    # Si es string, intentar convertirlo a time
    if isinstance(excel_time, str):
        # Eliminar espacios en blanco
        excel_time = excel_time.strip()
        
        # Comprobar si ya tiene el formato de hora (contiene :)
        if ':' in excel_time:
            try:
                # Probar diferentes formatos comunes de hora
                formats_to_try = [
                    '%H:%M',
                    '%H:%M:%S',
                    '%I:%M %p',
                    '%I:%M:%S %p',
                    '%H.%M',
                    '%H.%M.%S'
                ]
                
                for fmt in formats_to_try:
                    try:
                        return datetime.strptime(excel_time, fmt).time()
                    except ValueError:
                        continue
                
                # Si no coincide con ningún formato, intentar analizar manualmente
                parts = excel_time.split(':')
                if len(parts) >= 2:
                    hour = int(parts[0])
                    minute = int(parts[1])
                    second = int(parts[2]) if len(parts) > 2 else 0
                    return time(hour, minute, second)
                
                # Si todo falla, registrar un error detallado
                print(f"No se pudo convertir la hora: '{excel_time}', no coincide con formatos conocidos")
                return None
            except Exception as e:
                print(f"Error al convertir hora '{excel_time}': {str(e)}")
                return None
    
    # Para valores numéricos (decimal de Excel)
    try:
        if isinstance(excel_time, (int, float)):
            # Convertir valor decimal a horas y minutos
            total_seconds = excel_time * 86400  # 24 horas * 60 minutos * 60 segundos
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            seconds = int(total_seconds % 60)
            
            return time(hours, minutes, seconds)
    except Exception as e:
        print(f"Error al convertir valor decimal '{excel_time}': {str(e)}")
        return None
    
    # Si llegamos aquí, no pudimos convertir el valor
    print(f"Tipo de dato no manejado para hora: {type(excel_time)}, valor: {excel_time}")
    return None

# Modelos
class Profesor(db.Model):
    __tablename__ = 'profesor'  # Explicitly define the table name
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    tarifa_por_clase = db.Column(db.Float, nullable=False)
    telefono = db.Column(db.String(20))
    email = db.Column(db.String(100))
    horarios = db.relationship('HorarioClase', backref='profesor', lazy=True)
    clases_realizadas = db.relationship('ClaseRealizada', backref='profesor', lazy=True)
    
    def __repr__(self):
        return f"{self.nombre} {self.apellido}"

# Días de la semana
DIAS_SEMANA = [
    (0, 'Lunes'),
    (1, 'Martes'),
    (2, 'Miércoles'),
    (3, 'Jueves'),
    (4, 'Viernes'),
    (5, 'Sábado'),
    (6, 'Domingo')
]

# Tipos de clase
TIPOS_CLASE = [
    ('MOVE', 'MOVE'),
    ('RIDE', 'RIDE'),
    ('BOX', 'BOX'),
    ('OTRO', 'OTRO')
]

class HorarioClase(db.Model):
    """Representa una clase programada regularmente en un horario semanal"""
    __tablename__ = 'horario_clase'  # Explicitly define the table name
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    dia_semana = db.Column(db.Integer, nullable=False)  # 0=Lunes, 1=Martes, etc.
    hora_inicio = db.Column(db.Time, nullable=False)
    duracion = db.Column(db.Integer, default=60)  # Duración en minutos
    profesor_id = db.Column(db.Integer, db.ForeignKey('profesor.id'), nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    capacidad_maxima = db.Column(db.Integer, default=20)  # Capacidad máxima de alumnos
    tipo_clase = db.Column(db.String(20), default='OTRO')  # Tipo de clase: MOVE, RIDE, BOX o OTRO
    clases_realizadas = db.relationship('ClaseRealizada', backref='horario', lazy=True)
    
    def __repr__(self):
        dia = dict(DIAS_SEMANA).get(self.dia_semana)
        return f"{self.nombre} - {dia} {self.hora_inicio.strftime('%H:%M')}"
    
    def nombre_dia(self):
        return dict(DIAS_SEMANA).get(self.dia_semana)
        
    def hora_fin_str(self):
        """Devuelve la hora de finalización como string"""
        minutos_totales = self.hora_inicio.hour * 60 + self.hora_inicio.minute + self.duracion
        horas, minutos = divmod(minutos_totales, 60)
        return f"{horas:02d}:{minutos:02d}"

class ClaseRealizada(db.Model):
    """Representa una instancia real de una clase que fue impartida"""
    __tablename__ = 'clase_realizada'  # Explicitly define the table name
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, nullable=False)
    horario_id = db.Column(db.Integer, db.ForeignKey('horario_clase.id'), nullable=False)
    profesor_id = db.Column(db.Integer, db.ForeignKey('profesor.id'), nullable=False)
    hora_llegada_profesor = db.Column(db.Time, nullable=True)  # Hora real de llegada
    cantidad_alumnos = db.Column(db.Integer, default=0)
    observaciones = db.Column(db.Text)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    audio_file = db.Column(db.String(255), nullable=True)  # Nombre del archivo de audio
    
    def __repr__(self):
        return f"{self.horario.nombre} - {self.fecha.strftime('%d/%m/%Y')}"
    
    def estado(self):
        if not self.hora_llegada_profesor:
            return "Pendiente"
        return "Realizada"
    
    def puntualidad(self):
        if not self.hora_llegada_profesor:
            return "N/A"
        
        diferencia_minutos = (
            datetime.combine(date.min, self.hora_llegada_profesor) - 
            datetime.combine(date.min, self.horario.hora_inicio)
        ).total_seconds() / 60
        
        if diferencia_minutos <= 0:
            return "Puntual"
        elif diferencia_minutos <= 10:
            return "Retraso leve"
        else:
            return "Retraso significativo"

# Rutas
@app.route('/test')
def test_route():
    return "Application is working!"

@app.route('/test-template')
def test_template():
    return render_template('test.html')

@app.route('/')
def index():
    # Make sure this implementation is complete
    try:
        hoy = date.today()
        dia_semana = hoy.weekday()  # 0 for Monday, 6 for Sunday
        
        # Get classes scheduled for today
        horarios_hoy = HorarioClase.query.filter_by(dia_semana=dia_semana).all()
        
        # Check which ones already have attendance recorded
        clases_registradas = {cr.horario_id: cr for cr in ClaseRealizada.query.filter_by(fecha=hoy).all()}
        
        return render_template('index.html', 
                              horarios=horarios_hoy, 
                              clases_registradas=clases_registradas,
                              hoy=hoy)
    except Exception as e:
        app.logger.error(f"Error in index route: {str(e)}")
        return f"Error loading the homepage: {str(e)}", 500

@app.route('/simple')
def index_simple():
    try:
        # Obtener clases programadas para hoy
        hoy = datetime.now().date()
        dia_semana = hoy.weekday()  # 0 es lunes, 6 es domingo
        
        horarios_hoy = HorarioClase.query.filter_by(dia_semana=dia_semana).order_by(HorarioClase.hora_inicio).all()
        
        return render_template('index_simple.html', 
                              horarios_hoy=horarios_hoy, 
                              hoy=hoy)
    except Exception as e:
        # Log the error
        print(f"Error in simple index route: {str(e)}")
        traceback.print_exc()
        # Return a simple error page
        return f"<h1>Error</h1><p>An error occurred: {str(e)}</p><pre>{traceback.format_exc()}</pre>"

# Rutas para Profesores
@app.route('/profesores')
def listar_profesores():
    profesores = Profesor.query.all()
    return render_template('profesores/lista.html', profesores=profesores)

@app.route('/profesores/nuevo', methods=['GET', 'POST'])
def nuevo_profesor():
    if request.method == 'POST':
        profesor = Profesor(
            nombre=request.form['nombre'],
            apellido=request.form['apellido'],
            tarifa_por_clase=float(request.form['tarifa_por_clase']),
            telefono=request.form['telefono'],
            email=request.form['email']
        )
        db.session.add(profesor)
        db.session.commit()
        flash('Profesor registrado con éxito', 'success')
        return redirect(url_for('listar_profesores'))
    return render_template('profesores/nuevo.html')

@app.route('/profesores/editar/<int:id>', methods=['GET', 'POST'])
def editar_profesor(id):
    profesor = Profesor.query.get_or_404(id)
    if request.method == 'POST':
        profesor.nombre = request.form['nombre']
        profesor.apellido = request.form['apellido']
        profesor.tarifa_por_clase = float(request.form['tarifa_por_clase'])
        profesor.telefono = request.form['telefono']
        profesor.email = request.form['email']
        db.session.commit()
        flash('Profesor actualizado con éxito', 'success')
        return redirect(url_for('listar_profesores'))
    return render_template('profesores/editar.html', profesor=profesor)

@app.route('/profesores/eliminar/<int:id>')
def eliminar_profesor(id):
    profesor = Profesor.query.get_or_404(id)
    if HorarioClase.query.filter_by(profesor_id=id).first() or ClaseRealizada.query.filter_by(profesor_id=id).first():
        flash('No se puede eliminar el profesor porque tiene clases asociadas', 'danger')
    else:
        db.session.delete(profesor)
        db.session.commit()
        flash('Profesor eliminado con éxito', 'success')
    return redirect(url_for('listar_profesores'))

@app.route('/profesores/eliminar-varios', methods=['POST'])
def eliminar_varios_profesores():
    profesores_ids = request.form.getlist('profesores_ids[]')
    if not profesores_ids:
        flash('No se han seleccionado profesores para eliminar', 'warning')
        return redirect(url_for('listar_profesores'))
    
    profesores_eliminados = 0
    profesores_con_dependencias = 0
    
    for profesor_id in profesores_ids:
        profesor = Profesor.query.get(profesor_id)
        if profesor:
            # Verificar si tiene horarios o clases asociadas
            if HorarioClase.query.filter_by(profesor_id=profesor_id).first() or ClaseRealizada.query.filter_by(profesor_id=profesor_id).first():
                profesores_con_dependencias += 1
            else:
                db.session.delete(profesor)
                profesores_eliminados += 1
    
    db.session.commit()
    
    if profesores_eliminados > 0:
        flash(f'Se eliminaron {profesores_eliminados} profesores con éxito', 'success')
    
    if profesores_con_dependencias > 0:
        flash(f'No se pudieron eliminar {profesores_con_dependencias} profesores porque tienen clases asociadas', 'warning')
    
    return redirect(url_for('listar_profesores'))

# Rutas para Horarios de Clases
@app.route('/horarios')
def listar_horarios():
    horarios = HorarioClase.query.order_by(HorarioClase.dia_semana, HorarioClase.hora_inicio).all()
    return render_template('horarios/lista.html', horarios=horarios, dias_semana=dict(DIAS_SEMANA))

@app.route('/horarios/nuevo', methods=['GET', 'POST'])
def nuevo_horario():
    profesores = Profesor.query.order_by(Profesor.apellido).all()
    
    if request.method == 'POST':
        horario = HorarioClase(
            nombre=request.form['nombre'],
            dia_semana=int(request.form['dia_semana']),
            hora_inicio=datetime.strptime(request.form['hora_inicio'], '%H:%M').time(),
            duracion=int(request.form['duracion']),
            profesor_id=int(request.form['profesor_id']),
            capacidad_maxima=int(request.form['capacidad_maxima']),
            tipo_clase=request.form['tipo_clase']
        )
        db.session.add(horario)
        db.session.flush()  # Get the horario ID without committing
        
        # Create a ClaseRealizada record for today if the class is scheduled for today
        hoy = datetime.now().date()
        if horario.dia_semana == hoy.weekday():
            nueva_clase = ClaseRealizada(
                fecha=hoy,
                horario_id=horario.id,
                profesor_id=horario.profesor_id,
                hora_llegada_profesor=horario.hora_inicio,  # Default to scheduled time
                cantidad_alumnos=0,
                observaciones="Clase creada automáticamente"
            )
            db.session.add(nueva_clase)
        
        db.session.commit()
        flash('Horario creado con éxito', 'success')
        return redirect(url_for('listar_horarios'))
    
    return render_template('horarios/nuevo.html', profesores=profesores, dias_semana=DIAS_SEMANA, tipos_clase=TIPOS_CLASE)

@app.route('/horarios/editar/<int:id>', methods=['GET', 'POST'])
def editar_horario(id):
    horario = HorarioClase.query.get_or_404(id)
    profesores = Profesor.query.order_by(Profesor.apellido).all()
    
    if request.method == 'POST':
        horario.nombre = request.form['nombre']
        horario.dia_semana = int(request.form['dia_semana'])
        horario.hora_inicio = datetime.strptime(request.form['hora_inicio'], '%H:%M').time()
        horario.duracion = int(request.form['duracion'])
        horario.profesor_id = int(request.form['profesor_id'])
        horario.capacidad_maxima = int(request.form['capacidad_maxima'])
        horario.tipo_clase = request.form['tipo_clase']
        db.session.commit()
        flash('Horario actualizado con éxito', 'success')
        return redirect(url_for('listar_horarios'))
    
    return render_template('horarios/editar.html', horario=horario, profesores=profesores, dias_semana=DIAS_SEMANA, tipos_clase=TIPOS_CLASE)

@app.route('/horarios/eliminar/<int:id>')
def eliminar_horario(id):
    horario = HorarioClase.query.get_or_404(id)
    if ClaseRealizada.query.filter_by(horario_id=id).first():
        flash('No se puede eliminar el horario porque tiene clases realizadas asociadas', 'danger')
    else:
        db.session.delete(horario)
        db.session.commit()
        flash('Horario de clase eliminado con éxito', 'success')
    return redirect(url_for('listar_horarios'))

@app.route('/horarios/eliminar-varios', methods=['POST'])
def eliminar_varios_horarios():
    horarios_ids = request.form.getlist('horarios_ids[]')
    if not horarios_ids:
        flash('No se han seleccionado horarios para eliminar', 'warning')
        return redirect(url_for('listar_horarios'))
    
    horarios_eliminados = 0
    horarios_con_dependencias = 0
    
    for horario_id in horarios_ids:
        horario = HorarioClase.query.get(horario_id)
        if horario:
            # Verificar si tiene clases realizadas asociadas
            if ClaseRealizada.query.filter_by(horario_id=horario_id).first():
                horarios_con_dependencias += 1
            else:
                db.session.delete(horario)
                horarios_eliminados += 1
    
    db.session.commit()
    
    if horarios_eliminados > 0:
        flash(f'Se eliminaron {horarios_eliminados} horarios con éxito', 'success')
    
    if horarios_con_dependencias > 0:
        flash(f'No se pudieron eliminar {horarios_con_dependencias} horarios porque tienen clases realizadas asociadas', 'warning')
    
    return redirect(url_for('listar_horarios'))

# Rutas para Control de Asistencia
@app.route('/asistencia')
def control_asistencia():
    # Mostrar las clases programadas para hoy que no tienen registro de asistencia
    try:
        hoy = datetime.now().date()
        dia_semana = hoy.weekday()
        
        # Horarios programados para hoy
        horarios_hoy = HorarioClase.query.filter_by(dia_semana=dia_semana).order_by(HorarioClase.hora_inicio).all()
        
        # Clases ya registradas hoy
        clases_realizadas_hoy = ClaseRealizada.query.filter_by(fecha=hoy).all()
        
        # IDs de horarios que ya tienen clases realizadas registradas hoy
        horarios_ya_registrados = [cr.horario_id for cr in clases_realizadas_hoy]
        
        # Horarios pendientes (que no tienen registro aún)
        horarios_pendientes = [h for h in horarios_hoy if h.id not in horarios_ya_registrados]
        
        # Verificar si hay archivos de audio temporales para clases pendientes
        temp_audio_files = {}
        for horario in horarios_pendientes:
            for ext in ['mp3', 'wav', 'ogg']:
                audio_path = os.path.join(app.config.get('UPLOAD_FOLDER', 'static/uploads'), f'temp_horario_{horario.id}.{ext}')
                if os.path.exists(audio_path):
                    temp_audio_files[horario.id] = True
                    break
        
        # Handle empty horarios_pendientes list safely
        horario_id = None
        if horarios_pendientes:
            horario_id = horarios_pendientes[0].id
        
        # Only retrieve clase if needed
        clase = ClaseRealizada.query.first()
        
        return render_template('asistencia/control.html', 
                            horarios_pendientes=horarios_pendientes,
                            clases_realizadas=clases_realizadas_hoy,
                            temp_audio_files=temp_audio_files,
                            hoy=hoy,
                            horarioId=horario_id,
                            clase=clase,
                            current_timestamp=int(time_module.time()))
    except Exception as e:
        app.logger.error(f"Error in control_asistencia: {str(e)}")
        app.logger.error(traceback.format_exc())
        return f"Error: {str(e)}", 500

@app.route('/asistencia/registrar/<int:horario_id>', methods=['GET', 'POST'])
def registrar_asistencia(horario_id):
    horario = HorarioClase.query.get_or_404(horario_id)
    hoy = datetime.now().date()
    
    # Verificar si ya existe una clase realizada para este horario en esta fecha
    clase_existente = ClaseRealizada.query.filter_by(
        horario_id=horario_id,
        fecha=hoy
    ).first()
    
    if clase_existente:
        flash('Ya existe un registro para este horario en la fecha actual', 'warning')
        return redirect(url_for('control_asistencia'))
    
    if request.method == 'POST':
        hora_llegada = request.form.get('hora_llegada')
        cantidad_alumnos = request.form.get('cantidad_alumnos', 0)
        observaciones = request.form.get('observaciones', '')
        
        try:
            # Convertir la hora de llegada a un objeto time
            if hora_llegada:
                # Obtener hora como objeto time
                hora_llegada_time = datetime.strptime(hora_llegada, '%H:%M').time()
            else:
                hora_llegada_time = None
                
            # Crear un nuevo registro
            nueva_clase = ClaseRealizada(
                fecha=hoy,
                horario_id=horario_id,
                profesor_id=horario.profesor_id,
                hora_llegada_profesor=hora_llegada_time,
                cantidad_alumnos=cantidad_alumnos,
                observaciones=observaciones
            )
            
            # Verificar si hay un archivo de audio temporal para este horario
            audio_file = None
            for ext in ['mp3', 'wav', 'ogg']:
                temp_path = os.path.join(app.config.get('UPLOAD_FOLDER', 'static/uploads'), f'temp_horario_{horario_id}.{ext}')
                if os.path.exists(temp_path):
                    # Guardar el archivo definitivo
                    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                    new_filename = f'clase_{horario_id}_{timestamp}.{ext}'
                    new_path = os.path.join(app.config.get('UPLOAD_FOLDER', 'static/uploads'), new_filename)
                    
                    # Asegurar que el directorio existe
                    os.makedirs(os.path.dirname(new_path), exist_ok=True)
                    
                    # Mover el archivo temporal al definitivo
                    try:
                        os.rename(temp_path, new_path)
                    except Exception as e:
                        import shutil
                        shutil.copy2(temp_path, new_path)
                        os.remove(temp_path)
                    
                    nueva_clase.audio_file = new_filename
                    break
            
            db.session.add(nueva_clase)
            db.session.commit()
            
            flash('Registro de asistencia guardado correctamente', 'success')
            return redirect(url_for('control_asistencia'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al guardar el registro: {str(e)}', 'error')
    
    return render_template('asistencia/registrar.html', horario=horario, hoy=hoy)

@app.route('/asistencia/editar/<int:id>', methods=['GET', 'POST'])
def editar_asistencia(id):
    clase_realizada = ClaseRealizada.query.get_or_404(id)
    
    if request.method == 'POST':
        hora_llegada = None
        if request.form['hora_llegada']:
            hora_llegada = datetime.strptime(request.form['hora_llegada'], '%H:%M').time()
        
        clase_realizada.hora_llegada_profesor = hora_llegada
        clase_realizada.cantidad_alumnos = int(request.form['cantidad_alumnos'])
        clase_realizada.observaciones = request.form['observaciones']
        
        db.session.commit()
        flash('Registro de asistencia actualizado con éxito', 'success')
        return redirect(url_for('control_asistencia'))
    
    return render_template('asistencia/editar.html', clase=clase_realizada)

@app.route('/asistencia/eliminar/<int:id>')
def eliminar_asistencia(id):
    clase_realizada = ClaseRealizada.query.get_or_404(id)
    db.session.delete(clase_realizada)
    db.session.commit()
    flash('Registro de asistencia eliminado con éxito', 'success')
    return redirect(url_for('control_asistencia'))

@app.route('/asistencia/historial')
def historial_asistencia():
    # Parámetros de filtro
    fecha_inicio_str = request.args.get('fecha_inicio')
    fecha_fin_str = request.args.get('fecha_fin')
    profesor_id = request.args.get('profesor_id')
    
    # Fecha por defecto: últimos 7 días
    hoy = datetime.now().date()
    fecha_inicio = hoy - timedelta(days=7)
    fecha_fin = hoy
    
    # Aplicar filtros si existen
    if fecha_inicio_str:
        fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
    
    if fecha_fin_str:
        fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
    
    # Construir la consulta
    query = ClaseRealizada.query.filter(
        ClaseRealizada.fecha >= fecha_inicio,
        ClaseRealizada.fecha <= fecha_fin
    ).order_by(ClaseRealizada.fecha.desc(), ClaseRealizada.id.desc())
    
    if profesor_id and profesor_id != 'todos':
        query = query.filter_by(profesor_id=int(profesor_id))
    
    clases_realizadas = query.all()
    profesores = Profesor.query.all()
    
    return render_template('asistencia/historial.html',
                           clases_realizadas=clases_realizadas,
                           profesores=profesores,
                           fecha_inicio=fecha_inicio,
                           fecha_fin=fecha_fin,
                           profesor_id=profesor_id)

# Rutas para Informes
@app.route('/informes')
def informes():
    return render_template('informes/index.html')

@app.route('/informes/mensual', methods=['GET', 'POST'])
def informe_mensual():
    if request.method == 'POST':
        mes = int(request.form['mes'])
        anio = int(request.form['anio'])
        
        # Obtener el primer y último día del mes
        primer_dia = date(anio, mes, 1)
        ultimo_dia = date(anio, mes, calendar.monthrange(anio, mes)[1])
        
        # Consultar clases realizadas en el rango de fechas
        clases_realizadas = ClaseRealizada.query.filter(
            ClaseRealizada.fecha >= primer_dia,
            ClaseRealizada.fecha <= ultimo_dia
        ).order_by(ClaseRealizada.fecha).all()
        
        # Identificar clases programadas pero no registradas
        # 1. Obtener todos los horarios activos
        horarios_activos = HorarioClase.query.all()
        
        # 2. Generar fechas para el mes seleccionado
        fechas_mes = []
        fecha_actual = primer_dia
        while fecha_actual <= ultimo_dia:
            fechas_mes.append(fecha_actual)
            fecha_actual += timedelta(days=1)
        
        # 3. Generar las clases que deberían haberse realizado
        clases_esperadas = []
        for horario in horarios_activos:
            for fecha in fechas_mes:
                # Si el día de la semana coincide con el día del horario
                if fecha.weekday() == horario.dia_semana:
                    # Creamos un objeto para representar la clase esperada
                    clase_esperada = {
                        'fecha': fecha,
                        'horario': horario,
                        'profesor': horario.profesor,
                        'tipo_clase': horario.tipo_clase
                    }
                    clases_esperadas.append(clase_esperada)
        
        # 4. Identificar clases no registradas comparando con las realizadas
        clases_no_registradas = []
        for clase_esperada in clases_esperadas:
            # Verificar si esta clase esperada tiene un registro en clases_realizadas
            encontrada = False
            for clase_realizada in clases_realizadas:
                if (clase_realizada.fecha == clase_esperada['fecha'] and
                        clase_realizada.horario_id == clase_esperada['horario'].id):
                    encontrada = True
                    break
            
            if not encontrada:
                clases_no_registradas.append(clase_esperada)
        
        # Ordenar las clases no registradas por fecha
        clases_no_registradas.sort(key=lambda x: (x['fecha'], x['horario'].hora_inicio))
        
        # Inicializar variables para totales
        total_clases = {'value': 0}
        total_alumnos = {'value': 0}
        total_retrasos = {'value': 0}
        total_pagos = {'value': 0}
        
        # Calcular resumen por profesor
        resumen_profesores = {}
        # Contadores por tipo de clase
        conteo_tipos = {
            'MOVE': 0,
            'RIDE': 0,
            'BOX': 0,
            'OTRO': 0
        }
        # Alumnos por tipo de clase
        alumnos_tipos = {
            'MOVE': 0,
            'RIDE': 0,
            'BOX': 0,
            'OTRO': 0
        }
        
        for clase in clases_realizadas:
            profesor = clase.profesor
            tipo_clase = clase.horario.tipo_clase
            
            # Incrementar contadores por tipo
            conteo_tipos[tipo_clase] += 1
            alumnos_tipos[tipo_clase] += clase.cantidad_alumnos
            
            if profesor.id not in resumen_profesores:
                resumen_profesores[profesor.id] = {
                    'profesor': profesor,
                    'total_clases': 0,
                    'total_alumnos': 0,
                    'total_retrasos': 0,
                    'pago_total': 0.0,
                    'clases_por_tipo': {
                        'MOVE': 0,
                        'RIDE': 0,
                        'BOX': 0,
                        'OTRO': 0
                    },
                    'alumnos_por_tipo': {
                        'MOVE': 0,
                        'RIDE': 0,
                        'BOX': 0,
                        'OTRO': 0
                    }
                }
            resumen_profesores[profesor.id]['total_clases'] += 1
            resumen_profesores[profesor.id]['total_alumnos'] += clase.cantidad_alumnos
            resumen_profesores[profesor.id]['clases_por_tipo'][tipo_clase] += 1
            resumen_profesores[profesor.id]['alumnos_por_tipo'][tipo_clase] += clase.cantidad_alumnos
            
            if clase.hora_llegada_profesor and clase.hora_llegada_profesor > clase.horario.hora_inicio:
                resumen_profesores[profesor.id]['total_retrasos'] += 1
            
            # Si el profesor asistió (tiene hora de llegada) pero no hay alumnos, se paga la mitad
            pago_clase = profesor.tarifa_por_clase / 2 if (clase.hora_llegada_profesor and clase.cantidad_alumnos == 0) else profesor.tarifa_por_clase
            
            # Almacenar el pago individual por clase
            clase.pago_calculado = pago_clase
            
            # Añadir al total del profesor
            resumen_profesores[profesor.id]['pago_total'] += pago_clase
        
        # Calcular totales globales si hay datos
        if resumen_profesores:
            for profesor_id, datos in resumen_profesores.items():
                total_clases['value'] += datos['total_clases']
                total_alumnos['value'] += datos['total_alumnos']
                total_retrasos['value'] += datos['total_retrasos']
                total_pagos['value'] += datos['pago_total']
        
        # Contadores de clases no registradas por tipo
        conteo_no_registradas = {
            'MOVE': 0,
            'RIDE': 0,
            'BOX': 0,
            'OTRO': 0,
            'total': len(clases_no_registradas)
        }
        
        for clase in clases_no_registradas:
            tipo_clase = clase['tipo_clase']
            conteo_no_registradas[tipo_clase] += 1
        
        return render_template('informes/mensual_resultado.html', 
                              mes=mes, 
                              anio=anio, 
                              clases_realizadas=clases_realizadas,
                              clases_no_registradas=clases_no_registradas,
                              conteo_no_registradas=conteo_no_registradas,
                              resumen_profesores=resumen_profesores,
                              nombre_mes=calendar.month_name[mes],
                              conteo_tipos=conteo_tipos,
                              alumnos_tipos=alumnos_tipos,
                              total_clases=total_clases,
                              total_alumnos=total_alumnos,
                              total_retrasos=total_retrasos,
                              total_pagos=total_pagos)
    
    # Si es GET, mostrar formulario para seleccionar mes y año
    mes_actual = datetime.now().month
    anio_actual = datetime.now().year
    return render_template('informes/mensual.html', mes_actual=mes_actual, anio_actual=anio_actual)

# Rutas para la importación de Excel

@app.route('/importar/asistencia', methods=['GET', 'POST'])
def importar_asistencia():
    """Ruta para importar asistencia desde un archivo Excel."""
    resultados = {
        'procesados': 0,
        'nuevos': 0,
        'actualizados': 0,
        'errores': 0,
        'detalles': []
    }

    if request.method == 'POST':
        # Check if file was uploaded
        if 'archivo' not in request.files:
            flash('No se ha seleccionado un archivo', 'danger')
            return redirect(url_for('importar_asistencia'))
        
        archivo = request.files['archivo']
        if archivo.filename == '':
            flash('No se ha seleccionado un archivo', 'danger')
            return redirect(url_for('importar_asistencia'))
        
        if archivo and allowed_file(archivo.filename, ALLOWED_EXTENSIONS_EXCEL):
            # Initialize debug log
            with open('import_debug.log', 'a', encoding='utf-8') as f:
                f.write(f"\n========== NUEVA IMPORTACIÓN {datetime.now()} ==========\n")
            
            # Initialize error log
            with open('import_errors.log', 'a', encoding='utf-8') as f:
                f.write(f"\n========== NUEVA IMPORTACIÓN {datetime.now()} ==========\n")
            
            try:
                # Read Excel file with pandas
                df = pd.read_excel(archivo)
                
                # Verify required columns
                columnas_requeridas = ['Fecha', 'Hora', 'Intructor', 'Clase', 'Alumnos']
                for columna in columnas_requeridas:
                    if columna not in df.columns:
                        raise ValueError(f"El archivo no contiene la columna requerida: {columna}")
                
                # Log total rows to debug
                with open('import_debug.log', 'a', encoding='utf-8') as f:
                    f.write(f"Total de filas a procesar: {len(df)}\n")
                
                # Process each row
                for fila_num, row in df.iterrows():
                    try:
                        # Process date
                        fecha_str = row['Fecha']
                        if pd.isna(fecha_str):
                            raise ValueError("La fecha está vacía")
                        
                        # Log for debugging
                        with open('import_debug.log', 'a', encoding='utf-8') as f:
                            f.write(f"FECHA (Fila {fila_num}): '{fecha_str}', Tipo: {type(fecha_str)}\n")
                        
                        # Try to convert date
                        try:
                            if isinstance(fecha_str, str):
                                # Try different date formats
                                formats = ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%d.%m.%Y']
                                fecha = None
                                
                                for format_str in formats:
                                    try:
                                        fecha = datetime.strptime(fecha_str, format_str).date()
                                        # Log success
                                        with open('import_debug.log', 'a', encoding='utf-8') as f:
                                            f.write(f"  → Convertido con formato {format_str}: {fecha}\n")
                                        break
                                    except ValueError:
                                        continue
                                
                                if fecha is None:
                                    # Last attempt with pandas
                                    fecha = pd.to_datetime(fecha_str).date()
                                    with open('import_debug.log', 'a', encoding='utf-8') as f:
                                        f.write(f"  → Convertido con pandas: {fecha}\n")
                            elif isinstance(fecha_str, datetime):
                                fecha = fecha_str.date()
                                with open('import_debug.log', 'a', encoding='utf-8') as f:
                                    f.write(f"  → Es un objeto datetime: {fecha}\n")
                            else:
                                # For Excel date numbers or other formats
                                fecha = pd.to_datetime(fecha_str).date()
                                with open('import_debug.log', 'a', encoding='utf-8') as f:
                                    f.write(f"  → Convertido desde otro formato: {fecha}\n")
                        except Exception as e:
                            # Log error
                            with open('import_errors.log', 'a', encoding='utf-8') as f:
                                f.write(f"ERROR FECHA (Fila {fila_num}): '{fecha_str}' - {str(e)}\n")
                            
                            raise ValueError(f"No se pudo convertir la fecha '{fecha_str}': {str(e)}")
                        
                        # Process time
                        try:
                            hora_str = row['Hora']
                            
                            # Variable to track attendance
                            no_asistio = False
                            
                            # Log for debugging
                            with open('import_debug.log', 'a', encoding='utf-8') as f:
                                f.write(f"HORA (Fila {fila_num}): '{hora_str}', Tipo: {type(hora_str)}\n")
                            
                            # Check if it's "NO ASISTIO" or similar absence text
                            if isinstance(hora_str, str):
                                hora_upper = str(hora_str).upper().strip()
                                
                                with open('import_debug.log', 'a', encoding='utf-8') as f:
                                    f.write(f"  → Verificando texto: '{hora_upper}'\n")
                                
                                if any(palabra in hora_upper for palabra in ['NO ASISTIO', 'NO ASISTIÓ', 'AUSENTE', 'CANCELADO']):
                                    hora = time(0, 0)  # Default time for schedule
                                    no_asistio = True
                                    
                                    with open('import_debug.log', 'a', encoding='utf-8') as f:
                                        f.write(f"  → DETECTED as absence\n")
                            elif pd.isna(hora_str):
                                # If the value is NaN or empty
                                hora = time(0, 0)  # Use midnight as default
                                
                                with open('import_debug.log', 'a', encoding='utf-8') as f:
                                    f.write(f"  → NaN/empty value\n")
                            elif isinstance(hora_str, (int, float)):
                                # Convert Excel decimal to time
                                hora = excel_time_to_time(hora_str)
                                
                                with open('import_debug.log', 'a', encoding='utf-8') as f:
                                    f.write(f"  → Numeric value: {hora_str}, converted to: {hora}\n")
                                
                                if hora is None:
                                    raise ValueError(f"Could not convert value {hora_str} to time format")
                            else:
                                # Convert other formats
                                try:
                                    # Ensure it's a string and remove spaces
                                    hora_str = str(hora_str).strip()
                                    
                                    with open('import_debug.log', 'a', encoding='utf-8') as f:
                                        f.write(f"  → Processing time format: '{hora_str}'\n")
                                    
                                    # Check AM/PM format (example: 7:30AM, 7:30 PM)
                                    if 'AM' in hora_str.upper() or 'PM' in hora_str.upper():
                                        # Normalize format (remove spaces between time and AM/PM)
                                        hora_normalizada = hora_str.upper().replace(' ', '')
                                        
                                        with open('import_debug.log', 'a', encoding='utf-8') as f:
                                            f.write(f"  → AM/PM format detected: '{hora_normalizada}'\n")
                                        
                                        # Extract time parts (hour, minute, AM/PM)
                                        import re
                                        match = re.search(r'(\d+)(?::|\.)(\d+)\s*(AM|PM)', hora_str, re.IGNORECASE)
                                        
                                        if match:
                                            h, m, periodo = match.groups()
                                            h = int(h)
                                            m = int(m)
                                            
                                            # Adjust for PM
                                            if periodo.upper() == 'PM' and h < 12:
                                                h += 12
                                            elif periodo.upper() == 'AM' and h == 12:
                                                h = 0
                                            
                                            hora = time(h, m)
                                            
                                            with open('import_debug.log', 'a', encoding='utf-8') as f:
                                                f.write(f"  → Manually converted: h={h}, m={m}, result={hora}\n")
                                        else:
                                            # Attempt 1: standard 12h format
                                            try:
                                                hora_dt = datetime.strptime(hora_normalizada, '%I:%M%p')
                                                hora = hora_dt.time()
                                                
                                                with open('import_debug.log', 'a', encoding='utf-8') as f:
                                                    f.write(f"  → Converted with strptime format %I:%M%p: {hora}\n")
                                            except ValueError:
                                                # Attempt 2: format with dot
                                                try:
                                                    hora_norm_punto = hora_normalizada.replace(':', '.')
                                                    hora_dt = datetime.strptime(hora_norm_punto, '%I.%M%p')
                                                    hora = hora_dt.time()
                                                    
                                                    with open('import_debug.log', 'a', encoding='utf-8') as f:
                                                        f.write(f"  → Converted with strptime format %I.%M%p: {hora}\n")
                                                except ValueError:
                                                    # Last attempt with pandas
                                                    try:
                                                        hora = pd.to_datetime(hora_str).time()
                                                        
                                                        with open('import_debug.log', 'a', encoding='utf-8') as f:
                                                            f.write(f"  → Converted with pandas: {hora}\n")
                                                    except:
                                                        with open('import_debug.log', 'a', encoding='utf-8') as f:
                                                            f.write(f"  → All attempts failed\n")
                                                        
                                                        raise ValueError(f"Unrecognized AM/PM format: {hora_str}")
                                    elif ':' in hora_str:
                                        # If it has HH:MM format or similar
                                        partes = hora_str.split(':')
                                        try:
                                            hora = time(int(partes[0]), int(partes[1]) if len(partes) > 1 else 0)
                                            
                                            with open('import_debug.log', 'a', encoding='utf-8') as f:
                                                f.write(f"  → Converted with split: {hora}\n")
                                        except ValueError as e:
                                            raise ValueError(f"Invalid time format: {hora_str}")
                                    else:
                                        # Try with 24-hour format
                                        try:
                                            hora_dt = datetime.strptime(hora_str, '%H:%M')
                                            hora = hora_dt.time()
                                            
                                            with open('import_debug.log', 'a', encoding='utf-8') as f:
                                                f.write(f"  → Converted with format %H:%M: {hora}\n")
                                        except ValueError:
                                            # Last attempt with pandas
                                            try:
                                                hora = pd.to_datetime(hora_str).time()
                                                
                                                with open('import_debug.log', 'a', encoding='utf-8') as f:
                                                    f.write(f"  → Converted with pandas: {hora}\n")
                                            except Exception as e_pandas:
                                                raise ValueError(f"Unrecognized time format: {hora_str}")
                                except Exception as e:
                                    # Log error
                                    with open('import_errors.log', 'a', encoding='utf-8') as f:
                                        f.write(f"ERROR TIME (Fila {fila_num}): '{hora_str}' - {str(e)}\n")
                                    
                                    raise ValueError(f"Could not convert time '{hora_str}': {str(e)}")
                        except Exception as e:
                            # Log the detailed error
                            error_info = {
                                'fila': fila_num,
                                'profesor': str(row.get('Intructor', '')),
                                'fecha': str(row.get('Fecha', '')),
                                'hora': str(row.get('Hora', '')),
                                'clase': str(row.get('Clase', '')),
                                'estado': 'Error',
                                'mensaje_error': str(e)
                            }
                            
                            with open('import_errors.log', 'a', encoding='utf-8') as f:
                                f.write(f"ERROR EN FILA {fila_num}:\n")
                                for k, v in error_info.items():
                                    f.write(f"  {k}: {v}\n")
                                f.write("\n" + "-"*50 + "\n")
                            
                            # For user interface
                            resultados['errores'] += 1
                            resultados['detalles'].append({
                                'fila': fila_num,
                                'profesor': str(row.get('Intructor', '')),
                                'fecha': str(row.get('Fecha', '')),
                                'clase': str(row.get('Clase', '')),
                                'estado': 'Error',
                                'errores': [f"({type(e).__name__}) {str(e)}"]
                            })
                            continue  # Skip to the next row
                        
                        # Find or create professor
                        profesor_nombre = row['Intructor']
                        if pd.isna(profesor_nombre) or not profesor_nombre:
                            raise ValueError("El nombre del instructor está vacío")
                        
                        profesor = Profesor.query.filter(Profesor.nombre.ilike(f"%{profesor_nombre}%")).first()
                        if not profesor:
                            try:
                                # Create new professor with a default rate
                                profesor = Profesor(
                                    nombre=profesor_nombre,
                                    apellido='',  # Leave empty for now
                                    email='',     # Leave empty for now
                                    telefono='',  # Leave empty for now
                                    tarifa_por_clase=0.0  # Default rate
                                )
                                db.session.add(profesor)
                                db.session.commit()
                            except Exception as e:
                                db.session.rollback()
                                raise ValueError(f"Error al crear profesor '{profesor_nombre}': {str(e)}")
                        
                        # Find or create class
                        clase_nombre = row['Clase']
                        if pd.isna(clase_nombre) or not clase_nombre:
                            raise ValueError("El nombre de la clase está vacío")
                        
                        # No need to search for a Clase model (it doesn't exist)
                        # We'll use the nombre directly for HorarioClase
                        
                        # Get number of students
                        try:
                            alumnos = int(row['Alumnos'])
                        except:
                            alumnos = 0
                        
                        # Get comments if available
                        observaciones = row.get('Observaciones', '')
                        if pd.isna(observaciones):
                            observaciones = ''
                        
                        # Calculate arrival time (arrival = scheduled time + delay)
                        hora_llegada = hora
                        
                        # Check if this schedule exists
                        horario = HorarioClase.query.filter_by(
                            dia_semana=fecha.weekday(),
                            hora_inicio=hora,
                            nombre=clase_nombre
                        ).first()
                        
                        if not horario:
                            # Create new schedule
                            horario = HorarioClase(
                                nombre=clase_nombre,
                                dia_semana=fecha.weekday(),
                                hora_inicio=hora,
                                duracion=60,  # Duración en minutos
                                profesor_id=profesor.id,
                                tipo_clase='OTRO'  # Default type
                            )
                            db.session.add(horario)
                            db.session.commit()
                        
                        # Check if this class session already exists
                        clase_existente = ClaseRealizada.query.filter_by(
                            fecha=fecha,
                            horario_id=horario.id
                        ).first()
                        
                        if not clase_existente:
                            # Create new record
                            nueva_clase = ClaseRealizada(
                                fecha=fecha,
                                horario_id=horario.id,
                                profesor_id=profesor.id,
                                hora_llegada_profesor=None if no_asistio else hora,
                                cantidad_alumnos=alumnos,
                                observaciones="PROFESOR NO ASISTIÓ" if no_asistio else ""
                            )
                            db.session.add(nueva_clase)
                            
                            resultados['nuevos'] += 1
                            resultados['detalles'].append({
                                'fila': fila_num,
                                'profesor': profesor.nombre,
                                'fecha': fecha.strftime('%d/%m/%Y'),
                                'clase': horario.nombre,
                                'estado': 'Nuevo',
                                'nota': 'AUSENTE' if no_asistio else ''
                            })
                        else:
                            # Update existing record
                            clase_existente.profesor_id = profesor.id
                            clase_existente.hora_llegada_profesor = None if no_asistio else hora
                            clase_existente.cantidad_alumnos = alumnos
                            if no_asistio:
                                clase_existente.observaciones = "PROFESOR NO ASISTIÓ"
                            
                            resultados['actualizados'] += 1
                            resultados['detalles'].append({
                                'fila': fila_num,
                                'profesor': profesor.nombre,
                                'fecha': fecha.strftime('%d/%m/%Y'),
                                'clase': horario.nombre,
                                'estado': 'Actualizado',
                                'nota': 'AUSENTE' if no_asistio else ''
                            })
                        
                        # Commit the record
                        db.session.commit()
                        resultados['procesados'] += 1
                    
                    except Exception as e:
                        # Log detailed error information
                        error_info = {
                            'fila': fila_num,
                            'profesor': str(row.get('Intructor', '')),
                            'fecha': str(row.get('Fecha', '')),
                            'hora': str(row.get('Hora', '')),
                            'clase': str(row.get('Clase', '')),
                            'estado': 'Error',
                            'mensaje_error': str(e)
                        }
                        
                        # Registrar para depuración
                        with open('import_errors.log', 'a', encoding='utf-8') as f:
                            f.write(f"ERROR EN FILA {fila_num}:\n")
                            for k, v in error_info.items():
                                f.write(f"  {k}: {v}\n")
                            f.write("\n" + "-"*50 + "\n")
                        
                        # For user interface
                        resultados['errores'] += 1
                        resultados['detalles'].append({
                            'fila': fila_num,
                            'profesor': str(row.get('Intructor', '')),
                            'fecha': str(row.get('Fecha', '')),
                            'clase': str(row.get('Clase', '')),
                            'estado': 'Error',
                            'errores': [f"({type(e).__name__}) {str(e)}"]
                        })
                        
                # Log final result
                with open('import_debug.log', 'a', encoding='utf-8') as f:
                    f.write(f"Importación completada: {resultados['procesados']} procesados, {resultados['nuevos']} nuevos, "
                            f"{resultados['actualizados']} actualizados, {resultados['errores']} errores\n")
                
                # Show result to user
                if resultados['errores'] > 0:
                    flash(f"Importación completada con {resultados['errores']} errores. Se procesaron {resultados['procesados']} registros.", 'warning')
                else:
                    flash(f"Importación completada correctamente. Se procesaron {resultados['procesados']} registros.", 'success')
            
            except Exception as e:
                # Log global error
                with open('import_errors.log', 'a', encoding='utf-8') as f:
                    f.write(f"ERROR GLOBAL: {str(e)}\n")
                    f.write(f"{traceback.format_exc()}\n")
                
                flash(f"Error en la importación: {str(e)}", 'danger')
                resultados['errores'] += 1
        else:
            flash('Formato de archivo no permitido. Use archivos Excel (.xlsx, .xls)', 'danger')
    
    return render_template('importar/asistencia.html', titulo="Importar Asistencia", resultados=resultados)

@app.route('/import/asistencia', methods=['POST'])
def importar_asistencia_excel():
    """
    Procesa un archivo Excel con datos de asistencia y los importa al sistema.
    Los registros se asignarán al tipo de clase especificado por el usuario.
    """
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No se ha subido ningún archivo'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No se ha seleccionado ningún archivo'})
    
    # Verificar que se ha seleccionado un tipo de clase
    tipo_clase = request.form.get('tipo_clase')
    if not tipo_clase or tipo_clase not in ['MOVE', 'RIDE', 'BOX', 'OTRO']:
        return jsonify({'success': False, 'message': 'Debe seleccionar un tipo de clase válido (MOVE, RIDE, BOX, OTRO)'})
    
    # Resultados para devolver al cliente
    resultados = {
        'total': 0,
        'importados': 0,
        'errores': 0,
        'detalles': []
    }
    
    try:
        # Guardar temporalmente el archivo
        filename = secure_filename(file.filename)
        temp_filepath = os.path.join(app.instance_path, filename)
        os.makedirs(app.instance_path, exist_ok=True)
        file.save(temp_filepath)
        
        # Leer con pandas
        df = pd.read_excel(temp_filepath)
        
        # Eliminar el archivo temporal
        os.remove(temp_filepath)
        
        # Verificar columnas requeridas
        required_columns = ['Intructor', 'Fecha', 'Hora', 'Clase', 'Asistentes']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            return jsonify({
                'success': False, 
                'message': f'El archivo no contiene columnas requeridas: {", ".join(missing_columns)}'
            })
        
        # Actualizar el total de registros
        resultados['total'] = len(df)
        
        # Registrar inicio de importación
        with open('import_debug.log', 'a', encoding='utf-8') as f:
            f.write(f"\n=== INICIO IMPORTACIÓN {datetime.now()} ({resultados['total']} registros) ===\n")
            f.write(f"Tipo de clase seleccionado: {tipo_clase}\n")
        
        # Procesar cada fila
        for index, row in df.iterrows():
            fila_num = index + 2  # +2 porque Excel es 1-indexed y tenemos encabezado
            
            try:
                # Datos básicos
                instructor = str(row['Intructor']).strip()
                clase_nombre = str(row['Clase']).strip()
                alumnos = int(row['Asistentes']) if not pd.isna(row['Asistentes']) else 0
                
                # Procesar fecha
                fecha_str = row['Fecha']
                if isinstance(fecha_str, datetime):
                    fecha = fecha_str.date()
                elif isinstance(fecha_str, pd.Timestamp):
                    fecha = fecha_str.date()
                else:
                    # Intentar múltiples formatos de fecha
                    fecha = None
                    # Asegurar que sea string
                    fecha_str = str(fecha_str).strip()
                    # Probar formatos comunes de fecha
                    formatos_fecha = ['%d/%m/%Y', '%Y-%m-%d', '%m/%d/%Y', '%d-%m-%Y', '%d.%m.%Y']
                    for formato in formatos_fecha:
                        try:
                            fecha = datetime.strptime(fecha_str, formato).date()
                            break
                        except ValueError:
                            continue
                    
                    # Si aún no se pudo convertir, intentar con pandas
                    if fecha is None:
                        try:
                            fecha = pd.to_datetime(fecha_str, errors='raise', dayfirst=True).date()
                        except Exception as fecha_error:
                            raise ValueError(f"No se pudo convertir la fecha '{fecha_str}': {str(fecha_error)}")
                
                # Procesar hora
                hora_str = row['Hora']
                
                # Variable para seguimiento de la asistencia
                no_asistio = False
                
                # Comprobar si es "NO ASISTIO" u otro texto que indica ausencia
                if isinstance(hora_str, str) and any(texto in hora_str.upper() for texto in ["NO ASISTIO", "NO ASISTIÓ", "AUSENTE", "CANCELADO"]):
                    # Marcar como no asistido (usamos hora normal para el horario)
                    hora = time(0, 0)  # Hora predeterminada para el horario
                    no_asistio = True
                elif pd.isna(hora_str):
                    # Si el valor es NaN o está vacío
                    hora = time(0, 0)  # Usar medianoche como valor predeterminado
                elif isinstance(hora_str, (int, float)):
                    # Convertir decimal de Excel a tiempo
                    hora = excel_time_to_time(hora_str)
                    if hora is None:
                        raise ValueError(f"No se pudo convertir el valor {hora_str} a formato de hora")
                else:
                    # Asegurar que sea string y eliminar espacios
                    hora_str = str(hora_str).strip()
                    
                    # Convertir otros formatos
                    try:
                        if ':' in hora_str:
                            # Si tiene formato HH:MM o similar
                            # Check for AM/PM format
                            is_pm = 'PM' in hora_str.upper()
                            is_am = 'AM' in hora_str.upper()
                            # Remove AM/PM from string
                            hora_str = hora_str.upper().replace('AM', '').replace('PM', '').strip()
                            
                            partes = hora_str.split(':')
                            horas = int(partes[0])
                            minutos = int(partes[1]) if len(partes) > 1 else 0
                            
                            # Adjust hours for PM
                            if is_pm and horas < 12:
                                horas += 12
                            # Adjust for 12 AM
                            elif is_am and horas == 12:
                                horas = 0
                                
                            hora = time(horas, minutos)
                        else:
                            # Intentar con datetime primero
                            try:
                                hora = datetime.strptime(hora_str, '%H:%M').time()
                            except ValueError:
                                # Último intento con pandas
                                hora = pd.to_datetime(hora_str).time()
                    except Exception as e:
                        raise ValueError(f"No se pudo convertir la hora '{hora_str}': {str(e)}")
                
                # Find or create professor
                profesor_nombre = instructor
                if pd.isna(profesor_nombre) or not profesor_nombre:
                    raise ValueError("El nombre del instructor está vacío")
                
                profesor = Profesor.query.filter(Profesor.nombre.ilike(f"%{profesor_nombre}%")).first()
                if not profesor:
                    try:
                        # Create new professor with a default rate
                        profesor = Profesor(
                            nombre=profesor_nombre,
                            apellido='',  # Leave empty for now
                            email='',     # Leave empty for now
                            telefono='',  # Leave empty for now
                            tarifa_por_clase=0.0  # Default rate
                        )
                        db.session.add(profesor)
                        db.session.commit()
                    except Exception as e:
                        db.session.rollback()
                        raise ValueError(f"Error al crear profesor '{profesor_nombre}': {str(e)}")
                
                # Find or create class schedule
                # Usamos el tipo_clase que seleccionó el usuario en el formulario
                # Buscar un horario existente o crear uno nuevo
                dia_semana = fecha.weekday()
                horario = HorarioClase.query.filter_by(
                    dia_semana=dia_semana,
                    hora_inicio=hora,
                    tipo_clase=tipo_clase
                ).first()
                
                if not horario:
                    # Create new schedule with the class type from the form
                    horario = HorarioClase(
                        nombre=clase_nombre,
                        dia_semana=dia_semana,
                        hora_inicio=hora,
                        duracion=60,  # Default duration
                        profesor_id=profesor.id,
                        tipo_clase=tipo_clase  # Use the selected class type
                    )
                    db.session.add(horario)
                    db.session.commit()
                
                # Check if this class session already exists
                clase_existente = ClaseRealizada.query.filter_by(
                    fecha=fecha,
                    horario_id=horario.id
                ).first()
                
                if not clase_existente:
                    # Create new record
                    nueva_clase = ClaseRealizada(
                        fecha=fecha,
                        horario_id=horario.id,
                        profesor_id=profesor.id,
                        hora_llegada_profesor=None if no_asistio else hora,
                        cantidad_alumnos=alumnos,
                        observaciones="PROFESOR NO ASISTIÓ" if no_asistio else ""
                    )
                    db.session.add(nueva_clase)
                    
                    resultados['importados'] += 1
                    resultados['detalles'].append({
                        'fila': fila_num,
                        'profesor': profesor.nombre,
                        'fecha': fecha.strftime('%d/%m/%Y'),
                        'clase': horario.nombre,
                        'estado': 'Importado',
                        'tipo': tipo_clase
                    })
                else:
                    # Update existing record
                    clase_existente.profesor_id = profesor.id
                    clase_existente.hora_llegada_profesor = None if no_asistio else hora
                    clase_existente.cantidad_alumnos = alumnos
                    if no_asistio:
                        clase_existente.observaciones = "PROFESOR NO ASISTIÓ"
                    
                    resultados['importados'] += 1
                    resultados['detalles'].append({
                        'fila': fila_num,
                        'profesor': profesor.nombre,
                        'fecha': fecha.strftime('%d/%m/%Y'),
                        'clase': horario.nombre,
                        'estado': 'Actualizado',
                        'tipo': tipo_clase
                    })
                
                # Commit the record
                db.session.commit()
                
            except Exception as e:
                # Registrar error con información detallada
                error_info = {
                    'fila': fila_num,
                    'profesor': str(row.get('Intructor', '')),
                    'fecha': str(row.get('Fecha', '')),
                    'hora': str(row.get('Hora', '')),
                    'clase': str(row.get('Clase', '')),
                    'estado': 'Error',
                    'mensaje_error': str(e)
                }
                
                # Registrar para depuración
                with open('import_errors.log', 'a', encoding='utf-8') as debug_file:
                    debug_file.write(f"ERROR EN FILA {fila_num}:\n")
                    for k, v in error_info.items():
                        debug_file.write(f"  {k}: {v}\n")
                    debug_file.write("\n" + "-"*50 + "\n")
                
                # Para interfaz de usuario
                resultados['errores'] += 1
                resultados['detalles'].append({
                    'fila': fila_num,
                    'profesor': str(row.get('Intructor', '')),
                    'fecha': str(row.get('Fecha', '')),
                    'clase': str(row.get('Clase', '')),
                    'estado': 'Error',
                    'errores': [f"({type(e).__name__}) {str(e)}"]
                })
        
        # Log final result
        with open('import_debug.log', 'a', encoding='utf-8') as f:
            f.write(f"Importación completada: {resultados['total']} registros, {resultados['importados']} importados, "
                    f"{resultados['errores']} errores\n")
        
        return jsonify({
            'success': True,
            'message': f"Se importaron {resultados['importados']} registros de {resultados['total']} (Errores: {resultados['errores']})",
            'results': resultados
        })
    
    except Exception as e:
        # Log global error
        with open('import_errors.log', 'a', encoding='utf-8') as f:
            f.write(f"ERROR GLOBAL: {str(e)}\n")
            f.write(f"{traceback.format_exc()}\n")
        
        return jsonify({
            'success': False,
            'message': f"Error en la importación: {str(e)}",
            'results': resultados
        })

@app.route('/importar', methods=['GET'])
def importar_excel():
    return render_template('importar/excel.html')

# Inicializar la base de datos si no existe
@app.cli.command('init-db')
def init_db_command():
    """Inicializar la base de datos."""
    try:
        # Mostrar la configuración de la base de datos
        click.echo(f'URI de la base de datos: {app.config["SQLALCHEMY_DATABASE_URI"]}')
        click.echo(f'Directorio actual: {os.getcwd()}')
        
        # Crear todas las tablas
        db.create_all()
        
        # Verificar si el archivo se creó
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        if os.path.exists(db_path):
            click.echo(f'Base de datos creada correctamente en: {os.path.abspath(db_path)}')
        else:
            click.echo(f'No se encontró el archivo de base de datos en: {os.path.abspath(db_path)}')
    except Exception as e:
        click.echo(f'Error al inicializar la base de datos: {str(e)}')

@app.route('/asistencia/upload_audio/<int:horario_id>', methods=['POST'], endpoint='upload_audio_legacy2')
def upload_audio_legacy(horario_id):
    """Ruta legacy que redirige a la nueva ruta"""
    return redirect(url_for('audio_upload', horario_id=horario_id))

@app.route('/asistencia/get_audio/<int:horario_id>')
def get_audio_legacy(horario_id):
    """Ruta legacy que redirige a la nueva ruta"""
    return redirect(url_for('audio_get', horario_id=horario_id))

@app.route('/check_audio/<int:horario_id>')
def check_audio_legacy(horario_id):
    """Ruta legacy que redirige a la nueva ruta"""
    return redirect(url_for('audio_check', horario_id=horario_id))

@app.route('/test-old-upload')
def test_old_upload():
    """Ruta antigua con redirección automática via JavaScript"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta http-equiv="refresh" content="0;url=/test-upload">
        <script>
            // Redirección para APIs que usan la URL antigua
            if (window.fetch) {
                const originalFetch = window.fetch;
                window.fetch = function(url, options) {
                    if (url === '/asistencia/upload_audio/5') {
                        console.log('Redirigiendo fetch a nueva URL');
                        return originalFetch('/asistencia/audio/upload/5', options);
                    }
                    return originalFetch(url, options);
                };
            }
        </script>
    </head>
    <body>
        <p>Redirigiendo a la nueva página...</p>
    </body>
    </html>
    """

# Fix the audio route implementations - they are currently empty
@app.route('/asistencia/audio/upload/<int:horario_id>', methods=['POST'])
def audio_upload(horario_id):
    """Implement the main audio upload functionality"""
    try:
        app.logger.info(f"Audio upload request received for horario_id: {horario_id}")
        
        if 'audio' not in request.files:
            app.logger.warning(f"No audio file found in request for horario_id: {horario_id}")
            return jsonify({
                'success': False,
                'message': 'No audio file found in request',
                'error_code': 'NO_AUDIO_FILE'
            }), 400
        
        audio_file = request.files['audio']
        app.logger.info(f"Received file: {audio_file.filename} for horario_id: {horario_id}")
        
        if audio_file.filename == '':
            app.logger.warning(f"Empty filename received for horario_id: {horario_id}")
            return jsonify({
                'success': False,
                'message': 'No selected file or empty filename',
                'error_code': 'EMPTY_FILENAME'
            }), 400
        
        # Check file format
        allowed_extensions = {'mp3', 'wav', 'ogg', 'm4a'}
        file_ext = audio_file.filename.rsplit('.', 1)[1].lower() if '.' in audio_file.filename else ''
        
        if file_ext not in allowed_extensions:
            app.logger.warning(f"Invalid file format: {file_ext} for horario_id: {horario_id}")
            return jsonify({
                'success': False,
                'message': f"Formato de archivo no soportado. Por favor usa: {', '.join(allowed_extensions)}",
                'error_code': 'INVALID_FORMAT',
                'file_ext': file_ext,
                'allowed_extensions': list(allowed_extensions)
            }), 400
        
        if audio_file:
            # Asegurar que existen los directorios de almacenamiento
            ensure_upload_dirs()
            
            filename = secure_filename(audio_file.filename)
            timestamp = int(time_module.time())
            new_filename = f"audio_{timestamp}_{filename}"
            
            # Usar el nuevo sistema de almacenamiento organizado por horario_id
            storage_dir = get_audio_storage_path(horario_id)
            save_path = os.path.join(storage_dir, new_filename)
            
            try:
                # Eliminar archivos de audio anteriores para este horario
                try:
                    for old_file in os.listdir(storage_dir):
                        if old_file.startswith("audio_") and old_file != new_filename:
                            os.remove(os.path.join(storage_dir, old_file))
                            app.logger.info(f"Removed old audio file: {old_file} for horario_id: {horario_id}")
                except Exception as e:
                    app.logger.warning(f"Error cleaning old audio files: {str(e)}")
                
                # Guardar el nuevo archivo
                audio_file.save(save_path)
                app.logger.info(f"File saved successfully to {save_path} for horario_id: {horario_id}")
                
                file_size = os.path.getsize(save_path)
                file_size_readable = f"{file_size/1024:.2f} KB"
                
                # Ruta relativa del archivo para guardar en la base de datos
                relative_path = os.path.join(f'horario_{horario_id}', new_filename)
                
                # Update database if possible
                db_updated = False
                db_error = None
                try:
                    clase = ClaseRealizada.query.filter_by(horario_id=horario_id).order_by(ClaseRealizada.id.desc()).first()
                    if clase:
                        clase.audio_file = relative_path
                        db.session.commit()
                        db_updated = True
                        app.logger.info(f"Database updated for horario_id: {horario_id}, clase_id: {clase.id}")
                    else:
                        app.logger.warning(f"No ClaseRealizada found for horario_id: {horario_id}")
                except Exception as db_err:
                    db_error = str(db_err)
                    app.logger.error(f"Error updating database for horario_id: {horario_id}: {db_error}")
                
                return jsonify({
                    'success': True,
                    'message': 'Archivo subido exitosamente',
                    'file_path': f"/static/uploads/audios/permanent/{relative_path}",
                    'file_name': new_filename,
                    'file_size': file_size,
                    'file_size_readable': file_size_readable,
                    'db_updated': db_updated,
                    'db_error': db_error
                })
            except Exception as e:
                error_msg = str(e)
                app.logger.error(f"Error saving file for horario_id: {horario_id}: {error_msg}")
                return jsonify({
                    'success': False,
                    'message': f"Error al guardar el archivo: {error_msg}",
                    'error_code': 'SAVE_ERROR',
                    'error_details': error_msg
                }), 500
        
        app.logger.warning(f"Invalid file for horario_id: {horario_id}")
        return jsonify({
            'success': False,
            'message': 'Archivo invu00e1lido',
            'error_code': 'INVALID_FILE'
        }), 400
    except Exception as e:
        error_msg = str(e)
        app.logger.error(f"Unexpected error in audio_upload for horario_id: {horario_id}: {error_msg}")
        return jsonify({
            'success': False,
            'message': f"Error inesperado: {error_msg}",
            'error_code': 'UNEXPECTED_ERROR',
            'error_details': error_msg
        }), 500

@app.route('/asistencia/audio/get/<int:horario_id>')
def audio_get(horario_id):
    """Implement the function to get audio files"""
    try:
        app.logger.info(f"Audio get request received for horario_id: {horario_id}")
        
        clase = ClaseRealizada.query.filter_by(horario_id=horario_id).order_by(ClaseRealizada.id.desc()).first()
        
        if not clase:
            app.logger.warning(f"No clase found for horario_id: {horario_id}")
            return jsonify({
                'success': False,
                'message': 'No clase registrada found for this schedule',
                'error_code': 'NO_CLASE_FOUND'
            }), 404
            
        if not clase.audio_file:
            app.logger.warning(f"No audio file registered for horario_id: {horario_id}, clase_id: {clase.id}")
            return jsonify({
                'success': False,
                'message': 'No audio file registered for this class',
                'error_code': 'NO_AUDIO_REGISTERED',
                'clase_id': clase.id
            }), 404
        
        upload_folder = os.path.join(app.config.get('UPLOAD_FOLDER', 'static/uploads'), 'audios')
        audio_path = os.path.join(upload_folder, clase.audio_file) if clase.audio_file else None
        app.logger.info(f"Attempting to serve audio file: {audio_path}")
        
        if not os.path.exists(audio_path):
            app.logger.warning(f"Audio file not found on server: {audio_path}")
            
            # Intentar buscar el archivo en la nueva estructura
            try:
                audio_dir = get_audio_storage_path(horario_id)
                if os.path.exists(audio_dir):
                    files = os.listdir(audio_dir)
                    audio_files = [f for f in files if f.startswith('audio_')]
                    if audio_files:
                        # Usar el archivo más reciente
                        audio_files.sort(reverse=True)
                        newest_audio = audio_files[0]
                        audio_path = os.path.join(audio_dir, newest_audio)
                        app.logger.info(f"Found audio file in new structure: {audio_path}")
                        
                        # Actualizar la base de datos con la nueva ruta
                        relative_path = os.path.join(f'horario_{horario_id}', newest_audio)
                        clase.audio_file = relative_path
                        db.session.commit()
                        app.logger.info(f"Updated database with new audio path: {relative_path}")
                    else:
                        app.logger.warning(f"No audio files found in directory: {audio_dir}")
            except Exception as e:
                app.logger.error(f"Error searching for audio files: {str(e)}")
            
            # Si aún no encontramos el archivo, devolver error
            if not os.path.exists(audio_path):
                return jsonify({
                    'success': False,
                    'message': 'Audio file registered but not found on server',
                    'error_code': 'FILE_NOT_FOUND',
                    'file_name': clase.audio_file,
                    'clase_id': clase.id
                }), 404
        
        # Get file size for logging
        file_size = os.path.getsize(audio_path)
        app.logger.info(f"Serving audio file for horario_id: {horario_id}, size: {file_size/1024:.2f} KB")
        
        # Return the file with the correct MIME type
        extension = clase.audio_file.rsplit('.', 1)[1].lower() if '.' in clase.audio_file else 'mp3'
        mime_types = {
            'mp3': 'audio/mpeg',
            'wav': 'audio/wav',
            'ogg': 'audio/ogg',
            'm4a': 'audio/m4a'
        }
        mime_type = mime_types.get(extension, 'audio/mpeg')
        
        return send_file(audio_path, mimetype=mime_type, as_attachment=False)
    except Exception as e:
        error_msg = str(e)
        app.logger.error(f"Error getting audio for horario_id: {horario_id}: {error_msg}")
        return jsonify({
            'success': False,
            'has_audio': False,
            'message': f"Error retrieving audio file: {error_msg}",
            'error_details': error_msg
        }), 500

@app.route('/asistencia/audio/check/<int:horario_id>')
def audio_check(horario_id):
    """Implement the function to check if audio exists"""
    try:
        app.logger.info(f"Audio check request for horario_id: {horario_id}")
        
        clase = ClaseRealizada.query.filter_by(horario_id=horario_id).order_by(ClaseRealizada.id.desc()).first()
        
        # Primero, intentemos buscar en la nueva estructura, incluso si no hay registro en la BD
        audio_dir = get_audio_storage_path(horario_id)
        audio_files = []
        newest_audio = None
        newest_audio_path = None
        
        if os.path.exists(audio_dir):
            try:
                files = os.listdir(audio_dir)
                audio_files = [f for f in files if f.startswith('audio_')]
                if audio_files:
                    audio_files.sort(reverse=True)
                    newest_audio = audio_files[0]
                    newest_audio_path = os.path.join(audio_dir, newest_audio)
                    app.logger.info(f"Found audio file in storage: {newest_audio_path}")
                    
                    # Actualizar la base de datos con la nueva ruta
                    relative_path = os.path.join(f'horario_{horario_id}', newest_audio)
                    clase.audio_file = relative_path
                    db.session.commit()
                    app.logger.info(f"Updated database with found audio: {relative_path}")
                else:
                    app.logger.warning(f"No audio files found in directory: {audio_dir}")
            except Exception as e:
                app.logger.error(f"Error searching for audio files: {str(e)}")
        
        # Si encontramos un archivo pero no hay registro en la BD o el registro es incorrecto
        if newest_audio_path and (not clase or not clase.audio_file or not os.path.exists(os.path.join(app.config.get('UPLOAD_FOLDER', 'static/uploads'), 'audios', 'permanent', clase.audio_file))):
            if clase:
                # Actualizar la BD con la nueva ruta
                relative_path = os.path.join(f'horario_{horario_id}', newest_audio)
                clase.audio_file = relative_path
                db.session.commit()
                app.logger.info(f"Updated database with found audio: {relative_path}")
            elif newest_audio_path:
                app.logger.warning(f"Found audio file but no clase record for horario_id: {horario_id}")
                return jsonify({
                    'success': True,
                    'has_audio': True,
                    'exists': True,
                    'file_name': newest_audio,
                    'file_path': f"/static/uploads/audios/permanent/horario_{horario_id}/{newest_audio}",
                    'file_size': os.path.getsize(newest_audio_path),
                    'file_size_readable': f"{os.path.getsize(newest_audio_path)/1024:.2f} KB",
                    'clase_id': None,
                    'fecha': None
                })
        
        # Si no hay registro en la base de datos y no encontramos archivo
        if not clase and not newest_audio_path:
            app.logger.info(f"No audio registered for horario_id: {horario_id}")
            return jsonify({
                'success': True,
                'has_audio': False,
                'message': 'No audio registered'
            })
            
        # Si hay registro pero no tiene audio
        if clase and not clase.audio_file and not newest_audio_path:
            app.logger.info(f"No audio registered in database for horario_id: {horario_id}")
            return jsonify({
                'success': True,
                'has_audio': False,
                'message': 'No audio registered in database'
            })
        
        # Verificar la ruta del audio en la base de datos
        upload_folder = os.path.join(app.config.get('UPLOAD_FOLDER', 'static/uploads'), 'audios')
        audio_path = None
        
        # Determinar la ruta del audio según el formato almacenado
        if clase and clase.audio_file:
            if clase.audio_file.startswith('horario_') or '/' in clase.audio_file or '\\' in clase.audio_file:
                audio_path = os.path.join(upload_folder, 'permanent', clase.audio_file)
            else:
                # Compatibilidad con formato antiguo
                audio_path = os.path.join(upload_folder, clase.audio_file)
        elif newest_audio_path:
            audio_path = newest_audio_path
        
        if audio_path and os.path.exists(audio_path):
            file_size = os.path.getsize(audio_path)
            app.logger.info(f"Audio file exists for horario_id: {horario_id}, size: {file_size/1024:.2f} KB")
            
            # Extraer el nombre del archivo de la ruta
            file_name = os.path.basename(audio_path)
            
            # Determinar la ruta relativa para el frontend
            if audio_path == newest_audio_path:
                file_path = f"/static/uploads/audios/permanent/horario_{horario_id}/{file_name}"
            elif clase and clase.audio_file and clase.audio_file.startswith('horario_'):
                file_path = f"/static/uploads/audios/permanent/{clase.audio_file}"
            else:
                file_path = f"/static/uploads/audios/{file_name}"
            
            return jsonify({
                'success': True,
                'has_audio': True,
                'exists': True,
                'file_name': file_name,
                'file_path': file_path,
                'file_size': file_size,
                'file_size_readable': f"{file_size/1024:.2f} KB",
                'clase_id': clase.id if clase else None,
                'fecha': clase.fecha.strftime('%Y-%m-%d') if clase and clase.fecha else None
            })
        else:
            app.logger.warning(f"Audio file registered but not found on disk for horario_id: {horario_id}")
            
            # Si tenemos un registro en la BD pero el archivo no existe
            if clase and clase.audio_file:
                file_name = os.path.basename(clase.audio_file) if '/' in clase.audio_file or '\\' in clase.audio_file else clase.audio_file
                return jsonify({
                    'success': True,
                    'has_audio': False,
                    'exists': False,
                    'message': 'The file is registered in the database but does not exist on disk',
                    'file_name': file_name,
                    'clase_id': clase.id
                })
            else:
                return jsonify({
                    'success': True,
                    'has_audio': False,
                    'exists': False,
                    'message': 'No audio file found on disk'
                })
    except Exception as e:
        error_msg = str(e)
        app.logger.error(f"Error checking audio for horario_id: {horario_id}: {error_msg}")
        return jsonify({
            'success': False,
            'has_audio': False,
            'message': f"Error checking audio: {error_msg}",
            'error_details': error_msg
        }), 500

@app.route('/asistencia/audio/diagnostico')
def audio_diagnostics():
    """Diagnostics endpoint for audio files"""
    try:
        app.logger.info("Audio diagnostics requested")
        
        # Basic info
        upload_folder = app.config.get('UPLOAD_FOLDER', 'static/uploads')
        audio_folder = os.path.join(upload_folder, 'audios')
        
        # Ensure audio folder exists
        os.makedirs(audio_folder, exist_ok=True)
        
        # Gather disk stats
        disk_stats = {}
        try:
            total, used, free = shutil.disk_usage(audio_folder)
            disk_stats = {
                'total_gb': f"{total / (1024**3):.2f} GB",
                'used_gb': f"{used / (1024**3):.2f} GB",
                'free_gb': f"{free / (1024**3):.2f} GB",
                'usage_percent': f"{used / total * 100:.1f}%"
            }
        except Exception as e:
            disk_stats['error'] = str(e)
        
        # Count audio files in the folder
        audio_files = []
        try:
            if os.path.exists(audio_folder):
                for filename in os.listdir(audio_folder):
                    if filename.startswith('audio_'):
                        file_path = os.path.join(audio_folder, filename)
                        file_size = os.path.getsize(file_path)
                        file_time = os.path.getmtime(file_path)
                        
                        audio_files.append({
                            'filename': filename,
                            'size_kb': f"{file_size/1024:.2f} KB",
                            'last_modified': datetime.fromtimestamp(file_time).strftime('%Y-%m-%d %H:%M:%S')
                        })
        except Exception as e:
            app.logger.error(f"Error listing audio files: {str(e)}")
        
        # Get recent classes with audio
        recent_classes = []
        try:
            # Filter to last 30 days
            thirty_days_ago = datetime.now() - timedelta(days=30)
            classes_with_audio = ClaseRealizada.query.filter(
                ClaseRealizada.audio_file.isnot(None),
                ClaseRealizada.fecha >= thirty_days_ago
            ).order_by(ClaseRealizada.fecha.desc()).limit(10).all()
            
            for clase in classes_with_audio:
                audio_path = os.path.join(audio_folder, clase.audio_file) if clase.audio_file else None
                file_exists = audio_path and os.path.exists(audio_path)
                
                recent_classes.append({
                    'id': clase.id,
                    'horario_id': clase.horario_id,
                    'fecha': clase.fecha.strftime('%Y-%m-%d') if clase.fecha else None,
                    'asignatura': clase.horario.nombre if clase.horario else "Desconocida",
                    'audio_file': clase.audio_file,
                    'file_exists': file_exists
                })
        except Exception as e:
            app.logger.error(f"Error getting recent classes: {str(e)}")
        
        # Summary counts
        summary = {
            'total_audio_files': len(audio_files),
            'recent_classes_with_audio': len(recent_classes),
            'audio_folder': audio_folder,
            'folder_exists': os.path.exists(audio_folder)
        }
        
        return jsonify({
            'success': True,
            'summary': summary,
            'disk_stats': disk_stats,
            'recent_audio_files': sorted(audio_files, key=lambda x: x['last_modified'], reverse=True)[:10],
            'recent_classes': recent_classes
        })
    except Exception as e:
        app.logger.error(f"Error in audio diagnostics: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Error en diagnóstico de audio: {str(e)}"
        }), 500

# Agregar ruta para configuración de notificaciones
@app.route('/configuracion/notificaciones', methods=['GET', 'POST'])
def configuracion_notificaciones():
    """Configuración de notificaciones y alertas"""
    from notifications import check_and_notify_unregistered_classes, send_whatsapp_notification, is_notification_locked

    if request.method == 'POST':
        # Guardar la configuración del número de teléfono
        telefono = request.form.get('telefono_notificaciones', '').strip()
        
        # Validar que el número tenga el formato correcto
        if not telefono:
            flash('Ingrese un número de teléfono válido', 'danger')
        elif not telefono.startswith('+'):
            flash('El número debe incluir el código del país con el prefijo "+" (por ejemplo, +34612345678)', 'warning')
            telefono = '+' + telefono  # Intentar arreglarlo añadiendo el +
        
        if telefono:
            # Guardar en el archivo de configuración como variable de entorno permanente
            try:
                # Actualizar run.bat con el nuevo número
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
                    
                    with open(run_bat_path, 'w', encoding='utf-8') as file:
                        file.write(content)
            except Exception as e:
                app.logger.error(f"Error al actualizar run.bat: {str(e)}")
            
            # Guardar en las variables actuales
            os.environ['NOTIFICATION_PHONE_NUMBER'] = telefono
            app.config['NOTIFICATION_PHONE_NUMBER'] = telefono
            
            flash(f'Configuración de notificaciones actualizada. Número configurado: {telefono}', 'success')
            
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
    
    return render_template('configuracion/notificaciones.html', 
                          telefono_actual=current_phone)

# Agregar ruta para configuración de exportación de base de datos
@app.route('/configuracion/exportar', methods=['GET', 'POST'])
def configuracion_exportar():
    """Configuración de exportación de base de datos a Excel"""
    from export_to_excel import export_tables_to_excel
    
    # Valores predeterminados
    nivel_proteccion = 'completa'
    directorio = 'backups'
    excel_unificado = True
    excel_individuales = True
    mensaje_resultado = None
    archivos_exportados = []
    
    if request.method == 'POST':
        # Obtener parámetros del formulario
        nivel_proteccion = request.form.get('proteccion_datos', 'completa')
        directorio = request.form.get('directorio', 'backups').strip()
        excel_unificado = 'excel_unificado' in request.form
        excel_individuales = 'excel_individuales' in request.form
        
        # Validar que al menos una opción de exportación esté seleccionada
        if not excel_unificado and not excel_individuales:
            flash('Debe seleccionar al menos un formato de exportación', 'danger')
        else:
            try:
                # Realizar la exportación
                db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gimnasio.db')
                resultados = export_tables_to_excel(
                    db_path=db_path,
                    output_dir=directorio,
                    protection_level=nivel_proteccion,
                    create_unified=excel_unificado,
                    create_individual=excel_individuales
                )
                
                # Preparar mensaje de éxito
                total_tablas = len([k for k in resultados.keys() if k != 'completo'])
                total_registros = sum(info['row_count'] for tabla, info in resultados.items() if tabla != 'completo')
                
                mensaje_resultado = f"Exportación completada con éxito. Se exportaron {total_tablas} tablas con un total de {total_registros} registros."
                
                # Obtener lista de archivos exportados para mostrar
                for tabla, info in resultados.items():
                    archivos_exportados.append(info['file_path'])
                
                flash(mensaje_resultado, 'success')
            except Exception as e:
                flash(f'Error durante la exportación: {str(e)}', 'danger')
                app.logger.error(f"Error en exportación a Excel: {str(e)}")
    
    return render_template('configuracion/exportar_base_datos.html',
                          nivel_proteccion=nivel_proteccion,
                          directorio=directorio,
                          excel_unificado=excel_unificado,
                          excel_individuales=excel_individuales,
                          mensaje_resultado=mensaje_resultado,
                          archivos_exportados=archivos_exportados)

# Función para asegurar que los directorios de carga existan
def ensure_upload_dirs():
    """
    Asegura que los directorios necesarios para la carga de archivos existan.
    Crea los directorios si no existen.
    """
    app.logger.info("Verificando directorios de carga...")
    upload_base = app.config.get('UPLOAD_FOLDER', 'static/uploads')
    os.makedirs(upload_base, exist_ok=True)
    
    audio_dir = os.path.join(upload_base, 'audios')
    os.makedirs(audio_dir, exist_ok=True)
    
    permanent_audio_dir = os.path.join(audio_dir, 'permanent')
    os.makedirs(permanent_audio_dir, exist_ok=True)
    
    # Comprobar permisos de escritura
    test_file_path = os.path.join(upload_base, '.write_test')
    try:
        with open(test_file_path, 'w') as f:
            f.write('test')
        os.remove(test_file_path)
        app.logger.info(f"Directories created and write permissions verified: {upload_base}")
        return True
    except Exception as e:
        app.logger.error(f"Error checking write permissions: {str(e)}")
        return False

# Función para gestionar archivos de audio
def get_audio_storage_path(horario_id, filename=None):
    """
    Genera la ruta para almacenar o recuperar un archivo de audio.
    Si filename es None, devuelve el directorio para el horario_id.
    """
    upload_base = app.config.get('UPLOAD_FOLDER', 'static/uploads')
    permanent_audio_dir = os.path.join(upload_base, 'audios', 'permanent')
    
    # Crear directorio específico para este horario si no existe
    horario_dir = os.path.join(permanent_audio_dir, f'horario_{horario_id}')
    os.makedirs(horario_dir, exist_ok=True)
    
    if filename is None:
        return horario_dir
    else:
        return os.path.join(horario_dir, filename)

@app.route('/asistencia/fecha/<string:fecha>/<int:horario_id>', methods=['GET', 'POST'])
def registrar_asistencia_fecha(fecha, horario_id):
    """Registrar asistencia para una fecha específica y horario"""
    try:
        fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
    except ValueError:
        flash('Formato de fecha inválido', 'danger')
        return redirect(url_for('control_asistencia'))
    
    horario = HorarioClase.query.get_or_404(horario_id)
    
    # Verificar si la clase ya está registrada
    clase_existente = ClaseRealizada.query.filter_by(fecha=fecha_obj, horario_id=horario_id).first()
    if clase_existente:
        return redirect(url_for('editar_asistencia', id=clase_existente.id))
    
    # Procesar el formulario si es POST
    if request.method == 'POST':
        hora_llegada_str = request.form.get('hora_llegada')
        cantidad_alumnos = request.form.get('cantidad_alumnos', type=int)
        observaciones = request.form.get('observaciones')
        
        # Convertir hora de llegada a objeto Time
        if hora_llegada_str:
            try:
                hora_llegada = datetime.strptime(hora_llegada_str, '%H:%M').time()
            except ValueError:
                flash('Formato de hora inválido. Use HH:MM', 'danger')
                return render_template('asistencia/registrar.html', horario=horario, fecha=fecha_obj, hoy=fecha_obj)
        else:
            hora_llegada = None
        
        # Crear y guardar la nueva clase
        nueva_clase = ClaseRealizada(
            fecha=fecha_obj,
            horario_id=horario.id,
            profesor_id=horario.profesor_id,
            hora_llegada_profesor=hora_llegada,
            cantidad_alumnos=cantidad_alumnos,
            observaciones=observaciones
        )
        db.session.add(nueva_clase)
        db.session.commit()
        
        flash(f'Asistencia para la clase {horario.nombre} del {fecha_obj.strftime("%d/%m/%Y")} registrada con éxito', 'success')
        return redirect(url_for('control_asistencia'))
    
    return render_template('asistencia/registrar.html', horario=horario, fecha=fecha_obj, hoy=fecha_obj)


@app.route('/asistencia/registrar-clases-masivo', methods=['POST'])
@app.route('/registrar-clases-no-registradas', methods=['POST'])  # Alias para mantener compatibilidad
def registrar_clases_no_registradas():
    """Registrar múltiples clases no registradas de forma masiva"""
    if request.method == 'POST':
        clases_ids = request.form.getlist('clases_ids[]')
        
        if not clases_ids:
            flash('No seleccionó ninguna clase para registrar', 'warning')
            return redirect(url_for('informe_mensual'))
        
        clases_registradas = 0
        
        for clase_id in clases_ids:
            try:
                # El formato es 'YYYY-MM-DD|horario_id'
                partes = clase_id.split('|')
                fecha = partes[0]
                horario_id = int(partes[1])
                
                fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
                horario = HorarioClase.query.get(horario_id)
                
                if not horario:
                    continue
                
                # Verificar si ya existe un registro para esta clase
                clase_existente = ClaseRealizada.query.filter_by(
                    fecha=fecha_obj, 
                    horario_id=horario_id
                ).first()
                
                if clase_existente:
                    continue
                
                # Crear un nuevo registro con 0 alumnos
                nueva_clase = ClaseRealizada(
                    fecha=fecha_obj,
                    horario_id=horario_id,
                    profesor_id=horario.profesor_id,
                    hora_llegada_profesor=horario.hora_inicio,  # Por defecto, la hora programada
                    cantidad_alumnos=0,
                    observaciones="Registrada automáticamente"
                )
                
                db.session.add(nueva_clase)
                clases_registradas += 1
                
            except Exception as e:
                # Registrar el error pero continuar con las otras clases
                app.logger.error(f"Error al registrar clase {clase_id}: {str(e)}")
                continue
        
        if clases_registradas > 0:
            db.session.commit()
            flash(f'Se registraron {clases_registradas} clases correctamente', 'success')
        else:
            flash('No se registró ninguna clase nueva', 'warning')
        
        # Redirigir a la misma página de informe para ver los resultados actualizados
        # Volvemos a la página de selección de mes y año
        return redirect(url_for('informe_mensual'))

# Add initialization code to ensure the application starts correctly
if __name__ == '__main__':
    # Ensure upload directories exist
    ensure_upload_dirs()
    
    # Create database tables if they don't exist yet
    with app.app_context():
        db.create_all()
    
    # Inicializar scheduler de notificaciones para clases no registradas
    setup_notification_scheduler(app)
    
    # Start the app
    app.run(debug=True, port=8111)
