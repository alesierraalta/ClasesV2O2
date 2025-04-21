import requests
from bs4 import BeautifulSoup
import re
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_monthly_report():
    """
    Test if the fix for the schedule times in the monthly report worked correctly.
    Makes a request to the monthly report page and checks the displayed schedules.
    """
    try:
        # Make a request to the monthly report page
        url = "http://localhost:5000/informes/mensual"
        params = {
            "mes": 4,
            "anio": 2025,
            "auto": 1
        }
        
        logger.info(f"Requesting monthly report from {url} with params: {params}")
        response = requests.get(url, params=params)
        
        if response.status_code != 200:
            logger.error(f"Failed to get the report page. Status code: {response.status_code}")
            return False
        
        logger.info("Successfully retrieved the report page")
        
        # Parse the HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the table with the class schedule data
        table = soup.find('table', id='tableclases')
        if not table:
            logger.error("Could not find the class schedule table in the response")
            return False
        
        # Find all rows in the table body
        rows = table.find('tbody').find_all('tr')
        if not rows:
            logger.error("No class data found in the table")
            return False
        
        logger.info(f"Found {len(rows)} class entries in the report")
        
        # Check each row for the schedule format
        default_pattern = re.compile(r'10:13 - 11:13')
        fixed = True
        schedules = []
        
        for i, row in enumerate(rows[:10]):  # Check first 10 rows as a sample
            # Get the schedule cell (3rd cell in each row)
            cells = row.find_all('td')
            if len(cells) < 3:
                logger.warning(f"Row {i+1} does not have enough cells")
                continue
            
            schedule_cell = cells[2].get_text().strip()
            schedules.append(schedule_cell)
            
            # Check if the schedule is in the default erroneous format
            if default_pattern.match(schedule_cell):
                logger.error(f"Row {i+1} still has the erroneous schedule format: {schedule_cell}")
                fixed = False
            elif not re.match(r'\d{2}:\d{2} - \d{2}:\d{2}', schedule_cell):
                logger.warning(f"Row {i+1} has a schedule in an unexpected format: {schedule_cell}")
        
        if fixed:
            logger.info("Fix appears to be successful! Schedules are no longer showing as 10:13 - 11:13")
            logger.info(f"Sample schedules: {schedules[:5]}")
            return True
        else:
            logger.error("Fix did not work. Some schedules are still showing as 10:13 - 11:13")
            return False
            
    except Exception as e:
        logger.error(f"Error while testing the fix: {e}")
        return False

if __name__ == "__main__":
    success = test_monthly_report()
    if success:
        print("\n✅ TEST PASSED: The schedule time display issue has been fixed!")
    else:
        print("\n❌ TEST FAILED: The schedule time display issue persists.") 