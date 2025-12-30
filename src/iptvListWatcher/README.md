# iptvListWatcher

Monitor y gestor de listas IPTV con detección automática de cambios.

## ¿Qué hace?

1. **Descarga** una lista IPTV desde una URL configurable
2. **Reemplaza** automáticamente `127.0.0.1` por la IP de tu host
3. **Detecta cambios** comparando hash SHA256 del contenido
4. **Crea backups** automáticos con timestamp cuando hay cambios
5. **Limpia** archivos antiguos manteniendo solo los más recientes

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
├── iptv.m3u                    # Archivo actual
└── olds/                       # Backups
    ├── iptv_2025-12-28.m3u    # Backup del 28 de diciembre
    ├── iptv_2025-12-27.m3u    # Backup del 27 de diciembre
    └── iptv_2025-12-27_1.m3u  # Segundo backup del mismo día
```

## Funcionamiento Interno

### Detección de Cambios
1. Descarga contenido desde URL
2. Reemplaza `127.0.0.1` → `HOST_IP`
3. Calcula hash SHA256 del nuevo contenido
4. Compara con hash del archivo actual
5. **Si son diferentes:**
   - Mueve archivo actual a `olds/` con timestamp
   - Guarda nuevo archivo
6. **Si son iguales:**
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

- Python >= 3.8
- requests >= 2.31.0
- requests[socks]>=2.31.0

## Versión

1.0.0
