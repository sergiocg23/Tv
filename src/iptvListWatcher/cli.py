"""
CLI - Interfaz de línea de comandos para iptvListWatcher
"""

import argparse
import sys
import logging
from pathlib import Path
from typing import Optional

from iptvListWatcher import __version__, __description__
from iptvListWatcher.watcher import IPTVWatcher
from iptvListWatcher.config import Config
from iptvListWatcher.utils import setup_logging, calculate_file_hash


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
    
    return parser


def execute_download(args: argparse.Namespace, config: Config, logger: logging.Logger) -> int:
    """Ejecuta el comando download."""
    try:
        watcher = IPTVWatcher(config, logger)
        
        result = watcher.download_and_check(
            force=args.force,
            create_backup=not args.no_backup
        )
        
        if result["success"]:
            if result["changed"]:
                logger.info(f"✓ Lista actualizada: {result['file_path']}")
                if result.get("backup_path"):
                    logger.info(f"  Backup guardado: {result['backup_path']}")
            else:
                logger.info("✓ No hay cambios en la lista")
            return 0
        else:
            logger.error(f"✗ Error: {result.get('error', 'Error desconocido')}")
            return 1
            
    except Exception as e:
        logger.exception(f"Error ejecutando download: {e}")
        return 1


def execute_check(args: argparse.Namespace, config: Config, logger: logging.Logger) -> int:
    """Ejecuta el comando check."""
    try:
        watcher = IPTVWatcher(config, logger)
        info = watcher.get_current_status()
        
        logger.info("=== Estado actual ===")
        logger.info(f"Archivo actual: {info['current_file']}")
        logger.info(f"Existe: {info['exists']}")
        
        if info['exists']:
            logger.info(f"Tamaño: {info['size_bytes']} bytes")
            logger.info(f"Última modificación: {info['last_modified']}")
            logger.info(f"Hash: {info['hash']}")
            logger.info(f"Líneas: {info['lines']}")
        
        logger.info(f"Backups disponibles: {info['backup_count']}")
        
        return 0
        
    except Exception as e:
        logger.exception(f"Error ejecutando check: {e}")
        return 1


def execute_clean(args: argparse.Namespace, config: Config, logger: logging.Logger) -> int:
    """Ejecuta el comando clean."""
    try:
        watcher = IPTVWatcher(config, logger)
        
        result = watcher.clean_old_files(
            keep=args.keep,
            dry_run=args.dry_run
        )
        
        if args.dry_run:
            logger.info("=== Modo DRY RUN ===")
        
        logger.info(f"Archivos a eliminar: {result['deleted_count']}")
        logger.info(f"Archivos mantenidos: {result['kept_count']}")
        
        if result['deleted_files']:
            logger.info("\nArchivos eliminados:")
            for file in result['deleted_files']:
                logger.info(f"  - {file}")
        
        if not args.dry_run:
            logger.info("\n✓ Limpieza completada")
        
        return 0
        
    except Exception as e:
        logger.exception(f"Error ejecutando clean: {e}")
        return 1


def execute_info(args: argparse.Namespace, config: Config, logger: logging.Logger) -> int:
    """Ejecuta el comando info."""
    try:
        logger.info("=== Configuración actual ===")
        logger.info(f"URL de descarga: {config.list_url}")
        logger.info(f"IP del host: {config.host_ip}")
        logger.info(f"Directorio de salida: {config.output_dir}")
        logger.info(f"Directorio de backups: {config.olds_dir}")
        logger.info(f"Nombre del archivo: {config.filename}")
        
        # Verificar directorios
        logger.info("\n=== Estado de directorios ===")
        logger.info(f"Output dir existe: {config.output_dir.exists()}")
        logger.info(f"Olds dir existe: {config.olds_dir.exists()}")
        
        # Estado actual
        watcher = IPTVWatcher(config, logger)
        status = watcher.get_current_status()
        
        logger.info("\n=== Estado actual ===")
        logger.info(f"Archivo actual existe: {status['exists']}")
        if status['exists']:
            logger.info(f"Tamaño: {status['size_bytes']} bytes ({status['size_bytes'] / 1024:.2f} KB)")
            logger.info(f"Líneas: {status['lines']}")
        logger.info(f"Backups: {status['backup_count']}")
        
        return 0
        
    except Exception as e:
        logger.exception(f"Error ejecutando info: {e}")
        return 1


def execute_hash(args: argparse.Namespace, config: Config, logger: logging.Logger) -> int:
    """Ejecuta el comando hash."""
    try:
        file_path = args.file
        
        if not file_path.exists():
            logger.error(f"El archivo no existe: {file_path}")
            return 1
        
        file_hash = calculate_file_hash(file_path)
        logger.info(f"Hash SHA256 de {file_path.name}:")
        logger.info(file_hash)
        
        return 0
        
    except Exception as e:
        logger.exception(f"Error calculando hash: {e}")
        return 1


def main(argv: Optional[list] = None) -> int:
    """
    Función principal de la CLI.
    
    Args:
        argv: Lista de argumentos (opcional, usa sys.argv si no se proporciona)
        
    Returns:
        Código de salida (0 = éxito, 1 = error)
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
        if args.host_ip:
            config.host_ip = args.host_ip
        if args.output_dir:
            config.output_dir = args.output_dir
            config.olds_dir = config.output_dir / "olds"
            
    except Exception as e:
        logger.error(f"Error cargando configuración: {e}")
        return 1
    
    # Ejecutar comando correspondiente
    commands = {
        "download": execute_download,
        "check": execute_check,
        "clean": execute_clean,
        "info": execute_info,
        "hash": execute_hash,
    }
    
    command_func = commands.get(args.command)
    if command_func:
        return command_func(args, config, logger)
    else:
        logger.error(f"Comando desconocido: {args.command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
