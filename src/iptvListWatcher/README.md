# iptvListWatcher

Monitor y gestor de listas IPTV con detección automática de cambios.

## ¿Qué hace?

1. **Descarga** una lista IPTV desde una URL configurable
2. **Parsea** el M3U con formato estricto (`#EXTGRP`, `#EXTINF`) + fallback resiliente
3. **Reemplaza** automáticamente `127.0.0.1` por la IP de tu host
4. **Detecta cambios** comparando hash SHA256 del contenido
5. **Crea backups** automáticos con timestamp cuando hay cambios
6. **Limpia** archivos antiguos manteniendo solo los más recientes
7. **Gestiona URLs** en runtime con override persistente y historial

## Instalación

```bash
pip install -e .
```

## Configuración

Todas las variables son **obligatorias** y deben estar en el archivo `.env`:

```bash
HOST_IP=192.168.1.138                    # IP de tu servidor Acestream
IPTV_LIST_URL=https://...                # URL de la lista IPTV
IPTV_OUTPUT_DIR=/app/playlist/ListWatcher # Directorio de salida
IPTV_FILENAME=iptv.m3u                   # Nombre del archivo
IPTV_GENERIC_IP=127.0.0.1                # IP a reemplazar
IPTV_DOWNLOAD_TIMEOUT=30                 # Timeout en segundos
```

## Comandos

### 📥 download - Descargar lista
Descarga la lista, reemplaza IPs y detecta cambios.

```bash
# Descarga básica
iptvListWatcher download

# Forzar descarga aunque no haya cambios
iptvListWatcher download --force

# Sin crear backup del archivo anterior
iptvListWatcher download --no-backup

# Con URL personalizada
iptvListWatcher download --url https://ejemplo.com/lista.m3u

# Con IP personalizada
iptvListWatcher download --host-ip 192.168.1.100
```

**Argumentos:**
- `--force` - Guarda el archivo aunque no haya cambios
- `--no-backup` - No crea backup del archivo anterior
- `--url URL` - Sobrescribe la URL del .env
- `--host-ip IP` - Sobrescribe la IP del .env

---

### 🔍 check - Verificar estado
Muestra información del archivo actual sin descargar.

```bash
iptvListWatcher check
```

**Muestra:**
- Si el archivo existe
- Tamaño en bytes
- Fecha de última modificación
- Hash SHA256
- Número de líneas
- Cantidad de backups disponibles

---

### 🧹 clean - Limpiar backups antiguos
Elimina backups antiguos manteniendo solo los más recientes.

```bash
# Mantener los últimos 5 backups
iptvListWatcher clean --keep 5

# Ver qué se eliminaría sin borrar (dry-run)
iptvListWatcher clean --keep 5 --dry-run
```

**Argumentos:**
- `--keep N` - Número de backups a mantener (por defecto: 5)
- `--dry-run` - Simula la limpieza sin borrar archivos

---

### ℹ️ info - Ver configuración
Muestra la configuración actual y estado del sistema.

```bash
iptvListWatcher info
```

**Muestra:**
- URL de descarga configurada
- IP del host
- Directorios (salida y backups)
- Estado de directorios
- Información del archivo actual

---

### 🔐 hash - Calcular hash de archivo
Calcula el hash SHA256 de un archivo M3U.

```bash
iptvListWatcher hash /ruta/al/archivo.m3u
```

**Útil para:**
- Verificar integridad de archivos
- Comparar manualmente dos versiones
- Debugging

---

### 🔗 set-url - Cambiar URL en runtime
Establece una nueva URL de descarga sin reiniciar el contenedor.
Se persiste en `url_config.json` dentro del directorio de salida.

```bash
# Cambiar URL
iptvListWatcher set-url "https://nueva-fuente.com/lista.m3u"

# Con motivo (queda en el historial)
iptvListWatcher set-url "https://nueva-fuente.com/lista.m3u" --reason "la fuente anterior dejó de funcionar"
```

**Desde Docker:**
```bash
docker compose --env-file .env -f compose/docker-compose.tv.yml run --rm cron \
  python3 -m iptvListWatcher set-url "https://nueva-fuente.com/lista.m3u" --reason "nueva fuente"
```

---

### 📋 get-url - Ver URL activa e historial
Muestra la URL de descarga en uso, su fuente y el historial de cambios.

```bash
iptvListWatcher get-url
```

**Muestra:**
- URL actualmente en uso
- Fuente (`env`, `override` o `cli`)
- Si hay override activo
- Historial completo de URLs con fechas y motivos

---

### 🔄 reset-url - Volver a la URL del .env
Elimina el override y vuelve a usar `IPTV_LIST_URL` del `.env`.

```bash
# Reset simple
iptvListWatcher reset-url

# Con motivo
iptvListWatcher reset-url --reason "la nueva fuente no funciona"
```

---

## Opciones Globales

Se aplican a todos los comandos:

```bash
# Modo verbose (más información en logs)
iptvListWatcher -v download

# Especificar archivo de log personalizado
iptvListWatcher --log-file /ruta/logs/custom.log download

# Sobrescribir directorio de salida
iptvListWatcher --output-dir /otra/ruta download

# Ver versión
iptvListWatcher --version

# Ver ayuda
iptvListWatcher --help
iptvListWatcher download --help
```

## Jerarquía de Resolución de URL

Cuando se ejecuta `download`, la URL se resuelve en este orden:

1. **`--url` flag CLI** — máxima prioridad, no se persiste
2. **`url_config.json` → `active_url`** — override persistente via `set-url`
3. **`IPTV_LIST_URL` env var** — fallback por defecto desde `.env`

El comando `info` muestra qué fuente se está usando.

## Parser M3U

El módulo incluye un parser de M3U en 2 niveles:

### Modo estricto
Parsea el formato esperado:
```
#EXTM3U url-tvg="..." refresh="..."
#EXTVLCOPT:http-reconnect=true
#EXTGRP: group-title="DEPORTES" group-logo="https://..."
#EXTGRP: group-title="CINE"
#EXTINF:-1 tvg-id="DAZN" tvg-logo="https://..." group-title="DEPORTES",DAZN 1 HD
http://127.0.0.1:6878/ace/getstream?id=abc123
```

### Modo fallback
Si el formato estricto falla o no encuentra canales, intenta rescatar el máximo:
- Busca pares `#EXTINF` + URL
- Busca URLs de Acestream sueltas (sin `#EXTINF`)
- Canales sin grupo se asignan al grupo `OTROS`

## Ejemplos de Uso

### Ejemplo 1: Uso básico con cron
```bash
# Descargar cada hora (en crontab)
0 * * * * cd /app && python -m iptvListWatcher download >> /app/logs/iptvListWatcher.log 2>&1
```

### Ejemplo 2: Descarga con configuración personalizada
```bash
iptvListWatcher download \
  --url https://mi-servidor.com/lista.m3u \
  --host-ip 10.0.0.50 \
  --force
```

### Ejemplo 3: Verificar y limpiar
```bash
# Ver estado actual
iptvListWatcher check

# Si hay muchos backups, limpiar manteniendo los últimos 10
iptvListWatcher clean --keep 10
```

### Ejemplo 4: Debugging con verbose
```bash
# Ver información detallada durante la descarga
iptvListWatcher -v download
```

## Estructura de Archivos

```
playlist/ListWatcher/
├── iptvWatcher.m3u              # Archivo actual
├── url_config.json              # Override de URL + historial
└── olds/                        # Backups
    ├── iptvWatcher_2026-04-28.m3u
    ├── iptvWatcher_2026-04-27.m3u
    └── iptvWatcher_2026-04-27_1.m3u
```

## Funcionamiento Interno

### Detección de Cambios
1. Descarga contenido desde URL (con jerarquía de resolución)
2. Parsea M3U (estricto → fallback si falla)
3. Reemplaza `127.0.0.1` → `HOST_IP` en las URLs parseadas
4. Reconstruye el M3U desde los canales parseados
5. Calcula hash SHA256 del nuevo contenido
6. Compara con hash del archivo actual
7. **Si son diferentes:**
   - Mueve archivo actual a `olds/` con timestamp
   - Guarda nuevo archivo
8. **Si son iguales:**
   - No hace nada (ahorra escrituras)

### Formato de Backups
- **Nombre:** `{filename}_{YYYY-MM-DD}.m3u`
- **Si ya existe:** Se añade contador `_{N}`
- **Ejemplo:** `iptv_2025-12-28_1.m3u`

## Códigos de Salida

- `0` - Éxito
- `1` - Error (ver logs para detalles)

## Logs

Por defecto se guardan en `logs/iptvListWatcher.log`:

```
2025-12-28 10:30:00 - iptvListWatcher - INFO - Descargando lista desde: https://...
2025-12-28 10:30:02 - iptvListWatcher - INFO - Lista guardada: /app/playlist/ListWatcher/iptv.m3u
2025-12-28 10:30:02 - iptvListWatcher - INFO - ✓ Lista actualizada
```

## Requisitos

- Python >= 3.12
- requests >= 2.31.0
- requests[socks] >= 2.31.0

## Versión

1.1.0
