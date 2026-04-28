#!/bin/bash
# Health check para el contenedor cron

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Función para log a stdout
log_info() {
    echo "[$TIMESTAMP] HEALTHCHECK ✓ $1"
}

# Función para log de error a stderr
log_error() {
    echo "[$TIMESTAMP] HEALTHCHECK ✗ ERROR: $1" >&2
}

# Inicio del healthcheck
echo "[$TIMESTAMP] HEALTHCHECK Iniciando verificación..."

# PROCESO CRON
# Verificar que el proceso cron está corriendo
# Buscar por "cron" en la lista de procesos (cron -f corre como "cron")
if ps aux | grep -v grep | grep -q "[c]ron"; then
    log_info "Proceso cron corriendo"
else
    log_error "Proceso cron no está corriendo"
    exit 1
fi

# Verificar que el archivo de log existe y es escribible
if [ ! -w /var/log/cron/cron.log ]; then
    log_error "No se puede escribir en /var/log/cron/cron.log"
    exit 1
fi
log_info "Log de cron escribible"

# Verificar que Python está disponible
if ! command -v python > /dev/null 2>&1; then
    log_error "Python no está disponible"
    exit 1
fi
log_info "Python disponible"


# MODULO IPTVLISTWATCHER
# Verificar módulo iptvListWatcher
if ! python -m iptvListWatcher --version > /dev/null 2>&1; then
    log_error "Módulo iptvListWatcher no está instalado o no funciona"
    exit 1
fi
log_info "Módulo iptvListWatcher OK"

# MODULO IPTVLISTVALIDATOR
# Verificar módulo iptvListValidator
if ! python -m iptvListValidator --version > /dev/null 2>&1; then
    log_error "Módulo iptvListValidator no está instalado o no funciona"
    exit 1
fi
log_info "Módulo iptvListValidator OK"

# MODULO STREAMM3UGENERATOR
# Verificar módulo streamM3UGenerator
if ! python -m streamM3UGenerator --version > /dev/null 2>&1; then
    log_error "Módulo streamM3UGenerator no está instalado o no funciona"
    exit 1
fi
log_info "Módulo streamM3UGenerator OK"

# Verificar que el stream de prueba está corriendo
if ! python -m streamM3UGenerator health > /dev/null 2>&1; then
    log_error "Stream de prueba no está respondiendo"
    exit 1
fi
log_info "Stream de prueba OK"

# Verificar directorios necesarios
if [ ! -d /app/playlist ]; then
    log_error "Directorio /app/playlist no existe"
    exit 1
fi
log_info "Directorio /app/playlist existe"

if [ ! -d /app/logs ]; then
    log_error "Directorio /app/logs no existe"
    exit 1
fi
log_info "Directorio /app/logs existe"

# Verificar que los directorios son escribibles
if [ ! -w /app/playlist ] || [ ! -w /app/logs ]; then
    log_error "No se puede escribir en directorios necesarios"
    exit 1
fi
log_info "Directorios escribibles"


#END CHECKS
echo "[$TIMESTAMP] HEALTHCHECK ✅ OK: Todos los checks pasaron"
exit 0
