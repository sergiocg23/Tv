"""
CLI - Interfaz de línea de comandos para iptvListValidator
"""

import argparse
import sys
import logging
from pathlib import Path
from typing import Optional

from iptvListValidator import __version__, __description__
from iptvListValidator.validator import IPTVValidator
from iptvListValidator.config import Config
from iptvListValidator.utils import setup_logging, get_file_info


def create_parser() -> argparse.ArgumentParser:
    """
    Crea y configura el parser de argumentos de la CLI.
    
    Returns:
        ArgumentParser configurado con todos los comandos y argumentos
    """
    parser = argparse.ArgumentParser(
        prog="iptvListValidator",
        description=__description__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  # Validar enlaces y generar listas
  iptvListValidator validate
  
  # Validar forzando procesamiento
  iptvListValidator validate --force
  
  # Verificar estado de los archivos
  iptvListValidator check
  
  # Limpiar backups antiguos (mantener últimos 5)
  iptvListValidator clean --keep 5
  
  # Ver información de la configuración actual
  iptvListValidator info
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
        help="Ruta al archivo de log (por defecto: logs/iptvListValidator.log)"
    )
    
    # Argumentos globales de configuración
    parser.add_argument(
        "--input",
        type=Path,
        help="Archivo M3U de entrada (sobrescribe IPTV_OUTPUT_DIR + IPTV_FILENAME del .env)"
    )
    
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directorio de salida (sobrescribe VALIDATOR_OUTPUT_DIR del .env)"
    )
    
    # Subcomandos
    subparsers = parser.add_subparsers(
        dest="command",
        help="Comandos disponibles",
        required=True
    )
    
    # Comando: validate
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validar enlaces IPTV y generar listas",
        description="Valida todos los enlaces, mide calidad y genera archivos separados de válidos/inválidos"
    )
    validate_parser.add_argument(
        "--force",
        action="store_true",
        help="Forzar validación aunque no haya cambios en el archivo de entrada"
    )
    validate_parser.add_argument(
        "--no-backup",
        action="store_true",
        help="No crear backup de los archivos anteriores"
    )
    validate_parser.add_argument(
        "--max-links",
        type=int,
        help="Limitar número de enlaces a validar (útil para pruebas)"
    )
    
    # Comando: check
    subparsers.add_parser(
        "check",
        help="Verificar estado de los archivos",
        description="Muestra información de los archivos generados sin validar"
    )
    
    # Comando: clean
    clean_parser = subparsers.add_parser(
        "clean",
        help="Limpiar backups antiguos",
        description="Elimina backups antiguos manteniendo solo los más recientes"
    )
    clean_parser.add_argument(
        "--keep",
        type=int,
        default=5,
        help="Número de backups a mantener de cada tipo (por defecto: 5)"
    )
    clean_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simular limpieza sin borrar archivos"
    )
    
    # Comando: info
    subparsers.add_parser(
        "info",
        help="Ver configuración actual",
        description="Muestra la configuración cargada y estado del sistema"
    )
    
    return parser


def cmd_validate(args: argparse.Namespace, config: Config, logger: logging.Logger) -> int:
    """
    Ejecuta el comando validate.
    
    Args:
        args: Argumentos parseados
        config: Configuración
        logger: Logger
        
    Returns:
        Código de salida (0 = éxito, 1 = error)
    """
    try:
        validator = IPTVValidator(config, logger)
        
        result = validator.validate_and_generate(
            force=args.force,
            create_backup=not args.no_backup,
            max_links=args.max_links if hasattr(args, 'max_links') else None
        )
        
        if not result['success']:
            logger.error(f"Error durante la validación: {result.get('error', 'Error desconocido')}")
            return 1
        
        if not result.get('input_changed', False):
            logger.info("No se requiere validación (sin cambios en el archivo de entrada)")
            logger.info("Usa --force para forzar la validación")
            return 0
        
        # Mostrar resumen
        print("\n" + "=" * 70)
        print("RESUMEN DE VALIDACIÓN")
        print("=" * 70)
        print(f"Canales totales: {result['channels_total']}")
        print(f"Canales con enlaces válidos: {result['channels_with_valid_links']}")
        print(f"Canales sin enlaces válidos: {result['channels_all_failed']}")
        print(f"Enlaces válidos: {result['links_valid']}/{result['links_total']}")
        print(f"Enlaces fallidos: {result['links_failed']}/{result['links_total']}")
        print("\nArchivos generados:")
        print(f"  Válidos: {result['valid_file']}")
        print(f"  Fallidos: {result['fail_file']}")
        
        if result.get('backup_valid') or result.get('backup_fail'):
            print("\nBackups creados:")
            if result.get('backup_valid'):
                print(f"  {result['backup_valid']}")
            if result.get('backup_fail'):
                print(f"  {result['backup_fail']}")
        
        print("=" * 70)
        
        return 0
        
    except Exception as e:
        logger.exception(f"Error inesperado: {e}")
        return 1


def cmd_check(_args: argparse.Namespace, config: Config, logger: logging.Logger) -> int:
    """
    Ejecuta el comando check.
    
    Args:
        args: Argumentos parseados
        config: Configuración
        logger: Logger
        
    Returns:
        Código de salida (0 = éxito, 1 = error)
    """
    try:
        valid_path = config.get_valid_output_path()
        fail_path = config.get_fail_output_path()
        
        print("\n" + "=" * 70)
        print("ESTADO DE ARCHIVOS")
        print("=" * 70)
        
        # Información del archivo de válidos
        print("\nArchivo de válidos:")
        valid_info = get_file_info(valid_path)
        if valid_info['exists']:
            print(f"  Ruta: {valid_info['file']}")
            print(f"  Tamaño: {valid_info['size_bytes']} bytes")
            print(f"  Última modificación: {valid_info['last_modified']}")
            print(f"  Hash: {valid_info['hash'][:16]}...")
            print(f"  Líneas: {valid_info['lines']}")
            print(f"  Canales: {valid_info['channels']}")
        else:
            print(f"  ❌ No existe: {valid_info['file']}")
        
        # Información del archivo de fallidos
        print("\nArchivo de fallidos:")
        fail_info = get_file_info(fail_path)
        if fail_info['exists']:
            print(f"  Ruta: {fail_info['file']}")
            print(f"  Tamaño: {fail_info['size_bytes']} bytes")
            print(f"  Última modificación: {fail_info['last_modified']}")
            print(f"  Hash: {fail_info['hash'][:16]}...")
            print(f"  Líneas: {fail_info['lines']}")
            print(f"  Canales: {fail_info['channels']}")
        else:
            print(f"  ❌ No existe: {fail_info['file']}")
        
        # Contar backups
        if config.olds_dir.exists():
            valid_backups = list(config.olds_dir.glob(f"{valid_path.stem}_*"))
            fail_backups = list(config.olds_dir.glob(f"{fail_path.stem}_*"))
            
            print("\nBackups disponibles:")
            print(f"  Válidos: {len(valid_backups)}")
            print(f"  Fallidos: {len(fail_backups)}")
            print(f"  Directorio: {config.olds_dir}")
        else:
            print("\nNo hay directorio de backups")
        
        print("=" * 70)
        
        return 0
        
    except Exception as e:
        logger.exception(f"Error inesperado: {e}")
        return 1


def cmd_clean(args: argparse.Namespace, config: Config, logger: logging.Logger) -> int:
    """
    Ejecuta el comando clean.
    
    Args:
        args: Argumentos parseados
        config: Configuración
        logger: Logger
        
    Returns:
        Código de salida (0 = éxito, 1 = error)
    """
    try:
        validator = IPTVValidator(config, logger)
        
        result = validator.clean_old_backups(
            keep=args.keep,
            dry_run=args.dry_run
        )
        
        if not result['success']:
            logger.error(f"Error durante la limpieza: {result.get('error', 'Error desconocido')}")
            return 1
        
        print("\n" + "=" * 70)
        if args.dry_run:
            print("SIMULACIÓN DE LIMPIEZA (DRY-RUN)")
        else:
            print("LIMPIEZA DE BACKUPS")
        print("=" * 70)
        print(f"Backups mantenidos: {result['kept']}")
        print(f"Backups eliminados: {result['deleted']}")
        if result.get('message'):
            print(f"\n{result['message']}")
        print("=" * 70)
        
        return 0
        
    except Exception as e:
        logger.exception(f"Error inesperado: {e}")
        return 1


def cmd_info(_args: argparse.Namespace, config: Config, logger: logging.Logger) -> int:
    """
    Ejecuta el comando info.
    
    Args:
        args: Argumentos parseados
        config: Configuración
        logger: Logger
        
    Returns:
        Código de salida (0 = éxito, 1 = error)
    """
    try:
        print("\n" + "=" * 70)
        print("CONFIGURACIÓN ACTUAL")
        print("=" * 70)
        print(f"Versión: {__version__}")
        print("\nRutas:")
        print(f"  Archivo de entrada: {config.get_input_path()}")
        print(f"  Directorio de salida: {config.output_dir}")
        print(f"  Archivo de válidos: {config.get_valid_output_path()}")
        print(f"  Archivo de fallidos: {config.get_fail_output_path()}")
        print(f"  Directorio de backups: {config.olds_dir}")
        print("\nTimeouts:")
        print(f"  Conexión: {config.timeout_connect}s")
        print(f"  Stream: {config.timeout_stream}s")
        print(f"  Test de estabilidad: {config.stability_test_duration}s")
        print("\nOtros:")
        print(f"  IP del host: {config.host_ip}")
        print(f"  Bitrate mínimo: {config.min_bitrate} bytes/s")
        print("=" * 70)
        
        # Verificar si existe el archivo de entrada
        input_path = config.get_input_path()
        if not input_path.exists():
            print(f"\n⚠️  ADVERTENCIA: El archivo de entrada no existe: {input_path}")
            print("   Asegúrate de ejecutar iptvListWatcher primero para descargar la lista.")
        
        return 0
        
    except Exception as e:
        logger.exception(f"Error inesperado: {e}")
        return 1


def main() -> int:
    """
    Función principal de la CLI.
    
    Returns:
        Código de salida (0 = éxito, 1 = error)
    """
    # Parsear argumentos
    parser = create_parser()
    args = parser.parse_args()
    
    # Configurar logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    log_file = args.log_file or "logs/iptvListValidator.log"
    logger = setup_logging(level=log_level, log_file=log_file)
    
    try:
        # Cargar configuración desde .env
        env_file = Path(".env")
        config = Config.from_env(env_file if env_file.exists() else None)
        
        # Sobrescribir con argumentos de CLI si se proporcionan
        if args.input:
            config.input_dir = args.input.parent
            config.input_filename = args.input.name
        
        if args.output_dir:
            config.output_dir = args.output_dir
            config.olds_dir = args.output_dir / "olds"
        
        # Ejecutar comando
        if args.command == "validate":
            return cmd_validate(args, config, logger)
        elif args.command == "check":
            return cmd_check(args, config, logger)
        elif args.command == "clean":
            return cmd_clean(args, config, logger)
        elif args.command == "info":
            return cmd_info(args, config, logger)
        else:
            logger.error(f"Comando desconocido: {args.command}")
            parser.print_help()
            return 1
        
    except ValueError as e:
        logger.error(f"Error de configuración: {e}")
        return 1
    except Exception as e:
        logger.exception(f"Error inesperado: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
