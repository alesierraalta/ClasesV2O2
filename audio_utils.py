import os
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import librosa
import io
import numpy as np
from flask import send_file, abort, Blueprint, current_app

audio_bp = Blueprint('audio', __name__)

def find_audio_file(horario_id, app):
    """Find audio file for a specific horario_id"""
    # Get allowed extensions
    ALLOWED_EXTENSIONS_AUDIO = {'mp3', 'wav', 'ogg'}
    
    # Check for temporary audio files first
    for ext in ALLOWED_EXTENSIONS_AUDIO:
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f'temp_horario_{horario_id}.{ext}')
        if os.path.exists(temp_path):
            return temp_path
    
    # Import here to avoid circular imports
    from app import ClaseRealizada
    
    # Check for permanent audio files
    clase = ClaseRealizada.query.filter_by(horario_id=horario_id).order_by(ClaseRealizada.fecha.desc()).first()
    if clase and clase.audio_file:
        audio_path = os.path.join(app.config['UPLOAD_FOLDER'], clase.audio_file)
        if os.path.exists(audio_path):
            return audio_path
    
    return None

@audio_bp.route('/audio_waveform/<int:horario_id>')
def audio_waveform(horario_id):
    """Generate waveform visualization for audio"""
    audio_path = find_audio_file(horario_id, current_app)
    if not audio_path:
        abort(404)
    
    try:
        y, sr = librosa.load(audio_path, sr=None)
        
        # Create waveform plot
        fig = plt.figure(figsize=(10, 2))
        plt.plot(np.linspace(0, len(y)/sr, len(y)), y, color='blue', alpha=0.6)
        plt.axis('off')
        plt.tight_layout(pad=0)
        
        # Save to buffer
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', bbox_inches='tight', pad_inches=0)
        plt.close(fig)
        buffer.seek(0)
        
        return send_file(buffer, mimetype='image/png')
    except Exception as e:
        print(f"Error generating waveform: {str(e)}")
        abort(500)