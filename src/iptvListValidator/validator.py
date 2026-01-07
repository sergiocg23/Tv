"""
Lógica principal del validador de listas IPTV
"""

import logging
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import concurrent.futures

import requests

from iptvListValidator.config import Config
from iptvListValidator.utils import (
    M3UChannel,
    ValidationResult,
    parse_m3u_file,
    generate_m3u_content,
    calculate_file_hash,
    format_duration
)


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
    
    def validate_and_generate(
        self,
        force: bool = False,
        create_backup: bool = True,
        max_links: Optional[int] = None
    ) -> Dict:
        """
        Valida todos los enlaces de la lista IPTV y genera archivos de salida.
        
        Args:
            force: Si es True, procesa aunque no haya cambios en el archivo de entrada
            create_backup: Si es True, crea backup de los archivos anteriores
            max_links: Número máximo de enlaces a validar (None = todos, útil para pruebas)
            
        Returns:
            Diccionario con el resultado:
            {
                'success': bool,
                'input_changed': bool,
                'channels_total': int,
                'channels_with_valid_links': int,
                'channels_all_failed': int,
                'links_total': int,
                'links_valid': int,
                'links_failed': int,
                'valid_file': Path,
                'fail_file': Path,
                'backup_valid': Path (opcional),
                'backup_fail': Path (opcional),
                'duration': float,
                'error': str (opcional)
            }
        """
        start_time = time.time()
        
        try:
            # Verificar si hubo cambios en el archivo de entrada
            input_path = self.config.get_input_path()
            input_hash = calculate_file_hash(input_path)
            
            # Verificar si necesitamos procesar
            last_hash_file = self.config.output_dir / '.last_input_hash'
            should_process = force
            
            if not should_process and last_hash_file.exists():
                try:
                    with open(last_hash_file, 'r') as f:
                        last_hash = f.read().strip()
                    should_process = (input_hash != last_hash)
                except Exception:
                    should_process = True
            else:
                should_process = True
            
            if not should_process:
                self.logger.info("No hay cambios en el archivo de entrada")
                return {
                    'success': True,
                    'input_changed': False,
                    'duration': time.time() - start_time
                }
            
            self.logger.info("=" * 70)
            self.logger.info("INICIANDO VALIDACIÓN DE ENLACES IPTV")
            self.logger.info("=" * 70)
            self.logger.info(f"Archivo de entrada: {input_path}")
            
            # Parsear archivo M3U
            self.logger.info("Parseando archivo M3U...")
            channels = parse_m3u_file(input_path)
            
            if not channels:
                raise ValueError(f"No se encontraron canales en {input_path}")
            
            self.logger.info(f"Encontrados {len(channels)} canales")
            
            # Contar enlaces totales
            total_links = sum(len(ch.links) for ch in channels)
            self.logger.info(f"Total de enlaces a validar: {total_links}")
            
            # Limitar enlaces si se especifica (para pruebas)
            if max_links and max_links > 0:
                self.logger.info(f"MODO PRUEBA: Limitando a los primeros {max_links} enlaces")
                # Truncar la lista de canales para procesar solo max_links enlaces
                links_count = 0
                truncated_channels = []
                for channel in channels:
                    if links_count >= max_links:
                        break
                    truncated_channels.append(channel)
                    links_count += len(channel.links)
                channels = truncated_channels
                self.logger.info(f"Validando {len(channels)} canales ({links_count} enlaces)")
            
            # Validar todos los enlaces
            self.logger.info("Iniciando validación de enlaces...")
            all_results = self._validate_all_links(channels)
            
            # Separar resultados válidos e inválidos
            valid_results = {link: result for link, result in all_results.items() if result.success}
            failed_results = {link: result for link, result in all_results.items() if not result.success}
            
            self.logger.info(f"Enlaces válidos: {len(valid_results)}")
            self.logger.info(f"Enlaces fallidos: {len(failed_results)}")
            
            # Log de primeros 5 errores para debugging
            if failed_results:
                self.logger.warning("Mostrando primeros 5 errores:")
                for i, (link, result) in enumerate(list(failed_results.items())[:5]):
                    self.logger.warning(f"  [{i+1}] {link[:80]}... → {result.error}")
            
            # Generar estadísticas por grupo
            self._log_group_statistics(channels, valid_results)
            
            # Crear backups si es necesario
            backup_valid_path = None
            backup_fail_path = None
            
            if create_backup:
                backup_valid_path = self._create_backup(self.config.get_valid_output_path())
                backup_fail_path = self._create_backup(self.config.get_fail_output_path())
            
            # Generar archivos de salida
            self.logger.info("Generando archivos de salida...")
            
            # Archivo de válidos
            valid_content = generate_m3u_content(channels, valid_results)
            valid_output_path = self.config.get_valid_output_path()
            self._save_content(valid_content, valid_output_path)
            self.logger.info(f"Archivo de válidos guardado: {valid_output_path}")
            
            # Archivo de fallidos
            fail_content = generate_m3u_content(channels, failed_results)
            fail_output_path = self.config.get_fail_output_path()
            self._save_content(fail_content, fail_output_path)
            self.logger.info(f"Archivo de fallidos guardado: {fail_output_path}")
            
            # Guardar hash del archivo de entrada
            with open(last_hash_file, 'w') as f:
                f.write(input_hash)
            
            # Estadísticas finales
            channels_with_valid = sum(
                1 for ch in channels
                if any(link in valid_results for link in ch.links)
            )
            channels_all_failed = len(channels) - channels_with_valid
            
            duration = time.time() - start_time
            
            self.logger.info("=" * 70)
            self.logger.info("VALIDACIÓN COMPLETADA")
            self.logger.info("=" * 70)
            self.logger.info(f"Canales totales: {len(channels)}")
            self.logger.info(f"Canales con enlaces válidos: {channels_with_valid}")
            self.logger.info(f"Canales sin enlaces válidos: {channels_all_failed}")
            self.logger.info(f"Enlaces válidos: {len(valid_results)}/{total_links}")
            self.logger.info(f"Enlaces fallidos: {len(failed_results)}/{total_links}")
            self.logger.info(f"Duración total: {format_duration(duration)}")
            self.logger.info("=" * 70)
            
            return {
                'success': True,
                'input_changed': True,
                'channels_total': len(channels),
                'channels_with_valid_links': channels_with_valid,
                'channels_all_failed': channels_all_failed,
                'links_total': total_links,
                'links_valid': len(valid_results),
                'links_failed': len(failed_results),
                'valid_file': valid_output_path,
                'fail_file': fail_output_path,
                'backup_valid': backup_valid_path,
                'backup_fail': backup_fail_path,
                'duration': duration
            }
            
        except Exception as e:
            self.logger.exception(f"Error en validate_and_generate: {e}")
            return {
                'success': False,
                'input_changed': False,
                'error': str(e),
                'duration': time.time() - start_time
            }
    
    def _validate_all_links(self, channels: List[M3UChannel]) -> Dict[str, ValidationResult]:
        """
        Valida todos los enlaces de todos los canales en paralelo.
        
        Args:
            channels: Lista de canales con sus enlaces
            
        Returns:
            Diccionario {link: ValidationResult}
        """
        # Recopilar todos los enlaces únicos
        all_links = set()
        for channel in channels:
            all_links.update(channel.links)
        
        all_links = list(all_links)
        results = {}
        
        # Validar en paralelo con ThreadPoolExecutor
        # Limitamos a 10 hilos para no saturar el servidor Acestream
        max_workers = 10
        
        self.logger.info(f"Validando {len(all_links)} enlaces únicos con {max_workers} hilos...")
        
        # Log info sobre reemplazo de IP si aplica
        if 'HOST_IP' in os.environ:
            host_ip = os.environ['HOST_IP']
            self.logger.info(f"Reemplazando {host_ip}:6878 por acestream:6878 para validación")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Enviar todas las tareas
            future_to_link = {
                executor.submit(self._validate_link, link): link
                for link in all_links
            }
            
            # Procesar resultados a medida que se completan
            completed = 0
            for future in concurrent.futures.as_completed(future_to_link):
                link = future_to_link[future]
                try:
                    result = future.result()
                    results[link] = result
                    
                    completed += 1
                    if completed % 10 == 0 or completed == len(all_links):
                        self.logger.info(
                            f"Progreso: {completed}/{len(all_links)} enlaces validados "
                            f"({(completed/len(all_links)*100):.1f}%)"
                        )
                    
                except Exception as e:
                    self.logger.error(f"Error validando {link}: {e}")
                    results[link] = ValidationResult(
                        link=link,
                        success=False,
                        error=f"Excepción durante validación: {str(e)}"
                    )
        
        return results
    
    def _validate_link(self, link: str) -> ValidationResult:
        """
        Valida un enlace individual de Acestream.
        
        Args:
            link: URL del enlace a validar
            
        Returns:
            ValidationResult con los resultados de la validación
        """
        # Reemplazar IP del host por nombre del contenedor acestream
        # cuando se ejecuta dentro de Docker
        validation_link = link
        if 'HOST_IP' in os.environ:
            host_ip = os.environ['HOST_IP']
            validation_link = link.replace(f"{host_ip}:6878", "acestream:6878")
        
        try:
            # Headers para que Acestream acepte la conexión
            headers = {
                'User-Agent': 'VLC/3.0.16 LibVLC/3.0.16',
                'Accept': '*/*',
                'Connection': 'keep-alive'
            }
            
            # Medición de latencia (tiempo de primera respuesta)
            start_time = time.time()
            
            # Timeout en tupla: (connect_timeout, read_timeout)
            # Acestream puede tardar en iniciar el stream
            timeout = (self.config.timeout_connect, self.config.timeout_stream)
            
            response = requests.get(
                validation_link,
                headers=headers,
                timeout=timeout,
                stream=True,
                allow_redirects=True
            )
            
            # Verificar código de respuesta
            if response.status_code != 200:
                response.close()
                return ValidationResult(
                    link=link,
                    success=False,
                    error=f"HTTP {response.status_code}"
                )
            
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
                    
                    # Verificar si ya pasó el tiempo de prueba
                    elapsed = time.time() - chunk_start_time
                    if elapsed >= self.config.stability_test_duration:
                        break
                
                # Si no descargamos nada, el stream no funciona
                if bytes_downloaded == 0:
                    stable = False
                    self.logger.debug(f"Stream vacío para {link}")
                else:
                    # Calcular bitrate
                    test_duration = time.time() - chunk_start_time
                    bitrate = bytes_downloaded / test_duration if test_duration > 0 else 0
                    
                    # Verificar si el bitrate es suficiente
                    if bitrate < self.config.min_bitrate:
                        stable = False
                        self.logger.debug(f"Bitrate bajo para {link}: {bitrate:.0f} B/s")
                
            except Exception as e:
                # Si falla durante la descarga, no es estable
                stable = False
                self.logger.debug(f"Inestabilidad en {link}: {e}")
            
            finally:
                response.close()
            
            return ValidationResult(
                link=link,
                success=True,
                latency=latency,
                bitrate=bitrate,
                stable=stable
            )
            
        except requests.Timeout as e:
            return ValidationResult(
                link=link,
                success=False,
                error=f"Timeout: {str(e)}"
            )
        except requests.ConnectionError as e:
            return ValidationResult(
                link=link,
                success=False,
                error=f"Error de conexión: {str(e)}"
            )
        except Exception as e:
            return ValidationResult(
                link=link,
                success=False,
                error=f"Error: {str(e)}"
            )
    
    def _log_group_statistics(
        self,
        channels: List[M3UChannel],
        valid_results: Dict[str, ValidationResult]
    ) -> None:
        """
        Registra estadísticas de validación por grupo.
        
        Args:
            channels: Lista de canales
            valid_results: Diccionario de resultados válidos
        """
        # Agrupar por group-title
        groups = {}
        for channel in channels:
            group = channel.group or "Sin grupo"
            if group not in groups:
                groups[group] = {'total': 0, 'valid': 0, 'failed': 0}
            
            for link in channel.links:
                groups[group]['total'] += 1
                if link in valid_results:
                    groups[group]['valid'] += 1
                else:
                    groups[group]['failed'] += 1
        
        # Log por grupo
        self.logger.info("Estadísticas por grupo:")
        for group, stats in sorted(groups.items()):
            valid_pct = (stats['valid'] / stats['total'] * 100) if stats['total'] > 0 else 0
            self.logger.info(
                f"  {group}: {stats['valid']}/{stats['total']} válidos ({valid_pct:.1f}%), "
                f"{stats['failed']} fallidos"
            )
    
    def _create_backup(self, file_path: Path) -> Optional[Path]:
        """
        Crea un backup de un archivo con timestamp.
        
        Args:
            file_path: Ruta al archivo a respaldar
            
        Returns:
            Ruta del backup creado, o None si no existía el archivo
        """
        if not file_path.exists():
            return None
        
        # Generar nombre del backup con timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
        backup_path = self.config.olds_dir / backup_name
        
        # Copiar archivo
        shutil.copy2(file_path, backup_path)
        
        return backup_path
    
    def _save_content(self, content: str, output_path: Path) -> None:
        """
        Guarda contenido en un archivo.
        
        Args:
            content: Contenido a guardar
            output_path: Ruta del archivo de salida
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def clean_old_backups(self, keep: int = 5, dry_run: bool = False) -> Dict:
        """
        Limpia backups antiguos manteniendo solo los más recientes de cada tipo.
        
        Args:
            keep: Número de backups a mantener de cada tipo
            dry_run: Si es True, solo simula sin borrar
            
        Returns:
            Diccionario con el resultado
        """
        try:
            if not self.config.olds_dir.exists():
                return {
                    'success': True,
                    'deleted': 0,
                    'kept': 0,
                    'message': 'No hay directorio de backups'
                }
            
            # Obtener backups de válidos e inválidos por separado
            valid_pattern = f"{self.config.get_valid_output_path().stem}_*"
            fail_pattern = f"{self.config.get_fail_output_path().stem}_*"
            
            deleted_count = 0
            kept_count = 0
            
            for pattern in [valid_pattern, fail_pattern]:
                backups = sorted(
                    self.config.olds_dir.glob(pattern),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True
                )
                
                # Mantener los N más recientes, eliminar el resto
                for i, backup in enumerate(backups):
                    if i < keep:
                        kept_count += 1
                        self.logger.info(f"Manteniendo: {backup.name}")
                    else:
                        if dry_run:
                            self.logger.info(f"[DRY-RUN] Eliminaría: {backup.name}")
                        else:
                            backup.unlink()
                            self.logger.info(f"Eliminado: {backup.name}")
                        deleted_count += 1
            
            return {
                'success': True,
                'deleted': deleted_count,
                'kept': kept_count,
                'dry_run': dry_run
            }
            
        except Exception as e:
            self.logger.exception(f"Error en clean_old_backups: {e}")
            return {
                'success': False,
                'error': str(e)
            }
