from flask import Blueprint, request, jsonify
import os
import base64
from werkzeug.utils import secure_filename

# Crear un Blueprint para organizar mejor las rutas
api = Blueprint('api', __name__, url_prefix='/api')

# Configurar la carpeta de subidas
UPLOAD_FOLDER = 'static/uploads/audio'
# Asegurarse de que el directorio existe
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@api.route('/upload_audio/<int:user_id>', methods=['POST'])
def upload_audio(user_id):
    # Agregar log para depuración
    print(f"Headers: {request.headers}")
    print(f"Files: {request.files}")
    
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file found'}), 400
    
    audio_file = request.files['audio']
    if audio_file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if audio_file:
        filename = secure_filename(audio_file.filename)
        upload_method = request.form.get('upload_method', 'default')
        
        # Puedes personalizar el nombre del archivo para evitar colisiones
        save_path = os.path.join(UPLOAD_FOLDER, f'user_{user_id}_{filename}')
        
        try:
            audio_file.save(save_path)
            # Ruta relativa para acceder desde el navegador
            relative_path = f'/static/uploads/audio/user_{user_id}_{filename}'
            return jsonify({
                'message': f'File uploaded successfully as {filename}',
                'file_path': relative_path,
                'upload_method': upload_method
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return jsonify({'error': 'Invalid file format'}), 400

@api.route('/upload_audio_base64/<int:user_id>', methods=['POST'])
def upload_audio_base64(user_id):
    data = request.json
    
    if not data or 'audio_data' not in data:
        return jsonify({'error': 'No se proporcionaron datos de audio'}), 400
    
    try:
        # Decodificar datos Base64
        audio_data = base64.b64decode(data['audio_data'])
        
        # Obtener nombre de archivo y tipo MIME
        filename = secure_filename(data.get('filename', f'audio_{user_id}.mp3'))
        
        # Guardar archivo
        save_path = os.path.join(UPLOAD_FOLDER, f'user_{user_id}_{filename}')
        
        with open(save_path, 'wb') as f:
            f.write(audio_data)
        
        # Ruta relativa para acceder desde el navegador
        relative_path = f'/static/uploads/audio/user_{user_id}_{filename}'
        return jsonify({
            'message': 'Archivo subido correctamente en formato Base64',
            'file_path': relative_path
        })
    
    except Exception as e:
        return jsonify({'error': f'Error al procesar archivo Base64: {str(e)}'}), 500 