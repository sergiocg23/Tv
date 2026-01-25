"""
Módulo de análisis avanzado de streams usando ffprobe/ffmpeg.
Proporciona funciones para analizar streams IPTV y extraer métricas detalladas.
"""

import json
import logging
import re
import subprocess
import time
from typing import Dict, Optional, Tuple


logger = logging.getLogger(__name__)


def is_ffprobe_available() -> bool:
    """
    Verifica si ffprobe está disponible en el sistema.
    
    Returns:
        True si ffprobe está instalado y accesible
    """
    try:
        result = subprocess.run(
            ['ffprobe', '-version'],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def is_ffmpeg_available() -> bool:
    """
    Verifica si ffmpeg está disponible en el sistema.
    
    Returns:
        True si ffmpeg está instalado y accesible
    """
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def analyze_with_ffprobe(
    stream_url: str,
    timeout: int = 15
) -> Optional[Dict]:
    """
    Analiza un stream usando ffprobe (rápido, solo metadatos).
    
    Args:
        stream_url: URL del stream a analizar
        timeout: Timeout en segundos
        
    Returns:
        Dict con métricas extraídas o None si falla
        {
            'resolution': '1920x1080',
            'fps': 25.0,
            'video_codec': 'h264',
            'audio_codec': 'aac',
            'bitrate': 5000000,  # en bps
            'duration': 0.0  # No aplicable para streams live
        }
    """
    try:
        # Comando ffprobe para obtener info de streams
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_streams',
            '-show_format',
            '-of', 'json',
            '-timeout', str(timeout * 1000000),  # Microsegundos
            stream_url
        ]
        
        logger.debug(f"Ejecutando ffprobe en {stream_url[:80]}...")
        
        start_time = time.time()
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout + 5,
            text=True
        )
        elapsed = time.time() - start_time
        
        if result.returncode != 0:
            logger.debug(f"ffprobe falló con código {result.returncode} para {stream_url[:80]}...")
            return None
        
        # Parsear JSON output
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON de ffprobe: {e}")
            return None
        
        # Extraer streams de video y audio
        video_stream = None
        audio_stream = None
        
        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video' and not video_stream:
                video_stream = stream
            elif stream.get('codec_type') == 'audio' and not audio_stream:
                audio_stream = stream
        
        if not video_stream:
            logger.debug("No se encontró stream de video")
            return None
        
        # Extraer métricas
        metrics = {}
        
        # Resolución
        width = video_stream.get('width', 0)
        height = video_stream.get('height', 0)
        if width and height:
            metrics['resolution'] = f"{width}x{height}"
        else:
            metrics['resolution'] = "0x0"
        
        # FPS
        fps_str = video_stream.get('r_frame_rate', '0/1')
        try:
            num, den = map(int, fps_str.split('/'))
            metrics['fps'] = num / den if den != 0 else 0.0
        except (ValueError, ZeroDivisionError):
            metrics['fps'] = 0.0
        
        # Codec de video
        metrics['video_codec'] = video_stream.get('codec_name', 'unknown')
        
        # Codec de audio
        if audio_stream:
            metrics['audio_codec'] = audio_stream.get('codec_name', 'unknown')
        else:
            metrics['audio_codec'] = 'none'
        
        # Bitrate (preferir del stream, si no del formato)
        bitrate = video_stream.get('bit_rate')
        if not bitrate:
            format_info = data.get('format', {})
            bitrate = format_info.get('bit_rate')
        
        if bitrate:
            try:
                metrics['bitrate'] = int(bitrate)  # en bps
            except (ValueError, TypeError):
                metrics['bitrate'] = 0
        else:
            metrics['bitrate'] = 0
        
        # Duración del análisis
        metrics['probe_duration'] = round(elapsed, 2)
        
        logger.debug(f"ffprobe completado: {metrics['resolution']} @ {metrics['fps']:.1f}fps, {metrics['video_codec']}")
        
        return metrics
        
    except subprocess.TimeoutExpired:
        logger.debug(f"ffprobe timeout después de {timeout}s")
        return None
    except Exception as e:
        logger.error(f"Error en analyze_with_ffprobe: {e}")
        return None


def analyze_with_ffmpeg(
    stream_url: str,
    duration: int = 10,
    timeout: int = 30
) -> Optional[Dict]:
    """
    Analiza un stream usando ffmpeg (más completo, descarga video).
    
    Args:
        stream_url: URL del stream a analizar
        duration: Segundos de video a analizar
        timeout: Timeout en segundos
        
    Returns:
        Dict con métricas extraídas o None si falla
        Similar a analyze_with_ffprobe pero con más detalles sobre errores
    """
    try:
        # Comando ffmpeg para analizar stream
        cmd = [
            'ffmpeg',
            '-i', stream_url,
            '-t', str(duration),
            '-f', 'null',
            '-'
        ]
        
        logger.debug(f"Ejecutando ffmpeg en {stream_url[:80]} ({duration}s)...")
        
        start_time = time.time()
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            text=True
        )
        elapsed = time.time() - start_time
        
        # ffmpeg escribe info en stderr
        output = result.stderr
        
        # Parsear output de ffmpeg
        metrics = _parse_ffmpeg_output(output)
        
        if not metrics:
            logger.debug("No se pudieron extraer métricas de ffmpeg")
            return None
        
        metrics['analysis_duration'] = round(elapsed, 2)
        
        logger.debug(f"ffmpeg completado: {metrics.get('resolution', 'N/A')} @ {metrics.get('fps', 0):.1f}fps")
        
        return metrics
        
    except subprocess.TimeoutExpired:
        logger.debug(f"ffmpeg timeout después de {timeout}s")
        return None
    except Exception as e:
        logger.error(f"Error en analyze_with_ffmpeg: {e}")
        return None


def _parse_ffmpeg_output(output: str) -> Optional[Dict]:
    """
    Parsea el output de ffmpeg para extraer métricas.
    
    Args:
        output: Texto stderr de ffmpeg
        
    Returns:
        Dict con métricas o None si no se puede parsear
    """
    metrics = {}
    
    try:
        # Buscar línea de Stream (Video)
        # Ejemplo: Stream #0:0: Video: h264 (High), yuv420p(tv, bt709), 1920x1080 [SAR 1:1 DAR 16:9], 25 fps
        video_match = re.search(
            r'Stream #\d+:\d+.*?Video:\s*(\w+).*?,\s*(\d+)x(\d+).*?,\s*([\d.]+)\s*fps',
            output,
            re.IGNORECASE
        )
        
        if video_match:
            metrics['video_codec'] = video_match.group(1).lower()
            metrics['resolution'] = f"{video_match.group(2)}x{video_match.group(3)}"
            metrics['fps'] = float(video_match.group(4))
        
        # Buscar línea de Stream (Audio)
        # Ejemplo: Stream #0:1: Audio: aac (LC), 48000 Hz, stereo, fltp
        audio_match = re.search(
            r'Stream #\d+:\d+.*?Audio:\s*(\w+)',
            output,
            re.IGNORECASE
        )
        
        if audio_match:
            metrics['audio_codec'] = audio_match.group(1).lower()
        else:
            metrics['audio_codec'] = 'none'
        
        # Buscar bitrate
        # Puede estar en diferentes lugares del output
        bitrate_match = re.search(
            r'bitrate:\s*([\d.]+)\s*kb/s',
            output,
            re.IGNORECASE
        )
        
        if bitrate_match:
            bitrate_kbps = float(bitrate_match.group(1))
            metrics['bitrate'] = int(bitrate_kbps * 1000)  # Convertir a bps
        else:
            metrics['bitrate'] = 0
        
        # Detectar errores de decodificación
        error_count = output.lower().count('error')
        metrics['decode_errors'] = error_count
        
        return metrics if metrics else None
        
    except Exception as e:
        logger.error(f"Error parseando output de ffmpeg: {e}")
        return None


def analyze_stream(
    stream_url: str,
    method: str = 'auto',
    duration: int = 10,
    timeout: int = 30
) -> Tuple[Optional[Dict], str]:
    """
    Analiza un stream usando el método especificado.
    
    Args:
        stream_url: URL del stream
        method: 'auto', 'ffprobe', 'ffmpeg', o 'basic'
        duration: Segundos a analizar (solo para ffmpeg)
        timeout: Timeout en segundos
        
    Returns:
        Tupla (métricas, método_usado)
        - métricas: Dict con las métricas extraídas o None si falla
        - método_usado: String indicando el método que funcionó
    """
    
    if method == 'auto':
        # Intentar ffprobe primero (más rápido)
        if is_ffprobe_available():
            metrics = analyze_with_ffprobe(stream_url, timeout=timeout)
            if metrics:
                return metrics, 'ffprobe'
        
        # Si ffprobe falla, intentar ffmpeg
        if is_ffmpeg_available():
            metrics = analyze_with_ffmpeg(stream_url, duration=duration, timeout=timeout)
            if metrics:
                return metrics, 'ffmpeg'
        
        # Si ambos fallan, retornar None
        return None, 'none'
    
    elif method == 'ffprobe':
        if not is_ffprobe_available():
            logger.error("ffprobe no está disponible en el sistema")
            return None, 'none'
        
        metrics = analyze_with_ffprobe(stream_url, timeout=timeout)
        return metrics, 'ffprobe' if metrics else 'none'
    
    elif method == 'ffmpeg':
        if not is_ffmpeg_available():
            logger.error("ffmpeg no está disponible en el sistema")
            return None, 'none'
        
        metrics = analyze_with_ffmpeg(stream_url, duration=duration, timeout=timeout)
        return metrics, 'ffmpeg' if metrics else 'none'
    
    else:
        # Método 'basic' o desconocido
        return None, 'basic'
