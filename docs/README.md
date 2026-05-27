# Stack: tv

## Descripción

Stack de IPTV para reproducción, pruebas y validación de canales. Incluye proxy WARP para anonimizar tráfico, motor AceStream para streams P2P, Jellyfin como media server, y un contenedor cron con 3 módulos Python de automatización.

## Servicios

| Servicio | Imagen | Puerto | Función |
|---|---|---|---|
| warp | `monius/docker-warp-socks:v4` | 9091 (interno) | Proxy SOCKS5 vía Cloudflare WARP |
| acestream | `rotiemex/acewarp:latest` | 6878, 8621 | Motor AceStream P2P |
| jellyfin | `jellyfin/jellyfin:10.10.6` | 8096, 7359/udp | Media server para reproducción IPTV |
| autoheal | `willfarrell/autoheal:latest` | — | Auto-reinicio de contenedores unhealthy |
| cron | Build local (`config/cron/Dockerfile`) | — | Automatización con 3 módulos Python |

### Módulos Python (cron)

| Módulo | Función |
|---|---|
| `iptvListWatcher` | Descarga y actualiza listas IPTV periódicamente |
| `iptvListValidator` | Valida streams con sistema de confianza por tiers |
| `streamM3UGenerator` | Genera streams M3U de prueba |

## Redes

| Red | Tipo | Motivo |
|---|---|---|
| `stream_net` | bridge, named | Comunicación warp ↔ acestream ↔ cron |
| `tv_net` | bridge, named | Red principal del stack (jellyfin, autoheal) |
| `shared_obs_net` | external | Observabilidad — si aplica |

## Estructura

```
tv/
├── compose/                           # Docker Compose files
│   ├── docker-compose.tv.yml          # Compose principal
│   ├── docker-compose.tv.intel-ext.yml   # Override GPU Intel/AMD
│   └── docker-compose.tv.nvidia-ext.yml  # Override GPU NVIDIA
├── config/                            # Configuración versionable
│   ├── acestream/acestream.conf
│   ├── cron/                          # Dockerfile + scripts cron
│   │   ├── Dockerfile
│   │   ├── entrypoint.sh
│   │   ├── cron-health.sh
│   │   ├── crontab
│   │   └── requirements.txt
│   ├── jellyfin/entrypoint.sh
│   └── nginx/                         # Legacy (desactivado)
├── src/                               # Código fuente módulos Python
│   ├── iptvListValidator/
│   ├── iptvListWatcher/
│   └── streamM3UGenerator/
├── data/                              # ⚠️ Datos runtime (en .gitignore)
│   ├── jellyfin/{config,cache,media}
│   ├── playlist/
│   └── logs/
├── docs/                              # Documentación del stack
├── .env                               # Variables (NO versionable)
├── .env.example                       # Plantilla de variables
└── .gitignore
```

## Arranque

```bash
# Desde la raíz del stack (tv/)
cd stacks/tv  # o la ruta que corresponda

# Solo CPU
docker compose -f compose/docker-compose.tv.yml up -d

# Con GPU Intel/AMD (Beelink S12 Pro - Intel N100)
docker compose -f compose/docker-compose.tv.yml -f compose/docker-compose.tv.intel-ext.yml up -d

# Con GPU NVIDIA
docker compose -f compose/docker-compose.tv.yml -f compose/docker-compose.tv.nvidia-ext.yml up -d
```

## Troubleshooting

| Problema | Verificación |
|---|---|
| AceStream no conecta | `curl http://localhost:8621` — debe responder |
| Jellyfin no carga | `curl -f http://localhost:8096/health` |
| WARP no activo | `curl -x socks5h://127.0.0.1:9091 https://www.cloudflare.com/cdn-cgi/trace` → debe mostrar `warp=on` |
| Cron no funciona | `docker exec cron crontab -l` — debe mostrar tareas |

## Backup

**Datos a respaldar:**
- `data/jellyfin/config/` — Configuración Jellyfin (usuarios, bibliotecas)
- `data/playlist/` — Listas IPTV curadas y validadas
- `.env` — Variables de entorno

**Datos regenerables (no necesitan backup):**
- `data/jellyfin/cache/` — Cache de transcoding
- `data/logs/` — Logs de automatización
