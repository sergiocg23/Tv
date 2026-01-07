#!/bin/bash
# Health check para el contenedor cron

# PROCESO CRON
# Verificar que el proceso cron está corriendo (usando pidof como fallback)
if command -v pgrep > /dev/null 2>&1; then
    if ! pgrep -x cron > /dev/null 2>&1; then
        echo "ERROR: Proceso cron no está corriendo" >&2
        exit 1
    fi
elif command -v pidof > /dev/null 2>&1; then
    if ! pidof cron > /dev/null 2>&1; then
        echo "ERROR: Proceso cron no está corriendo" >&2
        exit 1
    fi
else
    echo "ERROR: No se puede verificar el proceso cron" >&2
    exit 1
fi

# Verificar que el archivo de log existe y es escribible
if [ ! -w /var/log/cron/cron.log ]; then
    echo "ERROR: No se puede escribir en /var/log/cron/cron.log" >&2
    exit 1
fi

# Verificar que Python está disponible
if ! command -v python > /dev/null 2>&1; then
    echo "ERROR: Python no está disponible" >&2
    exit 1
fi


# MODULO IPTVLISTWATCHER
# Verificar módulo iptvListWatcher
if ! python -m iptvListWatcher --version > /dev/null 2>&1; then
    echo "ERROR: Módulo iptvListWatcher no está instalado o no funciona" >&2
    exit 1
fi

# MODULO IPTVLISTVALIDATOR
# Verificar módulo iptvListValidator
if ! python -m iptvListValidator --version > /dev/null 2>&1; then
    echo "ERROR: Módulo iptvListValidator no está instalado o no funciona" >&2
    exit 1
fi

# Verificar directorios necesarios
if [ ! -d /app/playlist ]; then
    echo "ERROR: Directorio /app/playlist no existe" >&2
    exit 1
fi

if [ ! -d /app/logs ]; then
    echo "ERROR: Directorio /app/logs no existe" >&2
    exit 1
fi

# Verificar que los directorios son escribibles
if [ ! -w /app/playlist ] || [ ! -w /app/logs ]; then
    echo "ERROR: No se puede escribir en directorios necesarios" >&2
    exit 1
fi


#END CHECKS
echo "OK: Cron health check passed"
exit 0
