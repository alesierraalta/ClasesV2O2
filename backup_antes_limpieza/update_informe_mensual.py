"""
Script para verificar y corregir problemas con el informe mensual
"""

import os
import sys
import sqlite3
from datetime import datetime, date

def verificar_consulta_informe():
    # Ruta a la base de datos
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gimnasio.db')
    
    if not os.path.exists(db_path):
        print("ERROR: No se encontró la base de datos gimnasio.db")
        return False
    
    try:
        # Consulta corregida que debe funcionar
        sql_clases = """
        SELECT 
            cr.id, cr.fecha, cr.horario_id, cr.profesor_id, cr.hora_llegada_profesor, 
            cr.cantidad_alumnos, cr.observaciones, cr.audio_file, cr.fecha_registro,
            hc.nombre, hc.hora_inicio as horario_hora_inicio, hc.tipo_clase, hc.duracion,
            p.nombre as profesor_nombre, p.apellido as profesor_apellido, p.tarifa_por_clase
        FROM clase_realizada cr
        JOIN horario_clase hc ON cr.horario_id = hc.id
        JOIN profesor p ON cr.profesor_id = p.id
        LIMIT 1
        """
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Probar la consulta
        try:
            cursor.execute(sql_clases)
            print("✅ Consulta SQL para informe_mensual funciona correctamente.")
            return True
        except sqlite3.OperationalError as e:
            error_msg = str(e)
            print(f"❌ Error en la consulta SQL: {error_msg}")
            
            # Verificar si es el error específico de 'no such column: cr.hora_inicio'
            if "no such column: cr.hora_inicio" in error_msg:
                print("\n🔍 Diagnóstico: La columna 'hora_inicio' no existe en la tabla 'clase_realizada'.")
                print("\nPara solucionar este problema tienes dos opciones:")
                print("\n1. Actualizar la aplicación usando la versión más reciente del código")
                print("   que ya tiene corregido este problema.")
                print("\n2. Modificar manualmente el archivo app.py y eliminar 'cr.hora_inicio' ")
                print("   de la consulta SQL en la función informe_mensual.")
                
                # Verificar si la columna existe en la estructura de la tabla
                try:
                    cursor.execute("PRAGMA table_info(clase_realizada)")
                    columnas = [col[1] for col in cursor.fetchall()]
                    if 'hora_inicio' in columnas:
                        print("\n⚠️ NOTA: La columna 'hora_inicio' SÍ existe en la tabla 'clase_realizada',")
                        print("   pero hay un problema con la consulta SQL. Contacta al desarrollador.")
                    else:
                        print("\n⚠️ NOTA: La columna 'hora_inicio' NO existe en la tabla 'clase_realizada'.")
                        print("   Este es el comportamiento esperado en la versión actual de la aplicación.")
                except Exception as e2:
                    print(f"\nError al verificar estructura de la tabla: {e2}")
            
            return False
        
    except Exception as e:
        print(f"Error general: {e}")
        return False
    finally:
        try:
            conn.close()
        except:
            pass

if __name__ == "__main__":
    print("=== Verificación de Consulta de Informe Mensual ===")
    verificar_consulta_informe() 