from app import app
from notifications import check_and_notify_unregistered_classes

# Asegurarse de que el número de teléfono está configurado
phone_number = input("Ingrese el número de teléfono para la notificación (formato +123456789): ")
app.config['NOTIFICATION_PHONE_NUMBER'] = phone_number

print("Verificando clases no registradas...")
check_and_notify_unregistered_classes()
print("Verificación completada. Revise notifications.log para más detalles.")
