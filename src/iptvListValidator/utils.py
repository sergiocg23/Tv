"""
Utilidades comunes para el módulo iptvListValidator
"""

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
import re


# ============================================================================
# CLASES DE DATOS
# ============================================================================

class M3UChannel:
    """Representa un canal IPTV con sus enlaces."""
    
    def __init__(
        self,
        name: str,
        group: str = "",
        logo: str = "",
        tvg_id: str = "",
        extinf_line: str = ""
    ):
        """
        Inicializa un canal M3U.
        
        Args:
            name: Nombre del canal
            group: Grupo al que pertenece (group-title)
            logo: URL del logo (tvg-logo)
            tvg_id: ID del canal (tvg-id)
            extinf_line: Línea EXTINF completa original
        """
        self.name = name
        self.group = group
        self.logo = logo
        self.tvg_id = tvg_id
        self.extinf_line = extinf_line
        self.links: List[str] = []
    
    def add_link(self, link: str) -> None:
        """Añade un enlace al canal."""
        if link and link not in self.links:
            self.links.append(link)
    
    def __repr__(self) -> str:
        return f"M3UChannel(name='{self.name}', group='{self.group}', links={len(self.links)})"


class ValidationResult:
    """Resultado de validación de un enlace."""
    
    def __init__(
        self,
        link: str,
        success: bool,
        latency: float = 0.0,
        bitrate: float = 0.0,
        stable: bool = False,
        error: str = ""
    ):
        """
        Inicializa un resultado de validación.
        
        Args:
            link: URL del enlace validado
            success: Si la validación fue exitosa
            latency: Latencia en segundos
            bitrate: Bitrate en bytes/segundo
            stable: Si el stream es estable
            error: Mensaje de error si falló
        """
        self.link = link
        self.success = success
        self.latency = latency
        self.bitrate = bitrate
        self.stable = stable
        self.error = error
    
    def get_quality_score(self) -> float:
        """
        Calcula un score de calidad para ordenar.
        Mayor score = mejor calidad.
        
        Returns:
            Score de calidad (0.0 - 100.0)
        """
        if not self.success:
            return 0.0
        
        score = 0.0
        
        # Estabilidad es lo más importante (40 puntos)
        if self.stable:
            score += 40.0
        
        # Latencia baja es importante (30 puntos)
        # Convertimos latencia a score: 0s = 30pts, 5s = 15pts, 10s+ = 0pts
        latency_score = max(0, 30 - (self.latency * 3))
        score += latency_score
        
        # Bitrate alto es un plus (30 puntos)
        # Normalizamos: 500KB/s = 15pts, 1MB/s = 30pts
        bitrate_mb = self.bitrate / 1_000_000
        bitrate_score = min(30, bitrate_mb * 30)
        score += bitrate_score
        
        return score
    
    def __repr__(self) -> str:
        if self.success:
            return (
                f"ValidationResult(link='{self.link[:50]}...', "
                f"latency={self.latency:.2f}s, bitrate={self.bitrate/1000:.1f}KB/s, "
                f"stable={self.stable}, score={self.get_quality_score():.1f})"
            )
        else:
            return f"ValidationResult(link='{self.link[:50]}...', FAILED: {self.error})"


# ============================================================================
# FUNCIONES DE HASH
# ============================================================================

def calculate_file_hash(file_path: Path) -> str:
    """
    Calcula el hash SHA256 de un archivo.
    
    Args:
        file_path: Ruta al archivo
        
    Returns:
        Hash SHA256 en formato hexadecimal
    """
    sha256_hash = hashlib.sha256()
    
    with open(file_path, 'rb') as f:
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
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


# ============================================================================
# PARSER M3U
# ============================================================================

def parse_m3u_file(file_path: Path) -> List[M3UChannel]:
    """
    Parsea un archivo M3U y extrae los canales con sus enlaces.
    
    Args:
        file_path: Ruta al archivo M3U
        
    Returns:
        Lista de objetos M3UChannel
    """
    channels: List[M3UChannel] = []
    current_channel: M3UChannel | None = None
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            
            # Ignorar líneas vacías
            if not line:
                continue
            
            # Ignorar líneas de metadatos generales
            if line.startswith('#EXTM3U') or line.startswith('#EXTVLCOPT') or line.startswith('#EXTGRP'):
                continue
            
            # Línea EXTINF (información del canal)
            if line.startswith('#EXTINF:'):
                # Si hay un canal previo, guardarlo
                if current_channel and current_channel.links:
                    channels.append(current_channel)
                
                # Parsear información del canal
                name, group, logo, tvg_id = _parse_extinf_line(line)
                current_channel = M3UChannel(
                    name=name,
                    group=group,
                    logo=logo,
                    tvg_id=tvg_id,
                    extinf_line=line
                )
            
            # Línea con URL
            elif line.startswith('http://') or line.startswith('https://'):
                if current_channel:
                    current_channel.add_link(line)
        
        # Agregar el último canal si existe
        if current_channel and current_channel.links:
            channels.append(current_channel)
    
    return channels


def _parse_extinf_line(line: str) -> Tuple[str, str, str, str]:
    """
    Parsea una línea EXTINF extrayendo información del canal.
    
    Args:
        line: Línea EXTINF completa
        
    Returns:
        Tupla (nombre, grupo, logo, tvg_id)
    """
    name = ""
    group = ""
    logo = ""
    tvg_id = ""
    
    # Extraer group-title
    group_match = re.search(r'group-title="([^"]*)"', line)
    if group_match:
        group = group_match.group(1)
    
    # Extraer tvg-logo
    logo_match = re.search(r'tvg-logo="([^"]*)"', line)
    if logo_match:
        logo = logo_match.group(1)
    
    # Extraer tvg-id
    tvg_id_match = re.search(r'tvg-id="([^"]*)"', line)
    if tvg_id_match:
        tvg_id = tvg_id_match.group(1)
    
    # Extraer nombre (después de la última coma)
    if ',' in line:
        name = line.split(',', 1)[-1].strip()
    
    return name, group, logo, tvg_id


# ============================================================================
# GENERACIÓN DE M3U
# ============================================================================

def generate_m3u_content(
    channels: List[M3UChannel],
    valid_results: Dict[str, ValidationResult]
) -> str:
    """
    Genera el contenido de un archivo M3U a partir de canales y resultados.
    
    Args:
        channels: Lista de canales
        valid_results: Diccionario de resultados de validación {link: ValidationResult}
        
    Returns:
        Contenido del archivo M3U como string
    """
    lines = [
        '#EXTM3U url-tvg="https://raw.githubusercontent.com/davidmuma/EPG_dobleM/refs/heads/master/guiatv.xml,https://epgshare01.online/epgshare01/epg_ripper_NL1.xml.gz,https://raw.githubusercontent.com/davidmuma/EPG_dobleM/master/guiatv.xml" refresh="3600"',
        '#EXTVLCOPT:network-caching=1000',
        ''
    ]
    
    for channel in channels:
        # Obtener enlaces con sus resultados
        channel_links = []
        for link in channel.links:
            if link in valid_results:
                channel_links.append((link, valid_results[link]))
        
        # Si no hay enlaces válidos, saltar este canal
        if not channel_links:
            continue
        
        # Ordenar enlaces por calidad (mejor primero)
        channel_links.sort(key=lambda x: x[1].get_quality_score(), reverse=True)
        
        # Escribir canal
        lines.append(channel.extinf_line)
        
        # Escribir enlaces ordenados
        for link, result in channel_links:
            lines.append(link)
        
        lines.append('')  # Línea vacía entre canales
    
    return '\n'.join(lines)


# ============================================================================
# INFORMACIÓN DE ARCHIVOS
# ============================================================================

def get_file_info(file_path: Path) -> Dict:
    """
    Obtiene información detallada de un archivo.
    
    Args:
        file_path: Ruta al archivo
        
    Returns:
        Diccionario con información del archivo
    """
    if not file_path.exists():
        return {
            'file': str(file_path),
            'exists': False
        }
    
    stat = file_path.stat()
    
    # Contar líneas
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = sum(1 for _ in f)
    except Exception:
        lines = 0
    
    # Contar canales (líneas EXTINF)
    channels = 0
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            channels = sum(1 for line in f if line.strip().startswith('#EXTINF:'))
    except Exception:
        pass
    
    return {
        'file': str(file_path),
        'exists': True,
        'size_bytes': stat.st_size,
        'last_modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
        'hash': calculate_file_hash(file_path),
        'lines': lines,
        'channels': channels
    }


# ============================================================================
# LOGGING
# ============================================================================

def setup_logging(level: int = logging.INFO, log_file: str = None) -> logging.Logger:
    """
    Configura el sistema de logging.
    
    Args:
        level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Ruta opcional al archivo de log
        
    Returns:
        Logger configurado
    """
    # Crear logger
    logger = logging.getLogger('iptvListValidator')
    logger.setLevel(level)
    
    # Evitar propagación al logger raíz
    logger.propagate = False
    
    # Limpiar handlers existentes para evitar duplicados
    if logger.handlers:
        logger.handlers.clear()
    
    # Formato de log
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler para archivo si se especifica
    if log_file:
        try:
            # Crear directorio de logs si no existe
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            # Si falla el archivo, usar consola como fallback
            console_handler = logging.StreamHandler()
            console_handler.setLevel(level)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
            logger.warning(f"No se pudo configurar archivo de log {log_file}: {e}")
    else:
        # Si no hay archivo de log, usar solo consola
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    return logger


# ============================================================================
# FORMATEO
# ============================================================================

def format_bytes(bytes_val: float) -> str:
    """
    Formatea bytes a una representación legible.
    
    Args:
        bytes_val: Cantidad de bytes
        
    Returns:
        String formateado (ej: "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_val < 1024.0:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.1f} TB"


def format_duration(seconds: float) -> str:
    """
    Formatea segundos a una representación legible.
    
    Args:
        seconds: Cantidad de segundos
        
    Returns:
        String formateado (ej: "1m 30s")
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    
    minutes = int(seconds // 60)
    remaining_seconds = seconds % 60
    
    if minutes < 60:
        return f"{minutes}m {remaining_seconds:.0f}s"
    
    hours = int(minutes // 60)
    remaining_minutes = minutes % 60
    return f"{hours}h {remaining_minutes}m"
