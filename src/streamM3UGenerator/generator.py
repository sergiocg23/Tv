"""
Generador de M3U y gestor del stream
"""

import logging
import os
import subprocess
import signal
import time
from pathlib import Path
from typing import Optional, Dict, Any

from streamM3UGenerator.config import Config

# Constantes
STARTUP_WAIT_TIME = 2  # segundos
SHUTDOWN_WAIT_TIME = 1  # segundos
MAX_SHUTDOWN_WAIT = 5  # segundos

logger = logging.getLogger(__name__)


class StreamGenerator:
    """Generador y gestor del stream de video"""
    
    def __init__(self, video_path: Optional[Path] = None):
        """
        Inicializa el generador.
        
        Args:
            video_path: Ruta al video a reproducir (usa el por defecto si no se especifica)
        """
        self.video_path = video_path or Config.DEFAULT_VIDEO
        self.process: Optional[subprocess.Popen] = None
        self.pid_file = Config.PID_FILE
    
    def _get_ffmpeg_command(self) -> list[str]:
        """
        Construye el comando FFmpeg para el stream.
        
        Returns:
            Lista con el comando y argumentos
        """
        if Config.FFMPEG_PROTOCOL == "tcp":
            # TCP listen mode - más robusto
            listen_url = f"tcp://{Config.STREAM_HOST}:{Config.STREAM_PORT}?listen=1"
            cmd = [
                "ffmpeg",
                "-re",  # Velocidad real
                "-stream_loop", "-1",  # Bucle infinito
                "-i", str(self.video_path),
                "-c", "copy",  # Copy codec (sin recodificar)
                "-f", "mpegts",  # Formato MPEG-TS
                "-loglevel", Config.FFMPEG_LOGLEVEL,
                listen_url
            ]
        else:
            # HTTP mediante servidor simple
            # Usamos formato que puede ser servido por HTTP
            cmd = [
                "ffmpeg",
                "-re",
                "-stream_loop", "-1",
                "-i", str(self.video_path),
                "-c", "copy",
                "-f", "mpegts",
                "-loglevel", Config.FFMPEG_LOGLEVEL,
                "pipe:1"  # Output a stdout para el servidor HTTP
            ]
        
        return cmd
    
    def start(self, background: bool = True) -> bool:
        """
        Inicia el stream de FFmpeg.
        
        Args:
            background: Si True, ejecuta en background
            
        Returns:
            True si se inició correctamente
            
        Raises:
            FileNotFoundError: Si el video no existe
            RuntimeError: Si el stream no se puede iniciar
        """
        # Verificar si ya está corriendo
        if self.is_running():
            logger.info("El stream ya está corriendo")
            print("⚠️  El stream ya está corriendo")
            return True
        
        # Verificar que el video existe
        if not self.video_path.exists():
            error_msg = f"Video no encontrado: {self.video_path}"
            logger.error(error_msg)
            print(f"❌ Error: {error_msg}")
            return False
        
        try:
            cmd = self._get_ffmpeg_command()
            
            logger.info(f"Iniciando stream de: {self.video_path.name}")
            print(f"🎬 Iniciando stream de: {self.video_path.name}")
            print(f"📡 URL: {Config.get_stream_url()}")
            
            if background:
                return self._start_background(cmd)
            else:
                return self._start_foreground(cmd)
                
        except FileNotFoundError as e:
            error_msg = f"FFmpeg no encontrado: {e}"
            logger.error(error_msg)
            print(f"❌ Error: {error_msg}")
            return False
        except Exception as e:
            error_msg = f"Error inesperado al iniciar stream: {e}"
            logger.exception(error_msg)
            print(f"❌ {error_msg}")
            return False
    
    def _start_background(self, cmd: list[str]) -> bool:
        """
        Inicia el stream en background.
        
        Args:
            cmd: Comando FFmpeg a ejecutar
            
        Returns:
            True si se inició correctamente
        """
        try:
            # Iniciar en background
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                start_new_session=True  # Desacoplar del proceso padre (suficiente)
            )
            
            # Guardar PID de forma atómica
            self._write_pid_file(self.process.pid)
            
            # Dar tiempo a FFmpeg para iniciar
            time.sleep(STARTUP_WAIT_TIME)
            
            # Verificar que sigue corriendo
            if self.process.poll() is not None:
                error_msg = "FFmpeg se detuvo inmediatamente"
                stderr_output = self.process.stderr.read().decode() if self.process.stderr else ""
                logger.error(f"{error_msg}. stderr: {stderr_output}")
                print(f"❌ Error: {error_msg}")
                self._cleanup_pid_file()
                return False
            
            logger.info(f"Stream iniciado correctamente (PID: {self.process.pid})")
            print(f"✅ Stream iniciado (PID: {self.process.pid})")
            return True
            
        except Exception as e:
            logger.exception("Error al iniciar stream en background")
            self._cleanup_pid_file()
            raise
    
    def _start_foreground(self, cmd: list[str]) -> bool:
        """
        Inicia el stream en foreground.
        
        Args:
            cmd: Comando FFmpeg a ejecutar
            
        Returns:
            True si se ejecutó correctamente
        """
        try:
            logger.info("Iniciando stream en foreground")
            print("🔄 Stream corriendo... (Ctrl+C para detener)")
            result = subprocess.run(cmd, check=True)
            return result.returncode == 0
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg falló con código: {e.returncode}")
            return False
        except KeyboardInterrupt:
            logger.info("Stream interrumpido por usuario")
            print("\n⚠️  Stream detenido por usuario")
            return True
    
    def _write_pid_file(self, pid: int) -> None:
        """
        Escribe el PID de forma atómica.
        
        Args:
            pid: PID del proceso
        """
        try:
            # Escribir a archivo temporal primero
            temp_file = self.pid_file.with_suffix('.tmp')
            temp_file.write_text(str(pid))
            # Renombrar atómicamente
            temp_file.replace(self.pid_file)
        except Exception as e:
            logger.error(f"Error al escribir PID file: {e}")
            raise
    
    def _cleanup_pid_file(self) -> None:
        """Elimina el PID file si existe"""
        try:
            if self.pid_file.exists():
                self.pid_file.unlink()
        except Exception as e:
            logger.warning(f"Error al limpiar PID file: {e}")
    
    def stop(self) -> bool:
        """
        Detiene el stream de FFmpeg de forma limpia.
        
        Intenta primero SIGTERM para shutdown limpio, espera, y luego
        fuerza con SIGKILL si es necesario.
        
        Returns:
            True si se detuvo correctamente
        """
        if not self.pid_file.exists():
            logger.info("No hay stream corriendo (no se encontró PID file)")
            print("⚠️  No hay stream corriendo (no se encontró PID file)")
            return True
        
        try:
            pid = int(self.pid_file.read_text().strip())
            logger.info(f"Intentando detener proceso PID: {pid}")
            
            return self._terminate_process(pid)
                
        except ValueError as e:
            logger.error(f"PID file corrupto: {e}")
            print(f"❌ Error: PID file corrupto")
            self._cleanup_pid_file()
            return False
        except Exception as e:
            error_msg = f"Error inesperado al detener stream: {e}"
            logger.exception(error_msg)
            print(f"❌ {error_msg}")
            return False
    
    def _terminate_process(self, pid: int) -> bool:
        """
        Termina un proceso de forma limpia.
        
        Args:
            pid: PID del proceso a terminar
            
        Returns:
            True si se terminó correctamente
        """
        try:
            # Intentar terminar el proceso limpiamente
            os.kill(pid, signal.SIGTERM)
            logger.info(f"SIGTERM enviado a PID {pid}")
            
            # Esperar con timeout
            for _ in range(MAX_SHUTDOWN_WAIT):
                time.sleep(SHUTDOWN_WAIT_TIME)
                try:
                    os.kill(pid, 0)  # Verificar si sigue vivo
                except ProcessLookupError:
                    # Ya terminó
                    logger.info(f"Proceso {pid} terminado limpiamente")
                    self._cleanup_pid_file()
                    print("✅ Stream detenido correctamente")
                    return True
            
            # Si llegó aquí, sigue vivo - forzar
            logger.warning(f"Proceso {pid} no terminó, enviando SIGKILL")
            os.kill(pid, signal.SIGKILL)
            time.sleep(SHUTDOWN_WAIT_TIME)
            
            self._cleanup_pid_file()
            print("✅ Stream detenido (forzado)")
            return True
            
        except ProcessLookupError:
            logger.info(f"Proceso {pid} ya no existe")
            print("⚠️  El proceso ya no existe")
            self._cleanup_pid_file()
            return True
        except PermissionError as e:
            logger.error(f"Permiso denegado para terminar proceso {pid}: {e}")
            print(f"❌ Error: Sin permisos para detener el proceso")
            return False
    
    def is_running(self) -> bool:
        """
        Verifica si el stream está corriendo.
        
        Comprueba si el proceso existe y es válido.
        
        Returns:
            True si está corriendo
        """
        if not self.pid_file.exists():
            return False
        
        try:
            pid = int(self.pid_file.read_text().strip())
            # Verificar si el proceso existe (sin matarlo)
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            # ProcessLookupError: proceso no existe
            # PermissionError: proceso existe pero no tenemos permisos (asumir que existe)
            return False
        except (ValueError, OSError) as e:
            # PID inválido o error al leer
            logger.warning(f"Error al verificar proceso: {e}")
            self._cleanup_pid_file()
            return False
    
    def status(self) -> Dict[str, Any]:
        """
        Obtiene el estado del stream.
        
        Returns:
            Diccionario con información del estado incluyendo:
            - running: bool - Si el stream está activo
            - video: str - Ruta al video
            - video_exists: bool - Si el video existe
            - stream_url: str - URL del stream
            - m3u_path: str - Ruta al archivo M3U
            - m3u_exists: bool - Si el M3U existe
            - pid: int (opcional) - PID del proceso si está corriendo
        """
        is_running = self.is_running()
        
        status: Dict[str, Any] = {
            "running": is_running,
            "video": str(self.video_path),
            "video_exists": self.video_path.exists(),
            "stream_url": Config.get_stream_url(),
            "m3u_path": str(Config.get_m3u_path()),
            "m3u_exists": Config.get_m3u_path().exists()
        }
        
        if is_running and self.pid_file.exists():
            try:
                status["pid"] = int(self.pid_file.read_text().strip())
            except (ValueError, OSError) as e:
                logger.warning(f"Error al leer PID: {e}")
        
        return status


class M3UGenerator:
    """Generador de archivos M3U"""
    
    @staticmethod
    def generate() -> bool:
        """
        Genera el archivo M3U con el canal de prueba.
        
        Crea un archivo M3U válido con el formato EXTINF estándar.
        El archivo se escribe de forma atómica para evitar lecturas parciales.
        
        Returns:
            True si se generó correctamente
            
        Raises:
            OSError: Si no se puede escribir el archivo
        """
        try:
            output_path = Config.get_m3u_path()
            stream_url = Config.get_stream_url()
            
            # Asegurar que el directorio existe
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Contenido del M3U (sin líneas en blanco al inicio)
            m3u_content = f"""#EXTM3U
#EXTINF:-1 tvg-id="" tvg-name="{Config.CHANNEL_NAME}" tvg-logo="{Config.CHANNEL_LOGO}" group-title="{Config.CHANNEL_GROUP}",{Config.CHANNEL_NAME}
{stream_url}
"""
            
            # Escribir de forma atómica
            temp_path = output_path.with_suffix('.tmp')
            temp_path.write_text(m3u_content, encoding="utf-8")
            temp_path.replace(output_path)
            
            logger.info(f"M3U generado: {output_path}")
            print(f"✅ M3U generado: {output_path}")
            print(f"📺 Canal: {Config.CHANNEL_NAME}")
            print(f"🔗 URL: {stream_url}")
            
            return True
            
        except PermissionError as e:
            error_msg = f"Sin permisos para escribir en {output_path}: {e}"
            logger.error(error_msg)
            print(f"❌ Error: {error_msg}")
            return False
        except OSError as e:
            error_msg = f"Error al escribir archivo M3U: {e}"
            logger.error(error_msg)
            print(f"❌ {error_msg}")
            return False
        except Exception as e:
            error_msg = f"Error inesperado al generar M3U: {e}"
            logger.exception(error_msg)
            print(f"❌ {error_msg}")
            return False
