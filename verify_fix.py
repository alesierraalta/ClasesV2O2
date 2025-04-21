import requests
from bs4 import BeautifulSoup
import sqlite3
import re
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_expected_schedules():
    """Query the database to get the expected schedules for April 2025 classes"""
    conn = sqlite3.connect('gimnasio.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Query all classes for April 2025
    query = """
    SELECT 
        cr.id, cr.fecha, cr.horario_id, 
        hc.nombre as clase_nombre, hc.hora_inicio, hc.duracion
    FROM clase_realizada cr
    JOIN horario_clase hc ON cr.horario_id = hc.id
    WHERE cr.fecha >= '2025-04-01' AND cr.fecha <= '2025-04-30'
    ORDER BY cr.fecha, hc.hora_inicio
    """
    
    cursor.execute(query)
    rows = cursor.fetchall()
    
    expected = {}
    
    for row in rows:
        hora_inicio_raw = row['hora_inicio']
        
        # Process the time to match the expected format
        if isinstance(hora_inicio_raw, str):
            # Remove microseconds if present
            if '.' in hora_inicio_raw:
                hora_inicio_raw = hora_inicio_raw.split('.')[0]
            
            # Parse based on format
            try:
                if hora_inicio_raw.count(':') == 1:
                    hora_inicio = datetime.strptime(hora_inicio_raw, '%H:%M').time()
                else:
                    hora_inicio = datetime.strptime(hora_inicio_raw, '%H:%M:%S').time()
                
                # Calculate end time
                duracion = row['duracion']
                minutos_totales = hora_inicio.hour * 60 + hora_inicio.minute + duracion
                horas, minutos = divmod(minutos_totales, 60)
                horas = horas % 24
                
                # Format as HH:MM - HH:MM
                schedule = f"{hora_inicio.hour:02d}:{hora_inicio.minute:02d} - {horas:02d}:{minutos:02d}"
                
                expected[row['id']] = {
                    'id': row['id'],
                    'schedule': schedule, 
                    'hora_inicio_raw': hora_inicio_raw
                }
            except Exception as e:
                logger.error(f"Error processing time for class {row['id']}: {e}")
    
    conn.close()
    return expected

def get_actual_schedules():
    """Get the schedules as displayed in the monthly report"""
    try:
        # Request the monthly report
        url = "http://localhost:5000/informes/mensual"
        params = {
            "mes": 4,
            "anio": 2025,
            "auto": 1
        }
        
        logger.info(f"Requesting monthly report from {url} with params {params}")
        response = requests.get(url, params=params)
        
        if response.status_code != 200:
            logger.error(f"Failed to get report. Status code: {response.status_code}")
            return {}
        
        # Parse the HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all class rows (first locate the table, then get rows)
        table = soup.find('table', id='tableclases')
        if not table:
            logger.error("Could not find the classes table in the HTML")
            return {}
        
        rows = table.find('tbody').find_all('tr')
        
        # Extract the schedules
        actual = {}
        for row in rows:
            try:
                # Extract the class ID from the URL in a possible edit link
                links = row.find_all('a', href=re.compile(r'/asistencia/editar/(\d+)'))
                if links:
                    class_id = int(re.search(r'/asistencia/editar/(\d+)', links[0]['href']).group(1))
                else:
                    # If no edit link, try to find another way to identify the class
                    # For now, we'll skip this row
                    continue
                
                # Get the schedule cell (3rd column)
                cells = row.find_all('td')
                if len(cells) >= 3:
                    schedule = cells[2].get_text().strip()
                    actual[class_id] = {
                        'id': class_id,
                        'schedule': schedule
                    }
            except Exception as e:
                logger.error(f"Error extracting schedule from row: {e}")
        
        return actual
    
    except Exception as e:
        logger.error(f"Error getting actual schedules: {e}")
        return {}

def verify_fix():
    """Verify if the fix for the schedule display issue worked"""
    # Get expected schedules from database
    expected = get_expected_schedules()
    
    # Get actual schedules from HTML
    actual = get_actual_schedules()
    
    if not expected or not actual:
        logger.error("Could not get expected or actual schedules")
        return False
    
    logger.info(f"Retrieved {len(expected)} expected schedules and {len(actual)} actual schedules")
    
    # Compare schedules
    matches = 0
    failures = 0
    
    print("\n=== SCHEDULE COMPARISON ===")
    print(f"{'CLASS ID':<10} {'EXPECTED':<20} {'ACTUAL':<20} {'MATCH':<5}")
    print("-" * 55)
    
    for class_id, expected_data in expected.items():
        if class_id in actual:
            expected_schedule = expected_data['schedule']
            actual_schedule = actual[class_id]['schedule']
            
            # Check if they match
            is_match = (expected_schedule == actual_schedule)
            match_str = "✓" if is_match else "✗"
            
            # Only print first 10 for brevity
            if class_id <= 10 or not is_match:
                print(f"{class_id:<10} {expected_schedule:<20} {actual_schedule:<20} {match_str}")
            
            if is_match:
                matches += 1
            else:
                failures += 1
    
    # Print summary
    print("\n=== SUMMARY ===")
    print(f"Total classes checked: {len(expected)}")
    print(f"Matches: {matches}")
    print(f"Failures: {failures}")
    
    success_rate = (matches / len(expected)) * 100 if expected else 0
    print(f"Success rate: {success_rate:.1f}%")
    
    # Check if we had the 10:13 - 11:13 problem
    all_schedules = [data['schedule'] for data in actual.values()]
    ten_thirteen_pattern = "10:13 - 11:13"
    has_ten_thirteen = any(s == ten_thirteen_pattern for s in all_schedules)
    
    if has_ten_thirteen:
        logger.error(f"The '10:13 - 11:13' issue is still present in {all_schedules.count(ten_thirteen_pattern)} schedules")
        print(f"\n❌ The '10:13 - 11:13' issue is still present!")
    else:
        logger.info("The '10:13 - 11:13' issue has been fixed")
        print("\n✅ The '10:13 - 11:13' issue has been fixed!")
    
    return success_rate >= 90 and not has_ten_thirteen

if __name__ == "__main__":
    print("\n🔍 VERIFYING SCHEDULE FIX...\n")
    success = verify_fix()
    
    if success:
        print("\n✅ VERIFICATION PASSED: The schedule display issue has been fixed!")
    else:
        print("\n❌ VERIFICATION FAILED: The schedule display issue is still present.") 