FROM nginx:1.29.1-alpine

# Instala openssl
RUN apk add --no-cache openssl bash

# Copia tu nginx.conf y entrypoint
COPY ./nginx.conf /etc/nginx/conf.d/default.conf
COPY ./entrypoint.sh /docker-custom-entrypoint.sh
COPY ./empty.sh /docker-entrypoint.d/10-listen-on-ipv6-by-default.sh

RUN chmod +x /docker-entrypoint.sh

# Copia el script de healthcheck dentro de la imagen
COPY ./nginx-health.sh /usr/local/bin/nginx-health.sh
RUN chmod +x /docker-custom-entrypoint.sh /usr/local/bin/nginx-health.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]