from flask import url_for; import app; with app.app.test_request_context(): print(url_for("depurar_base_datos"))
