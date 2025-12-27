#!/bin/bash
# Entrypoint personalizado para Jellyfin con pre-configuración, cargando gpu y ajustando permisos

set -e

echo "🚀 Iniciando Jellyfin con pre-configuración..."

CONFIG_DIR="/config/config"

# Solo pre-configurar si es la primera vez
if [ ! -f "$CONFIG_DIR/system.xml" ]; then
    echo "🔧 Primera ejecución detectada - Pre-configurando..."
    
    # Crear directorios necesarios (como root si es necesario)
    mkdir -p "$CONFIG_DIR" 2>/dev/null || true
    mkdir -p /config/log 2>/dev/null || true
    mkdir -p /config/data 2>/dev/null || true
    mkdir -p /config/metadata 2>/dev/null || true
    mkdir -p /config/plugins 2>/dev/null || true
    mkdir -p /cache/transcodes 2>/dev/null || true

    # Configurar red
    echo "📡 Configurando red..."
    cat > "$CONFIG_DIR/network.xml" << 'EOF'
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
EOF

    # Configurar sistema (idioma español)
    echo "🌍 Configurando idioma y región..."
    cat > "$CONFIG_DIR/system.xml" << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<ServerConfiguration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <IsStartupWizardCompleted>false</IsStartupWizardCompleted>
  <ServerName>Jellyfin TV</ServerName>
  <UICulture>es-ES</UICulture>
  <MetadataCountryCode>ES</MetadataCountryCode>
  <PreferredMetadataLanguage>es</PreferredMetadataLanguage>
  <EnableMetrics>false</EnableMetrics>
  <EnableAutomaticRestart>false</EnableAutomaticRestart>
  <ActivityLogRetentionDays>30</ActivityLogRetentionDays>
  <LogFileRetentionDays>3</LogFileRetentionDays>
  <SaveMetadataHidden>false</SaveMetadataHidden>
</ServerConfiguration>
EOF

    # Detectar tipo de GPU
    echo "🔍 Detectando hardware..."
    if [ -c "/dev/nvidia0" ] || [ -d "/usr/local/nvidia" ]; then
        GPU_TYPE="nvidia"
        echo "   → GPU NVIDIA detectada"
        cat > "$CONFIG_DIR/encoding.xml" << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<EncodingOptions xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <EncodingThreadCount>-1</EncodingThreadCount>
  <TranscodingTempPath>/cache/transcodes</TranscodingTempPath>
  <EnableThrottling>false</EnableThrottling>
  <EnableHardwareEncoding>true</EnableHardwareEncoding>
  <HardwareAccelerationType>nvenc</HardwareAccelerationType>
  <EnableTonemapping>true</EnableTonemapping>
  <EnableVppTonemapping>false</EnableVppTonemapping>
  <EnableDecodingColorDepth10Hevc>true</EnableDecodingColorDepth10Hevc>
  <EnableDecodingColorDepth10Vp9>true</EnableDecodingColorDepth10Vp9>
  <H264Crf>23</H264Crf>
  <H265Crf>28</H265Crf>
  <EncoderPreset>medium</EncoderPreset>
  <DeinterlaceDoubleRate>false</DeinterlaceDoubleRate>
  <DeinterlaceMethod>yadif</DeinterlaceMethod>
</EncodingOptions>
EOF
    elif [ -d "/dev/dri" ]; then
        GPU_TYPE="intel/amd"
        echo "   → GPU Intel/AMD detectada"
        cat > "$CONFIG_DIR/encoding.xml" << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<EncodingOptions xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <EncodingThreadCount>-1</EncodingThreadCount>
  <TranscodingTempPath>/cache/transcodes</TranscodingTempPath>
  <EnableThrottling>false</EnableThrottling>
  <EnableHardwareEncoding>true</EnableHardwareEncoding>
  <HardwareAccelerationType>vaapi</HardwareAccelerationType>
  <EnableTonemapping>false</EnableTonemapping>
  <EnableVppTonemapping>false</EnableVppTonemapping>
  <EnableDecodingColorDepth10Hevc>true</EnableDecodingColorDepth10Hevc>
  <EnableDecodingColorDepth10Vp9>true</EnableDecodingColorDepth10Vp9>
  <H264Crf>23</H264Crf>
  <H265Crf>28</H265Crf>
  <EncoderPreset>veryfast</EncoderPreset>
  <DeinterlaceDoubleRate>false</DeinterlaceDoubleRate>
  <DeinterlaceMethod>yadif</DeinterlaceMethod>
  <VaapiDevice>/dev/dri/renderD128</VaapiDevice>
</EncodingOptions>
EOF
    else
        GPU_TYPE="cpu"
        echo "   ⚠ No se detectó GPU, usando CPU"
        cat > "$CONFIG_DIR/encoding.xml" << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<EncodingOptions xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <EncodingThreadCount>-1</EncodingThreadCount>
  <TranscodingTempPath>/cache/transcodes</TranscodingTempPath>
  <EnableThrottling>false</EnableThrottling>
  <EnableHardwareEncoding>false</EnableHardwareEncoding>
  <H264Crf>23</H264Crf>
  <H265Crf>28</H265Crf>
  <EncoderPreset>veryfast</EncoderPreset>
  <DeinterlaceDoubleRate>false</DeinterlaceDoubleRate>
  <DeinterlaceMethod>yadif</DeinterlaceMethod>
</EncodingOptions>
EOF
    fi

    # Ajustar permisos de todos los archivos creados
    chown -R 1000:1000 /config /cache 2>/dev/null || true
    
    echo ""
    echo "✅ Pre-configuración completada"
    echo "   ✓ Red configurada (IPv4, puerto 8096)"
    echo "   ✓ Idioma: Español (España)"
    echo "   ✓ Región: España (ES)"
    echo "   ✓ Transcoding optimizado para $GPU_TYPE"
    echo "   ✓ Permisos ajustados (1000:1000)"
    echo ""
else
    echo "✅ Configuración existente detectada"
fi

# Iniciar Jellyfin con el comando original (cambiar a usuario 1000:1000)
echo "🎬 Iniciando servidor Jellyfin..."
if [ "$(id -u)" = "0" ]; then
    # Si somos root, cambiar a usuario 1000:1000
    # Intentar usar su-exec, gosu, o setpriv según lo que esté disponible
    if command -v su-exec >/dev/null 2>&1; then
        exec su-exec 1000:1000 /jellyfin/jellyfin \
            --datadir=/config \
            --cachedir=/cache \
            --ffmpeg=/usr/lib/jellyfin-ffmpeg/ffmpeg
    elif command -v gosu >/dev/null 2>&1; then
        exec gosu 1000:1000 /jellyfin/jellyfin \
            --datadir=/config \
            --cachedir=/cache \
            --ffmpeg=/usr/lib/jellyfin-ffmpeg/ffmpeg
    elif command -v setpriv >/dev/null 2>&1; then
        exec setpriv --reuid=1000 --regid=1000 --clear-groups /jellyfin/jellyfin \
            --datadir=/config \
            --cachedir=/cache \
            --ffmpeg=/usr/lib/jellyfin-ffmpeg/ffmpeg
    else
        # Fallback: usar runuser o su
        exec runuser -u jellyfin -- /jellyfin/jellyfin \
            --datadir=/config \
            --cachedir=/cache \
            --ffmpeg=/usr/lib/jellyfin-ffmpeg/ffmpeg
    fi
else
    # Si ya somos el usuario correcto, ejecutar directamente
    exec /jellyfin/jellyfin \
        --datadir=/config \
        --cachedir=/cache \
        --ffmpeg=/usr/lib/jellyfin-ffmpeg/ffmpeg
fi
