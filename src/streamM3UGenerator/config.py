"""
Configuración para streamM3UGenerator
"""

import os
from pathlib import Path


class Config:
    """Configuración del generador de streams"""
    
    # Directorio base del módulo
    BASE_DIR = Path(__file__).parent
    RESOURCES_DIR = BASE_DIR / "resources"
    
    # Video por defecto
    DEFAULT_VIDEO = RESOURCES_DIR / "GolRamos.mp4"
    
    # Configuración del stream
    STREAM_HOST = os.environ.get("STREAM_HOST", "127.0.0.1")
    STREAM_PORT = int(os.environ.get("STREAM_PORT", "8765"))
    
    # Configuración del M3U
    OUTPUT_DIR = Path(os.environ.get("STREAM_OUTPUT_DIR", "/app/playlist"))
    M3U_FILENAME = os.environ.get("STREAM_M3U_FILENAME", "test-channel.m3u")
    
    # Configuración del canal
    CHANNEL_NAME = os.environ.get("STREAM_CHANNEL_NAME", "Test Channel - Gol Ramos")
    CHANNEL_GROUP = os.environ.get("STREAM_CHANNEL_GROUP", "Testing")
    CHANNEL_LOGO = os.environ.get("STREAM_CHANNEL_LOGO", "")
    
    # Configuración de FFmpeg
    FFMPEG_LOGLEVEL = os.environ.get("FFMPEG_LOGLEVEL", "error")
    FFMPEG_PROTOCOL = os.environ.get("FFMPEG_PROTOCOL", "http")  # http o tcp
    
    # PID file para control del proceso
    PID_FILE = Path("/tmp/streamM3UGenerator.pid")
    
    @classmethod
    def get_stream_url(cls) -> str:
        """Obtiene la URL del stream"""
        return f"{cls.FFMPEG_PROTOCOL}://{cls.STREAM_HOST}:{cls.STREAM_PORT}/"
    
    @classmethod
    def get_m3u_path(cls) -> Path:
        """Obtiene la ruta completa del archivo M3U"""
        return cls.OUTPUT_DIR / cls.M3U_FILENAME
    
    @classmethod
    def validate_config(cls) -> tuple[bool, list[str]]:
        """
        Valida la configuración.
        
        Returns:
            tuple: (es_valida, lista_de_errores)
        """
        errors = []
        
        if not cls.DEFAULT_VIDEO.exists():
            errors.append(f"Video no encontrado: {cls.DEFAULT_VIDEO}")
        
        if not cls.OUTPUT_DIR.exists():
            try:
                cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"No se puede crear directorio de salida: {e}")
        
        if cls.STREAM_PORT < 1024 or cls.STREAM_PORT > 65535:
            errors.append(f"Puerto inválido: {cls.STREAM_PORT}")
        
        return len(errors) == 0, errors
