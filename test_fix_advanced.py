import sqlite3
import requests
from bs4 import BeautifulSoup
import re
import logging
from datetime import datetime, time

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_db_schedules():
    """Query the database to get the actual schedules for classes in April 2025"""
    conn = sqlite3.connect('gimnasio.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get class schedules from the database for April 2025
    query = """
    SELECT 
        cr.id, cr.fecha, cr.horario_id, 
        hc.nombre as clase_nombre, hc.hora_inicio, hc.duracion,
        p.nombre as profesor_nombre, p.apellido as profesor_apellido
    FROM clase_realizada cr
    JOIN horario_clase hc ON cr.horario_id = hc.id
    JOIN profesor p ON cr.profesor_id = p.id
    WHERE cr.fecha >= '2025-04-01' AND cr.fecha <= '2025-04-30'
    ORDER BY cr.fecha, hc.hora_inicio
    """
    
    cursor.execute(query)
    rows = cursor.fetchall()
    
    logger.info(f"Found {len(rows)} classes in April 2025 in the database")
    
    # Process and return the schedules
    schedules = []
    for row in rows:
        hora_inicio = row['hora_inicio']
        duracion = row['duracion']
        
        # Process hora_inicio
        if isinstance(hora_inicio, str):
            if '.' in hora_inicio:
                hora_inicio = hora_inicio.split('.')[0]
            
            try:
                if hora_inicio.count(':') == 1:
                    hora_inicio_obj = datetime.strptime(hora_inicio, '%H:%M').time()
                else:
                    hora_inicio_obj = datetime.strptime(hora_inicio, '%H:%M:%S').time()
            except Exception as e:
                logger.error(f"Error converting time for class {row['id']}: {e}")
                hora_inicio_obj = None
        else:
            hora_inicio_obj = hora_inicio
        
        # Calculate hora_fin
        if hora_inicio_obj:
            minutos_totales = hora_inicio_obj.hour * 60 + hora_inicio_obj.minute + duracion
            horas, minutos = divmod(minutos_totales, 60)
            horas = horas % 24
            hora_fin = f"{horas:02d}:{minutos:02d}"
            hora_inicio_str = f"{hora_inicio_obj.hour:02d}:{hora_inicio_obj.minute:02d}"
            schedule = f"{hora_inicio_str} - {hora_fin}"
        else:
            schedule = "Unknown"
        
        schedules.append({
            'id': row['id'],
            'fecha': row['fecha'],
            'clase_nombre': row['clase_nombre'],
            'profesor': f"{row['profesor_nombre']} {row['profesor_apellido']}",
            'hora_inicio_raw': row['hora_inicio'],
            'hora_inicio_obj': hora_inicio_obj,
            'duracion': duracion,
            'schedule': schedule
        })
    
    conn.close()
    return schedules

def get_html_schedules():
    """Get schedules as displayed in the HTML report"""
    try:
        # Make a request to the monthly report page
        url = "http://localhost:5000/informes/mensual"
        params = {
            "mes": 4,
            "anio": 2025,
            "auto": 1
        }
        
        logger.info(f"Requesting monthly report from {url}")
        response = requests.get(url, params=params)
        
        if response.status_code != 200:
            logger.error(f"Failed to get the report page. Status code: {response.status_code}")
            return []
        
        # Parse the HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the table with the class schedule data
        table = soup.find('table', id='tableclases')
        if not table:
            logger.error("Could not find the class schedule table in the response")
            return []
        
        # Find all rows in the table body
        rows = table.find('tbody').find_all('tr')
        if not rows:
            logger.error("No class data found in the table")
            return []
        
        logger.info(f"Found {len(rows)} class entries in the HTML report")
        
        # Extract class schedules from HTML
        html_schedules = []
        for i, row in enumerate(rows):
            cells = row.find_all('td')
            if len(cells) < 10:  # Make sure we have all expected columns
                continue
            
            date = cells[0].get_text().strip()
            class_name = cells[1].get_text().strip()
            schedule = cells[2].get_text().strip()
            professor = cells[3].get_text().strip()
            
            html_schedules.append({
                'date': date,
                'class_name': class_name,
                'schedule': schedule,
                'professor': professor
            })
        
        return html_schedules
            
    except Exception as e:
        logger.error(f"Error while getting HTML schedules: {e}")
        return []

def advanced_test():
    """Perform an advanced test to diagnose the schedule issue"""
    # Get schedules from database
    db_schedules = get_db_schedules()
    
    # Get schedules from HTML
    html_schedules = get_html_schedules()
    
    if not db_schedules or not html_schedules:
        logger.error("Could not retrieve schedules from either database or HTML")
        return False
    
    # Compare schedules
    logger.info("\n======= COMPARISON OF SCHEDULES =======")
    logger.info(f"{'ID':<5} {'Date':<12} {'Class':<25} {'DB Schedule':<15} {'HTML Schedule':<15}")
    logger.info("-" * 80)
    
    matching = 0
    for i, db_sched in enumerate(db_schedules[:10]):  # Check first 10 as a sample
        if i < len(html_schedules):
            html_sched = html_schedules[i]
            
            # Format date for comparison (remove year)
            db_date = db_sched['fecha'].split('-')[2] + '/' + db_sched['fecha'].split('-')[1]
            html_date = '/'.join(html_sched['date'].split('/')[:2])
            
            is_match = (db_sched['schedule'] == html_sched['schedule'])
            match_str = "✓" if is_match else "✗"
            
            logger.info(f"{db_sched['id']:<5} {db_date:<12} {db_sched['clase_nombre']:<25} "
                        f"{db_sched['schedule']:<15} {html_sched['schedule']:<15} {match_str}")
            
            if is_match:
                matching += 1
    
    success_rate = (matching / min(len(db_schedules[:10]), len(html_schedules))) * 100
    logger.info("-" * 80)
    logger.info(f"Match rate: {matching}/{min(len(db_schedules[:10]), len(html_schedules))} ({success_rate:.1f}%)")
    
    # Additional diagnosis: Check hora_inicio values
    logger.info("\n======= DETAILED ANALYSIS OF hora_inicio VALUES =======")
    for i, db_sched in enumerate(db_schedules[:5]):  # Check first 5 for detailed analysis
        logger.info(f"Class ID: {db_sched['id']}")
        logger.info(f"  Raw hora_inicio from DB: {db_sched['hora_inicio_raw']} (type: {type(db_sched['hora_inicio_raw'])})")
        logger.info(f"  Processed hora_inicio: {db_sched['hora_inicio_obj']} (type: {type(db_sched['hora_inicio_obj'])})")
        logger.info(f"  Duration: {db_sched['duracion']} minutes")
        logger.info(f"  Computed schedule: {db_sched['schedule']}")
        logger.info("  ----")
    
    return success_rate > 50

if __name__ == "__main__":
    print("\n🔍 Running advanced test to diagnose schedule issue...\n")
    success = advanced_test()
    
    if success:
        print("\n✅ TEST PASSED: Most schedules match between database and HTML!")
    else:
        print("\n❌ TEST FAILED: Schedules in HTML don't match database values.") 