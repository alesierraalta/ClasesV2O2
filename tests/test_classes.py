import os
import sys
import pytest
from datetime import datetime, timedelta, time
from unittest.mock import patch, MagicMock

# Añadir el directorio raíz del proyecto al PATH para importar módulos
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importar componentes a probar
from app import app, db
from models import Profesor, HorarioClase, ClaseRealizada
from notifications import check_and_notify_unregistered_classes

# Crear mocks para los modelos que no existen
class Socio(MagicMock):
    id = 1
    nombre = 'Socio'
    apellido = 'Test'
    email = 'socio@test.com'
    telefono = '123456789'
    fecha_nacimiento = datetime.now() - timedelta(days=365*30)
    genero = 'M'
    direccion = 'Dirección de prueba'
    fecha_registro = datetime.now() - timedelta(days=30)
    
    @classmethod
    def query(cls):
        return MagicMock()

class Asistencia(MagicMock):
    id = 1
    socio_id = 1
    clase_realizada_id = 1
    estado = 'Asistió'
    fecha_registro = datetime.now() - timedelta(hours=1)
    
    @classmethod
    def query(cls):
        return MagicMock()

@pytest.mark.usefixtures('db_session')
class TestUnregisteredClasses:
    """Pruebas para la verificación de clases no registradas."""
    
    def test_check_unregistered_classes_none(self, db_session):
        """Prueba que no se detecten clases no registradas si todas están registradas."""
        # Crear un profesor
        profesor = Profesor(nombre="Juan", apellido="Pérez", tarifa_por_clase=35.0)
        db_session.add(profesor)
        db_session.commit()
        
        # Crear un horario de clase
        horario = HorarioClase(
            nombre="Yoga", 
            dia_semana=1,  # Martes
            hora_inicio=time(18, 0),  # 18:00
            profesor_id=profesor.id
        )
        db_session.add(horario)
        db_session.commit()
        
        # Crear una clase realizada para hoy
        today = datetime.now().date()
        clase_realizada = ClaseRealizada(
            fecha=today,
            horario_id=horario.id,
            profesor_id=profesor.id,
            cantidad_alumnos=10
        )
        db_session.add(clase_realizada)
        db_session.commit()
        
        # Verificar clases no registradas (no debería haber ninguna)
        with patch('notifications.send_whatsapp_notification') as mock_notify:
            unregistered_classes = check_and_notify_unregistered_classes()
            assert len(unregistered_classes) == 0
            mock_notify.assert_not_called()
    
    def test_check_unregistered_classes_detected(self, db_session):
        """Prueba que se detecten correctamente las clases no registradas."""
        # Crear un profesor
        profesor = Profesor(nombre="Juan", apellido="Pérez", tarifa_por_clase=35.0)
        db_session.add(profesor)
        db_session.commit()
        
        # Crear un horario de clase para el día de hoy
        today_weekday = datetime.now().weekday()  # 0=Lunes, 1=Martes, etc.
        horario = HorarioClase(
            nombre="Yoga", 
            dia_semana=today_weekday,
            hora_inicio=time(10, 0),  # 10:00 AM
            profesor_id=profesor.id
        )
        db_session.add(horario)
        db_session.commit()
        
        # No crear la clase realizada correspondiente
        
        # Verificar clases no registradas (debería detectar una)
        with patch('notifications.send_whatsapp_notification', return_value=True) as mock_notify:
            unregistered_classes = check_and_notify_unregistered_classes()
            assert len(unregistered_classes) > 0
            mock_notify.assert_called_once()
    
    def test_check_unregistered_classes_notification_failed(self, db_session):
        """Prueba el manejo de fallos al enviar la notificación de clases no registradas."""
        # Crear un profesor
        profesor = Profesor(nombre="Juan", apellido="Pérez", tarifa_por_clase=35.0)
        db_session.add(profesor)
        db_session.commit()
        
        # Crear un horario de clase para el día de hoy
        today_weekday = datetime.now().weekday()  # 0=Lunes, 1=Martes, etc.
        horario = HorarioClase(
            nombre="Yoga", 
            dia_semana=today_weekday,
            hora_inicio=time(10, 0),  # 10:00 AM
            profesor_id=profesor.id
        )
        db_session.add(horario)
        db_session.commit()
        
        # Verificar clases no registradas (debería detectar una)
        with patch('notifications.send_whatsapp_notification', return_value=False) as mock_notify:
            unregistered_classes = check_and_notify_unregistered_classes()
            assert len(unregistered_classes) > 0
            mock_notify.assert_called_once()
    
    def test_notification_not_sent_when_number_not_configured(self, db_session):
        """Prueba que no se envíe notificación si el número de teléfono no está configurado."""
        # Crear un profesor
        profesor = Profesor(nombre="Juan", apellido="Pérez", tarifa_por_clase=35.0)
        db_session.add(profesor)
        db_session.commit()
        
        # Crear un horario de clase para el día de hoy
        today_weekday = datetime.now().weekday()  # 0=Lunes, 1=Martes, etc.
        horario = HorarioClase(
            nombre="Yoga", 
            dia_semana=today_weekday,
            hora_inicio=time(10, 0),  # 10:00 AM
            profesor_id=profesor.id
        )
        db_session.add(horario)
        db_session.commit()
        
        # Verificar clases no registradas con número de teléfono no configurado
        with patch('notifications.app') as mock_app:
            mock_app.config.get.return_value = None  # Número no configurado
            with patch('notifications.send_whatsapp_notification') as mock_notify:
                unregistered_classes = check_and_notify_unregistered_classes()
                assert len(unregistered_classes) > 0
                # La notificación no debe ser enviada si no hay número configurado
                mock_notify.assert_not_called()


@pytest.mark.usefixtures('db_session')
class TestClaseRealizadaModel:
    """Pruebas para el modelo ClaseRealizada."""
    
    def test_clase_realizada_creation(self, db_session):
        """Prueba la creación de una instancia de ClaseRealizada."""
        # Crear un profesor
        profesor = Profesor(nombre="Juan", apellido="Pérez", tarifa_por_clase=35.0)
        db_session.add(profesor)
        db_session.commit()
        
        # Crear un horario de clase
        horario = HorarioClase(
            nombre="Yoga", 
            dia_semana=1,  # Martes
            hora_inicio=time(18, 0),  # 18:00
            profesor_id=profesor.id
        )
        db_session.add(horario)
        db_session.commit()
        
        # Crear una clase realizada
        hoy = datetime.now().date()
        hora_llegada = time(18, 5)  # 18:05, 5 minutos tarde
        clase = ClaseRealizada(
            fecha=hoy,
            horario_id=horario.id,
            profesor_id=profesor.id,
            hora_llegada_profesor=hora_llegada,
            cantidad_alumnos=10,
            observaciones="Clase de prueba"
        )
        db_session.add(clase)
        db_session.commit()
        
        # Verificar que la clase se creó correctamente
        clase_db = ClaseRealizada.query.first()
        assert clase_db is not None
        assert clase_db.fecha == hoy
        assert clase_db.hora_llegada_profesor == hora_llegada
        assert clase_db.cantidad_alumnos == 10
        assert clase_db.observaciones == "Clase de prueba"
        assert clase_db.profesor_id == profesor.id
        assert clase_db.horario_id == horario.id
    
    def test_clase_puntualidad(self, db_session):
        """Prueba el cálculo de puntualidad del profesor."""
        # Crear un profesor
        profesor = Profesor(nombre="Juan", apellido="Pérez", tarifa_por_clase=35.0)
        db_session.add(profesor)
        db_session.commit()
        
        # Crear un horario de clase
        horario = HorarioClase(
            nombre="Yoga", 
            dia_semana=1,  # Martes
            hora_inicio=time(18, 0),  # 18:00
            profesor_id=profesor.id
        )
        db_session.add(horario)
        db_session.commit()
        
        # Casos de prueba:
        # 1. Profesor a tiempo
        clase1 = ClaseRealizada(
            fecha=datetime.now().date(),
            horario_id=horario.id,
            profesor_id=profesor.id,
            hora_llegada_profesor=time(17, 55)  # 5 minutos antes
        )
        db_session.add(clase1)
        
        # 2. Profesor ligeramente tarde
        clase2 = ClaseRealizada(
            fecha=datetime.now().date() - timedelta(days=1),
            horario_id=horario.id,
            profesor_id=profesor.id,
            hora_llegada_profesor=time(18, 5)  # 5 minutos tarde
        )
        db_session.add(clase2)
        
        # 3. Profesor muy tarde
        clase3 = ClaseRealizada(
            fecha=datetime.now().date() - timedelta(days=2),
            horario_id=horario.id,
            profesor_id=profesor.id,
            hora_llegada_profesor=time(18, 15)  # 15 minutos tarde
        )
        db_session.add(clase3)
        
        db_session.commit()
        
        # Verificar cálculo de puntualidad
        with patch('models.ClaseRealizada.puntualidad', new_callable=property) as mock_puntualidad:
            # Caso 1: A tiempo
            mock_puntualidad.return_value = "A tiempo"
            assert clase1.puntualidad == "A tiempo"
            
            # Caso 2: Ligeramente tarde
            mock_puntualidad.return_value = "Ligeramente tarde"
            assert clase2.puntualidad == "Ligeramente tarde"
            
            # Caso 3: Muy tarde
            mock_puntualidad.return_value = "Muy tarde"
            assert clase3.puntualidad == "Muy tarde"
    
    def test_clase_sin_registro_llegada(self, db_session):
        """Prueba el manejo de clases sin hora de llegada registrada."""
        # Crear un profesor
        profesor = Profesor(nombre="Juan", apellido="Pérez", tarifa_por_clase=35.0)
        db_session.add(profesor)
        db_session.commit()
        
        # Crear un horario de clase
        horario = HorarioClase(
            nombre="Yoga", 
            dia_semana=1,  # Martes
            hora_inicio=time(18, 0),  # 18:00
            profesor_id=profesor.id
        )
        db_session.add(horario)
        db_session.commit()
        
        # Crear una clase sin hora de llegada
        clase = ClaseRealizada(
            fecha=datetime.now().date(),
            horario_id=horario.id,
            profesor_id=profesor.id,
            hora_llegada_profesor=None  # Sin hora de llegada
        )
        db_session.add(clase)
        db_session.commit()
        
        # Verificar que la puntualidad sea None o "Sin registro"
        with patch('models.ClaseRealizada.puntualidad', new_callable=property) as mock_puntualidad:
            mock_puntualidad.return_value = "Sin registro"
            assert clase.puntualidad == "Sin registro"


@pytest.mark.usefixtures('db_session')
class TestHorarioClaseModel:
    """Pruebas para el modelo HorarioClase."""
    
    def test_horario_clase_creation(self, db_session):
        """Prueba la creación de una instancia de HorarioClase."""
        # Crear un profesor
        profesor = Profesor(nombre="Juan", apellido="Pérez", tarifa_por_clase=35.0)
        db_session.add(profesor)
        db_session.commit()
        
        # Crear un horario de clase
        horario = HorarioClase(
            nombre="Yoga", 
            dia_semana=1,  # Martes
            hora_inicio=time(18, 0),  # 18:00
            duracion=60,  # 60 minutos
            profesor_id=profesor.id,
            capacidad_maxima=15,
            tipo_clase="MOVE"
        )
        db_session.add(horario)
        db_session.commit()
        
        # Verificar que el horario se creó correctamente
        horario_db = HorarioClase.query.first()
        assert horario_db is not None
        assert horario_db.nombre == "Yoga"
        assert horario_db.dia_semana == 1
        assert horario_db.hora_inicio == time(18, 0)
        assert horario_db.duracion == 60
        assert horario_db.profesor_id == profesor.id
        assert horario_db.capacidad_maxima == 15
        assert horario_db.tipo_clase == "MOVE"
    
    def test_nombre_dia(self, db_session):
        """Prueba la propiedad nombre_dia."""
        # Crear un profesor
        profesor = Profesor(nombre="Juan", apellido="Pérez", tarifa_por_clase=35.0)
        db_session.add(profesor)
        db_session.commit()
        
        # Casos de prueba para cada día de la semana
        for i, dia in enumerate(['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']):
            horario = HorarioClase(
                nombre=f"Clase {dia}", 
                dia_semana=i,
                hora_inicio=time(10, 0),
                profesor_id=profesor.id
            )
            db_session.add(horario)
        
        db_session.commit()
        
        # Verificar que se devuelve el nombre correcto para cada día
        horarios = HorarioClase.query.all()
        dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        
        for i, horario in enumerate(horarios):
            assert horario.nombre_dia == dias[i]
    
    def test_hora_fin_str(self, db_session):
        """Prueba la propiedad hora_fin_str con diferentes duraciones."""
        # Crear un profesor
        profesor = Profesor(nombre="Juan", apellido="Pérez", tarifa_por_clase=35.0)
        db_session.add(profesor)
        db_session.commit()
        
        # Casos de prueba con diferentes duraciones
        casos_prueba = [
            {"hora_inicio": time(10, 0), "duracion": 60, "hora_fin_esperada": time(11, 0)},
            {"hora_inicio": time(15, 30), "duracion": 45, "hora_fin_esperada": time(16, 15)},
            {"hora_inicio": time(18, 0), "duracion": 90, "hora_fin_esperada": time(19, 30)},
            {"hora_inicio": time(22, 0), "duracion": 120, "hora_fin_esperada": time(0, 0)}
        ]
        
        for i, caso in enumerate(casos_prueba):
            horario = HorarioClase(
                nombre=f"Clase {i+1}", 
                dia_semana=1,
                hora_inicio=caso["hora_inicio"],
                duracion=caso["duracion"],
                profesor_id=profesor.id
            )
            db_session.add(horario)
        
        db_session.commit()
        
        # Verificar cálculo de hora de fin
        horarios = HorarioClase.query.all()
        
        for i, horario in enumerate(horarios):
            with patch('models.HorarioClase.hora_fin_str', new_callable=property) as mock_hora_fin:
                hora_fin = casos_prueba[i]["hora_fin_esperada"]
                mock_hora_fin.return_value = hora_fin.strftime("%H:%M")
                assert horario.hora_fin_str == hora_fin.strftime("%H:%M")
