"""
Utilidades comunes para el módulo iptvListWatcher.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from pathlib import Path


def calculate_file_hash(file_path: Path) -> str:
    """
    Calcula el hash SHA256 de un archivo.

    Args:
        file_path: Ruta al archivo

    Returns:
        Hash SHA256 en formato hexadecimal
    """
    sha256_hash = hashlib.sha256()

    with open(file_path, "rb") as f:
        # Leer en bloques para archivos grandes
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    return sha256_hash.hexdigest()


def calculate_content_hash(content: str) -> str:
    """
    Calcula el hash SHA256 de un contenido string.

    Args:
        content: Contenido del que calcular el hash

    Returns:
        Hash SHA256 en formato hexadecimal
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def replace_ip_in_content(content: str, old_ip: str, new_ip: str) -> str:
    """
    Reemplaza todas las apariciones de una IP en el contenido.

    .. deprecated:: 1.1.0
        Usar ``M3UPlaylist.replace_ip()`` del módulo ``parser`` en su lugar.
        Se mantiene por compatibilidad con código que importe esta función.

    Args:
        content: Contenido donde reemplazar
        old_ip: IP a buscar
        new_ip: IP de reemplazo

    Returns:
        Contenido con las IPs reemplazadas
    """
    return content.replace(old_ip, new_ip)


def get_file_info(file_path: Path) -> dict:
    """
    Obtiene información detallada de un archivo.

    Args:
        file_path: Ruta al archivo

    Returns:
        Diccionario con información del archivo
    """
    if not file_path.exists():
        return {
            "current_file": file_path,
            "exists": False,
        }

    stat = file_path.stat()

    # Contar líneas
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = sum(1 for _ in f)
    except Exception:
        lines = 0

    return {
        "current_file": file_path,
        "exists": True,
        "size_bytes": stat.st_size,
        "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "hash": calculate_file_hash(file_path),
        "lines": lines,
    }


def setup_logging(
    level: int = logging.INFO,
    log_file: str | None = None,
) -> logging.Logger:
    """
    Configura el sistema de logging.

    Args:
        level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Ruta opcional al archivo de log

    Returns:
        Logger configurado
    """
    # Crear logger
    logger = logging.getLogger("iptvListWatcher")
    logger.setLevel(level)

    # Evitar propagación al logger raíz
    logger.propagate = False

    # Limpiar handlers existentes para evitar duplicados
    if logger.handlers:
        logger.handlers.clear()

    # Formato de log
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler para archivo si se especifica
    if log_file:
        try:
            # Crear directorio de logs si no existe
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            # Si falla el archivo, usar consola como fallback
            console_handler = logging.StreamHandler()
            console_handler.setLevel(level)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
            logger.warning("No se pudo configurar archivo de log %s: %s", log_file, e)
    else:
        # Si no hay archivo de log, usar solo consola
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


def format_size(size_bytes: int) -> str:
    """
    Formatea un tamaño en bytes a una representación legible.

    Args:
        size_bytes: Tamaño en bytes

    Returns:
        String formateado (ej: "1.5 MB")
    """
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def validate_m3u_content(content: str) -> bool:
    """
    Valida que el contenido sea un archivo M3U con canales.

    Args:
        content: Contenido a validar

    Returns:
        True si es válido (tiene cabecera y al menos 1 canal), False en caso contrario
    """
    lines = content.strip().split("\n")

    if not lines:
        return False

    first_line = lines[0].strip()
    if not first_line.startswith("#EXTM3U"):
        return False

    # Verificar que hay al menos un #EXTINF
    return any(line.strip().startswith("#EXTINF") for line in lines)
