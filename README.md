# ClasesO2 
Un sistema completo de gestión para academias de fitness y gimnasios. 
ECHO is off.
## Características 
- Gestión de horarios de clases 
- Control de asistencia de profesores 
- Registro de alumnos en clases 
- Informes y estadísticas 
- Importación/exportación de datos 
ECHO is off.
## Instalación 
1. Clonar el repositorio 
2. Ejecutar los scripts de inicialización dependiendo de tu sistema operativo:
   - Windows: `run.bat`
   - macOS: `run_mac.sh` (ejecutar `chmod +x run_mac.sh` primero para dar permisos de ejecución)
## Estructura del Proyecto
El proyecto ha sido reorganizado para una mejor administración:
- **app.py**: Aplicación principal
- **tests/**: Scripts de prueba
  - Para ejecutar pruebas: `run_all_tests.bat`
- **utils/**: Scripts de utilidad
  - Para crear la base de datos: `create_database.bat` o `utils/create_db.py`
  - Para verificar notificaciones: `check_notifications.bat` o `utils/check_notifications.py`
- **scripts/**: Scripts específicos para cada sistema operativo
  - **mac/**: Scripts para macOS
  - **windows/**: Scripts para Windows
# ClasesV2O2
