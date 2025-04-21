from datetime import datetime, time

def hora_fin_str(hora_inicio, duracion):
    """Devuelve la hora de finalización como string"""
    print(f"Test hora_fin_str: hora_inicio={hora_inicio}, duracion={duracion}")
    
    minutos_totales = hora_inicio.hour * 60 + hora_inicio.minute + duracion
    print(f"minutos_totales = {minutos_totales}")
    
    horas, minutos = divmod(minutos_totales, 60)
    print(f"horas antes modulo = {horas}, minutos = {minutos}")
    
    # Asegurar que las horas estén en formato 24h (0-23)
    horas = horas % 24
    print(f"horas después modulo = {horas}")
    
    resultado = f"{horas:02d}:{minutos:02d}"
    print(f"hora_fin_str resultado final = {resultado}")
    return resultado

def test_multiple_times():
    test_cases = [
        # Regular morning class
        (time(8, 0), 60, "09:00"),
        # Evening class
        (time(19, 0), 60, "20:00"),
        # Late night class crossing midnight
        (time(23, 0), 60, "00:00"),
        # Class ending in next day
        (time(23, 30), 45, "00:15"),
        # Class with irregular duration
        (time(10, 15), 45, "11:00"),
        # Special times from the error report
        (time(9, 49), 60, "10:49"),
        (time(9, 49), 120, "11:49"),
    ]
    
    print("===== TESTING TIME CALCULATIONS =====")
    
    for i, (start_time, duration, expected) in enumerate(test_cases):
        print(f"\nTest case {i+1}: {start_time.strftime('%H:%M')} + {duration} min")
        result = hora_fin_str(start_time, duration)
        if result == expected:
            print(f"✅ PASS: Result {result} matches expected {expected}")
        else:
            print(f"❌ FAIL: Result {result} doesn't match expected {expected}")
    
    print("\n===== TESTING DATABASE EXAMPLE TIMES =====")
    
    # Specific test for the reported issue
    print("\nSpecial test for reported times (09:49):")
    test_start = time(9, 49)
    result = hora_fin_str(test_start, 60)
    print(f"09:49 + 60min = {result}")

if __name__ == "__main__":
    test_multiple_times() 