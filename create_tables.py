from app import app, db
from models import Profesor, HorarioClase, ClaseRealizada

print("Starting database table creation...")

# Execute within the app context
with app.app_context():
    # Create all tables if they don't exist
    db.create_all()
    print("Tables created successfully.")
    
    # Check if tables exist
    print("Verifying tables...")
    try:
        # Trying to query the tables to see if they exist
        profesor_count = Profesor.query.count()
        horario_count = HorarioClase.query.count()
        clase_count = ClaseRealizada.query.count()
        
        print(f"Database contains:")
        print(f"- {profesor_count} profesores")
        print(f"- {horario_count} horarios de clase")
        print(f"- {clase_count} clases realizadas")
        
    except Exception as e:
        print(f"Error verifying tables: {e}")
    
    print("Database setup complete.") 