from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, time

# Inicializamos SQLAlchemy sin la aplicación, para hacerlo más modular.
db = SQLAlchemy()

class Profesor(db.Model):
    __tablename__ = 'profesor'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    tarifa_por_clase = db.Column(db.Float, nullable=False)
    telefono = db.Column(db.String(20))
    email = db.Column(db.String(100))
    # Relaciones con otros modelos
    horarios = db.relationship('HorarioClase', backref='profesor', lazy=True)
    clases_realizadas = db.relationship('ClaseRealizada', backref='profesor', lazy=True)
    
    def __repr__(self):
        return f'<Profesor {self.nombre} {self.apellido}>'

class HorarioClase(db.Model):
    __tablename__ = 'horario_clase'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    dia_semana = db.Column(db.Integer, nullable=False)  # 0: Lunes, 1: Martes, etc.
    hora_inicio = db.Column(db.Time, nullable=False)
    duracion = db.Column(db.Integer, default=60)  # Duración en minutos
    profesor_id = db.Column(db.Integer, db.ForeignKey('profesor.id'), nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    capacidad_maxima = db.Column(db.Integer, default=20)
    tipo_clase = db.Column(db.String(20), default='OTRO')
    clases_realizadas = db.relationship('ClaseRealizada', backref='horario', lazy=True)
    
    def __repr__(self):
        return f'<HorarioClase {self.nombre} - {self.dia_semana} {self.hora_inicio}>'
    
    @property
    def nombre_dia(self):
        # Convertir el número de día a nombre de día
        dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        return dias[self.dia_semana]
    
    @property
    def hora_fin_str(self):
        # Calcula la hora de fin sumando la duración (en minutos) a la hora de inicio
        total_minutos = self.hora_inicio.hour * 60 + self.hora_inicio.minute + self.duracion
        end_hour, end_minute = divmod(total_minutos, 60)
        # Ajuste si la hora supera las 24 horas
        end_hour = end_hour % 24
        return f"{end_hour:02d}:{end_minute:02d}"

class ClaseRealizada(db.Model):
    __tablename__ = 'clase_realizada'
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
        return f'<ClaseRealizada {self.horario.nombre} - {self.fecha}>'
    
    @property
    def estado(self):
        # Si no se ha registrado la hora de llegada, la clase se considera pendiente
        if self.hora_llegada_profesor is None:
            return "Pendiente"
        return "Realizada"
    
    @property
    def puntualidad(self):
        # Compara la hora de inicio con la hora de llegada para determinar si fue puntual o con retraso
        if self.hora_llegada_profesor is None:
            return "N/A"
        scheduled = self.horario.hora_inicio
        arrival = self.hora_llegada_profesor
        if arrival <= scheduled:
            return "Puntual"
        else:
            diff = (datetime.combine(datetime.today(), arrival) - datetime.combine(datetime.today(), scheduled)).seconds / 60
            if diff <= 10:
                return "Retraso leve"
            else:
                return "Retraso significativo"
