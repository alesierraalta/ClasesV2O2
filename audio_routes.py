from flask import Blueprint, request, jsonify, current_app, send_file
from werkzeug.utils import secure_filename
import os
import time
from datetime import datetime
import logging
# Importar desde models, no desde app
from models import db, ClaseRealizada

# Crear blueprint para todas las funcionalidades de audio
audio_bp = Blueprint('audio', __name__, url_prefix='/asistencia/audio')

# Configuración y constantes
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav', 'ogg', 'm4a', 'aac'}
UPLOAD_FOLDER = 'static/uploads/audios'
MAX_AUDIO_SIZE = 32 * 1024 * 1024  # 32 MB

def allowed_audio_file(filename):
    """Verifica si el archivo tiene una extensión de audio permitida"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_AUDIO_EXTENSIONS

def get_upload_path(horario_id=None, filename=None):
    """Genera la ruta de carga para un archivo de audio"""
    # Asegurar que el directorio existe
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    if not filename:
        return UPLOAD_FOLDER
        
    timestamp = int(time.time())
    new_filename = f"audio_{horario_id}_{timestamp}_{secure_filename(filename)}"
    return os.path.join(UPLOAD_FOLDER, new_filename), new_filename

def update_database(horario_id, filename):
    """Actualiza la base de datos con la información del archivo de audio"""
    try:
        # Usar los modelos importados de models.py, no de app
        clase = ClaseRealizada.query.filter_by(horario_id=horario_id).order_by(ClaseRealizada.id.desc()).first()
        if clase:
            clase.audio_file = filename
            db.session.commit()
            return True, clase.id
        return False, None
    except Exception as e:
        current_app.logger.error(f"Error al actualizar la base de datos: {str(e)}")
        return False, None

@audio_bp.route('/upload/<int:horario_id>', methods=['POST'])
def upload_audio(horario_id):
    """Ruta principal para subir archivos de audio"""
    # Registrar información de depuración
    current_app.logger.info(f"Recibida solicitud para subir audio para horario_id: {horario_id}")
    current_app.logger.debug(f"Encabezados: {dict(request.headers)}")
    
    try:
        # Verificar si hay un archivo en la solicitud
        if 'audio' not in request.files:
            current_app.logger.warning("No se encontró el campo 'audio' en los archivos")
            return jsonify({'error': 'No se encontró el archivo de audio'}), 400
            
        audio_file = request.files['audio']
        
        # Verificar si se seleccionó un archivo
        if audio_file.filename == '':
            current_app.logger.warning("Nombre de archivo vacío")
            return jsonify({'error': 'No se seleccionó ningún archivo'}), 400
            
        # Verificar si el archivo es válido
        if not allowed_audio_file(audio_file.filename):
            current_app.logger.warning(f"Tipo de archivo no permitido: {audio_file.filename}")
            return jsonify({'error': 'Tipo de archivo no permitido. Use mp3, wav, ogg, m4a o aac'}), 400
            
        # Verificar tamaño del archivo
        if request.content_length and request.content_length > MAX_AUDIO_SIZE:
            current_app.logger.warning(f"Archivo demasiado grande: {request.content_length} bytes")
            return jsonify({'error': f'El archivo excede el tamaño máximo permitido de {MAX_AUDIO_SIZE/1024/1024} MB'}), 413
            
        # Generar ruta de guardado
        save_path, new_filename = get_upload_path(horario_id, audio_file.filename)
        
        # Guardar el archivo
        try:
            audio_file.save(save_path)
            current_app.logger.info(f"Archivo guardado exitosamente: {save_path}")
            
            # Actualizar la base de datos
            success, clase_id = update_database(horario_id, new_filename)
            
            # Generar URL para acceder al archivo
            file_url = f"/static/uploads/audios/{new_filename}"
            
            # Devolver respuesta exitosa
            response = {
                'success': True,
                'message': 'Archivo subido correctamente',
                'file_path': file_url,
                'file_name': new_filename
            }
            
            if success:
                response['clase_id'] = clase_id
                
            return jsonify(response)
            
        except Exception as e:
            current_app.logger.error(f"Error al guardar el archivo: {str(e)}")
            import traceback
            current_app.logger.error(traceback.format_exc())
            return jsonify({'error': f'Error al guardar el archivo: {str(e)}'}), 500
            
    except Exception as e:
        current_app.logger.error(f"Error no controlado: {str(e)}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': 'Error interno del servidor'}), 500

@audio_bp.route('/get/<int:horario_id>')
def get_audio(horario_id):
    """Obtiene el archivo de audio asociado a un horario"""
    try:
        # Usar ClaseRealizada de models, no de app
        clase = ClaseRealizada.query.filter_by(horario_id=horario_id).order_by(ClaseRealizada.id.desc()).first()
        
        if not clase or not clase.audio_file:
            current_app.logger.warning(f"No se encontró audio para horario_id: {horario_id}")
            return jsonify({'error': 'No se encontró un archivo de audio para este horario'}), 404
            
        # Construir la ruta del archivo
        audio_path = os.path.join(UPLOAD_FOLDER, clase.audio_file)
        
        # Verificar si el archivo existe
        if not os.path.exists(audio_path):
            current_app.logger.warning(f"Archivo de audio no encontrado en disco: {audio_path}")
            return jsonify({'error': 'El archivo de audio no se encuentra en el servidor'}), 404
            
        # Devolver el archivo
        return send_file(audio_path, as_attachment=False)
        
    except Exception as e:
        current_app.logger.error(f"Error al obtener audio: {str(e)}")
        return jsonify({'error': f'Error al obtener el audio: {str(e)}'}), 500

@audio_bp.route('/check/<int:horario_id>')
def check_audio(horario_id):
    """Verifica si existe un archivo de audio para el horario especificado"""
    try:
        # Buscar la clase más reciente para el horario
        clase = ClaseRealizada.query.filter_by(horario_id=horario_id).order_by(ClaseRealizada.id.desc()).first()
        
        if not clase or not clase.audio_file:
            return jsonify({'exists': False, 'message': 'No hay audio registrado'})
            
        # Construir la ruta del archivo
        audio_path = os.path.join(UPLOAD_FOLDER, clase.audio_file)
        
        # Verificar si el archivo existe
        if os.path.exists(audio_path):
            file_size = os.path.getsize(audio_path)
            file_stats = os.stat(audio_path)
            creation_time = datetime.fromtimestamp(file_stats.st_ctime)
            
            return jsonify({
                'exists': True,
                'file_name': clase.audio_file,
                'file_path': f"/static/uploads/audios/{clase.audio_file}",
                'file_size': file_size,
                'file_size_readable': f"{file_size/1024:.2f} KB",
                'creation_date': creation_time.strftime('%Y-%m-%d %H:%M:%S')
            })
        else:
            return jsonify({
                'exists': False,
                'message': 'El archivo está registrado en la base de datos pero no existe en el disco',
                'file_name': clase.audio_file
            })
            
    except Exception as e:
        current_app.logger.error(f"Error al verificar audio: {str(e)}")
        return jsonify({'error': f'Error al verificar el audio: {str(e)}'}), 500

# Función para verificar integridad de archivos de audio en el sistema
@audio_bp.route('/diagnostico')
def diagnostico_audio():
    """Diagnostica problemas con archivos de audio"""
    try:
        # Obtener todas las clases con archivos de audio
        clases_con_audio = ClaseRealizada.query.filter(ClaseRealizada.audio_file.isnot(None)).all()
        
        resultados = {
            'total_registros': len(clases_con_audio),
            'archivos_encontrados': 0,
            'archivos_faltantes': 0,
            'detalles': []
        }
        
        for clase in clases_con_audio:
            audio_path = os.path.join(UPLOAD_FOLDER, clase.audio_file)
            existe = os.path.exists(audio_path)
            
            if existe:
                resultados['archivos_encontrados'] += 1
                tamano = os.path.getsize(audio_path)
            else:
                resultados['archivos_faltantes'] += 1
                tamano = 0
                
            resultados['detalles'].append({
                'clase_id': clase.id,
                'horario_id': clase.horario_id,
                'fecha': clase.fecha.strftime('%Y-%m-%d'),
                'archivo': clase.audio_file,
                'existe': existe,
                'tamano': tamano
            })
            
        return jsonify(resultados)
        
    except Exception as e:
        current_app.logger.error(f"Error en diagnóstico: {str(e)}")
        return jsonify({'error': f'Error en diagnóstico: {str(e)}'}), 500