"""
Utilidades para streamM3UGenerator
"""

import sys
import requests
from typing import Optional

from streamM3UGenerator.config import Config


def check_stream_health() -> tuple[bool, str]:
    """
    Verifica que el stream está respondiendo.
    
    Returns:
        tuple: (is_healthy, message)
    """
    try:
        stream_url = Config.get_stream_url()
        
        # Intentar conectar al stream
        response = requests.head(stream_url, timeout=3)
        
        if response.status_code in [200, 206]:  # 206 = Partial Content (streaming)
            return True, "Stream respondiendo OK"
        else:
            return False, f"Stream devuelve código {response.status_code}"
            
    except requests.exceptions.ConnectionError:
        return False, "No se puede conectar al stream"
    except requests.exceptions.Timeout:
        return False, "Timeout al conectar al stream"
    except Exception as e:
        return False, f"Error inesperado: {e}"


def print_info():
    """Imprime información de configuración"""
    print("=" * 60)
    print("  streamM3UGenerator - Información")
    print("=" * 60)
    print(f"Video: {Config.DEFAULT_VIDEO}")
    print(f"Video existe: {'✅' if Config.DEFAULT_VIDEO.exists() else '❌'}")
    print(f"Stream URL: {Config.get_stream_url()}")
    print(f"M3U path: {Config.get_m3u_path()}")
    print(f"M3U existe: {'✅' if Config.get_m3u_path().exists() else '❌'}")
    print(f"Canal: {Config.CHANNEL_NAME}")
    print(f"Grupo: {Config.CHANNEL_GROUP}")
    print("=" * 60)


def validate_environment() -> bool:
    """
    Valida que el entorno está configurado correctamente.
    
    Returns:
        True si todo está OK
    """
    is_valid, errors = Config.validate_config()
    
    if not is_valid:
        print("❌ Errores de configuración:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    return True
