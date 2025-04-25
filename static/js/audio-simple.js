/**
 * Audio Simple Controls - Manejo básico de reproducción de audio
 */

console.log('Audio Simple Controls script cargando...');

// Función autoinvocada para inicializar todo sin esperar DOMContentLoaded
(function() {
    // Mensaje para debug
    console.log('Audio Simple Controls inicializado');

    // Inicializar después de una breve espera para asegurar que el DOM esté listo
    setTimeout(function() {
        console.log('[DEBUG] Iniciando controles de audio después de espera...');
        try {
            // Manejar la reproducción de audio
            initializeAudioControls();
            console.log('[DEBUG] Controles de audio inicializados correctamente');
        } catch(error) {
            console.error('[ERROR] Fallo al inicializar controles de audio:', error);
        }
    }, 1000);

    // Función principal para inicializar todos los controles de audio
    function initializeAudioControls() {
        console.log('[DEBUG] Inicializando controles de audio...');
        
        // Verificar si existen controles de audio en la página
        const audioControls = document.querySelectorAll('.audio-control');
        console.log(`[DEBUG] Se encontraron ${audioControls.length} controles de audio en la página`);
        
        if (audioControls.length === 0) {
            console.warn('[ADVERTENCIA] No se encontraron elementos .audio-control en la página');
        }
        
        // Manejar botones de reproducción de audio
        initializePlayButtons();
        
        // Manejar enlaces para reemplazar audio
        initializeReplaceLinks();
        
        // Manejar subida de audio
        initializeUploadButtons();
        
        // Verificar audio existente para todos los contenedores al cargar la página
        audioControls.forEach(container => {
            const horarioId = container.getAttribute('data-horario-id');
            console.log(`[DEBUG] Verificando audio para horario ID: ${horarioId}`);
            
            // Si ya tiene la clase has-audio, sabemos que tiene audio
            if (container.classList.contains('has-audio')) {
                console.log(`[DEBUG] El contenedor ya tiene la clase has-audio, comprobando si el elemento audio está correctamente inicializado`);
                
                // Verificar si el elemento audio está correctamente inicializado
                const audioElement = container.querySelector('audio');
                if (audioElement) {
                    // Asegurarse de que la fuente tenga el timestamp más reciente
                    const audioSource = audioElement.querySelector('source');
                    if (audioSource) {
                        const currentSrc = audioSource.src;
                        const baseUrl = currentSrc.split('?')[0];
                        audioSource.src = `${baseUrl}?t=${new Date().getTime()}`;
                        audioElement.load();
                        console.log(`[DEBUG] Actualizada la URL del audio con timestamp nuevo: ${audioSource.src}`);
                    }
                }
            } else {
                // Verificar la existencia del audio en el servidor
                checkAudioExistence(horarioId, (data) => {
                    if (data.exists) {
                        // Reemplazar el contenedor con los controles de reproducción
                        replaceWithAudioPlayer(container, horarioId, data.audio_info);
                    }
                }, (error) => {
                    console.error('[ERROR] Error verificando la existencia del audio:', error);
                });
            }
        });
    }

    // Función para realizar la verificación de audio existente
    function checkAudioExistence(horarioId, successCallback, errorCallback) {
        const checkUrl = window.AUDIO_CHECK_URL ? `${window.AUDIO_CHECK_URL}/${horarioId}` : `/asistencia/audio/check/${horarioId}`;
        console.log(`[DEBUG] Verificando existencia de audio en URL: ${checkUrl}`);
        
        // Agregar un parámetro timestamp para evitar caché
        const urlWithTimestamp = `${checkUrl}?t=${new Date().getTime()}`;
        
        // Hacer la petición para verificar la existencia del audio
        fetch(urlWithTimestamp)
            .then(response => response.json())
            .then(data => {
                console.log(`[DEBUG] Respuesta del servidor para verificación de audio:`, data);
                if (data.success) {
                    if (successCallback) successCallback(data);
                } else {
                    console.error(`[ERROR] Error verificando audio:`, data.message);
                    if (errorCallback) errorCallback(data);
                }
            })
            .catch(error => {
                console.error(`[ERROR] Error en la petición al verificar audio:`, error);
                if (errorCallback) errorCallback({ success: false, message: error.message });
            });
    }

    // Función para reemplazar el contenedor de audio con los controles de reproducción
    function replaceWithAudioPlayer(container, horarioId, audioInfo) {
        const playerId = `audio-${horarioId}`;
        console.log(`[DEBUG] Reemplazando contenedor con reproductor, horario ID: ${horarioId}`, audioInfo);
        
        // Construir la URL del audio
        let audioSrc = '';
        
        if (audioInfo && audioInfo.file_path) {
            audioSrc = audioInfo.file_path.startsWith('/') 
                ? `${audioInfo.file_path}?t=${new Date().getTime()}`
                : `/${audioInfo.file_path}?t=${new Date().getTime()}`;
        } else {
            audioSrc = window.AUDIO_GET_URL 
                ? `${window.AUDIO_GET_URL}/${horarioId}?t=${new Date().getTime()}`
                : `/asistencia/audio/get/${horarioId}?t=${new Date().getTime()}`;
        }
        
        console.log(`[DEBUG] URL del audio construida: ${audioSrc}`);
        
        // Construir el HTML del reproductor
        container.innerHTML = `
            <div class="d-flex align-items-center">
                <button class="btn btn-primary btn-lg audio-play-btn me-2" data-horario-id="${horarioId}">
                    <i class="fas fa-play"></i>
                </button>
                <div>
                    <span class="audio-label">Audio de la clase</span>
                    <a href="#" class="replace-audio-link small d-block" data-horario-id="${horarioId}">Reemplazar audio</a>
                </div>
                <audio id="${playerId}" class="d-none" data-horario-id="${horarioId}">
                    <source src="${audioSrc}" type="audio/mpeg">
                </audio>
            </div>
        `;
        
        container.classList.add('has-audio');
        
        // Re-inicializar los eventos para este contenedor
        initializePlayButtons();
        initializeReplaceLinks();
    }

    // Función para inicializar los botones de reproducción
    function initializePlayButtons() {
        document.querySelectorAll('.audio-play-btn:not([data-initialized])').forEach(btn => {
            btn.setAttribute('data-initialized', 'true');
            btn.addEventListener('click', function() {
                const horarioId = this.getAttribute('data-horario-id');
                const audioElement = document.getElementById(`audio-${horarioId}`);
                
                if (!audioElement) {
                    console.error(`No se encontró el elemento de audio para el horario ${horarioId}`);
                    showToast('error', 'No se pudo reproducir el audio');
                    return;
                }
                
                // Pausar todos los demás audios
                document.querySelectorAll('audio').forEach(audio => {
                    if (audio.id !== `audio-${horarioId}` && !audio.paused) {
                        audio.pause();
                        const otherBtn = document.querySelector(`.audio-play-btn[data-horario-id="${audio.getAttribute('data-horario-id')}"]`);
                        if (otherBtn) otherBtn.innerHTML = '<i class="fas fa-play"></i>';
                    }
                });
                
                // Reproducir o pausar el audio
                if (!audioElement.paused) {
                    audioElement.pause();
                    this.innerHTML = '<i class="fas fa-play"></i>';
                } else {
                    const playPromise = audioElement.play();
                    
                    if (playPromise !== undefined) {
                        playPromise
                        .then(() => {
                            this.innerHTML = '<i class="fas fa-pause"></i>';
                        })
                        .catch(error => {
                            console.error('Error al reproducir audio:', error);
                            showToast('error', 'Error al reproducir: ' + error.message);
                        });
                    }
                }
            });
        });
        
        // Manejar eventos de finalización de reproducción
        document.querySelectorAll('audio:not([data-event-added])').forEach(audio => {
            audio.setAttribute('data-event-added', 'true');
            
            audio.addEventListener('ended', function() {
                const horarioId = this.getAttribute('data-horario-id');
                const playBtn = document.querySelector(`.audio-play-btn[data-horario-id="${horarioId}"]`);
                if (playBtn) {
                    playBtn.innerHTML = '<i class="fas fa-play"></i>';
                }
            });
            
            // Manejar errores de audio
            audio.addEventListener('error', function(e) {
                console.error('Error en la reproducción de audio:', e);
                const horarioId = this.getAttribute('data-horario-id');
                const playBtn = document.querySelector(`.audio-play-btn[data-horario-id="${horarioId}"]`);
                if (playBtn) {
                    playBtn.innerHTML = '<i class="fas fa-exclamation-triangle"></i>';
                    playBtn.classList.add('btn-warning');
                    playBtn.classList.remove('btn-primary');
                }
                showToast('error', 'Error al cargar el audio');
            });
        });
    }
    
    // Función para inicializar los enlaces de reemplazo
    function initializeReplaceLinks() {
        document.querySelectorAll('.replace-audio-link:not([data-initialized])').forEach(link => {
            link.setAttribute('data-initialized', 'true');
            link.addEventListener('click', function(e) {
                e.preventDefault();
                const horarioId = this.getAttribute('data-horario-id');
                const audioControl = document.querySelector(`.audio-control[data-horario-id="${horarioId}"]`);
                
                if (audioControl) {
                    // Pausar el audio si está reproduciéndose
                    const audio = document.getElementById(`audio-${horarioId}`);
                    if (audio && !audio.paused) {
                        audio.pause();
                    }
                    
                    // Mostrar formulario de subida
                    const uploadForm = document.createElement('div');
                    uploadForm.className = 'audio-upload-form mt-2';
                    uploadForm.innerHTML = `
                        <div class="input-group input-group-responsive">
                            <input type="file" id="audioUpload-${horarioId}" name="audio" class="form-control" accept="audio/*" />
                            <button type="button" class="btn btn-primary upload-audio-btn" data-horario-id="${horarioId}">
                                <i class="fas fa-upload"></i> Subir
                            </button>
                        </div>
                        <small class="form-text text-muted d-block mb-2">Selecciona un archivo de audio (MP3, WAV, OGG)</small>
                        <button type="button" class="btn btn-sm btn-secondary cancel-replace-btn">Cancelar</button>
                        
                        <div id="progressBar-${horarioId}" class="progress mt-1" style="display: none;">
                            <div class="progress-bar" role="progressbar" style="width: 0%;"></div>
                        </div>
                        <div id="uploadMessage-${horarioId}" class="mt-2"></div>
                    `;
                    
                    // Reemplazar el contenido actual
                    const originalContent = audioControl.innerHTML;
                    audioControl.innerHTML = '';
                    audioControl.appendChild(uploadForm);
                    
                    // Configurar el botón de cancelar
                    const cancelBtn = uploadForm.querySelector('.cancel-replace-btn');
                    if (cancelBtn) {
                        cancelBtn.addEventListener('click', function() {
                            audioControl.innerHTML = originalContent;
                            initializeAudioControls();
                        });
                    }
                    
                    // Inicializar el botón de subida después de añadirlo al DOM
                    initializeUploadButtons();
                }
            });
        });
    }
    
    // Función para inicializar botones de subida
    function initializeUploadButtons() {
        console.log('[DEBUG] Inicializando botones de subida de audio...');
        const uploadButtons = document.querySelectorAll('.upload-audio-btn:not([data-initialized])');
        console.log(`[DEBUG] Encontrados ${uploadButtons.length} botones de subida sin inicializar`);
        
        uploadButtons.forEach(btn => {
            console.log(`[DEBUG] Inicializando botón de subida para horario ID: ${btn.getAttribute('data-horario-id')}`);
            btn.setAttribute('data-initialized', 'true');
            btn.addEventListener('click', function() {
                console.log(`[DEBUG] Botón de subida clickeado para horario ID: ${this.getAttribute('data-horario-id')}`);
                const horarioId = this.getAttribute('data-horario-id');
                const fileInput = document.getElementById(`audioUpload-${horarioId}`);
                const progressDiv = document.getElementById(`progressBar-${horarioId}`);
                const progressBar = progressDiv.querySelector('.progress-bar');
                const messageDiv = document.getElementById(`uploadMessage-${horarioId}`);
                const audioControl = document.querySelector(`.audio-control[data-horario-id="${horarioId}"]`);
                
                // Verificar que se haya seleccionado un archivo
                if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
                    console.log(`[DEBUG] No se seleccionó ningún archivo para horario ID: ${horarioId}`);
                    if (messageDiv) messageDiv.innerHTML = '<div class="alert alert-warning">Por favor, selecciona un archivo de audio.</div>';
                    showToast('warning', 'Por favor, selecciona un archivo de audio');
                    return;
                }
                
                const file = fileInput.files[0];
                console.log(`[DEBUG] Archivo seleccionado: ${file.name}, tipo: ${file.type}, tamaño: ${file.size} bytes`);
                const formData = new FormData();
                formData.append('audio', file);
                
                // Validar tipo de archivo
                const validTypes = ['audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/mp3', 'audio/x-m4a', 'audio/aac'];
                if (!validTypes.includes(file.type) && !file.name.match(/\.(mp3|wav|ogg|m4a|aac)$/i)) {
                    if (messageDiv) messageDiv.innerHTML = '<div class="alert alert-danger">Tipo de archivo no válido. Por favor, selecciona un archivo de audio compatible.</div>';
                    showToast('error', 'Tipo de archivo no válido');
                    return;
                }
                
                // Mostrar barra de progreso
                if (progressDiv) progressDiv.style.display = 'block';
                if (progressBar) progressBar.style.width = '0%';
                if (messageDiv) messageDiv.innerHTML = '<div class="alert alert-info">Subiendo archivo...</div>';
                
                // Deshabilitar el botón durante la carga
                this.disabled = true;
                this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Subiendo...';
                
                // Enviar el archivo
                const xhr = new XMLHttpRequest();
                // Nota: La ruta correcta es /asistencia/audio/upload/{id} según app.py
                const uploadUrl = window.AUDIO_UPLOAD_URL ? 
                    `${window.AUDIO_UPLOAD_URL}/${horarioId}` : 
                    `/asistencia/audio/upload/${horarioId}`;
                
                console.log(`[DEBUG] URL de subida de audio: ${uploadUrl}`);
                console.log(`[DEBUG] window.AUDIO_UPLOAD_URL: ${window.AUDIO_UPLOAD_URL}`);
                
                xhr.open('POST', uploadUrl, true);
                console.log(`[DEBUG] Petición XHR abierta a URL: ${uploadUrl}`);
                
                // Manejar el progreso
                xhr.upload.onprogress = function(e) {
                    if (e.lengthComputable && progressBar) {
                        const percent = Math.round((e.loaded / e.total) * 100);
                        progressBar.style.width = percent + '%';
                        progressBar.textContent = percent + '%';
                        console.log(`[DEBUG] Progreso de subida: ${percent}%`);
                    }
                };
                
                // Manejar la respuesta
                xhr.onload = function() {
                    console.log(`[DEBUG] Respuesta recibida. Status: ${xhr.status}, Respuesta: ${xhr.responseText}`);
                    // Habilitar el botón nuevamente
                    btn.disabled = false;
                    
                    if (xhr.status >= 200 && xhr.status < 300) {
                        try {
                            const response = JSON.parse(xhr.responseText);
                            if (response.success) {
                                if (messageDiv) messageDiv.innerHTML = '<div class="alert alert-success">¡Audio subido correctamente!</div>';
                                showToast('success', '¡Audio subido correctamente!');
                                
                                // Actualizar la UI sin recargar la página
                                setTimeout(() => {
                                    // Crear la nueva UI de reproducción
                                    const newAudioUI = `
                                        <div class="d-flex align-items-center">
                                            <button class="btn btn-primary btn-lg audio-play-btn me-2" data-horario-id="${horarioId}">
                                                <i class="fas fa-play"></i>
                                            </button>
                                            <div>
                                                <span class="audio-label">Audio de la clase</span>
                                                <a href="#" class="replace-audio-link small d-block" data-horario-id="${horarioId}">Reemplazar audio</a>
                                            </div>
                                            <audio id="audio-${horarioId}" class="d-none" data-horario-id="${horarioId}">
                                                <source src="${window.AUDIO_GET_URL}/${horarioId}?t=${new Date().getTime()}" type="audio/mpeg">
                                            </audio>
                                        </div>
                                    `;
                                    
                                    // Actualizar el contenedor
                                    if (audioControl) {
                                        audioControl.innerHTML = newAudioUI;
                                        // Añadir la clase has-audio para aplicar estilos
                                        audioControl.classList.add('has-audio');
                                    }
                                    
                                    // Reinicializar los controles
                                    initializeAudioControls();
                                }, 1500);
                            } else {
                                if (messageDiv) messageDiv.innerHTML = `<div class="alert alert-danger">Error: ${response.error || 'Desconocido'}</div>`;
                                showToast('error', `Error: ${response.error || 'Desconocido'}`);
                                btn.innerHTML = '<i class="fas fa-upload"></i> Subir';
                            }
                        } catch (error) {
                            if (messageDiv) messageDiv.innerHTML = '<div class="alert alert-danger">Error al procesar la respuesta</div>';
                            showToast('error', 'Error al procesar la respuesta');
                            console.error('Error parsing JSON response:', error, xhr.responseText);
                            btn.innerHTML = '<i class="fas fa-upload"></i> Subir';
                        }
                    } else {
                        if (messageDiv) messageDiv.innerHTML = `<div class="alert alert-danger">Error ${xhr.status}: ${xhr.statusText}</div>`;
                        showToast('error', `Error ${xhr.status}: ${xhr.statusText}`);
                        btn.innerHTML = '<i class="fas fa-upload"></i> Subir';
                    }
                };
                
                // Manejar errores de red
                xhr.onerror = function() {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fas fa-upload"></i> Subir';
                    if (messageDiv) messageDiv.innerHTML = '<div class="alert alert-danger">Error de conexión</div>';
                    showToast('error', 'Error de conexión');
                };
                
                // Manejar cancelación
                xhr.onabort = function() {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fas fa-upload"></i> Subir';
                    if (messageDiv) messageDiv.innerHTML = '<div class="alert alert-warning">Subida cancelada</div>';
                    showToast('warning', 'Subida cancelada');
                };
                
                xhr.send(formData);
                console.log(`[DEBUG] Enviando archivo para horario ${horarioId}`);
            });
        });
    }
    
    // Función para mostrar mensajes toast
    function showToast(type, message) {
        // Verificar si ya existe un contenedor para toasts
        let toastContainer = document.getElementById('toast-container');
        
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toast-container';
            toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
            document.body.appendChild(toastContainer);
        }
        
        // Crear un nuevo toast
        const toastId = 'toast-' + Date.now();
        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.id = toastId;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');
        
        // Clases de estilo según el tipo
        let bgClass = 'bg-primary';
        let iconClass = 'fa-info-circle';
        
        switch(type) {
            case 'success':
                bgClass = 'bg-success';
                iconClass = 'fa-check-circle';
                break;
            case 'error':
                bgClass = 'bg-danger';
                iconClass = 'fa-exclamation-circle';
                break;
            case 'warning':
                bgClass = 'bg-warning text-dark';
                iconClass = 'fa-exclamation-triangle';
                break;
        }
        
        // Contenido del toast
        toast.innerHTML = `
            <div class="toast-header ${bgClass} text-white">
                <i class="fas ${iconClass} me-2"></i>
                <strong class="me-auto">Notificación</strong>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Cerrar"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        `;
        
        // Añadir al contenedor
        toastContainer.appendChild(toast);
        
        // Inicializar y mostrar el toast usando el objeto bootstrap si está disponible
        if (typeof bootstrap !== 'undefined') {
            const bsToast = new bootstrap.Toast(toast, { autohide: true, delay: 3000 });
            bsToast.show();
        } else {
            // Fallback si bootstrap no está disponible
            toast.style.display = 'block';
            toast.style.opacity = '1';
            
            // Añadir controlador para el botón de cierre
            const closeBtn = toast.querySelector('.btn-close');
            if (closeBtn) {
                closeBtn.addEventListener('click', function() {
                    toast.remove();
                });
            }
            
            // Auto-eliminar después de 3 segundos
            setTimeout(() => {
                toast.remove();
            }, 3000);
        }
    }
    
    // Exportar funciones al objeto window para uso global
    window.AudioSimpleControls = {
        initialize: initializeAudioControls,
        showToast: showToast
    };
})();
