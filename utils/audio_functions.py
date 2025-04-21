import os
import matplotlib.pyplot as plt
import librosa
import librosa.display
import io
import base64
import numpy as np
from flask import jsonify

def generate_spectrogram(audio_path):
    """Genera un espectrograma a partir de un archivo de audio"""
    try:
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
        
        return img_base64
    except Exception as e:
        return None
