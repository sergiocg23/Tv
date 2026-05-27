# Preconfiguración de Jellyfin

## 📋 Variables de Entorno Disponibles

Todas estas se pueden configurar en `docker-compose.yml` bajo `environment:`:

### Básicas
- `TZ`: Zona horaria (ej: `Europe/Madrid`)
- `JELLYFIN_PublishedServerUrl`: URL pública para acceso remoto

### Directorios
- `JELLYFIN_DATA_DIR`: Directorio de datos (default: `/config/data`)
- `JELLYFIN_CONFIG_DIR`: Directorio de configuración (default: `/config`)
- `JELLYFIN_LOG_DIR`: Directorio de logs (default: `/config/log`)
- `JELLYFIN_CACHE_DIR`: Directorio de caché (default: `/cache`)

### Logging
- `JELLYFIN_LOG_LEVEL`: Nivel de log
  - `Trace`: Muy detallado
  - `Debug`: Información de debug
  - `Information`: Normal (default)
  - `Warning`: Solo advertencias
  - `Error`: Solo errores
  - `Critical`: Solo críticos

### Red
- `JELLYFIN_HttpListenerPort`: Puerto HTTP (default: 8096)
- `JELLYFIN_PublicPort`: Puerto público HTTP
- `JELLYFIN_PublicHttpsPort`: Puerto público HTTPS

### Web Client
- `JELLYFIN_NOWEBCLIENT`: `true` para deshabilitar el cliente web
- `JELLYFIN_WEB_DIR`: Directorio del cliente web

### FFmpeg
- `JELLYFIN_FFmpeg__probesize`: Tamaño de sondeo para análisis de archivos
- `JELLYFIN_FFmpeg__analyzeduration`: Duración de análisis

## 📁 Archivos de Configuración Pre-Setup

### 1. Network Configuration (network.xml)

Crear en: `jellyfin/config/config/network.xml`

```xml
<?xml version="1.0" encoding="utf-8"?>
<NetworkConfiguration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <RequireHttps>false</RequireHttps>
  <BaseUrl />
  <PublicHttpsPort>8920</PublicHttpsPort>
  <HttpServerPortNumber>8096</HttpServerPortNumber>
  <HttpsPortNumber>8920</HttpsPortNumber>
  <EnableHttps>false</EnableHttps>
  <PublicPort>8096</PublicPort>
  <UPnPCreateHttpPortMap>false</UPnPCreateHttpPortMap>
  <EnableRemoteAccess>true</EnableRemoteAccess>
  <EnableAutomaticRestart>true</EnableAutomaticRestart>
  <EnableIPv4>true</EnableIPv4>
  <EnableIPv6>false</EnableIPv6>
  <LocalNetworkAddresses>
    <string>192.168.0.0/16</string>
    <string>172.16.0.0/12</string>
    <string>10.0.0.0/8</string>
  </LocalNetworkAddresses>
  <KnownProxies />
</NetworkConfiguration>
```

### 2. System Configuration (system.xml)

Crear en: `jellyfin/config/config/system.xml`

```xml
<?xml version="1.0" encoding="utf-8"?>
<ServerConfiguration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <IsStartupWizardCompleted>false</IsStartupWizardCompleted>
  <UICulture>es-ES</UICulture>
  <MetadataCountryCode>ES</MetadataCountryCode>
  <PreferredMetadataLanguage>es</PreferredMetadataLanguage>
  <EnableMetrics>false</EnableMetrics>
  <EnableAutomaticRestart>false</EnableAutomaticRestart>
  <ActivityLogRetentionDays>30</ActivityLogRetentionDays>
</ServerConfiguration>
```

### 3. Encoding Configuration (encoding.xml)

Crear en: `jellyfin/config/config/encoding.xml`

```xml
<?xml version="1.0" encoding="utf-8"?>
<EncodingOptions xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <EncodingThreadCount>-1</EncodingThreadCount>
  <TranscodingTempPath>/cache/transcodes</TranscodingTempPath>
  <EnableThrottling>false</EnableThrottling>
  <EnableHardwareEncoding>true</EnableHardwareEncoding>
  <EnableTonemapping>false</EnableTonemapping>
  <EnableVppTonemapping>false</EnableVppTonemapping>
  <EnableDecodingColorDepth10Hevc>true</EnableDecodingColorDepth10Hevc>
  <EnableDecodingColorDepth10Vp9>true</EnableDecodingColorDepth10Vp9>
  <H264Crf>23</H264Crf>
  <H265Crf>28</H265Crf>
  <EncoderPreset>veryfast</EncoderPreset>
  <DeinterlaceDoubleRate>false</DeinterlaceDoubleRate>
  <DeinterlaceMethod>yadif</DeinterlaceMethod>
</EncodingOptions>
```

## 🔧 Script de Pre-Configuración

Puedes ejecutar este script ANTES de iniciar Jellyfin por primera vez:

```bash
#!/bin/bash
# Pre-configurar Jellyfin

CONFIG_DIR="./jellyfin/config/config"
mkdir -p "$CONFIG_DIR"

# Configurar red
cat > "$CONFIG_DIR/network.xml" << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<NetworkConfiguration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <RequireHttps>false</RequireHttps>
  <HttpServerPortNumber>8096</HttpServerPortNumber>
  <PublicPort>8096</PublicPort>
  <EnableRemoteAccess>true</EnableRemoteAccess>
  <EnableIPv4>true</EnableIPv4>
  <EnableIPv6>false</EnableIPv6>
  <LocalNetworkAddresses>
    <string>192.168.0.0/16</string>
  </LocalNetworkAddresses>
</NetworkConfiguration>
EOF

# Configurar sistema (idioma español)
cat > "$CONFIG_DIR/system.xml" << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<ServerConfiguration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <IsStartupWizardCompleted>false</IsStartupWizardCompleted>
  <UICulture>es-ES</UICulture>
  <MetadataCountryCode>ES</MetadataCountryCode>
  <PreferredMetadataLanguage>es</PreferredMetadataLanguage>
  <EnableMetrics>false</EnableMetrics>
</ServerConfiguration>
EOF

# Configurar transcoding
cat > "$CONFIG_DIR/encoding.xml" << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<EncodingOptions xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <TranscodingTempPath>/cache/transcodes</TranscodingTempPath>
  <EnableHardwareEncoding>true</EnableHardwareEncoding>
  <H264Crf>23</H264Crf>
  <H265Crf>28</H265Crf>
  <EncoderPreset>veryfast</EncoderPreset>
</EncodingOptions>
EOF

# Ajustar permisos
chown -R 1000:1000 jellyfin/

echo "✅ Jellyfin pre-configurado"
echo "   - Red configurada"
echo "   - Idioma: Español (España)"
echo "   - Transcoding optimizado"
echo ""
echo "⚠️  El wizard de configuración TODAVÍA aparecerá"
echo "   Pero los valores por defecto serán los correctos"
```

## 🚀 Uso

1. **Detén Jellyfin** (si está corriendo):
   ```bash
   docker compose down
   ```

2. **Limpia configuración anterior** (opcional):
   ```bash
   rm -rf jellyfin/config/*
   ```

3. **Ejecuta pre-configuración**:
   ```bash
   chmod +x scripts/jellyfin-preconfig.sh
   ./scripts/jellyfin-preconfig.sh
   ```

4. **Inicia Jellyfin**:
   ```bash
   docker compose up -d
   ```

5. **Completa el wizard** manualmente en el navegador
   - El idioma ya estará en español
   - Las configuraciones de red estarán listas

## ⚠️ Limitaciones

**Lo que NO puedes preconfigurar:**
- Usuario administrador (debe crearse en el wizard)
- Bibliotecas de medios (deben agregarse manualmente)
- Plugins (deben instalarse después)
- Algunas opciones avanzadas

**Lo que SÍ puedes preconfigurar:**
- Idioma y región
- Configuración de red
- Opciones de transcoding
- Logging
- Rutas de directorios
