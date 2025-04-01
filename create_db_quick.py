import sqlite3 
try: 
    conn = sqlite3.connect('gimnasio.db') 
    print('Base de datos verificada correctamente') 
    conn.close() 
except Exception as e: 
    print(f'Error con la base de datos: {e}') 
