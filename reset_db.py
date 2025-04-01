from app import app, db
import os

# Ejecutar dentro del contexto de la aplicación
with app.app_context():
    # Eliminar la base de datos si existe
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gimnasio.db')
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f'Base de datos {db_path} eliminada.')
    else:
        print(f'No se encontró la base de datos en {db_path}')
    
    # Crear todas las tablas
    db.create_all()
    print('Tablas creadas con la estructura actualizada.')
    
    print('Base de datos inicializada correctamente.')
