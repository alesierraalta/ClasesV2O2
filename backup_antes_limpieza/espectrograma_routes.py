from flask import jsonify, Blueprint
import os
import matplotlib.pyplot as plt
import librosa
import librosa.display
import io
import base64
import numpy as np
from app import app

# Extensiones de audio permitidas
ALLOWED_EXTENSIONS_AUDIO = {'mp3', 'wav', 'ogg'}

# Crear blueprint para espectrogramas
espectrograma_bp = Blueprint('espectrograma', __name__)

@espectrograma_bp.route('/espectrograma/<int:horario_id>')
def get_espectrograma(horario_id):
    """Genera un espectrograma para el archivo de audio asociado al horario"""
    try:
        # Nombre del archivo de audio
        filename = f'horario_{horario_id}'
        
        # Buscar el archivo con cualquier extensión permitida
        audio_path = None
        for ext in ALLOWED_EXTENSIONS_AUDIO:
            test_path = os.path.join(app.config['UPLOAD_FOLDER'], f'{filename}.{ext}')
            if os.path.exists(test_path):
                audio_path = test_path
                break
        
        if not audio_path:
            return jsonify({'error': 'No se encontró el archivo de audio'}), 404
        
        # Cargar archivo de audio con librosa
        y, sr = librosa.load(audio_path, sr=None)
        
        # Generar espectrograma
        plt.figure(figsize=(8, 4))
        D = librosa.amplitude_to_db(np.abs(librosa.stft(y)), ref=np.max)
        librosa.display.specshow(D, sr=sr, x_axis='time', y_axis='log')
        plt.colorbar(format='%+2.0f dB')
        plt.title(f'Espectrograma de {os.path.basename(audio_path)}')
        
        # Guardar la figura en un buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        
        # Codificar la imagen en base64
        img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        plt.close()
        
        return jsonify({'success': True, 'espectrograma': img_base64})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Ruta para verificar si existe un archivo de audio para un horario
@espectrograma_bp.route('/check_audio/<int:horario_id>')
def check_audio(horario_id):
    """Verifica si existe un archivo de audio para el horario especificado"""
    # Nombre del archivo de audio
    filename = f'horario_{horario_id}'
    
    # Buscar el archivo con cualquier extensión permitida
    for ext in ALLOWED_EXTENSIONS_AUDIO:
        test_path = os.path.join(app.config['UPLOAD_FOLDER'], f'{filename}.{ext}')
        if os.path.exists(test_path):
            return jsonify({'success': True, 'has_audio': True})
    
    return jsonify({'success': True, 'has_audio': False})
