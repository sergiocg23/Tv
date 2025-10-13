#!/bin/sh
mkdir -p /tmp/certs

# Generar certificado autofirmado
if [ ! -f /tmp/certs/privkey.pem ]; then
  openssl req -x509 -nodes -days 365 \
    -newkey rsa:2048 \
    -keyout /tmp/certs/privkey.pem \
    -out /tmp/certs/fullchain.pem \
    -subj "/C=ES/ST=Spain/L=City/O=Tv/CN=localhost" \
    >/dev/null 2>&1
fi

# Lanzar Nginx
exec /docker-entrypoint.sh nginx -g "daemon off;"