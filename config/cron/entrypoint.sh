#!/bin/bash
set -e

echo "=================================================="
echo "  TV Automation - Cron Container"
echo "=================================================="
echo "Fecha: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Timezone: $TZ"
echo "Python: $(python --version)"
echo "Usuario: $(whoami)"
echo ""

# Verificar ffmpeg/ffprobe
echo "Herramientas de análisis de video:"
if command -v ffmpeg >/dev/null 2>&1; then
    echo "  ✓ ffmpeg: $(ffmpeg -version 2>&1 | head -n1 | cut -d' ' -f3)"
else
    echo "  ✗ ffmpeg: No disponible"
fi

if command -v ffprobe >/dev/null 2>&1; then
    echo "  ✓ ffprobe: $(ffprobe -version 2>&1 | head -n1 | cut -d' ' -f3)"
else
    echo "  ✗ ffprobe: No disponible"
fi
echo ""

# Verificar permisos de directorios
echo "Verificando permisos..."
chown -R cron-user:cron-user /app/logs 2>/dev/null || true

# Verificar que existe el archivo de log de cron (debe ser root ya que cron se ejecuta como root)
if [ ! -f /var/log/cron/cron.log ]; then
    touch /var/log/cron/cron.log
    chmod 644 /var/log/cron/cron.log
fi

# Mostrar módulos Python disponibles
echo "Módulos Python disponibles:"
if [ -d /app ]; then
    for dir in /app/*/; do
        if [ -f "$dir/__init__.py" ]; then
            module_name=$(basename "$dir")
            echo "  - $module_name"
        fi
    done
else
    echo "  (ninguno todavía)"
fi
echo ""

# Iniciar stream de prueba con streamM3UGenerator
echo "Iniciando stream de prueba..."
if python -m streamM3UGenerator start; then
    echo "✓ Stream de prueba iniciado"
else
    echo "✗ ERROR: No se pudo iniciar el stream de prueba"
fi
echo ""

# Mostrar configuración del validador
echo "Configuración iptvListValidator:"
echo "  - VALIDATOR_ANALYSIS_METHOD: ${VALIDATOR_ANALYSIS_METHOD:-auto (por defecto)}"
echo "  - VALIDATOR_FFMPEG_DURATION: ${VALIDATOR_FFMPEG_DURATION:-10 (por defecto)} segundos"
echo "  - VALIDATOR_FFMPEG_TIMEOUT: ${VALIDATOR_FFMPEG_TIMEOUT:-30 (por defecto)} segundos"
echo "  - VALIDATOR_HYBRID_ANALYSIS: ${VALIDATOR_HYBRID_ANALYSIS:-true (por defecto)}"
echo "  - VALIDATOR_MAX_RETRIES: ${VALIDATOR_MAX_RETRIES:-3 (por defecto)} intentos"
echo "  - VALIDATOR_RETRY_DELAY: ${VALIDATOR_RETRY_DELAY:-5 (por defecto)} segundos"
echo "  - VALIDATOR_TIMEOUT_CONNECT: ${VALIDATOR_TIMEOUT_CONNECT:-90} segundos"
echo "  - VALIDATOR_MIN_BITRATE: ${VALIDATOR_MIN_BITRATE:-300000} bytes/s"
echo ""

# Verificar que existe el archivo crontab
if [ ! -f /etc/cron.d/tv-automation ]; then
    echo "✗ ERROR: No se encontró el archivo crontab en /etc/cron.d/tv-automation"
    exit 1
fi

# Mostrar tareas programadas
echo "Tareas cron programadas:"
grep -v '^#' /etc/cron.d/tv-automation | grep -v '^$' || echo "  (ninguna configurada)"
echo ""

# Registrar el crontab
crontab /etc/cron.d/tv-automation
echo "✓ Crontab registrado"

# Ejecutar iptvListWatcher download al iniciar el contenedor
echo "Ejecutando iptvListWatcher download inicial..."
#TODO: ACTIVAR, no va con el cambio del formato de la lista
cd /app && python -m iptvListWatcher download >> /app/logs/iptvListWatcher.log 2>&1 || true

# Ejecutar iptvListValidator validate al iniciar el contenedor (si existe la lista)
# Acestream ya está healthy gracias a depends_on: service_healthy en docker-compose
echo "Ejecutando iptvListValidator validate inicial..."
# TODO: ACTIVAR
# cd /app && python -m iptvListValidator validate --force >> /app/logs/iptvListValidator.log 2>&1 || true
echo ""
echo "=================================================="
echo "Iniciando servicio cron..."
echo "=================================================="
echo ""

# Iniciar cron en primer plano
exec cron -f -L 15
