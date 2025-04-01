from app import app, db, HorarioClase, Profesor
from datetime import datetime, time

with app.app_context():
    # Verificar si ya existe un profesor
    profesor = Profesor.query.first()
    
    # Si no existe, crear uno
    if not profesor:
        profesor = Profesor(
            nombre='Profesor Test',
            telefono='123456789',
            email='test@test.com'
        )
        db.session.add(profesor)
        db.session.commit()
        print("Profesor de prueba creado.")
    
    # Crear una clase para el día de hoy que ya haya pasado
    ahora = datetime.now()
    hora_actual = ahora.time()
    
    # Establecer una hora que ya haya pasado (1 hora antes)
    hora_clase = time(
        hour=(hora_actual.hour - 2) % 24,
        minute=hora_actual.minute
    )
    
    # Crear un horario de clase para hoy
    horario = HorarioClase(
        nombre='Clase Test',
        dia_semana=ahora.weekday(),
        hora_inicio=hora_clase,
        duracion=45,
        profesor_id=profesor.id,
        tipo_clase='MOVE'
    )
    
    db.session.add(horario)
    db.session.commit()
    
    print(f"Clase de prueba creada con éxito para hoy a las {hora_clase.strftime('%H:%M')}")
