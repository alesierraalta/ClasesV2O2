import sys
import os
# Agregar el directorio raíz al path para poder importar los módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flask import url_for
import app
with app.app.test_request_context(): 
    print(url_for("depurar_base_datos"))
