import sqlite3 
try: 
    import os 
    from app import app, db 
    with app.app_context(): 
        db.create_all() 
    print('Base de datos inicializada correctamente (metodo 1)') 
except Exception as e1: 
    try: 
        conn = sqlite3.connect('gimnasio.db') 
        print('Base de datos creada correctamente (metodo 2)') 
        conn.close() 
    except Exception as e2: 
        print(f'Error al crear la base de datos: {e1}\\n{e2}') 
