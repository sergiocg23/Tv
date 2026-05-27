# 🎬 Jellyfin - Configuración Multi-Hardware

Este proyecto soporta diferentes configuraciones de GPU mediante archivos compose específicos.

## 📋 Archivos de Configuración

```
docker-compose.yml              # Base (común para todos)
docker-compose-intel-ext.yml    # Intel/AMD GPU (VA-API/QSV)
docker-compose-nvidia-ext.yml   # NVIDIA GPU (NVENC/NVDEC)
```

## 🚀 Uso según Hardware

### **Intel/AMD (Beelink S12 Pro - Intel N100)**
```bash
docker compose -f docker-compose.yml -f docker-compose-intel-ext.yml up -d
```

### **NVIDIA (PC con GTX 1650, RTX, etc.)**
```bash
docker compose -f docker-compose.yml -f docker-compose-nvidia-ext.yml up -d
```

### **Sin GPU (Solo CPU)**
```bash
docker compose up -d
# Funcionará pero sin hardware acceleration
```

## 🔧 Script de Inicialización

El script `config/jellyfin/entrypoint.sh` **detecta automáticamente** tu GPU y configura:
- **NVIDIA detectada** → NVENC
- **Intel/AMD detectada** → VA-API
- **Sin GPU** → Transcoding por software

## 📝 Notas

- El archivo `-ext` se **combina** con el base, no lo reemplaza
- Solo usa **uno** de los archivos `-ext` según tu hardware
- En el Beelink usa: `intel-ext`
- En PC con NVIDIA usa: `nvidia-ext`


## 📊 Rendimiento Esperado

| Hardware | Aceleración | Streams 1080p |
|----------|-------------|---------------|
| Intel N100 | VA-API/QSV | 2-3 simultáneos |
| GTX 1650 | NVENC | 4-6 simultáneos |
| Sin GPU | Software | 1 stream |
