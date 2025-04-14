import os
import logging
import traceback
import re  # para expresiones regulares
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort, send_file, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
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
from notifications import update_notification_schedule, DEFAULT_NOTIFICATION_HOUR_1, DEFAULT_NOTIFICATION_HOUR_2

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
def now_filter(value=None):
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
    
    # Eliminar el horario y todas sus clases asociadas
    clases_asociadas = ClaseRealizada.query.filter_by(horario_id=id).all()
    
    # Eliminar todas las clases asociadas
    for clase in clases_asociadas:
        # Si la clase tiene archivo de audio, eliminar el archivo
        if clase.audio_file:
            try:
                audio_path = os.path.join(app.config.get('UPLOAD_FOLDER', 'static/uploads'), clase.audio_file)
                if os.path.exists(audio_path):
                    os.remove(audio_path)
            except Exception as e:
                app.logger.error(f"Error eliminando archivo de audio: {str(e)}")
        
        db.session.delete(clase)
    
    # Eliminar el horario
    db.session.delete(horario)
    db.session.commit()
    
    if clases_asociadas:
        flash(f'Horario de clase y {len(clases_asociadas)} clases asociadas eliminadas con éxito.', 'success')
    else:
        flash('Horario de clase eliminado con éxito', 'success')
    
    return redirect(url_for('listar_horarios'))

@app.route('/horarios/confirmar-eliminar/<int:id>', methods=['GET', 'POST'])
def confirmar_eliminar_horario(id):
    horario = HorarioClase.query.get_or_404(id)
    
    # Contar cuántas clases realizadas están asociadas
    clases_asociadas = ClaseRealizada.query.filter_by(horario_id=id).all()
    cantidad_clases = len(clases_asociadas)
    
    if request.method == 'POST':
        opcion = request.form.get('opcion')
        
        if opcion == 'solo_horario':
            # Opción 1: Eliminar solo el horario, pero las clases no pueden quedar huérfanas
            # ya que horario_id es NOT NULL en la tabla clase_realizada
            
            # Buscar o crear un horario especial "Horario Eliminado" para mantener la referencia
            horario_eliminado = HorarioClase.query.filter_by(nombre="Horario Eliminado (Clases Históricas)").first()
            
            if not horario_eliminado:
                # Crear un horario especial si no existe
                horario_eliminado = HorarioClase(
                    nombre="Horario Eliminado (Clases Históricas)",
                    dia_semana=0,  # Lunes
                    hora_inicio=datetime.strptime("00:00", '%H:%M').time(),
                    duracion=0,
                    profesor_id=horario.profesor_id,  # Mantener el mismo profesor
                    capacidad_maxima=0,
                    tipo_clase="OTRO"
                )
                db.session.add(horario_eliminado)
                db.session.flush()  # Para obtener el ID sin hacer commit
            
            # Mover todas las clases asociadas al horario eliminado
            for clase in clases_asociadas:
                clase.horario_id = horario_eliminado.id
            
            # Eliminar el horario original
            db.session.delete(horario)
            db.session.commit()
            flash(f'Horario de clase eliminado con éxito. {cantidad_clases} clases asociadas se mantienen en el sistema con referencia a "Horario Eliminado".', 'success')
            
        elif opcion == 'horario_y_clases':
            # Opción 2: Eliminar el horario y todas las clases asociadas
            for clase in clases_asociadas:
                # Si la clase tiene archivo de audio, eliminar el archivo
                if clase.audio_file:
                    try:
                        audio_path = os.path.join(app.config.get('UPLOAD_FOLDER', 'static/uploads'), clase.audio_file)
                        if os.path.exists(audio_path):
                            os.remove(audio_path)
                    except Exception as e:
                        app.logger.error(f"Error eliminando archivo de audio: {str(e)}")
                
                db.session.delete(clase)
            
            db.session.delete(horario)
            db.session.commit()
            flash(f'Horario de clase y {cantidad_clases} clases asociadas eliminadas con éxito.', 'success')
        else:
            flash('Operación cancelada', 'info')
            
        return redirect(url_for('listar_horarios'))
    
    return render_template('horarios/confirmar_eliminar.html', 
                           horario=horario, 
                           cantidad_clases=cantidad_clases)

@app.route('/horarios/eliminar-varios', methods=['POST'])
def eliminar_varios_horarios():
    horarios_ids = request.form.getlist('horarios_ids[]')
    if not horarios_ids:
        flash('No se han seleccionado horarios para eliminar', 'warning')
        return redirect(url_for('listar_horarios'))
    
    horarios_eliminados = 0
    clases_eliminadas = 0
    
    for horario_id in horarios_ids:
        horario = HorarioClase.query.get(horario_id)
        if horario:
            # Eliminar todas las clases asociadas a este horario
            clases_asociadas = ClaseRealizada.query.filter_by(horario_id=horario_id).all()
            
            # Eliminar los archivos de audio de las clases
            for clase in clases_asociadas:
                if clase.audio_file:
                    try:
                        audio_path = os.path.join(app.config.get('UPLOAD_FOLDER', 'static/uploads'), clase.audio_file)
                        if os.path.exists(audio_path):
                            os.remove(audio_path)
                    except Exception as e:
                        app.logger.error(f"Error eliminando archivo de audio: {str(e)}")
                
                db.session.delete(clase)
                clases_eliminadas += 1
            
            # Eliminar el horario
            db.session.delete(horario)
            horarios_eliminados += 1
    
    db.session.commit()
    
    if horarios_eliminados > 0:
        if clases_eliminadas > 0:
            flash(f'Se eliminaron {horarios_eliminados} horarios y {clases_eliminadas} clases asociadas con éxito', 'success')
        else:
            flash(f'Se eliminaron {horarios_eliminados} horarios con éxito', 'success')
    
    return redirect(url_for('listar_horarios'))

# Rutas para Control de Asistencia
@app.route('/asistencia')
def control_asistencia():
    # Mostrar las clases programadas para hoy que no tienen registro de asistencia
    try:
        hoy = datetime.now().date()
        # En Python, weekday() devuelve 0 (lunes) a 6 (domingo)
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
        
        # Obtener el profesor_id del formulario o usar el del horario por defecto
        profesor_id = request.form.get('profesor_id')
        if not profesor_id:
            profesor_id = horario.profesor_id
        else:
            profesor_id = int(profesor_id)
        
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
                profesor_id=profesor_id,
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
    
    # Obtener todos los profesores para el selector
    profesores = Profesor.query.all()
    
    return render_template('asistencia/registrar.html', horario=horario, hoy=hoy, profesores=profesores)

@app.route('/asistencia/editar/<int:id>', methods=['GET', 'POST'])
def editar_asistencia(id):
    clase_realizada = ClaseRealizada.query.get_or_404(id)
    
    if request.method == 'POST':
        hora_llegada = None
        if request.form['hora_llegada']:
            hora_llegada = datetime.strptime(request.form['hora_llegada'], '%H:%M').time()
        
        # Actualizar la fecha de la clase
        if request.form['fecha']:
            nueva_fecha = datetime.strptime(request.form['fecha'], '%Y-%m-%d').date()
            clase_realizada.fecha = nueva_fecha
        
        # Actualizar el profesor si se cambió
        if 'profesor_id' in request.form and request.form['profesor_id']:
            clase_realizada.profesor_id = int(request.form['profesor_id'])
        
        clase_realizada.hora_llegada_profesor = hora_llegada
        clase_realizada.cantidad_alumnos = int(request.form['cantidad_alumnos'])
        clase_realizada.observaciones = request.form['observaciones']
        
        db.session.commit()
        flash('Registro de asistencia actualizado con éxito', 'success')
        
        # Redireccionar según la fecha de la clase actualizada
        hoy = datetime.now().date()
        if clase_realizada.fecha == hoy:
            return redirect(url_for('control_asistencia'))
        else:
            return redirect(url_for('historial_asistencia'))
    
    # Obtener todos los profesores para el selector
    profesores = Profesor.query.all()
    
    # Obtener la fecha actual para compararla en la plantilla
    hoy = datetime.now().date()
    
    return render_template('asistencia/editar.html', clase=clase_realizada, profesores=profesores, hoy=hoy)

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

@app.route('/asistencia/clases-no-registradas')
def clases_no_registradas():
    """
    Muestra un historial de clases que no fueron registradas en su día
    para facilitar su registro posterior
    """
    # Parámetros de filtro
    fecha_inicio_str = request.args.get('fecha_inicio')
    fecha_fin_str = request.args.get('fecha_fin')
    profesor_id = request.args.get('profesor_id')
    refresh = request.args.get('refresh')  # Usar para forzar actualización
    clear_cache = request.args.get('clear_cache')  # Para forzar limpieza de caché
    
    # Mensaje de depuración
    timestamp_actual = int(time_module.time())
    print(f"DEBUG: Ejecutando clases_no_registradas con timestamp: {timestamp_actual}, refresh: {refresh}, clear_cache: {clear_cache}")
    
    # Si se solicita limpiar la caché, forzar una actualización de la sesión
    if clear_cache == '1':
        print("DEBUG: Limpiando caché de la sesión")
        # Forzar sincronización de la base de datos
        db.session.commit()
        # Cerrar y reabrir la sesión
        db.session.close()
        db.session = db.create_scoped_session()
        # Limpiar también la caché de SQLAlchemy
        db.session.expire_all()
    
    # Fecha por defecto: últimos 30 días
    hoy = datetime.now().date()
    fecha_inicio = hoy - timedelta(days=30)
    fecha_fin = hoy - timedelta(days=1)  # Hasta ayer
    
    # Aplicar filtros si existen
    if fecha_inicio_str:
        fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
    
    if fecha_fin_str:
        fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
    
    # 1. Obtener todos los horarios activos
    horarios = HorarioClase.query
    if profesor_id and profesor_id != 'todos':
        horarios = horarios.filter_by(profesor_id=int(profesor_id))
    horarios = horarios.all()
    
    # 2. Generar todas las fechas en el rango
    fechas = []
    fecha_actual = fecha_inicio
    while fecha_actual <= fecha_fin:
        fechas.append(fecha_actual)
        fecha_actual += timedelta(days=1)
    
    # 3. Crear un diccionario de clases ya registradas para búsqueda eficiente
    # Formato: {(fecha, horario_id): True}
    clases_registradas_dict = {}
    
    # Obtener todas las clases registradas en el período - USANDO CONSULTA FRESCA
    # Evitar usar ORM para asegurar que obtenemos los datos más recientes
    sql = """
    SELECT id, fecha, horario_id, profesor_id 
    FROM clase_realizada 
    WHERE fecha >= :fecha_inicio AND fecha <= :fecha_fin
    """
    # Crear una conexión fresca para asegurar que no hay caché
    connection = db.engine.connect()
    result = connection.execute(sql, {
        'fecha_inicio': fecha_inicio, 
        'fecha_fin': fecha_fin
    })
    
    # Procesar los resultados de la consulta directa
    clases_realizadas = []
    for row in result:
        clases_realizadas.append({
            'id': row[0],
            'fecha': row[1],
            'horario_id': row[2],
            'profesor_id': row[3]
        })
        # Agregar al diccionario para búsqueda rápida
        key = (row[1], row[2])  # fecha, horario_id
        clases_registradas_dict[key] = True
        print(f"DEBUG: Clase registrada encontrada - Fecha: {row[1]}, Horario ID: {row[2]}, ID: {row[0]}")
    
    # Cerrar la conexión después de usarla
    connection.close()
    
    # 4. Generar las clases esperadas que NO están registradas
    clases_no_registradas = []
    for horario in horarios:
        for fecha in fechas:
            # Si el día de la semana coincide con el día del horario
            if fecha.weekday() == horario.dia_semana:
                # Verificar si esta clase ya está registrada
                key = (fecha, horario.id)
                if key in clases_registradas_dict:
                    print(f"DEBUG: Clase ya registrada (omitiendo) - Fecha: {fecha}, Horario ID: {horario.id}")
                else:
                    # Esta clase no está registrada, añadirla a la lista
                    clase_esperada = {
                        'fecha': fecha,
                        'horario': horario,
                        'profesor': horario.profesor,
                        'tipo_clase': horario.tipo_clase,
                        'id_combinado': f"{fecha.strftime('%Y-%m-%d')}|{horario.id}"
                    }
                    clases_no_registradas.append(clase_esperada)
                    print(f"DEBUG: Añadiendo clase no registrada - Fecha: {fecha}, Horario ID: {horario.id}")
    
    # Mensaje de depuración con el número de clases
    print(f"DEBUG: Total de clases registradas: {len(clases_realizadas)}")
    print(f"DEBUG: Total de clases no registradas: {len(clases_no_registradas)}")
    
    # Ordenar por fecha (más reciente primero) y luego por hora de inicio
    clases_no_registradas.sort(key=lambda x: (x['fecha'], x['horario'].hora_inicio), reverse=True)
    
    profesores = Profesor.query.all()
    
    return render_template('asistencia/clases_no_registradas.html',
                           clases_no_registradas=clases_no_registradas,
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
    # Para peticiones GET con parámetros
    if request.method == 'GET' and 'mes' in request.args and 'anio' in request.args:
        mes = int(request.args.get('mes'))
        anio = int(request.args.get('anio'))
        
        # Crear un archivo de log para este informe específico
        log_filename = f"informe_debug_{anio}_{mes}.log"
        with open(log_filename, "w") as log_file:
            log_file.write(f"=== INICIO DEBUG INFORME {anio}-{mes} ===\n")
        
        def debug_log(message):
            with open(log_filename, "a") as log_file:
                log_file.write(f"{message}\n")
        
        debug_log(f"Generando informe para mes={mes}, anio={anio}")
        
        # Obtener el primer y último día del mes
        primer_dia = date(anio, mes, 1)
        ultimo_dia = date(anio, mes, calendar.monthrange(anio, mes)[1])
        
        # Mensaje de depuración
        timestamp_actual = int(time_module.time())
        print(f"DEBUG: Ejecutando informe_mensual para {mes}/{anio} con timestamp: {timestamp_actual}")
        debug_log(f"Rango de fechas: {primer_dia} hasta {ultimo_dia}")
        
        # Forzar sincronización de la base de datos y limpiar caché
        db.session.commit()
        db.session.close()
        db.session = db.create_scoped_session()
        db.session.expire_all()
        
        # Consultar clases realizadas en el rango de fechas usando SQL directo
        # para evitar problemas de caché
        sql_clases = """
        SELECT 
            cr.id, cr.fecha, cr.horario_id, cr.profesor_id, cr.hora_llegada_profesor, 
            cr.cantidad_alumnos, cr.observaciones, cr.audio_file, cr.fecha_registro,
            hc.nombre, hc.hora_inicio, hc.tipo_clase, hc.duracion,
            p.nombre as profesor_nombre, p.apellido as profesor_apellido, p.tarifa_por_clase
        FROM clase_realizada cr
        JOIN horario_clase hc ON cr.horario_id = hc.id
        JOIN profesor p ON cr.profesor_id = p.id
        WHERE cr.fecha >= :fecha_inicio AND cr.fecha <= :fecha_fin
        ORDER BY cr.fecha, hc.hora_inicio
        """
        
        debug_log(f"SQL a ejecutar: {sql_clases}")
        debug_log(f"Parámetros: fecha_inicio={primer_dia}, fecha_fin={ultimo_dia}")
        
        # Crear una conexión fresca para asegurar que no hay caché
        connection = db.engine.connect()
        result_clases = connection.execute(sql_clases, {
            'fecha_inicio': primer_dia,
            'fecha_fin': ultimo_dia
        })
        
        # Verificar si hay registros en la consulta
        debug_log("Verificando si hay resultados en la consulta...")
        primer_registro = result_clases.fetchone()
        if primer_registro:
            debug_log(f"Primer registro encontrado: id={primer_registro.id}, fecha={primer_registro.fecha}")
            debug_log(f"hora_llegada_profesor={primer_registro.hora_llegada_profesor}, tipo={type(primer_registro.hora_llegada_profesor)}")
            # Reiniciar el cursor para procesar todos los registros
            result_clases = connection.execute(sql_clases, {
                'fecha_inicio': primer_dia,
                'fecha_fin': ultimo_dia
            })
        else:
            debug_log("No se encontraron registros en la consulta")
        
    elif request.method == 'POST':
        mes = int(request.form['mes'])
        anio = int(request.form['anio'])
        
        # Obtener el primer y último día del mes
        primer_dia = date(anio, mes, 1)
        ultimo_dia = date(anio, mes, calendar.monthrange(anio, mes)[1])
        
    else:
        # Para peticiones GET sin parámetros, mostrar el formulario
        hoy = datetime.now()
        mes_actual = hoy.month
        anio_actual = hoy.year
        return render_template('informes/mensual.html', mes_actual=mes_actual, anio_actual=anio_actual)
    
    # Esta parte se ejecuta tanto para POST como para GET con parámetros
    # Limpiar caché de la sesión
    db.session.commit()
    db.session.close()
    db.session = db.create_scoped_session()
    
    # Función para calcular la hora de finalización como string
    def calcular_hora_fin(hora_inicio, duracion=60):
        if not hora_inicio:
            return "00:00"
        
        if isinstance(hora_inicio, str):
            try:
                hora_inicio = datetime.strptime(hora_inicio, '%H:%M:%S').time()
            except ValueError:
                try:
                    hora_inicio = datetime.strptime(hora_inicio, '%H:%M').time()
                except ValueError:
                    return "00:00"
        
        minutos_totales = hora_inicio.hour * 60 + hora_inicio.minute + duracion
        horas, minutos = divmod(minutos_totales, 60)
        return f"{horas:02d}:{minutos:02d}"
    
    # Función para calcular la puntualidad
    def calcular_puntualidad(hora_llegada, hora_inicio):
        if not hora_llegada:
            return "N/A"
        
        if hora_llegada <= hora_inicio:
            return "Puntual"
        
        diferencia_minutos = (
            datetime.combine(date.min, hora_llegada) - 
            datetime.combine(date.min, hora_inicio)
        ).total_seconds() / 60
        
        if diferencia_minutos <= 10:
            return "Retraso leve"
        else:
            return "Retraso significativo"
    
    # Procesar los resultados y crear objetos para facilitar el manejo
    clases_realizadas = []
    for row in result_clases:
        # Asegurarse de que fecha sea un objeto datetime.date
        fecha = row.fecha
        if isinstance(fecha, str):
            try:
                fecha = datetime.strptime(fecha, '%Y-%m-%d').date()
            except ValueError:
                try:
                    fecha = datetime.strptime(fecha, '%d/%m/%Y').date()
                except ValueError:
                    fecha = datetime.now().date()

        # Asegurarse de que hora_llegada_profesor sea un objeto time
        hora_llegada = row.hora_llegada_profesor
        debug_log(f"DEBUG clase {row.id} - hora_llegada: {hora_llegada}, tipo: {type(hora_llegada)}")
        if hora_llegada and isinstance(hora_llegada, str):
            try:
                # Intentar con formato que incluye microsegundos (HH:MM:SS.SSSSSS)
                if '.' in hora_llegada:
                    # Extraer solo la parte de la hora sin microsegundos
                    hora_sin_micro = hora_llegada.split('.')[0]
                    hora_llegada = datetime.strptime(hora_sin_micro, '%H:%M:%S').time()
                    debug_log(f"Hora convertida sin microsegundos: {hora_llegada}")
                else:
                    # Intentar formatos estándar
                    try:
                        hora_llegada = datetime.strptime(hora_llegada, '%H:%M:%S').time()
                    except ValueError:
                        try:
                            hora_llegada = datetime.strptime(hora_llegada, '%H:%M').time()
                        except ValueError:
                            hora_llegada = None
            except Exception as e:
                debug_log(f"Error al convertir hora: {str(e)}")
                hora_llegada = None

        # Asegurarse de que hora_inicio sea un objeto time
        hora_inicio = row.hora_inicio
        if isinstance(hora_inicio, str):
            try:
                hora_inicio = datetime.strptime(hora_inicio, '%H:%M:%S').time()
            except ValueError:
                try:
                    hora_inicio = datetime.strptime(hora_inicio, '%H:%M').time()
                except ValueError:
                    hora_inicio = datetime.now().time()
        
        # Procesar hora_inicio de la clase realizada
        clase_hora_inicio = getattr(row, 'clase_hora_inicio', None)
        if clase_hora_inicio and isinstance(clase_hora_inicio, str):
            try:
                clase_hora_inicio = datetime.strptime(clase_hora_inicio, '%H:%M:%S').time()
            except ValueError:
                try:
                    clase_hora_inicio = datetime.strptime(clase_hora_inicio, '%H:%M').time()
                except ValueError:
                    clase_hora_inicio = None
        
        # Obtener la duración o usar valor por defecto
        duracion = getattr(row, 'duracion', 60)
        
        # Calcular la hora de finalización como string
        hora_fin_str = calcular_hora_fin(hora_inicio, duracion)
        
        # Calcular puntualidad
        estado_puntualidad = calcular_puntualidad(hora_llegada, hora_inicio)
        
        # Crear un objeto para representar la clase realizada
        clase = {
            'id': row.id,
            'fecha': fecha,
            'horario_id': row.horario_id,
            'profesor_id': row.profesor_id,
            'hora_llegada_profesor': hora_llegada,
            'cantidad_alumnos': row.cantidad_alumnos,
            'observaciones': row.observaciones,
            'audio_file': row.audio_file,
            'hora_inicio': clase_hora_inicio or hora_inicio,  # Usar hora_inicio de clase_realizada si existe, o del horario como respaldo
            'horario': {
                'id': row.horario_id,
                'nombre': row.nombre,
                'hora_inicio': hora_inicio,
                'tipo_clase': row.tipo_clase,
                'duracion': duracion,
                'hora_fin_str': hora_fin_str
            },
            'profesor': {
                'id': row.profesor_id,
                'nombre': row.profesor_nombre,
                'apellido': row.profesor_apellido,
                'tarifa_por_clase': row.tarifa_por_clase
            },
            'puntualidad': estado_puntualidad
        }
        debug_log(f"DEBUG clase {row.id}: hora_llegada_profesor={hora_llegada}, puntualidad={estado_puntualidad}")
        clases_realizadas.append(clase)
    
    # Antes de renderizar la plantilla, verificar algunas clases para diagnosticar
    if clases_realizadas:
        for idx, clase in enumerate(clases_realizadas[:3]):  # Verificar solo las primeras 3 clases
            debug_log(f"DEBUG pre-render clase {idx+1}: id={clase['id']}, fecha={clase['fecha']}, hora_llegada={clase['hora_llegada_profesor']}, puntualidad={clase['puntualidad']}")
    
    debug_log("=== FIN DEBUG INFORME ===")
    
    # Obtener todos los horarios activos
    sql_horarios = "SELECT id, nombre, hora_inicio, tipo_clase, dia_semana, profesor_id, duracion FROM horario_clase"
    result_horarios = db.session.execute(sql_horarios)
    
    horarios_activos = []
    for row in result_horarios:
        # Asegurarse de que hora_inicio sea un objeto time
        hora_inicio = row.hora_inicio
        debug_log(f"DEBUG horario {row.id} formato original: hora_inicio={hora_inicio}, tipo={type(hora_inicio)}")
        if isinstance(hora_inicio, str):
            try:
                # Manejar formato con microsegundos
                if '.' in hora_inicio:
                    hora_sin_micro = hora_inicio.split('.')[0]
                    hora_inicio = datetime.strptime(hora_sin_micro, '%H:%M:%S').time()
                    debug_log(f"DEBUG horario {row.id} convertido sin microsegundos: {hora_inicio}")
                else:
                    # Intentar formatos estándar
                    try:
                        hora_inicio = datetime.strptime(hora_inicio, '%H:%M:%S').time()
                    except ValueError:
                        try:
                            hora_inicio = datetime.strptime(hora_inicio, '%H:%M').time()
                        except ValueError:
                            hora_inicio = datetime.now().time()
            except Exception as e:
                debug_log(f"Error al convertir hora para horario {row.id}: {str(e)}")
                hora_inicio = datetime.now().time()
                    
        # Obtener la duración o usar valor por defecto
        duracion = getattr(row, 'duracion', 60)
        
        # Calcular la hora de finalización como string
        hora_fin_str = calcular_hora_fin(hora_inicio, duracion)
        
        horario = {
            'id': row.id,
            'nombre': row.nombre,
            'hora_inicio': hora_inicio,
            'tipo_clase': row.tipo_clase,
            'dia_semana': row.dia_semana,
            'profesor_id': row.profesor_id,
            'duracion': duracion,
            'hora_fin_str': hora_fin_str
        }
        horarios_activos.append(horario)
    
    # Generar fechas para el mes seleccionado
    fechas_mes = []
    fecha_actual = primer_dia
    while fecha_actual <= ultimo_dia:
        fechas_mes.append(fecha_actual)
        fecha_actual += timedelta(days=1)
    
    # Crear un diccionario para verificar clases ya registradas
    # Formato: {(fecha, horario_id): True}
    clases_registradas_dict = {}
    for clase in clases_realizadas:
        key = (clase['fecha'], clase['horario_id'])
        clases_registradas_dict[key] = True
    
    # Generar las clases que deberían haberse realizado pero no están registradas
    clases_no_registradas = []
    for horario in horarios_activos:
        for fecha in fechas_mes:
            # Si el día de la semana coincide con el día del horario
            if fecha.weekday() == horario['dia_semana']:
                key = (fecha, horario['id'])
                # Verificar si esta clase no está registrada
                if key not in clases_registradas_dict:
                    # Obtener información del profesor
                    sql_profesor = "SELECT id, nombre, apellido FROM profesor WHERE id = :profesor_id"
                    result_profesor = db.session.execute(sql_profesor, {'profesor_id': horario['profesor_id']}).fetchone()
                    
                    if result_profesor:
                        profesor = {
                            'id': result_profesor.id,
                            'nombre': result_profesor.nombre,
                            'apellido': result_profesor.apellido
                        }
                    else:
                        profesor = {
                            'id': 0,
                            'nombre': 'Desconocido',
                            'apellido': ''
                        }
                    
                    # Asegurarse de que fecha sea un objeto datetime.date
                    if not isinstance(fecha, date):
                        try:
                            fecha = datetime.strptime(fecha, '%Y-%m-%d').date()
                        except (ValueError, TypeError):
                            try:
                                fecha = datetime.strptime(fecha, '%d/%m/%Y').date()
                            except (ValueError, TypeError):
                                fecha = datetime.now().date()
                    
                    # Creamos un objeto para representar la clase esperada
                    clase_esperada = {
                        'fecha': fecha,
                        'horario': horario,
                        'profesor': profesor,
                        'tipo_clase': horario['tipo_clase'],
                        'id_combinado': f"{fecha.strftime('%Y-%m-%d')}|{horario['id']}"
                    }
                    debug_log(f"DEBUG clase no registrada: fecha={fecha}, horario_id={horario['id']}, profesor={profesor['nombre']} {profesor['apellido']}, tipo_clase={horario['tipo_clase']}")
                    debug_log(f"DEBUG horario.hora_inicio={horario['hora_inicio']}, hora_fin_str={horario['hora_fin_str']}")
                    clases_no_registradas.append(clase_esperada)
    
    # Ordenar las clases no registradas por fecha
    clases_no_registradas.sort(key=lambda x: (x['fecha'], x['horario']['hora_inicio']))
    
    # Verificar algunas clases no registradas para diagnosticar
    if clases_no_registradas:
        for idx, clase in enumerate(clases_no_registradas[:3]):  # Verificar solo las primeras 3 clases
            debug_log(f"DEBUG pre-render clase no registrada {idx+1}: fecha={clase['fecha']}, horario={clase['horario']['nombre']}, tipo={clase['tipo_clase']}, hora_inicio={clase['horario']['hora_inicio']}")
    
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
        profesor = clase['profesor']
        tipo_clase = clase['horario']['tipo_clase']
        
        # Incrementar contadores por tipo
        conteo_tipos[tipo_clase] += 1
        alumnos_tipos[tipo_clase] += clase['cantidad_alumnos']
        
        if profesor['id'] not in resumen_profesores:
            resumen_profesores[profesor['id']] = {
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
        resumen_profesores[profesor['id']]['total_clases'] += 1
        resumen_profesores[profesor['id']]['total_alumnos'] += clase['cantidad_alumnos']
        resumen_profesores[profesor['id']]['clases_por_tipo'][tipo_clase] += 1
        resumen_profesores[profesor['id']]['alumnos_por_tipo'][tipo_clase] += clase['cantidad_alumnos']
        
        if clase['hora_llegada_profesor'] and clase['hora_llegada_profesor'] > clase['horario']['hora_inicio']:
            resumen_profesores[profesor['id']]['total_retrasos'] += 1
        
        # Si el profesor asistió (tiene hora de llegada) pero no hay alumnos, se paga la mitad
        pago_clase = profesor['tarifa_por_clase'] / 2 if (clase['hora_llegada_profesor'] and clase['cantidad_alumnos'] == 0) else profesor['tarifa_por_clase']
        
        # Almacenar el pago individual por clase
        clase['pago_calculado'] = pago_clase
        
        # Añadir al total del profesor
        resumen_profesores[profesor['id']]['pago_total'] += pago_clase
    
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
        
        # Primero intentar buscar en la nueva estructura de directorios
        audio_dir = get_audio_storage_path(horario_id)
        newest_audio = None
        
        if os.path.exists(audio_dir):
            try:
                files = os.listdir(audio_dir)
                audio_files = [f for f in files if f.startswith('audio_')]
                if audio_files:
                    audio_files.sort(reverse=True)
                    newest_audio = audio_files[0]
                    audio_path = os.path.join(audio_dir, newest_audio)
                    
                    # Actualizar la base de datos si encontramos un audio
                    if clase and (not clase.audio_file or not os.path.exists(os.path.join(app.config.get('UPLOAD_FOLDER', 'static/uploads'), 'audios', clase.audio_file))):
                        relative_path = os.path.join(f'horario_{horario_id}', newest_audio)
                        clase.audio_file = relative_path
                        db.session.commit()
                        app.logger.info(f"Updated database with found audio: {relative_path}")
                    
                    # En lugar de enviar el archivo directamente, redirigir a la ruta estática
                    static_url = url_for('static', filename=f'uploads/audios/permanent/horario_{horario_id}/{newest_audio}')
                    app.logger.info(f"Redirecting to static audio URL: {static_url}")
                    return redirect(static_url)
            except Exception as e:
                app.logger.error(f"Error searching for audio files in directory: {str(e)}")
        
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
        
        # Determinar la ruta relativa para la URL estática
        if clase.audio_file.startswith('horario_') or '/' in clase.audio_file or '\\' in clase.audio_file:
            # Nueva estructura
            static_url = url_for('static', filename=f'uploads/audios/permanent/{clase.audio_file}')
        else:
            # Formato antiguo
            static_url = url_for('static', filename=f'uploads/audios/{clase.audio_file}')
        
        app.logger.info(f"Redirecting to static audio URL: {static_url}")
        return redirect(static_url)
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
        hoy = datetime.now().date()
        print(f"DEBUG: Registrando asistencia para FECHA REAL: {fecha_obj} (parámetro recibido: {fecha})")
        print(f"DEBUG: La fecha actual es: {hoy}")
    except ValueError:
        flash('Formato de fecha inválido', 'danger')
        return redirect(url_for('control_asistencia'))
    
    print(f"DEBUG: Registrando asistencia para fecha {fecha_obj} y horario {horario_id}")
    
    horario = HorarioClase.query.get_or_404(horario_id)
    if not horario:
        flash(f'No se encontró el horario con ID {horario_id}', 'danger')
        return redirect(url_for('clases_no_registradas'))
    
    # Verificar si la clase ya está registrada para la fecha específica - USAR SQL DIRECTO
    fecha_str = fecha_obj.strftime('%Y-%m-%d')
    sql = "SELECT id FROM clase_realizada WHERE fecha = :fecha AND horario_id = :horario_id LIMIT 1"
    result = db.session.execute(sql, {'fecha': fecha_str, 'horario_id': horario_id}).fetchone()
    
    if result:
        clase_existente_id = result[0]
        print(f"DEBUG: Ya existe una clase registrada con ID {clase_existente_id} para fecha {fecha_obj} (fecha_str={fecha_str}) y horario {horario_id}")
        flash(f'Ya existe un registro para la clase {horario.nombre} en la fecha {fecha_obj.strftime("%d/%m/%Y")}', 'warning')
        return redirect(url_for('editar_asistencia', id=clase_existente_id))
    
    # Verificar si la clase ya está registrada para la fecha actual (para evitar confusiones)
    if fecha_obj != hoy:  # Solo realizar esta comprobación si la fecha no es hoy
        hoy_str = hoy.strftime('%Y-%m-%d')
        sql = "SELECT id FROM clase_realizada WHERE fecha = :fecha AND horario_id = :horario_id LIMIT 1"
        result = db.session.execute(sql, {'fecha': hoy_str, 'horario_id': horario_id}).fetchone()
        if result:
            flash(f'Atención: Ya existe un registro para la clase {horario.nombre} en la fecha actual ({hoy.strftime("%d/%m/%Y")})', 'info')
    
    # Procesar el formulario si es POST
    if request.method == 'POST':
        hora_llegada_str = request.form.get('hora_llegada')
        cantidad_alumnos = request.form.get('cantidad_alumnos', type=int)
        observaciones = request.form.get('observaciones')
        
        # Obtener el profesor seleccionado o usar el del horario por defecto
        profesor_id = request.form.get('profesor_id')
        if not profesor_id:
            profesor_id = horario.profesor_id
        else:
            profesor_id = int(profesor_id)
        
        # Convertir hora de llegada a objeto Time
        if hora_llegada_str:
            try:
                hora_llegada = datetime.strptime(hora_llegada_str, '%H:%M').time()
            except ValueError:
                flash('Formato de hora inválido. Use HH:MM', 'danger')
                profesores = Profesor.query.all()
                return render_template('asistencia/registrar.html', horario=horario, fecha=fecha_obj, hoy=fecha_obj, profesores=profesores)
        else:
            hora_llegada = None
        
        # Crear y guardar la nueva clase
        nueva_clase = ClaseRealizada(
            fecha=fecha_obj,  # Asegurarse de usar la fecha original, no la actual
            horario_id=horario.id,
            profesor_id=profesor_id,
            hora_llegada_profesor=hora_llegada,
            cantidad_alumnos=cantidad_alumnos,
            observaciones=observaciones
        )
        
        try:
            # Verificar nuevamente si existe un registro para evitar duplicados
            fecha_str = fecha_obj.strftime('%Y-%m-%d')
            sql = "SELECT id FROM clase_realizada WHERE fecha = :fecha AND horario_id = :horario_id LIMIT 1"
            result = db.session.execute(sql, {'fecha': fecha_str, 'horario_id': horario_id}).fetchone()
            
            if result:
                clase_existente_id = result[0]
                print(f"DEBUG: Se detectó un registro existente durante la creación - ID: {clase_existente_id}")
                flash(f'Ya existe un registro para la clase {horario.nombre} en la fecha {fecha_obj.strftime("%d/%m/%Y")}', 'warning')
                return redirect(url_for('editar_asistencia', id=clase_existente_id))
            
            # Ejecutar SQL directo para garantizar la inserción
            sql = """
            INSERT INTO clase_realizada 
            (fecha, horario_id, profesor_id, hora_llegada_profesor, cantidad_alumnos, observaciones, fecha_registro) 
            VALUES (:fecha, :horario_id, :profesor_id, :hora_llegada, :cantidad_alumnos, :observaciones, :fecha_registro)
            """
            
            # Convertir fecha_obj a string ISO explícito
            fecha_str = fecha_obj.strftime('%Y-%m-%d')
            print(f"DEBUG: Insertando clase con fecha_obj={fecha_obj} convertida a fecha_str={fecha_str}")
            
            db.session.execute(sql, {
                'fecha': fecha_str,  # Usar string en formato ISO en lugar del objeto fecha_obj
                'horario_id': horario.id,
                'profesor_id': profesor_id,
                'hora_llegada': hora_llegada,
                'cantidad_alumnos': cantidad_alumnos,
                'observaciones': observaciones,
                'fecha_registro': datetime.utcnow()  # Solo la fecha_registro es la actual
            })
            
            db.session.commit()
            
            # Verificar que se haya guardado correctamente con la fecha original
            result_verificacion = db.session.execute(
                "SELECT id, fecha FROM clase_realizada WHERE horario_id = :horario_id ORDER BY id DESC LIMIT 1", 
                {'horario_id': horario.id}
            ).fetchone()
            
            if result_verificacion:
                print(f"DEBUG: Verificación post-inserción: ID={result_verificacion[0]}, fecha guardada={result_verificacion[1]}, fecha original={fecha_obj}")
            
            # Obtener el ID de la clase recién insertada
            result = db.session.execute(
                "SELECT id FROM clase_realizada WHERE fecha = :fecha AND horario_id = :horario_id ORDER BY id DESC LIMIT 1", 
                {'fecha': fecha_str, 'horario_id': horario.id}
            ).fetchone()
            
            nueva_clase_id = result[0] if result else 'desconocido'
            
            print(f"DEBUG: Clase registrada con éxito - ID: {nueva_clase_id}, Fecha: {fecha_obj}, Horario: {horario_id}")
            
            flash(f'Asistencia para la clase {horario.nombre} del {fecha_obj.strftime("%d/%m/%Y")} registrada con éxito', 'success')
            
            # Cerrar y reabrir la sesión para limpiar la caché
            db.session.close()
            db.session = db.create_scoped_session()
            
            # Si la fecha es hoy, redirigir al control de asistencia
            # Si es una fecha anterior, redirigir al historial de clases no registradas
            if fecha_obj == hoy:
                return redirect(url_for('control_asistencia'))
            else:
                # Añadir timestamp y clear_cache para forzar actualización completa
                timestamp = int(time_module.time())
                # Redirigir al informe mensual del mes correspondiente
                return redirect(url_for('informe_mensual', 
                                      mes=fecha_obj.month, 
                                      anio=fecha_obj.year, 
                                      refresh=timestamp, 
                                      clear_cache=1))
        except Exception as e:
            db.session.rollback()
            print(f"ERROR: No se pudo registrar la clase - {str(e)}")
            flash(f'Error al registrar la clase: {str(e)}', 'danger')
            return redirect(url_for('clases_no_registradas'))
    
    # Obtener todos los profesores para el selector
    profesores = Profesor.query.all()
    
    return render_template('asistencia/registrar.html', horario=horario, fecha=fecha_obj, hoy=fecha_obj, profesores=profesores)

@app.route('/asistencia/registrar-clases-masivo', methods=['POST'])
@app.route('/registrar-clases-no-registradas', methods=['POST'])  # Alias para mantener compatibilidad
def registrar_clases_no_registradas():
    """Registrar múltiples clases no registradas de forma masiva"""
    if request.method == 'POST':
        clases_ids = request.form.getlist('clases_ids[]')
        
        if not clases_ids:
            flash('No seleccionó ninguna clase para registrar', 'warning')
            return redirect(url_for('clases_no_registradas'))
        
        # Verificar si se especificó un profesor alternativo para todas las clases
        profesor_id_alternativo = request.form.get('profesor_id_alternativo')
        if profesor_id_alternativo:
            try:
                profesor_id_alternativo = int(profesor_id_alternativo)
                # Verificar que el profesor existe
                profesor = Profesor.query.get(profesor_id_alternativo)
                if not profesor:
                    profesor_id_alternativo = None
            except (ValueError, TypeError):
                profesor_id_alternativo = None
        
        clases_registradas = 0
        clases_procesadas = []
        
        for clase_id in clases_ids:
            try:
                # El formato es 'YYYY-MM-DD|horario_id'
                partes = clase_id.split('|')
                fecha = partes[0]
                horario_id = int(partes[1])
                
                print(f"DEBUG: Registrando clase masiva con fecha={fecha} y horario_id={horario_id}")
                
                fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
                print(f"DEBUG: Fecha convertida a fecha_obj={fecha_obj} (tipo: {type(fecha_obj)})")
                
                # Obtener información del horario usando SQL directo
                sql_horario = "SELECT id, profesor_id, hora_inicio FROM horario_clase WHERE id = :horario_id"
                result_horario = db.session.execute(sql_horario, {'horario_id': horario_id}).fetchone()
                
                if not result_horario:
                    print(f"DEBUG: Horario no encontrado - ID: {horario_id}")
                    continue
                
                horario_id = result_horario[0]
                # Usar el profesor alternativo si se especificó, de lo contrario usar el del horario
                profesor_id = profesor_id_alternativo if profesor_id_alternativo else result_horario[1]
                hora_inicio = result_horario[2]
                
                # Asegurar que hora_inicio sea un objeto time válido
                if isinstance(hora_inicio, str):
                    try:
                        hora_inicio = datetime.strptime(hora_inicio, '%H:%M:%S').time()
                    except ValueError:
                        try:
                            hora_inicio = datetime.strptime(hora_inicio, '%H:%M').time()
                        except ValueError:
                            # Si no se puede convertir, usar None o una hora por defecto
                            hora_inicio = None
                            print(f"DEBUG: No se pudo convertir hora_inicio para horario ID: {horario_id}")
                
                # Verificar si ya existe un registro para esta clase usando SQL directo
                fecha_str = fecha_obj.strftime('%Y-%m-%d')
                sql_verificar = "SELECT id FROM clase_realizada WHERE fecha = :fecha AND horario_id = :horario_id LIMIT 1"
                result_verificar = db.session.execute(sql_verificar, {'fecha': fecha_str, 'horario_id': horario_id}).fetchone()
                
                if result_verificar:
                    print(f"DEBUG: Clase ya existe - Fecha: {fecha_obj} (fecha_str={fecha_str}), Horario: {horario_id}")
                    continue
                
                # Crear un nuevo registro con SQL directo
                sql_insertar = """
                INSERT INTO clase_realizada 
                (fecha, horario_id, profesor_id, hora_llegada_profesor, hora_inicio, cantidad_alumnos, observaciones, fecha_registro) 
                VALUES (:fecha, :horario_id, :profesor_id, :hora_llegada, :hora_inicio, :cantidad_alumnos, :observaciones, :fecha_registro)
                """
                
                # Convertir fecha_obj a string ISO explícito
                fecha_str = fecha_obj.strftime('%Y-%m-%d')
                print(f"DEBUG: Insertando clase masiva con fecha_obj={fecha_obj} convertida a fecha_str={fecha_str}, hora_inicio={hora_inicio}")
                
                db.session.execute(sql_insertar, {
                    'fecha': fecha_str,  # Usar string en formato ISO en lugar del objeto fecha_obj
                    'horario_id': horario_id,
                    'profesor_id': profesor_id,
                    'hora_llegada': hora_inicio,
                    'hora_inicio': hora_inicio,  # Guardar explícitamente la hora_inicio
                    'cantidad_alumnos': 0,
                    'observaciones': "Registrada automáticamente",
                    'fecha_registro': datetime.utcnow()
                })
                
                db.session.commit()
                
                # Verificar que se haya guardado correctamente con la fecha original
                result_verificacion = db.session.execute(
                    "SELECT id, fecha FROM clase_realizada WHERE horario_id = :horario_id ORDER BY id DESC LIMIT 1", 
                    {'horario_id': horario_id}
                ).fetchone()
                
                if result_verificacion:
                    print(f"DEBUG: Verificación post-inserción masiva: ID={result_verificacion[0]}, fecha guardada={result_verificacion[1]}, fecha original={fecha_obj}")
                
                # Obtener el ID de la clase recién insertada
                sql_obtener_id = """
                SELECT id FROM clase_realizada 
                WHERE fecha = :fecha AND horario_id = :horario_id 
                ORDER BY id DESC LIMIT 1
                """
                result_id = db.session.execute(sql_obtener_id, {'fecha': fecha_str, 'horario_id': horario_id}).fetchone()
                
                nueva_clase_id = result_id[0] if result_id else 'desconocido'
                
                clases_registradas += 1
                clases_procesadas.append({
                    'fecha': fecha_obj,
                    'horario_id': horario_id,
                    'id': nueva_clase_id
                })
                
                print(f"DEBUG: Clase registrada con éxito - ID: {nueva_clase_id}, Fecha: {fecha_obj}, Horario: {horario_id}")
                
            except Exception as e:
                # Registrar el error pero continuar con las otras clases
                db.session.rollback()
                app.logger.error(f"Error al registrar clase {clase_id}: {str(e)}")
                print(f"ERROR: No se pudo registrar la clase {clase_id} - {str(e)}")
                continue
        
        if clases_registradas > 0:
            try:
                # Forzar un cierre y reapertura de la sesión para limpiar la caché
                db.session.close()
                db.session = db.create_scoped_session()
                
                print(f"DEBUG: Se registraron {clases_registradas} clases correctamente: {clases_procesadas}")
                flash(f'Se registraron {clases_registradas} clases correctamente', 'success')
            except Exception as e:
                print(f"ERROR: Error al limpiar la caché - {str(e)}")
                flash(f'Se registraron clases pero hubo un error al actualizar la vista: {str(e)}', 'warning')
        else:
            flash('No se registró ninguna clase nueva', 'warning')
        
        # Añadir timestamp y clear_cache para forzar actualización completa
        timestamp = int(time_module.time())
        
        # Para asegurar que la caché se limpie completamente, realizamos conexiones frescas
        try:
            # Forzar una actualización completa de la BD
            db.session.commit()
            # Cerrar la sesión actual
            db.session.close()
            # Crear una nueva sesión limpia
            db.session = db.create_scoped_session()
            # Expirar todos los objetos en la sesión
            db.session.expire_all()
            print("DEBUG: Limpieza de caché realizada antes del redirect")
        except Exception as e:
            print(f"ERROR: Error al realizar limpieza final de caché - {str(e)}")
        
        # Si hay clases procesadas, redirigir al informe del mes correspondiente a la primera clase
        if clases_procesadas:
            primera_fecha = clases_procesadas[0]['fecha']
            mes = primera_fecha.month
            anio = primera_fecha.year
            return redirect(url_for('informe_mensual', mes=mes, anio=anio, refresh=timestamp, clear_cache=1))
        else:
            return redirect(url_for('clases_no_registradas', refresh=timestamp, clear_cache=1))

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

@app.route('/diagnostico/eliminar_clase/<int:id>')
def diagnostico_eliminar_clase(id):
    """
    Ruta de diagnóstico para analizar y eliminar clases con problemas.
    Esta ruta utiliza un enfoque que evita restricciones comunes que pueden
    bloquear la eliminación de clases.
    """
    try:
        # Obtener la clase
        clase = ClaseRealizada.query.get_or_404(id)
        
        # Información de la clase para mostrar en el resultado
        info_clase = {
            'id': clase.id,
            'fecha': str(clase.fecha),
            'horario_id': clase.horario_id,
            'profesor_id': clase.profesor_id,
            'nombre_clase': clase.horario.nombre if clase.horario else "Desconocido",
            'profesor': f"{clase.profesor.nombre} {clase.profesor.apellido}" if clase.profesor else "Desconocido",
            'audio_file': clase.audio_file
        }
        
        # Eliminar archivo de audio si existe
        if clase.audio_file:
            try:
                # Buscar el archivo en diferentes ubicaciones
                audio_paths = []
                
                # Ruta en formato antiguo
                upload_folder = os.path.join(app.config.get('UPLOAD_FOLDER', 'static/uploads'), 'audios')
                audio_path1 = os.path.join(upload_folder, clase.audio_file)
                audio_paths.append(audio_path1)
                
                # Ruta en formato nuevo
                if '/' in clase.audio_file or '\\' in clase.audio_file:
                    audio_path2 = os.path.join(upload_folder, 'permanent', clase.audio_file)
                    audio_paths.append(audio_path2)
                else:
                    horario_dir = os.path.join(upload_folder, 'permanent', f'horario_{clase.horario_id}')
                    audio_path3 = os.path.join(horario_dir, clase.audio_file)
                    audio_paths.append(audio_path3)
                
                # Intentar eliminar el archivo de audio en todas las ubicaciones posibles
                for path in audio_paths:
                    if os.path.exists(path):
                        os.remove(path)
                        info_clase['audio_eliminado'] = f"Archivo de audio eliminado: {path}"
                        break
            except Exception as e:
                info_clase['error_audio'] = f"Error al eliminar archivo de audio: {str(e)}"
        
        # Usar una sesión nueva para evitar problemas con transacciones existentes
        from sqlalchemy.orm import Session
        from sqlalchemy import create_engine
        
        # Usar la misma URI de base de datos que la aplicación
        engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
        session = Session(engine)
        
        try:
            # Obtener la clase en esta nueva sesión
            clase_nueva_sesion = session.query(ClaseRealizada).get(id)
            
            if clase_nueva_sesion:
                # Eliminar la clase
                session.delete(clase_nueva_sesion)
                session.commit()
                info_clase['resultado'] = "Clase eliminada exitosamente con el método alternativo"
            else:
                info_clase['resultado'] = "No se encontró la clase en la nueva sesión"
        except Exception as e:
            session.rollback()
            info_clase['error_eliminar'] = f"Error al eliminar con método alternativo: {str(e)}"
            
            # Intentar con el método original
            try:
                db.session.delete(clase)
                db.session.commit()
                info_clase['resultado'] = "Clase eliminada exitosamente con el método original"
            except Exception as e2:
                db.session.rollback()
                info_clase['error_eliminar2'] = f"Error al eliminar con método original: {str(e2)}"
                
                # Último intento: eliminar directamente con SQL
                try:
                    db.session.execute(f"DELETE FROM clase_realizada WHERE id = {id}")
                    db.session.commit()
                    info_clase['resultado'] = "Clase eliminada exitosamente con SQL directo"
                except Exception as e3:
                    db.session.rollback()
                    info_clase['error_eliminar3'] = f"Error al eliminar con SQL directo: {str(e3)}"
                    info_clase['resultado'] = "No se pudo eliminar la clase"
        finally:
            session.close()
        
        # Redireccionar o mostrar información
        return jsonify(info_clase)
    except Exception as e:
        return jsonify({
            'error': f"Error general: {str(e)}",
            'id': id
        }), 500

@app.route('/configuracion/exportar_db', methods=['GET'])
def exportar_db():
    """Exportar el archivo de la base de datos completo"""
    try:
        # Ruta al archivo de base de datos
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gimnasio.db')
        
        # Verificar que el archivo existe
        if not os.path.exists(db_path):
            flash('No se encontró el archivo de base de datos', 'danger')
            return redirect(url_for('configuracion_exportar'))
        
        # Crear una copia temporal para exportar
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'gimnasio_backup_{timestamp}.db'
        temp_path = os.path.join(os.path.dirname(db_path), 'backups', backup_filename)
        
        # Asegurar que el directorio existe
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        
        # Copiar el archivo (sin bloquear la base de datos)
        import shutil
        shutil.copy2(db_path, temp_path)
        
        # Enviar el archivo al cliente
        return send_file(temp_path, 
                         as_attachment=True, 
                         download_name=backup_filename,
                         mimetype='application/octet-stream')
    
    except Exception as e:
        app.logger.error(f"Error exportando la base de datos: {str(e)}")
        flash(f'Error al exportar la base de datos: {str(e)}', 'danger')
        return redirect(url_for('configuracion_exportar'))

@app.route('/configuracion/importar_db', methods=['POST'])
def importar_db():
    """Importar un archivo de base de datos"""
    if 'db_file' not in request.files:
        flash('No se seleccionó ningún archivo', 'danger')
        return redirect(url_for('configuracion_exportar'))
    
    db_file = request.files['db_file']
    
    if db_file.filename == '':
        flash('No se seleccionó ningún archivo', 'danger')
        return redirect(url_for('configuracion_exportar'))
    
    if not db_file.filename.endswith('.db'):
        flash('El archivo debe tener extensión .db', 'danger')
        return redirect(url_for('configuracion_exportar'))
    
    try:
        # Ruta al archivo de base de datos original
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gimnasio.db')
        
        # Crear una copia de seguridad antes de reemplazar
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(os.path.dirname(db_path), 'backups', f'gimnasio_antes_importar_{timestamp}.db')
        
        # Asegurar que el directorio existe
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        
        # Copiar el archivo original como respaldo
        import shutil
        shutil.copy2(db_path, backup_path)
        
        # Cerrar la conexión actual a la base de datos antes de reemplazarla
        db.session.remove()
        
        # Guardar el archivo subido como el nuevo archivo de base de datos
        db_file.save(db_path)
        
        # Registrar el éxito
        app.logger.info(f"Base de datos importada exitosamente. Respaldo guardado en {backup_path}")
        flash('Base de datos importada exitosamente. Se ha creado una copia de seguridad de la base de datos anterior.', 'success')
        
        # Reiniciar la aplicación (esto no funciona en todas las configuraciones)
        # En producción, esto debería mostrar instrucciones para reiniciar manualmente
        return redirect(url_for('configuracion_exportar'))
    
    except Exception as e:
        app.logger.error(f"Error importando la base de datos: {str(e)}")
        flash(f'Error al importar la base de datos: {str(e)}', 'danger')
        return redirect(url_for('configuracion_exportar'))

@app.route('/generate-logo-png')
def generate_logo_png():
    """Generate a PNG version of the O2 logo and save it to static/img/o2-logo.png"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io
        import os
        
        # Create a new image with a transparent background
        size = (200, 200)
        img = Image.new('RGBA', size, color=(34, 34, 34, 255))  # Dark background
        draw = ImageDraw.Draw(img)
        
        # Draw outer circle
        draw.ellipse([(10, 10), (190, 190)], outline=(255, 255, 255, 255), width=10)
        
        # Draw inner circle
        draw.ellipse([(30, 30), (170, 170)], outline=(255, 255, 255, 255), width=10)
        
        # Try to add text "2" (this part might not work if the font is not available)
        try:
            font = ImageFont.truetype("arial.ttf", 100)
        except IOError:
            font = ImageFont.load_default()
        
        # Draw the "2" in the center
        draw.text((100, 80), "2", font=font, fill=(255, 255, 255, 255), anchor="mm")
        
        # Save the image
        output_path = os.path.join(app.static_folder, 'img', 'o2-logo.png')
        img.save(output_path)
        
        return f"Logo generated and saved to {output_path}"
    
    except Exception as e:
        app.logger.error(f"Error generating logo: {str(e)}")
        return f"Error generating logo: {str(e)}", 500

@app.route('/generate-favicon-ico')
def generate_favicon_ico():
    """Generate a favicon.ico file from the O2 logo SVG"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io
        import os
        
        # Crear las imágenes para diferentes tamaños (16x16, 32x32, 48x48)
        sizes = [16, 32, 48]
        favicon_images = []
        
        for size in sizes:
            # Crear una nueva imagen con fondo negro
            img = Image.new('RGBA', (size, size), color=(34, 34, 34, 255))
            draw = ImageDraw.Draw(img)
            
            # Calcular proporciones para los círculos
            outer_radius = int(size * 0.95 / 2)
            inner_radius = int(size * 0.7 / 2)
            circle_width = max(1, int(size * 0.08))  # Al menos 1 píxel de ancho
            
            # Dibujar círculo exterior
            draw.ellipse(
                [(size/2 - outer_radius, size/2 - outer_radius), 
                 (size/2 + outer_radius, size/2 + outer_radius)], 
                outline=(255, 255, 255, 255), width=circle_width
            )
            
            # Dibujar círculo interior
            draw.ellipse(
                [(size/2 - inner_radius, size/2 - inner_radius), 
                 (size/2 + inner_radius, size/2 + inner_radius)], 
                outline=(255, 255, 255, 255), width=circle_width
            )
            
            # En tamaños pequeños, usar un punto blanco en lugar del número "2"
            if size < 32:
                # Dibujar un punto en el centro
                center_radius = max(1, int(size * 0.15))
                draw.ellipse(
                    [(size/2 - center_radius, size/2 - center_radius), 
                     (size/2 + center_radius, size/2 + center_radius)], 
                    fill=(255, 255, 255, 255)
                )
            else:
                # Intentar usar una fuente para el "2"
                try:
                    # La fuente y tamaño dependen del tamaño del icono
                    font_size = int(size * 0.6)
                    font = ImageFont.truetype("arial.ttf", font_size)
                    # Posicionar el texto centrado
                    text_width = font_size * 0.6  # Aproximado
                    draw.text((size/2 - text_width/2, size/2 - font_size/2), "2", 
                              font=font, fill=(255, 255, 255, 255))
                except Exception:
                    # Si falla, usar un punto en el centro como fallback
                    center_radius = int(size * 0.2)
                    draw.ellipse(
                        [(size/2 - center_radius, size/2 - center_radius), 
                         (size/2 + center_radius, size/2 + center_radius)], 
                        fill=(255, 255, 255, 255)
                    )
            
            favicon_images.append(img)
        
        # Guardar como archivo .ico con múltiples tamaños
        output_path = os.path.join(app.static_folder, 'favicon.ico')
        favicon_images[0].save(
            output_path, 
            format='ICO', 
            sizes=[(size, size) for size in sizes],
            append_images=favicon_images[1:]
        )
        
        return f"Favicon.ico generado en {output_path}"
    
    except Exception as e:
        app.logger.error(f"Error generando favicon.ico: {str(e)}")
        return f"Error generando favicon.ico: {str(e)}", 500

@app.route('/asistencia/depurar-base-datos')
def depurar_asistencia_base_datos():
    """
    Función para depurar problemas con clases no registradas.
    Esta función identificará y eliminará duplicados en la base de datos.
    """
    try:
        # Verificar si hay clases duplicadas
        duplicados = db.session.query(
            ClaseRealizada.fecha,
            ClaseRealizada.horario_id,
            func.count().label('total')
        ).group_by(
            ClaseRealizada.fecha,
            ClaseRealizada.horario_id
        ).having(func.count() > 1).all()
        
        if not duplicados:
            flash('No se encontraron duplicados en la base de datos', 'success')
            return redirect(url_for('control_asistencia'))
        
        total_duplicados = len(duplicados)
        flash(f'Se encontraron {total_duplicados} conjuntos de clases duplicadas', 'warning')
        
        # Eliminar duplicados
        clases_eliminadas = 0
        for duplicado in duplicados:
            fecha = duplicado.fecha
            horario_id = duplicado.horario_id
            
            # Obtener todas las clases con esa fecha y horario
            clases = ClaseRealizada.query.filter_by(
                fecha=fecha,
                horario_id=horario_id
            ).order_by(ClaseRealizada.id).all()
            
            # Mantener la primera clase y eliminar las demás
            for clase in clases[1:]:
                db.session.delete(clase)
                clases_eliminadas += 1
                
        db.session.commit()
        flash(f'Se eliminaron {clases_eliminadas} clases duplicadas', 'success')
        
        # Forzar un reinicio de la sesión para limpiar la caché
        db.session.remove()
        db.session = db.create_scoped_session()
        
        return redirect(url_for('control_asistencia'))
            
    except Exception as e:
        db.session.rollback()
        flash(f'Error al depurar la base de datos: {str(e)}', 'danger')
        return redirect(url_for('control_asistencia'))

@app.route('/mantenimiento/depurar-base-datos')
def depurar_base_datos():
    """
    Función para depurar la base de datos y resolver problemas comunes.
    Esta ruta permite realizar operaciones de limpieza y mantenimiento.
    """
    resultados = {
        'success': True,
        'mensajes': []
    }
    
    try:
        # 1. Reiniciar completamente la sesión de base de datos
        db.session.close()
        db.session = db.create_scoped_session()
        resultados['mensajes'].append("Sesión de base de datos reiniciada exitosamente")
        
        # 2. Verificar clases duplicadas (misma fecha y horario)
        sql_duplicados = """
        SELECT cr1.id, cr1.fecha, cr1.horario_id, cr1.profesor_id
        FROM clase_realizada cr1
        JOIN (
            SELECT fecha, horario_id, COUNT(*) as cnt
            FROM clase_realizada
            GROUP BY fecha, horario_id
            HAVING COUNT(*) > 1
        ) cr2 ON cr1.fecha = cr2.fecha AND cr1.horario_id = cr2.horario_id
        ORDER BY cr1.fecha, cr1.horario_id, cr1.id
        """
        
        duplicados = db.session.execute(sql_duplicados).fetchall()
        
        if duplicados:
            resultados['mensajes'].append(f"Se encontraron {len(duplicados)} clases duplicadas")
            
            # Agrupar por fecha y horario
            grupos_duplicados = {}
            for dup in duplicados:
                key = (dup.fecha, dup.horario_id)
                if key not in grupos_duplicados:
                    grupos_duplicados[key] = []
                grupos_duplicados[key].append(dup.id)
            
            # Resolver duplicados (mantener el ID más bajo y eliminar los demás)
            for key, ids in grupos_duplicados.items():
                fecha, horario_id = key
                ids_ordenados = sorted(ids)
                id_mantener = ids_ordenados[0]
                ids_eliminar = ids_ordenados[1:]
                
                resultados['mensajes'].append(f"Manteniendo clase ID {id_mantener} para fecha {fecha} y horario {horario_id}")
                
                for id_eliminar in ids_eliminar:
                    try:
                        # Eliminar directo con SQL para evitar restricciones
                        db.session.execute(f"DELETE FROM clase_realizada WHERE id = {id_eliminar}")
                        resultados['mensajes'].append(f"Eliminada clase duplicada ID {id_eliminar}")
                    except Exception as e:
                        resultados['mensajes'].append(f"Error al eliminar clase ID {id_eliminar}: {str(e)}")
            
            db.session.commit()
        else:
            resultados['mensajes'].append("No se encontraron clases duplicadas")
        
        # 3. Buscar clases con referencias a horarios que ya no existen
        sql_huerfanas = """
        SELECT cr.id, cr.fecha, cr.horario_id
        FROM clase_realizada cr
        LEFT JOIN horario_clase hc ON cr.horario_id = hc.id
        WHERE hc.id IS NULL
        """
        
        huerfanas = db.session.execute(sql_huerfanas).fetchall()
        
        if huerfanas:
            resultados['mensajes'].append(f"Se encontraron {len(huerfanas)} clases huérfanas (sin horario asociado)")
            
            for h in huerfanas:
                try:
                    # Intentar recuperar eliminando solo la clase problemática
                    db.session.execute(f"DELETE FROM clase_realizada WHERE id = {h.id}")
                    resultados['mensajes'].append(f"Eliminada clase huérfana ID {h.id} (fecha: {h.fecha}, horario_id inválido: {h.horario_id})")
                except Exception as e:
                    resultados['mensajes'].append(f"Error al eliminar clase huérfana ID {h.id}: {str(e)}")
            
            db.session.commit()
        else:
            resultados['mensajes'].append("No se encontraron clases huérfanas")
        
        # 4. Verificar consistencia de profesores
        sql_prof_inconsistentes = """
        SELECT cr.id, cr.fecha, cr.horario_id, cr.profesor_id as prof_clase, hc.profesor_id as prof_horario
        FROM clase_realizada cr
        JOIN horario_clase hc ON cr.horario_id = hc.id
        WHERE cr.profesor_id != hc.profesor_id
        """
        
        inconsistentes = db.session.execute(sql_prof_inconsistentes).fetchall()
        
        if inconsistentes:
            resultados['mensajes'].append(f"Se encontraron {len(inconsistentes)} clases con profesor inconsistente")
            
            for inc in inconsistentes:
                try:
                    # Corregir la inconsistencia actualizando el profesor de la clase al del horario
                    db.session.execute(
                        "UPDATE clase_realizada SET profesor_id = :prof_horario WHERE id = :id",
                        {'prof_horario': inc.prof_horario, 'id': inc.id}
                    )
                    resultados['mensajes'].append(f"Corregida clase ID {inc.id} - profesor actualizado de {inc.prof_clase} a {inc.prof_horario}")
                except Exception as e:
                    resultados['mensajes'].append(f"Error al corregir profesor en clase ID {inc.id}: {str(e)}")
            
            db.session.commit()
        else:
            resultados['mensajes'].append("No se encontraron clases con profesor inconsistente")
            
        # Final: Compactar la base de datos (VACUUM)
        try:
            db.session.execute("VACUUM")
            resultados['mensajes'].append("Base de datos compactada exitosamente")
        except Exception as e:
            resultados['mensajes'].append(f"Error al compactar la base de datos: {str(e)}")
        
        flash('Depuración de base de datos completada con éxito', 'success')
        
    except Exception as e:
        resultados['success'] = False
        resultados['mensajes'].append(f"Error general: {str(e)}")
        flash(f'Error durante la depuración: {str(e)}', 'danger')
    
    return render_template('mantenimiento/depurar_base_datos.html', resultados=resultados)

@app.route('/mantenimiento/test-debug')
def test_debug_mantenimiento():
    return "Ruta de prueba para mantenimiento activa"

@app.route('/test-debug-root')
def test_debug_root():
    return "Ruta de prueba en la raíz activa"