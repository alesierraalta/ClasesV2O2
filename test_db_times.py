import os
import sys
import sqlite3
from datetime import datetime, time, date

# Path to your database file
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gimnasio.db')

def hora_fin_str(hora_inicio, duracion):
    """Devuelve la hora de finalización como string"""
    if not hora_inicio:
        return "--:--"
        
    if isinstance(hora_inicio, str):
        try:
            # Handle microseconds
            if "." in hora_inicio:
                hora_inicio = hora_inicio.split('.')[0]  # Remove microseconds
                
            hora_inicio = datetime.strptime(hora_inicio, '%H:%M:%S').time()
        except ValueError:
            try:
                hora_inicio = datetime.strptime(hora_inicio, '%H:%M').time()
            except ValueError:
                return "--:--"
    
    minutos_totales = hora_inicio.hour * 60 + hora_inicio.minute + duracion
    horas, minutos = divmod(minutos_totales, 60)
    # Asegurar que las horas estén en formato 24h (0-23)
    horas = horas % 24
    return f"{horas:02d}:{minutos:02d}"

def check_database_times():
    """Connect to DB and check the hora_fin_str calculations for each HorarioClase"""
    try:
        # Connect to the database
        print(f"Connecting to database at {DB_PATH}")
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Query all HorarioClase records
        cursor.execute('''
            SELECT id, nombre, dia_semana, hora_inicio, duracion, profesor_id 
            FROM horario_clase
            ORDER BY hora_inicio
        ''')
        
        horarios = cursor.fetchall()
        print(f"Found {len(horarios)} scheduled classes in the database")
        
        # Check each record
        for horario in horarios:
            horario_id = horario['id']
            nombre = horario['nombre']
            hora_inicio_str = horario['hora_inicio']
            duracion = horario['duracion']
            
            # Convert hora_inicio to time object
            try:
                if hora_inicio_str and ":" in hora_inicio_str:
                    # Handle microseconds
                    if "." in hora_inicio_str:
                        hora_inicio_str = hora_inicio_str.split('.')[0]  # Remove microseconds
                        
                    if hora_inicio_str.count(":") == 1:
                        # HH:MM format
                        hora_inicio = datetime.strptime(hora_inicio_str, '%H:%M').time()
                    else:
                        # HH:MM:SS format
                        hora_inicio = datetime.strptime(hora_inicio_str, '%H:%M:%S').time()
                else:
                    print(f"⚠️ Invalid hora_inicio format: {hora_inicio_str}")
                    continue
            except Exception as e:
                print(f"⚠️ Error parsing hora_inicio '{hora_inicio_str}': {str(e)}")
                continue
            
            # Calculate end time
            hora_fin = hora_fin_str(hora_inicio, duracion)
            
            # Output the result
            print(f"ID: {horario_id}, Class: {nombre}")
            print(f"  Start: {hora_inicio.strftime('%H:%M')}, Duration: {duracion} min, End: {hora_fin}")
            
            # Get associated ClaseRealizada records and check their end times
            cursor.execute('''
                SELECT cr.id, cr.fecha, cr.hora_llegada_profesor, cr.cantidad_alumnos
                FROM clase_realizada cr
                WHERE cr.horario_id = ?
                ORDER BY cr.fecha DESC
                LIMIT 5
            ''', (horario_id,))
            
            clases = cursor.fetchall()
            if clases:
                print(f"  Recent classes ({len(clases)}):")
                for clase in clases:
                    clase_id = clase['id']
                    fecha = clase['fecha']
                    print(f"    ID: {clase_id}, Date: {fecha}, End time (calculated): {hora_fin}")
            else:
                print("  No classes found for this schedule")
            
            print("")  # Empty line for better readability
            
        conn.close()
        print("Database connection closed")
        
    except Exception as e:
        print(f"Error accessing database: {str(e)}")

if __name__ == "__main__":
    check_database_times() 