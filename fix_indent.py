with open('app.py', 'r') as file:
    content = file.read()

# Buscar el patrón problemático
pattern = """            return redirect(url_for('informe_mensual', mes=mes, anio=anio, refresh=timestamp, clear_cache=1))
        else:
                return redirect(url_for('clases_no_registradas', refresh=timestamp, clear_cache=1))"""

# Reemplazarlo con el correcto
fixed_pattern = """            return redirect(url_for('informe_mensual', mes=mes, anio=anio, refresh=timestamp, clear_cache=1))
        else:
            return redirect(url_for('clases_no_registradas', refresh=timestamp, clear_cache=1))"""

# Aplicar el reemplazo
content = content.replace(pattern, fixed_pattern)

with open('app.py', 'w') as file:
    file.write(content)

print("Archivo corregido con éxito") 