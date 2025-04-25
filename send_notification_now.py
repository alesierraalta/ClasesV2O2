from app import app, HorarioClase, ClaseRealizada
from notifications import send_whatsapp_notification
from datetime import datetime, time

def calcular_hora_fin(hora_inicio, duracion):
    """Calcula la hora de finalización de una clase"""
    minutos_totales = hora_inicio.hour * 60 + hora_inicio.minute + duracion
    horas, minutos = divmod(minutos_totales, 60)
    horas = horas % 24  # Manejar casos donde la clase termina después de la medianoche
    return time(hour=horas, minute=minutos)

def enviar_notificacion_ahora():
    """
    Verifica clases no registradas y envía una notificación inmediatamente.
    """
    with app.app_context():
        try:
            # Obtener la fecha actual
            hoy = datetime.now().date()
            dia_semana_hoy = hoy.weekday()  # 0 es lunes, 6 es domingo
            
            print(f"Fecha actual: {hoy}, día de la semana: {dia_semana_hoy}")
            
            # Obtener todos los horarios programados para hoy
            horarios_hoy = HorarioClase.query.filter(
                HorarioClase.dia_semana == dia_semana_hoy
            ).all()
            
            if not horarios_hoy:
                print(f"No hay clases programadas para hoy (día {dia_semana_hoy})")
                return False
            
            # Verificar qué clases ya han sido registradas hoy
            clases_realizadas_hoy = ClaseRealizada.query.filter(
                ClaseRealizada.fecha == hoy
            ).all()
            
            # IDs de horarios ya registrados hoy
            ids_registrados = {cr.horario_id for cr in clases_realizadas_hoy}
            
            # Identificar clases no registradas hasta ahora
            hora_actual = datetime.now().time()
            clases_pendientes = []
            
            for horario in horarios_hoy:
                if horario.id not in ids_registrados:
                    # Calcular la hora de finalización aproximada
                    hora_fin = calcular_hora_fin(horario.hora_inicio, horario.duracion)
                    
                    # Si la clase ya terminó y no está registrada, agregarla a pendientes
                    if hora_fin < hora_actual:
                        # Asegurarse de que existen los atributos necesarios
                        profesor_nombre = getattr(horario.profesor, 'nombre', 'Sin profesor asignado') if hasattr(horario, 'profesor') and horario.profesor else 'Sin profesor asignado'
                        
                        clases_pendientes.append({
                            'id': horario.id,
                            'tipo': getattr(horario, 'tipo_clase', 'N/A'),
                            'hora': horario.hora_inicio.strftime('%H:%M'),
                            'profesor': profesor_nombre
                        })
            
            if not clases_pendientes:
                print("Todas las clases de hoy están registradas o aún no han finalizado")
                return False
            
            # Construir mensaje
            mensaje = f"⚠️ ALERTA: {len(clases_pendientes)} clase(s) no registrada(s) hoy ({hoy.strftime('%d/%m/%Y')}):\n\n"
            
            for i, clase in enumerate(clases_pendientes, 1):
                mensaje += f"{i}. Clase de {clase['tipo']} a las {clase['hora']} con {clase['profesor']}\n"
                print(f"  {i}. Clase de {clase['tipo']} a las {clase['hora']} con {clase['profesor']}")
            
            mensaje += "\nPor favor, registre estas clases lo antes posible."
            
            # Enviar notificación
            print("\nEnviando notificación ahora...")
            sent = send_whatsapp_notification(mensaje)
            
            if sent:
                print(f"Notificación enviada para {len(clases_pendientes)} clases no registradas")
                return True
            else:
                print("No se pudo enviar la notificación")
                return False
                
        except Exception as e:
            print(f"Error al verificar clases no registradas: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    print("Verificando clases no registradas y enviando notificación...")
    resultado = enviar_notificacion_ahora()
    if resultado:
        print("Proceso completado con éxito.")
    else:
        print("El proceso no pudo completarse o no hay clases para notificar.") 