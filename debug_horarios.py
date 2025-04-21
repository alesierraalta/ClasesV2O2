import sqlite3
from datetime import datetime, time
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Connect to the database
conn = sqlite3.connect('gimnasio.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

def debug_hora_fin_str(hora_inicio, duracion):
    """Debugging function for hora_fin_str calculation"""
    logger.debug(f"Debugging hora_fin_str: hora_inicio={hora_inicio}, tipo={type(hora_inicio)}, duracion={duracion}")
    
    # Handle string format with microseconds
    if isinstance(hora_inicio, str):
        if "." in hora_inicio:
            hora_inicio = hora_inicio.split('.')[0]
            logger.debug(f"Removed microseconds: {hora_inicio}")
        
        # Convert string to time object
        try:
            if hora_inicio.count(":") == 1:
                hora_inicio = datetime.strptime(hora_inicio, '%H:%M').time()
            else:
                hora_inicio = datetime.strptime(hora_inicio, '%H:%M:%S').time()
            logger.debug(f"Converted to time object: {hora_inicio}")
        except Exception as e:
            logger.error(f"Error converting time: {e}")
            return "Error in time conversion"
    
    # Calculate end time
    try:
        minutos_totales = hora_inicio.hour * 60 + hora_inicio.minute + duracion
        logger.debug(f"minutos_totales = {minutos_totales}")
        
        horas, minutos = divmod(minutos_totales, 60)
        logger.debug(f"horas antes modulo = {horas}, minutos = {minutos}")
        
        # Ensure hours are in 24h format (0-23)
        horas = horas % 24
        logger.debug(f"horas después modulo = {horas}")
        
        resultado = f"{horas:02d}:{minutos:02d}"
        logger.debug(f"hora_fin_str resultado final = {resultado}")
        return resultado
    except Exception as e:
        logger.error(f"Error calculating end time: {e}")
        return "Error in calculation"

def check_class_data():
    """Query the database and check class data for schedule issues"""
    logger.info("Checking class data in the database...")
    
    # Query to get all classes in April 2025
    query = """
    SELECT 
        cr.id, cr.fecha, cr.horario_id, cr.profesor_id, cr.hora_llegada_profesor, 
        cr.cantidad_alumnos, cr.observaciones, cr.audio_file,
        hc.nombre, hc.hora_inicio, hc.tipo_clase, hc.duracion,
        p.nombre as profesor_nombre, p.apellido as profesor_apellido
    FROM clase_realizada cr
    JOIN horario_clase hc ON cr.horario_id = hc.id
    JOIN profesor p ON cr.profesor_id = p.id
    WHERE cr.fecha >= '2025-04-01' AND cr.fecha <= '2025-04-30'
    ORDER BY cr.fecha, hc.hora_inicio
    """
    
    cursor.execute(query)
    clases = cursor.fetchall()
    
    logger.info(f"Found {len(clases)} classes for April 2025")
    
    for i, clase in enumerate(clases[:20]):  # Only check the first 20 classes to avoid too much output
        logger.info(f"Class {i+1}: ID={clase['id']}, Date={clase['fecha']}, Name={clase['nombre']}")
        
        # Extract and check hora_inicio
        hora_inicio = clase['hora_inicio']
        logger.info(f"  hora_inicio (raw) = {hora_inicio}, type = {type(hora_inicio)}")
        
        # Process hora_inicio to make it usable
        if isinstance(hora_inicio, str):
            try:
                if '.' in hora_inicio:
                    hora_sin_micro = hora_inicio.split('.')[0]
                    logger.info(f"  Removing microseconds: {hora_sin_micro}")
                    
                    if hora_sin_micro.count(":") == 1:
                        hora_procesada = datetime.strptime(hora_sin_micro, '%H:%M').time()
                    else:
                        hora_procesada = datetime.strptime(hora_sin_micro, '%H:%M:%S').time()
                else:
                    if hora_inicio.count(":") == 1:
                        hora_procesada = datetime.strptime(hora_inicio, '%H:%M').time()
                    else:
                        hora_procesada = datetime.strptime(hora_inicio, '%H:%M:%S').time()
                
                logger.info(f"  Processed hora_inicio = {hora_procesada}")
            except Exception as e:
                logger.error(f"  Error processing hora_inicio: {e}")
                continue
        else:
            hora_procesada = hora_inicio
            logger.info(f"  No processing needed for hora_inicio")
        
        # Extract and check duracion
        duracion = clase['duracion']
        logger.info(f"  duracion = {duracion}")
        
        # Calculate hora_fin
        hora_fin = debug_hora_fin_str(hora_procesada, duracion)
        logger.info(f"  hora_fin_str = {hora_fin}")
        
        # Full schedule string
        if isinstance(hora_procesada, time):
            horario_completo = f"{hora_procesada.strftime('%H:%M')} - {hora_fin}"
        else:
            horario_completo = f"??:?? - {hora_fin}"
        
        logger.info(f"  Full schedule = {horario_completo}")
        logger.info("------")

def fix_informe_mensual_schedules():
    """Print the code fix needed to address the schedule issue in the informe_mensual function"""
    logger.info("Suggested fix for the informe_mensual function:")
    
    fix = """
    # When processing hora_inicio for each class in the query results:
    
    # CURRENT CODE (problematic):
    hora_inicio_str = str(row.hora_inicio)
    if '.' in hora_inicio_str:
        hora_inicio_str = hora_inicio_str.split('.')[0]
        
    try:
        # Convert string to time object
        if ':' in hora_inicio_str:
            parts = hora_inicio_str.split(':')
            if len(parts) == 2:
                hora_inicio_obj = time(int(parts[0]), int(parts[1]))
            elif len(parts) == 3:
                hora_inicio_obj = time(int(parts[0]), int(parts[1]), int(parts[2]))
            else:
                debug_log(f"Formato de hora inesperado: {hora_inicio_str}")
                hora_inicio_obj = time(0, 0)
        else:
            debug_log(f"Formato de hora no válido: {hora_inicio_str}")
            hora_inicio_obj = time(0, 0)
        
        # Calculate hora_fin as string
        duracion_mins = row.duracion
        minutos_totales = hora_inicio_obj.hour * 60 + hora_inicio_obj.minute + duracion_mins
        hora_fin = f"{minutos_totales // 60:02d}:{minutos_totales % 60:02d}"
    
    # FIXED CODE (recommended):
    hora_inicio_raw = row.hora_inicio
    debug_log(f"Procesando hora: {hora_inicio_raw}, tipo: {type(hora_inicio_raw)}")
    
    # Ensure hora_inicio is a time object
    if isinstance(hora_inicio_raw, str):
        try:
            # Handle microseconds if present
            if '.' in hora_inicio_raw:
                hora_inicio_str = hora_inicio_raw.split('.')[0]
                debug_log(f"Removed microseconds: {hora_inicio_str}")
            else:
                hora_inicio_str = hora_inicio_raw
            
            # Convert to time object based on format
            if hora_inicio_str.count(':') == 1:
                hora_inicio_obj = datetime.strptime(hora_inicio_str, '%H:%M').time()
            else:
                hora_inicio_obj = datetime.strptime(hora_inicio_str, '%H:%M:%S').time()
        except Exception as e:
            debug_log(f"Error converting time string: {str(e)}")
            hora_inicio_obj = time(10, 13)  # Default time that appears in error (for diagnostic)
    else:
        # If it's already a time object
        hora_inicio_obj = hora_inicio_raw
    
    # Calculate end time
    try:
        duracion_mins = int(row.duracion) if row.duracion is not None else 60
        minutos_totales = hora_inicio_obj.hour * 60 + hora_inicio_obj.minute + duracion_mins
        horas, minutos = divmod(minutos_totales, 60)
        horas = horas % 24  # Handle 24h format
        hora_fin = f"{horas:02d}:{minutos:02d}"
        debug_log(f"Calculated end time: {hora_fin} (from {hora_inicio_obj} + {duracion_mins} minutes)")
    except Exception as e:
        debug_log(f"Error calculating end time: {str(e)}")
        hora_fin = "11:13"  # Default time that appears in error (for diagnostic)
    """
    
    logger.info(fix)

if __name__ == "__main__":
    try:
        logger.info("Starting debug script for class schedules")
        check_class_data()
        logger.info("\n\n")
        fix_informe_mensual_schedules()
    except Exception as e:
        logger.error(f"Error in debug script: {e}")
    finally:
        conn.close()
        logger.info("Debug script completed") 