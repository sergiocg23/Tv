#!/bin/bash
# Health check para el contenedor cron

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

#TODO: Añadir checks cuando existan módulos específicos para cron

echo "OK: Cron health check passed"
exit 0
