"""
Configuración de fixtures para pruebas en pytest.
"""
import os
import sys
import pytest
from tempfile import mkstemp
from datetime import datetime, time

# Añadir el directorio raíz del proyecto al PATH para importar módulos
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app as flask_app, db
from models import Profesor, HorarioClase, ClaseRealizada
import notifications

@pytest.fixture(scope='session')
def app():
    """Fixture que proporciona una instancia de la aplicación Flask para pruebas."""
    # Configurar la aplicación para pruebas
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    flask_app.config['SERVER_NAME'] = 'localhost.localdomain'
    
    # Crear una base de datos en memoria para pruebas
    db_fd, db_path = mkstemp()
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    
    yield flask_app
    
    # Cerrar y eliminar el archivo temporal
    os.close(db_fd)
    os.unlink(db_path)

@pytest.fixture(scope='function')
def app_context(app):
    """Fixture que proporciona un contexto de aplicación Flask para pruebas."""
    with app.app_context():
        db.create_all()  # Crear tablas al inicio de cada prueba
        yield
        db.session.remove()
        db.drop_all()  # Eliminar tablas después de cada prueba

@pytest.fixture(scope='function')
def test_client(app, app_context):
    """Fixture que proporciona un cliente HTTP para pruebas."""
    with app.test_client() as client:
        yield client

@pytest.fixture(scope='function')
def db_session(app_context):
    """Fixture que proporciona una sesión de base de datos limpia para cada prueba."""
    connection = db.engine.connect()
    transaction = connection.begin()
    
    # Crear una sesión específica para la prueba
    session = db.session
    
    yield session
    
    # Limpiar después de la prueba
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture
def sample_profesor(db_session):
    """Fixture que crea un profesor de prueba."""
    profesor = Profesor(nombre="Juan", apellido="Pérez", tarifa_por_clase=35.0)
    db_session.add(profesor)
    db_session.commit()
    return profesor

@pytest.fixture
def sample_horario(db_session, sample_profesor):
    """Fixture que crea un horario de clase de prueba."""
    horario = HorarioClase(
        nombre="Yoga",
        dia_semana=1,  # Martes
        hora_inicio=time(18, 0),  # 18:00
        profesor_id=sample_profesor.id
    )
    db_session.add(horario)
    db_session.commit()
    return horario
