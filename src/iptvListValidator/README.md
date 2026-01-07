# iptvListValidator

Validador automático de enlaces IPTV con medición de calidad y estabilidad.

## ¿Qué hace?

1. **Lee** una lista IPTV (generada por iptvListWatcher)
2. **Valida** cada enlace Acestream intentando establecer conexión
3. **Mide** latencia y estabilidad de cada stream
4. **Ordena** los enlaces válidos por mejor calidad (menor latencia, mayor estabilidad)
5. **Separa** en dos listas:
   - `iptvListValidatorValid.m3u` - Enlaces que funcionan (ordenados por calidad)
   - `iptvListValidatorFail.m3u` - Enlaces que NO funcionan
6. **Crea backups** automáticos con timestamp cuando hay cambios

## Instalación

```bash
pip install -e .
```

## Configuración

Todas las variables son **obligatorias** y deben estar en el archivo `.env`:

```bash
HOST_IP=192.168.1.138                           # IP de tu servidor Acestream
IPTV_OUTPUT_DIR=/app/playlist/ListWatcher       # Directorio donde están las listas
IPTV_FILENAME=iptvWatcher.m3u                   # Nombre del archivo a validar
VALIDATOR_OUTPUT_DIR=/app/playlist/Validator    # Directorio de salida
VALIDATOR_TIMEOUT_CONNECT=5                     # Timeout conexión (segundos)
VALIDATOR_TIMEOUT_STREAM=10                     # Timeout stream (segundos)
VALIDATOR_MIN_BITRATE=500000                    # Bitrate mínimo (bytes/seg)
VALIDATOR_STABILITY_TEST_DURATION=5             # Duración test estabilidad (seg)
```

## Comandos

### 🔍 validate - Validar enlaces
Valida todos los enlaces de la lista IPTV, mide calidad y genera listas.

```bash
# Validación básica
iptvListValidator validate

# Forzar validación aunque no haya cambios
iptvListValidator validate --force

# Sin crear backup de archivos anteriores
iptvListValidator validate --no-backup

# Validar archivo específico
iptvListValidator validate --input /path/to/lista.m3u
```

**Argumentos:**
- `--force` - Fuerza validación aunque no haya cambios en el archivo de entrada
- `--no-backup` - No crea backup de los archivos anteriores
- `--input FILE` - Archivo M3U de entrada (sobrescribe configuración)

**Proceso:**
1. Lee el archivo M3U de entrada
2. Por cada canal y sus enlaces:
   - Intenta conectar al stream Acestream
   - Mide tiempo de respuesta (latencia)
   - Verifica estabilidad (descarga durante X segundos)
   - Calcula bitrate
3. Ordena enlaces válidos por mejor calidad
4. Genera dos archivos M3U separados

---

### 📊 check - Verificar estado
Muestra información de los archivos generados sin validar.

```bash
iptvListValidator check
```

**Muestra:**
- Si los archivos válidos/inválidos existen
- Tamaño en bytes
- Fecha de última modificación
- Hash SHA256
- Número de líneas y canales
- Cantidad de backups disponibles

---

### 🧹 clean - Limpiar backups antiguos
Elimina backups antiguos manteniendo solo los más recientes.

```bash
# Mantener los últimos 5 backups de cada tipo
iptvListValidator clean --keep 5

# Ver qué se eliminaría sin borrar (dry-run)
iptvListValidator clean --keep 5 --dry-run
```

**Argumentos:**
- `--keep N` - Número de backups a mantener por tipo (por defecto: 5)
- `--dry-run` - Simula la limpieza sin borrar archivos

---

### ℹ️ info - Ver configuración
Muestra la configuración actual y estado del sistema.

```bash
iptvListValidator info
```

**Muestra:**
- Archivo de entrada configurado
- Directorios de salida
- Timeouts y parámetros de validación
- Versión del módulo

---

## Opciones Globales

Se aplican a todos los comandos:

```bash
# Modo verbose (más información en logs)
iptvListValidator -v validate

# Especificar archivo de log personalizado
iptvListValidator --log-file /ruta/logs/custom.log validate

# Sobrescribir directorio de salida
iptvListValidator --output-dir /otra/ruta validate

# Ver versión
iptvListValidator --version

# Ver ayuda
iptvListValidator --help
iptvListValidator validate --help
```

## Ejemplos de Uso

### Ejemplo 1: Uso básico con cron
```bash
# Validar cada día a las 05:10 (en crontab)
10 5 * * * cd /app && python -m iptvListValidator validate >> /app/logs/iptvListValidator.log 2>&1
```

### Ejemplo 2: Validación con configuración personalizada
```bash
iptvListValidator validate \
  --input /app/playlist/ListWatcher/iptvWatcher.m3u \
  --force
```

### Ejemplo 3: Verificar y limpiar
```bash
# Ver estado actual
iptvListValidator check

# Si hay muchos backups, limpiar manteniendo los últimos 3
iptvListValidator clean --keep 3
```

### Ejemplo 4: Debugging con verbose
```bash
# Ver información detallada durante la validación
iptvListValidator -v validate
```

## Estructura de Archivos

```
playlist/Validator/
├── iptvListValidatorValid.m3u              # Enlaces válidos (ordenados)
├── iptvListValidatorFail.m3u               # Enlaces fallidos
└── olds/                                   # Backups
    ├── iptvListValidatorValid_20260107_051045.m3u
    ├── iptvListValidatorFail_20260107_051045.m3u
    └── ...
```

## Funcionamiento Interno

### Sistema de Validación
1. Lee archivo M3U de entrada
2. Parsea canales agrupando enlaces por canal
3. **Valida en paralelo** (10 hilos):
   - **Conexión HTTP**: Verifica que responde
   - **Latencia**: Mide tiempo de primera respuesta
   - **Estabilidad**: Descarga stream durante X segundos
   - **Bitrate**: Calcula velocidad de descarga
4. Asigna score de calidad a cada enlace:
   - 40% → Estabilidad
   - 30% → Latencia
   - 30% → Bitrate
5. Ordena enlaces válidos por mejor score
6. Genera archivos separados

### Detección de Cambios
1. Calcula hash del archivo de entrada
2. Compara con hash del último procesamiento
3. **Si son diferentes:**
   - Crea backups de archivos anteriores
   - Ejecuta validación completa
   - Guarda nuevos archivos
4. **Si son iguales:**
   - No procesa (usa `--force` para forzar)

### Formato de Backups
- **Nombre:** `{filename}_{YYYYMMDD_HHMMSS}.m3u`
- **Ejemplo:** `iptvListValidatorValid_20260107_051045.m3u`

## Métricas de Calidad

Para determinar la calidad de un enlace se consideran:

1. **Estabilidad** (40 puntos) - Lo más importante
   - Stream mantiene conexión durante prueba
   - Bitrate >= mínimo configurado

2. **Latencia** (30 puntos) - Menor es mejor
   - Tiempo de primera respuesta
   - 0s = 30pts, 5s = 15pts, 10s+ = 0pts

3. **Bitrate** (30 puntos) - Mayor es mejor
   - Velocidad de descarga del stream
   - 500KB/s = 15pts, 1MB/s = 30pts

**Score final:** Los enlaces se ordenan de mayor a menor score (máx 100 puntos)

## Códigos de Salida

- `0` - Éxito
- `1` - Error (ver logs para detalles)

## Logs

Por defecto se guardan en `logs/iptvListValidator.log`:

```
2026-01-07 05:10:00 - iptvListValidator - INFO - INICIANDO VALIDACIÓN DE ENLACES IPTV
2026-01-07 05:10:00 - iptvListValidator - INFO - Encontrados 150 canales
2026-01-07 05:10:00 - iptvListValidator - INFO - Total de enlaces a validar: 450
2026-01-07 05:10:00 - iptvListValidator - INFO - Validando 450 enlaces únicos con 10 hilos...
2026-01-07 05:12:30 - iptvListValidator - INFO - Enlaces válidos: 380
2026-01-07 05:12:30 - iptvListValidator - INFO - Enlaces fallidos: 70
2026-01-07 05:12:30 - iptvListValidator - INFO - Estadísticas por grupo:
2026-01-07 05:12:30 - iptvListValidator - INFO -   LA LIGA: 45/50 válidos (90.0%), 5 fallidos
2026-01-07 05:12:30 - iptvListValidator - INFO -   DAZN: 38/40 válidos (95.0%), 2 fallidos
2026-01-07 05:12:31 - iptvListValidator - INFO - VALIDACIÓN COMPLETADA
2026-01-07 05:12:31 - iptvListValidator - INFO - Duración total: 2m 31s
```

## Requisitos

- Python >= 3.8
- requests >= 2.31.0

## Versión

1.0.0
