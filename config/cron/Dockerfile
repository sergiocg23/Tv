# Dockerfile para contenedor cron con Python
FROM python:3.13-slim

# Metadata
LABEL description="Contenedor cron"

# Variables de entorno
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Europe/Madrid

# Instalar dependencias del sistema
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        cron \
        tzdata \
        curl \
        ca-certificates \
        procps \
        ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* /var/tmp/*

# Configurar timezone
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone

# Crear usuario no-root
RUN groupadd -r cron-user && \
    useradd -r -g cron-user -s /bin/bash cron-user

# Crear directorios necesarios
RUN mkdir -p /app/logs /app/playlist /app/scripts /var/log/cron && \
    chown -R cron-user:cron-user /app /var/log/cron

# Directorio de trabajo
WORKDIR /app

# Copiar requirements desde config/cron/
COPY config/cron/requirements.txt .

# Copiar módulos Python desde src/
COPY --chown=cron-user:cron-user src/iptvListWatcher ./iptvListWatcher
COPY --chown=cron-user:cron-user src/iptvListValidator ./iptvListValidator

# Instalar dependencias y módulos
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -e ./iptvListWatcher && \
    pip install --no-cache-dir -e ./iptvListValidator && \
    rm -rf /root/.cache/pip

# Copiar scripts de entrada y health check desde config/cron/
COPY config/cron/entrypoint.sh /entrypoint.sh
COPY config/cron/cron-health.sh /usr/local/bin/cron-health.sh

# Dar permisos de ejecución
RUN chmod +x /entrypoint.sh /usr/local/bin/cron-health.sh

# Copiar crontab desde config/cron/
COPY config/cron/crontab /etc/cron.d/tv-automation
RUN chmod 0644 /etc/cron.d/tv-automation && \
    chown root:root /etc/cron.d/tv-automation

# El cron necesita ejecutarse como root, pero los scripts pueden ejecutarse como usuario
# Crear directorio para logs de cron (sin crear el archivo, lo hará el entrypoint)
RUN chown -R root:root /var/log/cron

# Healthcheck
HEALTHCHECK --interval=60s --timeout=5s --start-period=15s --retries=3 \
    CMD ["/usr/local/bin/cron-health.sh"]

# Ejecutar como root (necesario para cron)
USER root

# Comando por defecto
CMD ["/entrypoint.sh"]
