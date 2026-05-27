"""
CLI - Interfaz de línea de comandos para iptvListWatcher.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from iptvListWatcher import __version__, __description__
from iptvListWatcher.config import Config
from iptvListWatcher.url_manager import UrlManager
from iptvListWatcher.utils import calculate_file_hash, setup_logging
from iptvListWatcher.watcher import IPTVWatcher


def create_parser() -> argparse.ArgumentParser:
    """
    Crea y configura el parser de argumentos de la CLI.
    
    Returns:
        ArgumentParser configurado con todos los comandos y argumentos
    """
    parser = argparse.ArgumentParser(
        prog="iptvListWatcher",
        description=__description__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  # Descargar y verificar cambios (usando variables de entorno)
  iptvListWatcher download
  
  # Descargar especificando URL y IP del host
  iptvListWatcher download --url https://ejemplo.com/lista.m3u --host-ip 192.168.1.100
  
  # Verificar sin descargar
  iptvListWatcher check
  
  # Limpiar archivos antiguos (mantener últimos 5)
  iptvListWatcher clean --keep 5
  
  # Ver información de la configuración actual
  iptvListWatcher info
        """
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Activar modo verbose (más información en logs)"
    )
    
    parser.add_argument(
        "--log-file",
        type=str,
        help="Ruta al archivo de log (por defecto: logs/iptvListWatcher.log)"
    )
    
    # Argumentos globales de configuración
    parser.add_argument(
        "--url",
        type=str,
        help="URL de descarga de la lista IPTV (sobrescribe IPTV_LIST_URL del .env)"
    )
    
    parser.add_argument(
        "--host-ip",
        type=str,
        help="IP del host Acestream (sobrescribe HOST_IP del .env)"
    )
    
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directorio de salida para las listas (por defecto: playlist/ListWatcher)"
    )
    
    # Subcomandos
    subparsers = parser.add_subparsers(
        dest="command",
        help="Comandos disponibles",
        required=True
    )
    
    # Comando: download
    download_parser = subparsers.add_parser(
        "download",
        help="Descargar lista IPTV y detectar cambios",
        description="Descarga la lista IPTV, reemplaza IPs y detecta cambios respecto a la versión anterior"
    )
    download_parser.add_argument(
        "--force",
        action="store_true",
        help="Forzar descarga aunque no haya cambios"
    )
    download_parser.add_argument(
        "--no-backup",
        action="store_true",
        help="No crear backup del archivo anterior"
    )
    
    # Comando: check
    subparsers.add_parser(
        "check",
        help="Verificar estado de la lista actual",
        description="Verifica el estado de la lista actual sin descargar"
    )
    
    # Comando: clean
    clean_parser = subparsers.add_parser(
        "clean",
        help="Limpiar archivos antiguos",
        description="Limpia archivos antiguos de la carpeta olds/"
    )
    clean_parser.add_argument(
        "--keep",
        type=int,
        default=5,
        help="Número de archivos antiguos a mantener (por defecto: 5)"
    )
    clean_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostrar qué archivos se eliminarían sin borrarlos"
    )
    
    # Comando: info
    subparsers.add_parser(
        "info",
        help="Mostrar información de configuración",
        description="Muestra la configuración actual y el estado del sistema"
    )
    
    # Comando: hash
    hash_parser = subparsers.add_parser(
        "hash",
        help="Calcular hash de un archivo",
        description="Calcula el hash SHA256 de un archivo M3U"
    )
    hash_parser.add_argument(
        "file",
        type=Path,
        help="Ruta al archivo M3U"
    )

    # Comando: set-url
    set_url_parser = subparsers.add_parser(
        "set-url",
        help="Cambiar la URL de descarga en runtime",
        description=(
            "Establece una nueva URL de descarga IPTV que se usará en lugar "
            "de la definida en IPTV_LIST_URL. Se persiste en url_config.json."
        ),
    )
    set_url_parser.add_argument(
        "new_url",
        type=str,
        help="Nueva URL de descarga IPTV",
    )
    set_url_parser.add_argument(
        "--reason",
        type=str,
        default="",
        help="Motivo del cambio (queda registrado en el historial)",
    )

    # Comando: get-url
    subparsers.add_parser(
        "get-url",
        help="Ver la URL activa y el historial de cambios",
        description="Muestra la URL de descarga activa y el historial de URLs.",
    )

    # Comando: reset-url
    reset_url_parser = subparsers.add_parser(
        "reset-url",
        help="Eliminar el override y volver a usar la URL del .env",
        description=(
            "Elimina el override de URL y vuelve a usar la variable "
            "de entorno IPTV_LIST_URL."
        ),
    )
    reset_url_parser.add_argument(
        "--reason",
        type=str,
        default="",
        help="Motivo del reset (queda registrado en el historial)",
    )

    return parser


def execute_download(args: argparse.Namespace, config: Config, logger: logging.Logger) -> int:
    """Ejecuta el comando download."""
    try:
        watcher = IPTVWatcher(config, logger)

        result = watcher.download_and_check(
            force=args.force,
            create_backup=not args.no_backup,
        )

        if result["success"]:
            if result["changed"]:
                logger.info("✓ Lista actualizada: %s", result["file_path"])
                if result.get("backup_path"):
                    logger.info("  Backup guardado: %s", result["backup_path"])
            else:
                logger.info("✓ No hay cambios en la lista")
            return 0

        logger.error("✗ Error: %s", result.get("error", "Error desconocido"))
        return 1

    except Exception:
        logger.exception("Error ejecutando download")
        return 1


def execute_check(args: argparse.Namespace, config: Config, logger: logging.Logger) -> int:
    """Ejecuta el comando check."""
    try:
        watcher = IPTVWatcher(config, logger)
        info = watcher.get_current_status()

        logger.info("=== Estado actual ===")
        logger.info("Archivo actual: %s", info["current_file"])
        logger.info("Existe: %s", info["exists"])

        if info["exists"]:
            logger.info("Tamaño: %d bytes", info["size_bytes"])
            logger.info("Última modificación: %s", info["last_modified"])
            logger.info("Hash: %s", info["hash"])
            logger.info("Líneas: %d", info["lines"])

        logger.info("Backups disponibles: %d", info["backup_count"])

        return 0

    except Exception:
        logger.exception("Error ejecutando check")
        return 1


def execute_clean(args: argparse.Namespace, config: Config, logger: logging.Logger) -> int:
    """Ejecuta el comando clean."""
    try:
        watcher = IPTVWatcher(config, logger)

        result = watcher.clean_old_files(
            keep=args.keep,
            dry_run=args.dry_run,
        )

        if args.dry_run:
            logger.info("=== Modo DRY RUN ===")

        logger.info("Archivos a eliminar: %d", result["deleted_count"])
        logger.info("Archivos mantenidos: %d", result["kept_count"])

        if result["deleted_files"]:
            logger.info("Archivos eliminados:")
            for file in result["deleted_files"]:
                logger.info("  - %s", file)

        if not args.dry_run:
            logger.info("✓ Limpieza completada")

        return 0

    except Exception:
        logger.exception("Error ejecutando clean")
        return 1


def execute_info(args: argparse.Namespace, config: Config, logger: logging.Logger) -> int:
    """Ejecuta el comando info."""
    try:
        logger.info("=== Configuración actual ===")
        logger.info("URL de descarga: %s", config.list_url)
        logger.info("Fuente de URL: %s", config.url_source)
        logger.info("IP del host: %s", config.host_ip)
        logger.info("Directorio de salida: %s", config.output_dir)
        logger.info("Directorio de backups: %s", config.olds_dir)
        logger.info("Nombre del archivo: %s", config.filename)

        # Verificar directorios
        logger.info("=== Estado de directorios ===")
        logger.info("Output dir existe: %s", config.output_dir.exists())
        logger.info("Olds dir existe: %s", config.olds_dir.exists())

        # Estado actual
        watcher = IPTVWatcher(config, logger)
        status = watcher.get_current_status()

        logger.info("=== Estado actual ===")
        logger.info("Archivo actual existe: %s", status["exists"])
        if status["exists"]:
            logger.info(
                "Tamaño: %d bytes (%.2f KB)",
                status["size_bytes"], status["size_bytes"] / 1024,
            )
            logger.info("Líneas: %d", status["lines"])
        logger.info("Backups: %d", status["backup_count"])

        return 0

    except Exception:
        logger.exception("Error ejecutando info")
        return 1


def execute_hash(args: argparse.Namespace, config: Config, logger: logging.Logger) -> int:
    """Ejecuta el comando hash."""
    try:
        file_path: Path = args.file

        if not file_path.exists():
            logger.error("El archivo no existe: %s", file_path)
            return 1

        file_hash = calculate_file_hash(file_path)
        logger.info("Hash SHA256 de %s:", file_path.name)
        logger.info(file_hash)

        return 0

    except Exception:
        logger.exception("Error calculando hash")
        return 1


def execute_set_url(
    args: argparse.Namespace, config: Config, logger: logging.Logger,
) -> int:
    """Ejecuta el comando set-url."""
    try:
        new_url: str = args.new_url

        if not new_url.startswith(("http://", "https://")):
            logger.error("La URL debe empezar con http:// o https://")
            return 1

        url_manager = config.get_url_manager()
        url_config = url_manager.set_url(new_url, reason=args.reason)

        logger.info("✓ URL override establecida")
        logger.info("  Nueva URL: %s", url_config.active_url)
        logger.info("  Actualizado: %s", url_config.updated_at)
        logger.info("  Historial: %d entradas", len(url_config.history))
        logger.info(
            "  La próxima ejecución de 'download' usará esta URL."
        )

        return 0

    except Exception:
        logger.exception("Error ejecutando set-url")
        return 1


def execute_get_url(
    args: argparse.Namespace, config: Config, logger: logging.Logger,
) -> int:
    """Ejecuta el comando get-url."""
    try:
        url_manager = config.get_url_manager()
        url_config = url_manager.load()

        logger.info("=== URL Activa ===")
        logger.info("URL en uso: %s", config.list_url)
        logger.info("Fuente: %s", config.url_source)

        if url_config.active_url:
            logger.info("Override activo: %s", url_config.active_url)
            logger.info("Override desde: %s", url_config.updated_at)
        else:
            logger.info("No hay URL override — se usa la del .env")

        history = url_config.history
        if history:
            logger.info("")
            logger.info("=== Historial de URLs (%d entradas) ===", len(history))
            for i, entry in enumerate(history, 1):
                status = "activa" if entry.used_until is None else entry.used_until
                reason = " (%s)" % entry.reason if entry.reason else ""
                logger.info(
                    "  %d. %s | desde %s → %s%s",
                    i, entry.url, entry.used_from, status, reason,
                )
        else:
            logger.info("Historial vacío — no se han hecho cambios de URL")

        return 0

    except Exception:
        logger.exception("Error ejecutando get-url")
        return 1


def execute_reset_url(
    args: argparse.Namespace, config: Config, logger: logging.Logger,
) -> int:
    """Ejecuta el comando reset-url."""
    try:
        url_manager = config.get_url_manager()
        url_config = url_manager.load()

        if not url_config.active_url:
            logger.info("No hay URL override activa, nada que resetear")
            return 0

        old_url = url_config.active_url
        url_manager.reset_url(reason=args.reason)

        logger.info("✓ URL override eliminada")
        logger.info("  URL anterior (override): %s", old_url)
        logger.info(
            "  La próxima ejecución de 'download' usará IPTV_LIST_URL del .env."
        )

        return 0

    except Exception:
        logger.exception("Error ejecutando reset-url")
        return 1


def main(argv: list[str] | None = None) -> int:
    """
    Función principal de la CLI.

    Args:
        argv: Lista de argumentos (opcional, usa sys.argv si no se proporciona).

    Returns:
        Código de salida (0 = éxito, 1 = error).
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    # Configurar logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    log_file = args.log_file if args.log_file else "logs/iptvListWatcher.log"
    logger = setup_logging(log_level, log_file)

    # Cargar configuración
    try:
        config = Config.from_env()

        # Sobrescribir con argumentos de CLI si se proporcionan
        if args.url:
            config.list_url = args.url
            config.url_source = "cli"
        if args.host_ip:
            config.host_ip = args.host_ip
        if args.output_dir:
            config.output_dir = args.output_dir
            config.olds_dir = config.output_dir / "olds"

    except Exception as exc:
        logger.error("Error cargando configuración: %s", exc)
        return 1

    # Ejecutar comando correspondiente
    commands = {
        "download": execute_download,
        "check": execute_check,
        "clean": execute_clean,
        "info": execute_info,
        "hash": execute_hash,
        "set-url": execute_set_url,
        "get-url": execute_get_url,
        "reset-url": execute_reset_url,
    }

    command_func = commands.get(args.command)
    if command_func:
        return command_func(args, config, logger)

    logger.error("Comando desconocido: %s", args.command)
    return 1


if __name__ == "__main__":
    sys.exit(main())
