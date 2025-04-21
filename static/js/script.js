/**
 * script.js - Archivo de scripts globales para la aplicación
 */

// Inicialización de componentes cuando el DOM está listo
document.addEventListener('DOMContentLoaded', function() {
    console.log('Script global cargado correctamente');
    
    // Inicializar tooltips de Bootstrap si existen
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    if (typeof bootstrap !== 'undefined') {
        tooltipTriggerList.map(function(tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
}); 