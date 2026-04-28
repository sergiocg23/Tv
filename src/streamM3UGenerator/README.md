# streamM3UGenerator

Generador de canales M3U para testing IPTV. Crea un stream en bucle de un video y genera un canal M3U para pruebas.

## 🎯 Propósito

Este módulo está diseñado para:
- Proporcionar un canal IPTV de prueba siempre disponible
- Validar el correcto funcionamiento de `iptvListValidator`
- Probar la conexión con Acestream
- Testing continuo sin depender de streams externos

## 📦 Características

- ✅ Stream en bucle 24/7 de un video
- ✅ Generación automática de archivo M3U
- ✅ Health checks integrados
- ✅ Control completo del ciclo de vida (start/stop/status)
- ✅ Ejecución en background
- ✅ Sin necesidad de puertos externos (todo interno al contenedor)

## 🚀 Uso

### Comandos básicos

```bash
# Iniciar stream en background y generar M3U
streamM3UGenerator start

# Ver estado
streamM3UGenerator status

# Detener stream
streamM3UGenerator stop

# Verificar salud del stream
streamM3UGenerator health

# Solo generar el M3U (sin iniciar stream)
streamM3UGenerator generate

# Ver información de configuración
streamM3UGenerator info
```

### Como módulo Python

```bash
python -m streamM3UGenerator start
python -m streamM3UGenerator status
```

## ⚙️ Configuración

Las variables de entorno disponibles:

```bash
# Host y puerto del stream (interno)
STREAM_HOST=127.0.0.1
STREAM_PORT=8765

# Directorio de salida
STREAM_OUTPUT_DIR=/app/playlist

# Nombre del archivo M3U
STREAM_M3U_FILENAME=test-channel.m3u

# Información del canal
STREAM_CHANNEL_NAME="Test Channel - Gol Ramos"
STREAM_CHANNEL_GROUP="Testing"
STREAM_CHANNEL_LOGO=""

# Protocolo FFmpeg (http o tcp)
FFMPEG_PROTOCOL=tcp

# Nivel de log de FFmpeg
FFMPEG_LOGLEVEL=error
```

## 📂 Estructura

```
streamM3UGenerator/
├── __init__.py          # Metadata del paquete
├── __main__.py          # Punto de entrada
├── cli.py               # Interfaz de línea de comandos
├── config.py            # Configuración
├── generator.py         # Generador de stream y M3U
├── utils.py             # Utilidades
├── setup.py             # Configuración de instalación
├── README.md            # Este archivo
└── resources/
    └── GolRamos.mp4     # Video de prueba
```

## 🐳 Integración con Docker

El módulo está diseñado para ejecutarse en el contenedor `cron`:

1. **Inicio automático**: El `entrypoint.sh` inicia el stream al arrancar
2. **Health checks**: El `cron-health.sh` verifica que el stream está funcionando
3. **M3U disponible**: Se genera en `/app/playlist/test-channel.m3u`

## 🔍 Testing con iptvListValidator

Una vez el stream está activo, puedes probarlo:

```bash
# Validar el canal de prueba
iptvListValidator validate --input /app/playlist/test-channel.m3u
```

## 📝 Notas técnicas

- El stream usa **FFmpeg** en modo bucle infinito (`-stream_loop -1`)
- Usa codec copy (`-c copy`) para no recodificar y minimizar CPU
- El formato es MPEG-TS, compatible con IPTV
- El servidor está en localhost, no expone puertos externos
- El PID del proceso se guarda en `/tmp/streamM3UGenerator.pid`

## 🛠️ Desarrollo

```bash
# Instalar en modo desarrollo
pip install -e .

# Ejecutar tests
python -m streamM3UGenerator info
python -m streamM3UGenerator start --foreground
```

## 📄 Licencia

Proyecto interno para testing.

## 👤 Autor

Sergio
