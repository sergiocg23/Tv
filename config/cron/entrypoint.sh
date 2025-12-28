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

# Verificar permisos de directorios
echo "Verificando permisos..."
chown -R cron-user:cron-user /app/logs 2>/dev/null || true

# Verificar que existe el archivo de log de cron (debe ser root ya que cron se ejecuta como root)
if [ ! -f /var/log/cron/cron.log ]; then
    touch /var/log/cron/cron.log
    chmod 644 /var/log/cron/cron.log
fi

# Mostrar módulos Python disponibles
#TODO: Actualizar cuando existan módulos específicos para cron
echo "Módulos Python disponibles en /app:"
ls -la /app/ 2>/dev/null || echo "  (ninguno todavía)"
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

echo ""
echo "=================================================="
echo "Iniciando servicio cron..."
echo "=================================================="
echo ""

# Iniciar cron en primer plano
exec cron -f -L 15
