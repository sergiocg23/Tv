"""
Lógica principal del validador de listas IPTV
"""

import concurrent.futures
import logging
import os
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests

from iptvListValidator.config import Config
from iptvListValidator.confidence import (
    StreamConfidenceManager,
    StreamMetadata,
    StreamQuality,
)
from iptvListValidator.utils import (
    M3UChannel,
    ValidationResult,
    parse_m3u_file,
    generate_m3u_content,
    format_duration,
)
from iptvListValidator.stream_analyzer import analyze_stream


class IPTVValidator:
    """Clase principal para validar listas IPTV."""

    def __init__(self, config: Config, logger: Optional[logging.Logger] = None):
        """
        Inicializa el validador.

        Args:
            config: Configuración del validador
            logger: Logger opcional (se crea uno por defecto si no se proporciona)
        """
        self.config = config
        self.logger = logger or logging.getLogger(__name__)

        # Validar configuración
        self.config.validate()

        # Asegurar que los directorios existen
        self.config.ensure_directories()
        
        # Inicializar gestor de confianza
        self.confidence_manager = StreamConfidenceManager(
            self.config.get_confidence_path()
        )

    def validate_single_url(self, url: str) -> Dict:
        """
        Valida una URL individual sin procesarla desde un archivo.

        Args:
            url: URL a validar

        Returns:
            Diccionario con el resultado:
            {
                'url': str,
                'success': bool,
                'latency': float (opcional),
                'bitrate': float (opcional),
                'stable': bool (opcional),
                'quality_score': float (opcional),
                'error': str (opcional),
                'duration': float
            }
        """
        start_time = time.time()

        try:
            self.logger.info("=" * 70)
            self.logger.info("VALIDANDO URL INDIVIDUAL")
            self.logger.info("=" * 70)
            self.logger.info(f"URL: {url}")

            result = self._validate_link(url)

            duration = time.time() - start_time

            response = {"url": url, "success": result.success, "duration": duration}

            if result.success:
                response.update(
                    {
                        "latency": result.latency,
                        "bitrate": result.bitrate,
                        "stable": result.stable,
                        "quality_score": result.get_quality_score(),
                        # Métricas avanzadas (pueden ser None)
                        "resolution": result.resolution,
                        "fps": result.fps,
                        "video_codec": result.video_codec,
                        "audio_codec": result.audio_codec,
                        "analysis_method": result.analysis_method,
                    }
                )
                self.logger.info(
                    f"✓ URL válida (latencia: {result.latency:.2f}s, bitrate: {result.bitrate:.0f} B/s)"
                )
            else:
                response["error"] = result.error
                self.logger.info(f"✗ URL inválida: {result.error}")

            self.logger.info("=" * 70)

            return response

        except Exception as e:
            self.logger.exception(f"Error validando URL: {e}")
            return {
                "url": url,
                "success": False,
                "error": str(e),
                "duration": time.time() - start_time,
            }

    def validate_by_tier(self, tier: Optional[str] = None) -> Dict:
        """
        Valida streams usando el sistema de confianza y genera archivos por tier.
        
        Args:
            tier: Tier específico a validar (None = todos)
            
        Returns:
            Diccionario con resultados y estadísticas
        """
        start_time = time.time()
        
        try:
            self.logger.info("=" * 70)
            self.logger.info("VALIDACIÓN CON SISTEMA DE CONFIANZA")
            self.logger.info("=" * 70)
            
            # Cargar archivo de entrada
            input_path = self.config.get_input_path()
            self.logger.info(f"Archivo de entrada: {input_path}")
            
            # Parsear M3U
            channels = parse_m3u_file(input_path)
            if not channels:
                raise ValueError(f"No se encontraron canales en {input_path}")
            
            self.logger.info(f"Encontrados {len(channels)} canales")
            
            # Guardar canales originales para generar archivos
            all_channels = channels
            
            # Filtrar por tier si se especifica
            if tier:
                self.logger.info(f"Filtrando streams del tier: {tier}")
                channels_to_validate = []
                for channel in channels:
                    filtered_links = []
                    for link in channel.links:
                        stream_info = self.confidence_manager.get_stream(link)
                        # Streams nuevos o del tier especificado
                        if (stream_info and stream_info.tier == tier) or (not stream_info and tier == 'good'):
                            filtered_links.append(link)
                    
                    if filtered_links:
                        new_channel = M3UChannel(
                            name=channel.name,
                            group=channel.group,
                            tvg_logo=channel.tvg_logo,
                            tvg_id=channel.tvg_id,
                            extinf_line=channel.extinf_line
                        )
                        new_channel.links = filtered_links
                        channels_to_validate.append(new_channel)
                
                channels = channels_to_validate
                self.logger.info(f"Validando {len(channels)} canales del tier {tier}")
            
            # Contar enlaces a validar
            links_to_validate = sum(len(ch.links) for ch in channels)
            
            # Validar enlaces
            validated_results = self._validate_all_links_with_confidence(channels)
            
            # Contar éxitos y fallos de esta validación
            success_count = sum(1 for result in validated_results.values() if result.success)
            fail_count = len(validated_results) - success_count
            
            # Actualizar archivo de confianza
            self.confidence_manager.save()
            
            # Generar archivos por tier (siempre con todos los canales originales)
            self._generate_tier_files(all_channels)
            
            # Estadísticas globales
            stats = self.confidence_manager.get_statistics()
            stats['validated_count'] = links_to_validate
            stats['success_count'] = success_count
            stats['fail_count'] = fail_count
            
            duration = time.time() - start_time
            
            self.logger.info("=" * 70)
            self.logger.info("VALIDACIÓN COMPLETADA")
            self.logger.info("=" * 70)
            if tier:
                self.logger.info(f"Tier validado: {tier}")
                self.logger.info(f"Enlaces validados: {links_to_validate}")
                self.logger.info(f"  Éxitos: {success_count}")
                self.logger.info(f"  Fallos: {fail_count}")
            self.logger.info(f"Total streams en sistema: {stats['total_streams']}")
            for tier_name, count in stats['by_tier'].items():
                self.logger.info(f"  - {tier_name.capitalize()}: {count}")
            self.logger.info(f"Confianza promedio: {stats['avg_confidence']:.1f}%")
            self.logger.info(f"Duración: {format_duration(duration)}")
            self.logger.info("=" * 70)
            
            return {
                'success': True,
                'statistics': stats,
                'duration': duration
            }
        
        except Exception as e:
            self.logger.exception(f"Error en validate_by_tier: {e}")
            return {
                'success': False,
                'error': str(e),
                'duration': time.time() - start_time
            }
    
    def _validate_all_links_with_confidence(
        self, channels: List[M3UChannel]
    ) -> Dict[str, ValidationResult]:
        """
        Valida enlaces y actualiza confianza en paralelo.
        
        Args:
            channels: Lista de canales
            
        Returns:
            Diccionario {link: ValidationResult}
        """
        # Recopilar enlaces únicos con su información de canal
        link_to_channel = {}
        for channel in channels:
            for link in channel.links:
                link_to_channel[link] = channel
        
        all_links = list(link_to_channel.keys())
        results = {}
        
        max_workers = 3
        self.logger.info(f"Validando {len(all_links)} enlaces con {max_workers} hilos...")
        
        # Determinar tier de cada enlace para usar configuración apropiada
        link_to_tier = {}
        for link in all_links:
            stream_info = self.confidence_manager.get_stream(link)
            link_to_tier[link] = stream_info.tier if stream_info else 'good'
        
        link_to_index = {link: idx + 1 for idx, link in enumerate(all_links)}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_link = {
                executor.submit(
                    self._validate_link,
                    link,
                    link_to_index[link],
                    len(all_links),
                    link_to_tier[link]
                ): link
                for link in all_links
            }
            
            completed = 0
            for future in concurrent.futures.as_completed(future_to_link):
                link = future_to_link[future]
                channel = link_to_channel[link]
                
                try:
                    result = future.result()
                    results[link] = result
                    
                except Exception as e:
                    self.logger.error(f"Error obteniendo resultado para {link}: {e}")
                    result = ValidationResult(
                        link=link,
                        success=False,
                        error=f"Excepción: {str(e)}"
                    )
                    results[link] = result
                
                # Actualizar confianza SIEMPRE (incluso si hubo error)
                try:
                    metadata = StreamMetadata(
                        group=channel.group,
                        name=channel.name,
                        tvg_id=channel.tvg_id,
                        tvg_logo=channel.tvg_logo
                    )
                    
                    quality = None
                    if result.success:
                        quality = StreamQuality(
                            resolution=result.resolution,
                            fps=result.fps,
                            video_codec=result.video_codec,
                            audio_codec=result.audio_codec,
                            bitrate=int(result.bitrate) if result.bitrate else None,
                            quality_score=result.get_quality_score()
                        )
                    
                    self.confidence_manager.update_stream(
                        link,
                        result.success,
                        metadata,
                        quality
                    )
                    
                except Exception as e:
                    self.logger.error(f"Error actualizando confianza para {link}: {e}")
                
                completed += 1
                if completed % 10 == 0 or completed == len(all_links):
                    self.logger.info(
                        f"Progreso: {completed}/{len(all_links)} ({(completed / len(all_links) * 100):.1f}%)"
                    )
        
        return results
    
    def _generate_tier_files(self, all_channels: List[M3UChannel]) -> None:
        """
        Genera archivos M3U por tier y Master.m3u
        
        Args:
            all_channels: Lista de todos los canales
        """
        self.logger.info("Generando archivos por tier...")
        
        # Agrupar streams por tier
        tier_channels = {
            'premium': [],
            'good': [],
            'suspect': [],
            'fail': []
        }
        
        # Obtener todos los streams ordenados
        sorted_streams = self.confidence_manager.get_all_streams_sorted()
        
        # Crear diccionario de links a stream_info
        link_to_info = dict(sorted_streams)
        
        # Para cada canal, separar sus links por tier
        for channel in all_channels:
            for link in channel.links:
                info = link_to_info.get(link)
                if info:
                    tier = info.tier
                    # Crear canal con un solo link
                    single_link_channel = M3UChannel(
                        name=channel.name,
                        group=channel.group,
                        tvg_logo=channel.tvg_logo,
                        tvg_id=channel.tvg_id,
                        extinf_line=channel.extinf_line
                    )
                    single_link_channel.links = [link]
                    tier_channels[tier].append(single_link_channel)
        
        # Generar archivo por cada tier
        for tier, channels in tier_channels.items():
            if channels:
                # Crear diccionario de resultados (todos válidos ya que están en el tier)
                valid_results = {}
                for ch in channels:
                    for link in ch.links:
                        valid_results[link] = ValidationResult(link=link, success=True)
                
                content = generate_m3u_content(channels, valid_results)
                output_path = self.config.get_tier_output_path(tier)
                self._save_content(content, output_path)
                self.logger.info(f"  - {tier.capitalize()}: {len(channels)} streams → {output_path}")
        
        # Generar Master.m3u (Premium + Good)
        master_channels = tier_channels['premium'] + tier_channels['good']
        if master_channels:
            valid_results = {}
            for ch in master_channels:
                for link in ch.links:
                    valid_results[link] = ValidationResult(link=link, success=True)
            
            content = generate_m3u_content(master_channels, valid_results)
            master_path = self.config.get_master_output_path()
            self._save_content(content, master_path)
            self.logger.info(f"  - Master: {len(master_channels)} streams → {master_path}")

    def _validate_link(
        self, link: str, link_index: int = 0, total_links: int = 0, tier: Optional[str] = None
    ) -> ValidationResult:
        """
        Valida un enlace individual de Acestream con análisis avanzado opcional.

        Dependiendo de la configuración, puede usar:
        - Método básico (HTTP streaming)
        - ffprobe (metadatos rápidos)
        - ffmpeg (análisis completo)
        - Híbrido (básico + ffmpeg)

        Args:
            link: URL del enlace a validar
            link_index: Índice del enlace (1-based)
            total_links: Total de enlaces a validar
            tier: Tier del stream (para usar configuración específica)

        Returns:
            ValidationResult con los resultados de la validación
        """
        # Log cuando el hilo comienza a procesar este enlace
        if link_index > 0 and total_links > 0:
            thread_id = threading.current_thread().name
            self.logger.info(
                f"[Hilo {thread_id}] Procesando enlace {link_index}/{total_links}"
            )

        # Pequeño delay para evitar saturar Acestream
        time.sleep(0.5)

        # Reemplazar IP del host por nombre del contenedor acestream
        validation_link = link
        if "HOST_IP" in os.environ:
            host_ip = os.environ["HOST_IP"]
            validation_link = link.replace(f"{host_ip}:6878", "acestream:6878")

        # Determinar configuración según tier
        if tier:
            tier_config = self.config.get_tier_config(tier)
            analysis_method = tier_config['analysis_method']
            hybrid_analysis = tier_config['hybrid_analysis']
        else:
            analysis_method = self.config.analysis_method
            hybrid_analysis = self.config.hybrid_analysis

        # Si es híbrido, primero hacer test básico de conectividad
        if hybrid_analysis and analysis_method != "basic":
            basic_result = self._validate_link_basic(
                validation_link, link, link_index, total_links, tier=tier
            )

            # Si falla el test básico, retornar directamente
            if not basic_result.success:
                return basic_result

            # Si pasa, hacer análisis avanzado
            return self._validate_link_advanced(
                validation_link,
                link,
                link_index,
                total_links,
                basic_latency=basic_result.latency,
                basic_bitrate=basic_result.bitrate,
                basic_stable=basic_result.stable,
                tier=tier,
            )

        # Si no es híbrido, usar el método configurado
        if analysis_method == "basic":
            return self._validate_link_basic(
                validation_link, link, link_index, total_links, tier=tier
            )
        else:
            return self._validate_link_advanced(
                validation_link, link, link_index, total_links, tier=tier
            )

    def _validate_link_basic(
        self,
        validation_link: str,
        original_link: str,
        link_index: int = 0,
        total_links: int = 0,
        tier: Optional[str] = None,
    ) -> ValidationResult:
        """
        Validación básica usando HTTP streaming (método original).

        Args:
            validation_link: URL con IP reemplazada para validación
            original_link: URL original del enlace
            link_index: Índice del enlace
            total_links: Total de enlaces
            tier: Tier del stream (para usar configuración específica)

        Returns:
            ValidationResult con métricas básicas
        """
        # Reintentos según tier o configuración general
        if tier:
            tier_config = self.config.get_tier_config(tier)
            max_retries = tier_config['max_retries']
            retry_delay = tier_config['retry_delay']
        else:
            max_retries = self.config.max_retries
            retry_delay = self.config.retry_delay
        
        for attempt in range(max_retries):
            try:
                # Headers para que Acestream acepte la conexión
                headers = {
                    "User-Agent": "VLC/3.0.16 LibVLC/3.0.16",
                    "Accept": "*/*",
                    "Connection": "keep-alive",
                }

                # Medición de latencia (tiempo de primera respuesta)
                start_time = time.time()

                # Timeout en tupla: (connect_timeout, read_timeout)
                timeout = (self.config.timeout_connect, self.config.timeout_stream)

                response = requests.get(
                    validation_link,
                    headers=headers,
                    timeout=timeout,
                    stream=True,
                    allow_redirects=True,
                )

                # Verificar código de respuesta
                if response.status_code != 200:
                    response.close()
                    
                    # Si es HTTP 500 y no es el último intento, reintentar
                    if response.status_code == 500 and attempt < max_retries - 1:
                        if link_index > 0:
                            thread_id = threading.current_thread().name
                            self.logger.info(
                                f"[Hilo {thread_id}] ⏳ Enlace {link_index}/{total_links}: "
                                f"HTTP 500, reintentando en {retry_delay}s (intento {attempt + 1}/{max_retries})..."
                            )
                        time.sleep(retry_delay)
                        continue  # Reintentar
                    
                    # Si no es HTTP 500 o es el último intento, fallar
                    if link_index > 0:
                        thread_id = threading.current_thread().name
                        if response.status_code == 500:
                            self.logger.warning(
                                f"[Hilo {thread_id}] ✗ Enlace {link_index}/{total_links} FALLÓ: "
                                f"HTTP 500 después de {max_retries} intentos"
                            )
                    
                    error_msg = f"HTTP {response.status_code}"
                    if response.status_code == 500:
                        error_msg += f" después de {max_retries} intentos"
                    
                    return ValidationResult(
                        link=original_link,
                        success=False,
                        error=error_msg,
                        analysis_method="basic",
                    )
                
                # Si llegamos aquí, el código es 200, salir del loop de reintentos
                break
                
            except requests.Timeout:
                # Si es timeout y no es el último intento, reintentar
                if attempt < max_retries - 1:
                    if link_index > 0:
                        thread_id = threading.current_thread().name
                        self.logger.info(
                            f"[Hilo {thread_id}] ⏳ Enlace {link_index}/{total_links}: "
                            f"Timeout, reintentando en {retry_delay}s (intento {attempt + 1}/{max_retries})..."
                        )
                    time.sleep(retry_delay)
                    continue  # Reintentar
                
                # Último intento falló
                if link_index > 0:
                    thread_id = threading.current_thread().name
                    self.logger.warning(
                        f"[Hilo {thread_id}] ✗ Enlace {link_index}/{total_links} FALLÓ: "
                        f"Timeout después de {max_retries} intentos"
                    )
                return ValidationResult(
                    link=original_link,
                    success=False,
                    error=f"Timeout después de {max_retries} intentos",
                    analysis_method="basic",
                )
        
        # Continuar con la validación normal (response está disponible)
        try:

            # Calcular latencia (tiempo hasta recibir headers)
            latency = time.time() - start_time

            # Test de estabilidad: descargar durante X segundos
            bytes_downloaded = 0
            stable = True
            bitrate = 0

            try:
                chunk_start_time = time.time()

                # Intentar descargar chunks durante el tiempo de prueba
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        bytes_downloaded += len(chunk)

                    elapsed = time.time() - chunk_start_time
                    if elapsed >= self.config.stability_test_duration:
                        break

                # Si no descargamos nada, el stream no funciona
                if bytes_downloaded == 0:
                    stable = False
                    self.logger.debug(f"Stream vacío para {original_link[:80]}")
                else:
                    # Calcular bitrate
                    test_duration = time.time() - chunk_start_time
                    bitrate = (
                        bytes_downloaded / test_duration if test_duration > 0 else 0
                    )

                    # Verificar si el bitrate es suficiente
                    if bitrate < self.config.min_bitrate:
                        stable = False
                        self.logger.debug(f"Bitrate bajo: {bitrate:.0f} B/s")

            except Exception as e:
                stable = False
                self.logger.debug(f"Inestabilidad: {e}")

            finally:
                response.close()

            result = ValidationResult(
                link=original_link,
                success=True,
                latency=latency,
                bitrate=bitrate,
                stable=stable,
                analysis_method="basic",
            )

            # Log del resultado
            if link_index > 0:
                thread_id = threading.current_thread().name
                self.logger.info(
                    f"[Hilo {thread_id}] ✓ Enlace {link_index}/{total_links} VÁLIDO "
                    f"(latencia: {latency:.2f}s, bitrate: {bitrate:.0f} B/s, estable: {stable})"
                )

            return result

        except requests.Timeout as e:
            if link_index > 0:
                thread_id = threading.current_thread().name
                self.logger.warning(
                    f"[Hilo {thread_id}] ✗ Enlace {link_index}/{total_links} FALLÓ: Timeout"
                )
            return ValidationResult(
                link=original_link,
                success=False,
                error=f"Timeout: {str(e)}",
                analysis_method="basic",
            )

        except requests.ConnectionError as e:
            if link_index > 0:
                thread_id = threading.current_thread().name
                error_msg = str(e)
                if "Connection refused" in error_msg:
                    self.logger.warning(
                        f"[Hilo {thread_id}] ✗ Enlace {link_index}/{total_links} FALLÓ: Conexión rechazada"
                    )
                else:
                    self.logger.warning(
                        f"[Hilo {thread_id}] ✗ Enlace {link_index}/{total_links} FALLÓ: {error_msg[:50]}"
                    )
            return ValidationResult(
                link=original_link,
                success=False,
                error=f"Error de conexión: {str(e)}",
                analysis_method="basic",
            )

        except Exception as e:
            if link_index > 0:
                thread_id = threading.current_thread().name
                self.logger.error(
                    f"[Hilo {thread_id}] ✗ Enlace {link_index}/{total_links} FALLÓ: {str(e)[:50]}"
                )
            return ValidationResult(
                link=original_link,
                success=False,
                error=f"Error inesperado: {str(e)}",
                analysis_method="basic",
            )

    def _validate_link_advanced(
        self,
        validation_link: str,
        original_link: str,
        link_index: int = 0,
        total_links: int = 0,
        basic_latency: float = 0.0,
        basic_bitrate: float = 0.0,
        basic_stable: bool = False,
        tier: Optional[str] = None,
    ) -> ValidationResult:
        """
        Validación avanzada usando ffprobe/ffmpeg.

        Args:
            validation_link: URL con IP reemplazada
            original_link: URL original
            link_index: Índice del enlace
            total_links: Total de enlaces
            basic_latency: Latencia del test básico (si es híbrido)
            basic_bitrate: Bitrate del test básico (si es híbrido)
            basic_stable: Estabilidad del test básico (si es híbrido)
            tier: Tier del stream (para usar configuración específica)

        Returns:
            ValidationResult con métricas avanzadas
        """
        try:
            # Determinar configuración según tier
            if tier:
                tier_config = self.config.get_tier_config(tier)
                analysis_method = tier_config['analysis_method']
                ffmpeg_duration = self.config.ffmpeg_analysis_duration
                ffmpeg_timeout = self.config.ffmpeg_timeout
            else:
                analysis_method = self.config.analysis_method
                ffmpeg_duration = self.config.ffmpeg_analysis_duration
                ffmpeg_timeout = self.config.ffmpeg_timeout
            
            # Analizar stream con ffprobe/ffmpeg
            metrics, method_used = analyze_stream(
                stream_url=validation_link,
                method=analysis_method,
                duration=ffmpeg_duration,
                timeout=ffmpeg_timeout,
            )

            if not metrics:
                # Si el análisis avanzado falló completamente, hacer fallback al método básico
                if link_index > 0:
                    thread_id = threading.current_thread().name
                    self.logger.warning(
                        f"[Hilo {thread_id}] ⚠ Enlace {link_index}/{total_links}: Análisis avanzado falló, usando método básico"
                    )
                
                # Fallback al método básico (pasando tier)
                return self._validate_link_basic(validation_link, original_link, link_index, total_links, tier)

            # Extraer métricas (pueden ser incompletas)
            resolution = metrics.get("resolution", "")
            fps = metrics.get("fps", 0.0)
            video_codec = metrics.get("video_codec", "")
            audio_codec = metrics.get("audio_codec", "")
            bitrate = metrics.get("bitrate", 0)

            # Si las métricas están vacías/incompletas pero el stream respondió,
            # aceptarlo como válido pero con baja puntuación
            # Solo hacer fallback si NO se pudo extraer NADA
            if not resolution and not video_codec and bitrate <= 0:
                # No se extrajo ninguna métrica útil, hacer fallback
                if link_index > 0:
                    thread_id = threading.current_thread().name
                    self.logger.warning(
                        f"[Hilo {thread_id}] ⚠ Enlace {link_index}/{total_links}: Sin métricas extraídas, usando método básico"
                    )
                return self._validate_link_basic(validation_link, original_link, link_index, total_links)

            # El stream es válido aunque tenga métricas incompletas
            # El sistema de scoring penalizará automáticamente los valores faltantes
            result = ValidationResult(
                link=original_link,
                success=True,
                latency=basic_latency,
                bitrate=bitrate if bitrate > 0 else basic_bitrate,  # Usar bitrate básico si no hay avanzado
                stable=basic_stable if basic_stable else (bitrate > 0),
                resolution=resolution if resolution and resolution != "0x0" else None,
                fps=fps if fps > 0 else None,
                video_codec=video_codec if video_codec else None,
                audio_codec=audio_codec if audio_codec else None,
                error="",
                analysis_method=method_used,
            )

            # Log del resultado
            if link_index > 0:
                thread_id = threading.current_thread().name
                metrics_str = []
                if resolution:
                    metrics_str.append(resolution)
                if fps > 0:
                    metrics_str.append(f"{fps:.1f}fps")
                if video_codec:
                    metrics_str.append(video_codec)
                if bitrate > 0:
                    metrics_str.append(f"{bitrate / 1000:.0f}kbps")
                
                metrics_info = ", ".join(metrics_str) if metrics_str else "métricas parciales"
                self.logger.info(
                    f"[Hilo {thread_id}] ✓ Enlace {link_index}/{total_links} VÁLIDO "
                    f"({metrics_info}) [método: {method_used}]"
                )

            return result

        except Exception as e:
            if link_index > 0:
                thread_id = threading.current_thread().name
                self.logger.error(
                    f"[Hilo {thread_id}] ✗ Enlace {link_index}/{total_links} FALLÓ: {str(e)[:50]}"
                )

            return ValidationResult(
                link=original_link,
                success=False,
                error=f"Error en análisis avanzado: {str(e)}",
                latency=basic_latency,
                bitrate=basic_bitrate,
                stable=basic_stable,
                analysis_method="error",
            )

    def _save_content(self, content: str, output_path: Path) -> None:
        """
        Guarda contenido en un archivo.

        Args:
            content: Contenido a guardar
            output_path: Ruta del archivo de salida
        """
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
