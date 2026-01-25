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
        tvg_logo: str = "",
        tvg_id: str = "",
        extinf_line: str = ""
    ):
        """
        Inicializa un canal M3U.
        
        Args:
            name: Nombre del canal
            group: Grupo al que pertenece (group-title)
            tvg_logo: URL del logo (tvg-logo)
            tvg_id: ID del canal (tvg-id)
            extinf_line: Línea EXTINF completa original
        """
        self.name = name
        self.group = group
        self.tvg_logo = tvg_logo
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
        error: str = "",
        # Nuevas métricas de video
        resolution: str = "",
        fps: float = 0.0,
        video_codec: str = "",
        audio_codec: str = "",
        # Metadata adicional
        analysis_method: str = "basic"  # basic, ffprobe, ffmpeg
    ):
        """
        Inicializa un resultado de validación.
        
        Args:
            link: URL del enlace validado
            success: Si la validación fue exitosa
            latency: Latencia en segundos
            bitrate: Bitrate en bytes/segundo (o kbps si es de ffmpeg)
            stable: Si el stream es estable
            error: Mensaje de error si falló
            resolution: Resolución del video (ej: "1920x1080")
            fps: Frames por segundo
            video_codec: Codec de video (ej: "h264", "hevc")
            audio_codec: Codec de audio (ej: "aac", "ac3")
            analysis_method: Método usado para el análisis
        """
        self.link = link
        self.success = success
        self.latency = latency
        self.bitrate = bitrate
        self.stable = stable
        self.error = error
        
        # Nuevas métricas
        self.resolution = resolution
        self.fps = fps
        self.video_codec = video_codec
        self.audio_codec = audio_codec
        self.analysis_method = analysis_method
    
    def get_quality_score(self) -> float:
        """
        Calcula un score de calidad para ordenar.
        Mayor score = mejor calidad.
        
        Usa un sistema de 5 factores si hay datos de ffmpeg,
        o 3 factores para el método básico.
        
        Returns:
            Score de calidad (0.0 - 100.0)
        """
        if not self.success:
            return 0.0
        
        # Si tenemos análisis de video (ffprobe/ffmpeg), usar score de 5 factores
        if self.analysis_method in ['ffprobe', 'ffmpeg'] and self.resolution:
            return self._calculate_advanced_score()
        else:
            return self._calculate_basic_score()
    
    def _calculate_basic_score(self) -> float:
        """Score básico (3 factores): estabilidad, latencia, bitrate"""
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
    
    def _calculate_advanced_score(self) -> float:
        """
        Score avanzado (5 factores) similar a StreamFlow:
        - Bitrate: 40%
        - Resolución: 35%
        - FPS: 15%
        - Codec: 10%
        Total: 100 puntos
        """
        score = 0.0
        
        # 1. Bitrate (40 puntos)
        # Convertir a kbps si está en bytes/s
        if self.bitrate > 100000:  # Probablemente está en bytes/s
            bitrate_kbps = (self.bitrate * 8) / 1000
        else:
            bitrate_kbps = self.bitrate
        
        # Normalizar a 8000 kbps (típico Full HD)
        bitrate_normalized = min(bitrate_kbps / 8000, 1.0)
        score += bitrate_normalized * 40.0
        
        # 2. Resolución (35 puntos)
        resolution_score = self._get_resolution_score()
        score += resolution_score * 35.0
        
        # 3. FPS (15 puntos)
        if self.fps > 0:
            fps_normalized = min(self.fps / 60, 1.0)  # Normalizar a 60 FPS
            score += fps_normalized * 15.0
        
        # 4. Codec de video (10 puntos)
        codec_score = self._get_codec_score()
        score += codec_score * 10.0
        
        return round(score, 2)
    
    def _get_resolution_score(self) -> float:
        """Calcula score de resolución (0.0 - 1.0)"""
        if not self.resolution or 'x' not in self.resolution:
            return 0.3  # Score por defecto
        
        try:
            _, height = map(int, self.resolution.split('x'))
            
            if height >= 2160:      # 4K
                return 1.0
            elif height >= 1080:    # Full HD
                return 1.0
            elif height >= 720:     # HD
                return 0.7
            elif height >= 576:     # SD (PAL)
                return 0.5
            elif height >= 480:     # SD (NTSC)
                return 0.4
            else:
                return 0.3
        except (ValueError, AttributeError):
            return 0.3
    
    def _get_codec_score(self) -> float:
        """Calcula score de codec (0.0 - 1.0)"""
        if not self.video_codec:
            return 0.5  # Score neutro si no hay info
        
        codec_lower = self.video_codec.lower()
        
        # H.265/HEVC es el mejor (más eficiente)
        if 'h265' in codec_lower or 'hevc' in codec_lower:
            return 1.0
        
        # H.264/AVC es muy bueno
        elif 'h264' in codec_lower or 'avc' in codec_lower:
            return 0.8
        
        # Otros codecs (VP9, VP8, etc.)
        elif codec_lower not in ['n/a', 'unknown', '']:
            return 0.5
        
        else:
            return 0.3
    
    def __repr__(self) -> str:
        if self.success:
            if self.analysis_method in ['ffprobe', 'ffmpeg']:
                return (
                    f"ValidationResult(link='{self.link[:50]}...', "
                    f"resolution={self.resolution}, fps={self.fps:.1f}, "
                    f"codec={self.video_codec}, bitrate={self.bitrate:.0f}, "
                    f"score={self.get_quality_score():.1f}, method={self.analysis_method})"
                )
            else:
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
                name, group, tvg_logo, tvg_id = _parse_extinf_line(line)
                current_channel = M3UChannel(
                    name=name,
                    group=group,
                    tvg_logo=tvg_logo,
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
        Tupla (nombre, grupo, tvg_logo, tvg_id)
    """
    name = ""
    group = ""
    tvg_logo = ""
    tvg_id = ""
    
    # Extraer group-title
    group_match = re.search(r'group-title="([^"]*)"', line)
    if group_match:
        group = group_match.group(1)
    
    # Extraer tvg-logo
    logo_match = re.search(r'tvg-logo="([^"]*)"', line)
    if logo_match:
        tvg_logo = logo_match.group(1)
    
    # Extraer tvg-id
    tvg_id_match = re.search(r'tvg-id="([^"]*)"', line)
    if tvg_id_match:
        tvg_id = tvg_id_match.group(1)
    
    # Extraer nombre (después de la última coma)
    if ',' in line:
        name = line.split(',', 1)[-1].strip()
    
    return name, group, tvg_logo, tvg_id


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
