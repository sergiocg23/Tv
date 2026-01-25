"""
Gestión del sistema de confianza de streams.
Maneja el JSON con información de confianza, calidad y estadísticas.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict


logger = logging.getLogger(__name__)


@dataclass
class StreamQuality:
    """Métricas de calidad de un stream."""
    resolution: Optional[str] = None
    fps: Optional[float] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    bitrate: Optional[int] = None
    quality_score: Optional[float] = None


@dataclass
class StreamMetadata:
    """Metadata del canal/stream."""
    group: str
    name: str
    tvg_id: Optional[str] = None
    tvg_logo: Optional[str] = None


@dataclass
class StreamInfo:
    """Información completa de un stream."""
    confidence: float
    last_validation: str
    last_success: Optional[str]
    last_failure: Optional[str]
    consecutive_successes: int
    consecutive_failures: int
    total_validations: int
    success_rate: float
    metadata: StreamMetadata
    quality: StreamQuality
    tier: str  # premium, good, suspect, fail
    
    def to_dict(self) -> Dict:
        """Convierte a diccionario para JSON."""
        return {
            'confidence': self.confidence,
            'last_validation': self.last_validation,
            'last_success': self.last_success,
            'last_failure': self.last_failure,
            'consecutive_successes': self.consecutive_successes,
            'consecutive_failures': self.consecutive_failures,
            'total_validations': self.total_validations,
            'success_rate': self.success_rate,
            'metadata': asdict(self.metadata),
            'quality': asdict(self.quality),
            'tier': self.tier
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'StreamInfo':
        """Crea instancia desde diccionario."""
        return cls(
            confidence=data['confidence'],
            last_validation=data['last_validation'],
            last_success=data.get('last_success'),
            last_failure=data.get('last_failure'),
            consecutive_successes=data['consecutive_successes'],
            consecutive_failures=data['consecutive_failures'],
            total_validations=data['total_validations'],
            success_rate=data['success_rate'],
            metadata=StreamMetadata(**data['metadata']),
            quality=StreamQuality(**data['quality']),
            tier=data['tier']
        )


class StreamConfidenceManager:
    """Gestor del sistema de confianza de streams."""
    
    # Configuración de confianza
    INITIAL_CONFIDENCE = 60.0
    SUCCESS_INCREMENT = 8.0
    FAILURE_DECREMENT = 15.0
    MIN_CONFIDENCE = 0.0
    MAX_CONFIDENCE = 100.0
    
    # Umbrales de tier
    PREMIUM_THRESHOLD = 70.0
    GOOD_THRESHOLD = 50.0
    SUSPECT_THRESHOLD = 30.0
    
    def __init__(self, confidence_file: Path):
        """
        Inicializa el gestor de confianza.
        
        Args:
            confidence_file: Ruta al archivo JSON de confianza
        """
        self.confidence_file = confidence_file
        self.streams: Dict[str, StreamInfo] = {}
        self.load()
    
    def load(self) -> None:
        """Carga el archivo de confianza desde disco."""
        if not self.confidence_file.exists():
            logger.info(f"Archivo de confianza no existe, creando nuevo: {self.confidence_file}")
            self.streams = {}
            return
        
        try:
            with open(self.confidence_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.streams = {
                url: StreamInfo.from_dict(info)
                for url, info in data.get('streams', {}).items()
            }
            
            logger.info(f"Cargados {len(self.streams)} streams desde archivo de confianza")
        
        except Exception as e:
            logger.error(f"Error cargando archivo de confianza: {e}")
            self.streams = {}
    
    def save(self) -> None:
        """Guarda el archivo de confianza a disco."""
        try:
            # Crear directorio si no existe
            self.confidence_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'last_update': datetime.now().isoformat(),
                'streams': {
                    url: info.to_dict()
                    for url, info in self.streams.items()
                }
            }
            
            with open(self.confidence_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Guardados {len(self.streams)} streams en archivo de confianza")
        
        except Exception as e:
            logger.error(f"Error guardando archivo de confianza: {e}")
    
    def get_stream(self, url: str) -> Optional[StreamInfo]:
        """Obtiene información de un stream."""
        return self.streams.get(url)
    
    def update_stream(
        self,
        url: str,
        success: bool,
        metadata: StreamMetadata,
        quality: Optional[StreamQuality] = None
    ) -> StreamInfo:
        """
        Actualiza la información de un stream después de validación.
        
        Args:
            url: URL del stream
            success: Si la validación fue exitosa
            metadata: Metadata del canal
            quality: Métricas de calidad (opcional)
            
        Returns:
            StreamInfo actualizado
        """
        now = datetime.now().isoformat()
        
        # Obtener o crear stream info
        if url in self.streams:
            info = self.streams[url]
        else:
            info = StreamInfo(
                confidence=self.INITIAL_CONFIDENCE,
                last_validation=now,
                last_success=None,
                last_failure=None,
                consecutive_successes=0,
                consecutive_failures=0,
                total_validations=0,
                success_rate=0.0,
                metadata=metadata,
                quality=quality or StreamQuality(),
                tier='good'
            )
        
        # Actualizar metadata (puede haber cambiado)
        info.metadata = metadata
        
        # Actualizar calidad si está disponible
        if quality:
            info.quality = quality
        
        # Actualizar estadísticas
        info.last_validation = now
        info.total_validations += 1
        
        if success:
            # Éxito: incrementar confianza
            info.confidence = min(
                info.confidence + self.SUCCESS_INCREMENT,
                self.MAX_CONFIDENCE
            )
            info.last_success = now
            info.consecutive_successes += 1
            info.consecutive_failures = 0
        else:
            # Fallo: decrementar confianza
            info.confidence = max(
                info.confidence - self.FAILURE_DECREMENT,
                self.MIN_CONFIDENCE
            )
            info.last_failure = now
            info.consecutive_failures += 1
            info.consecutive_successes = 0
        
        # Calcular success rate
        if info.total_validations > 0:
            # Aproximar basándonos en la confianza actual
            # (no guardamos historial completo)
            info.success_rate = info.confidence / 100.0
        
        # Determinar tier
        info.tier = self._get_tier(info.confidence)
        
        # Guardar en diccionario
        self.streams[url] = info
        
        return info
    
    def _get_tier(self, confidence: float) -> str:
        """Determina el tier basándose en la confianza."""
        if confidence >= self.PREMIUM_THRESHOLD:
            return 'premium'
        elif confidence >= self.GOOD_THRESHOLD:
            return 'good'
        elif confidence >= self.SUSPECT_THRESHOLD:
            return 'suspect'
        else:
            return 'fail'
    
    def get_streams_by_tier(self, tier: str) -> List[tuple[str, StreamInfo]]:
        """
        Obtiene streams filtrados por tier.
        
        NOTE: Método no usado actualmente pero disponible para uso futuro.
        Útil para exportar streams de un tier específico o análisis detallados.
        
        Args:
            tier: Tier a filtrar (premium, good, suspect, fail)
            
        Returns:
            Lista de tuplas (url, StreamInfo)
        """
        return [
            (url, info)
            for url, info in self.streams.items()
            if info.tier == tier
        ]
    
    def get_all_streams_sorted(self) -> List[tuple[str, StreamInfo]]:
        """
        Obtiene todos los streams ordenados por grupo, confianza y calidad.
        
        Returns:
            Lista de tuplas (url, StreamInfo) ordenadas
        """
        def sort_key(item):
            _, info = item
            # Ordenar por: grupo, confianza (desc), resolución (desc), bitrate (desc)
            resolution_priority = 0
            if info.quality.resolution:
                try:
                    height = int(info.quality.resolution.split('x')[1])
                    resolution_priority = height
                except (ValueError, IndexError):
                    resolution_priority = 0
            
            bitrate_priority = info.quality.bitrate or 0
            
            return (
                info.metadata.group,
                -info.confidence,  # Negativo para orden descendente
                -resolution_priority,
                -bitrate_priority
            )
        
        return sorted(self.streams.items(), key=sort_key)
    
    def get_statistics(self) -> Dict:
        """Obtiene estadísticas generales."""
        if not self.streams:
            return {
                'total_streams': 0,
                'by_tier': {},
                'avg_confidence': 0.0
            }
        
        by_tier = {
            'premium': 0,
            'good': 0,
            'suspect': 0,
            'fail': 0
        }
        
        total_confidence = 0.0
        
        for info in self.streams.values():
            by_tier[info.tier] += 1
            total_confidence += info.confidence
        
        return {
            'total_streams': len(self.streams),
            'by_tier': by_tier,
            'avg_confidence': total_confidence / len(self.streams) if self.streams else 0.0
        }
