import os
import sqlite3
import pandas as pd
from datetime import datetime
import time
import re

def protect_sensitive_data(df, level='completa'):
    """
    Protege datos sensibles en el DataFrame según el nivel especificado.
    
    Args:
        df (DataFrame): DataFrame con datos a proteger
        level (str): Nivel de protección ('completa', 'parcial', 'ninguna')
    
    Returns:
        DataFrame: DataFrame con datos protegidos
    """
    # Si el nivel es 'ninguna', devolver el DataFrame sin cambios
    if level == 'ninguna':
        return df
    
    # Crear una copia del DataFrame para no modificar el original
    protected_df = df.copy()
    
    # Lista de nombres de columnas que pueden contener datos sensibles
    sensitive_columns = ['telefono', 'email', 'correo', 'celular', 'movil', 'contacto']
    
    # Buscar columnas sensibles en el DataFrame
    columns_to_protect = []
    for col in protected_df.columns:
        col_lower = col.lower()
        if any(sensitive in col_lower for sensitive in sensitive_columns):
            columns_to_protect.append(col)
    
    # Aplicar protección a las columnas sensibles
    for col in columns_to_protect:
        if col in protected_df.columns:
            if level == 'completa':
                if 'email' in col.lower() or 'correo' in col.lower():
                    # Ocultar completamente el email
                    protected_df[col] = protected_df[col].apply(lambda x: '******@****.***' if pd.notna(x) else x)
                else:
                    # Ocultar completamente el teléfono
                    protected_df[col] = protected_df[col].apply(lambda x: '**********' if pd.notna(x) else x)
            elif level == 'parcial':
                if 'email' in col.lower() or 'correo' in col.lower():
                    # Mostrar solo el dominio del email
                    protected_df[col] = protected_df[col].apply(
                        lambda x: f'*****@{x.split("@")[1]}' if pd.notna(x) and '@' in str(x) else '******@****.***' if pd.notna(x) else x
                    )
                else:
                    # Mostrar solo los últimos 3 dígitos del teléfono
                    protected_df[col] = protected_df[col].apply(
                        lambda x: f'*******{str(x)[-3:]}' if pd.notna(x) and len(str(x)) >= 3 else '**********' if pd.notna(x) else x
                    )
    
    return protected_df

def export_tables_to_excel(db_path='gimnasio.db', output_dir='backups', protection_level='completa', 
                          create_unified=True, create_individual=True):
    """
    Exporta tablas de la base de datos SQLite a archivos Excel con protección de datos sensibles.
    
    Args:
        db_path (str): Ruta al archivo de base de datos SQLite
        output_dir (str): Directorio donde se guardarán los archivos Excel
        protection_level (str): Nivel de protección de datos ('completa', 'parcial', 'ninguna')
        create_unified (bool): Si se debe crear un archivo Excel unificado con todas las tablas
        create_individual (bool): Si se deben crear archivos Excel individuales para cada tabla
    
    Returns:
        dict: Diccionario con información de los archivos exportados
    """
    # Crear directorio de respaldo si no existe
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Timestamp para los nombres de archivo
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Conectar a la base de datos
    conn = sqlite3.connect(db_path)
    
    # Obtener lista de tablas
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    exported_files = {}
    dataframes = {}
    
    for table in tables:
        table_name = table[0]
        # Saltear tablas del sistema SQLite
        if table_name.startswith('sqlite_'):
            continue
            
        # Leer tabla en un DataFrame
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        
        # Proteger datos sensibles
        protected_df = protect_sensitive_data(df, level=protection_level)
        dataframes[table_name] = protected_df
        
        # Exportar a Excel si se solicita archivos individuales
        if create_individual:
            # Nombre del archivo de salida
            output_file = os.path.join(output_dir, f"{table_name}_{timestamp}.xlsx")
            
            # Exportar a Excel
            protected_df.to_excel(output_file, index=False)
            
            # Guardar info en diccionario de resultados
            exported_files[table_name] = {
                'file_path': output_file,
                'row_count': len(protected_df)
            }
            
            print(f"Tabla '{table_name}' exportada a '{output_file}' ({len(protected_df)} registros)")
    
    # También crear un archivo Excel con todas las tablas en distintas hojas si se solicita
    if create_unified:
        output_file_all = os.path.join(output_dir, f"gimnasio_completo_{timestamp}.xlsx")
        with pd.ExcelWriter(output_file_all) as writer:
            for table_name, protected_df in dataframes.items():
                protected_df.to_excel(writer, sheet_name=table_name, index=False)
        
        print(f"Backup completo creado en '{output_file_all}'")
        exported_files['completo'] = {'file_path': output_file_all}
    
    conn.close()
    
    return exported_files

if __name__ == "__main__":
    try:
        export_tables_to_excel()
        print("\nExportación completada con éxito.")
    except Exception as e:
        print(f"\nError durante la exportación: {str(e)}")
        time.sleep(5)  # Pausa para leer el error 