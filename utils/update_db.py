from app import db, HorarioClase
import sqlite3
import os

def add_tipo_clase_column():
    """
    Adds the tipo_clase column to the HorarioClase table if it doesn't exist.
    This script should be run once after updating the model.
    """
    print("Checking database structure...")
    
    # Find the database file
    db_path = 'gimnasio.db'
    if not os.path.exists(db_path):
        instance_path = os.path.join('instance', 'gimnasio.db')
        if os.path.exists(instance_path):
            db_path = instance_path
        else:
            print("Database file not found. Please make sure the application has been initialized.")
            return
    
    print(f"Using database at: {db_path}")
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if the table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='horario_clase'")
    if not cursor.fetchone():
        print("Table 'horario_clase' not found. Creating the database schema...")
        # Use SQLAlchemy to create all tables
        db.create_all()
        print("Database schema created.")
    
    # Check if the column already exists
    cursor.execute("PRAGMA table_info(horario_clase)")
    columns = cursor.fetchall()
    column_names = [column[1] for column in columns]
    
    if 'tipo_clase' not in column_names:
        print("Adding tipo_clase column to horario_clase table...")
        
        # Add the new column
        cursor.execute("ALTER TABLE horario_clase ADD COLUMN tipo_clase TEXT DEFAULT 'OTRO'")
        conn.commit()
        
        # Attempt to detect types based on class names
        print("Attempting to automatically categorize existing classes...")
        
        # Get all horarios
        cursor.execute("SELECT id, nombre FROM horario_clase")
        horarios = cursor.fetchall()
        
        # Update tipo_clase based on class name
        for horario_id, nombre in horarios:
            nombre_upper = nombre.upper()
            
            if nombre_upper.startswith('MOVE'):
                tipo = 'MOVE'
            elif nombre_upper.startswith('RIDE'):
                tipo = 'RIDE'
            elif nombre_upper.startswith('BOX'):
                tipo = 'BOX'
            else:
                tipo = 'OTRO'
            
            cursor.execute("UPDATE horario_clase SET tipo_clase = ? WHERE id = ?", (tipo, horario_id))
        
        conn.commit()
        print(f"Updated {len(horarios)} class records with type classification.")
    else:
        print("Column 'tipo_clase' already exists in horario_clase table.")
    
    conn.close()
    print("Database update completed.")

if __name__ == "__main__":
    add_tipo_clase_column() 