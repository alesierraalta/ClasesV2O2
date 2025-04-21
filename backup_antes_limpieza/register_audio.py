from app import app
from audio_routes import audio_bp

# Register the blueprint
app.register_blueprint(audio_bp)

print("Audio waveform blueprint registered successfully!")