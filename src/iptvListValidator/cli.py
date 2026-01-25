"""
CLI - Interfaz de línea de comandos para iptvListValidator
"""

import argparse
import sys
import logging
from pathlib import Path

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
  # Validar todos los tiers (Premium/Good/Suspect/Fail)
  iptvListValidator validate
  
  # Validar solo streams de un tier específico
  iptvListValidator validate --list premium
  iptvListValidator validate --list good
  
  # Verificar estado de los archivos
  iptvListValidator check
  
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
        help="Validar enlaces IPTV con sistema de confianza",
        description="Valida enlaces usando el sistema de puntuación por tiers (Premium/Good/Suspect/Fail) y genera archivos M3U clasificados. Por defecto valida todos los tiers."
    )
    validate_parser.add_argument(
        "--list",
        type=str,
        choices=['premium', 'good', 'suspect', 'fail'],
        help="Validar solo streams de un tier específico. Si no se especifica, valida todos los tiers."
    )
    validate_parser.add_argument(
        "--url",
        type=str,
        help="Validar solo una URL específica directamente (modo prueba rápida)"
    )
    
    # Comando: check
    subparsers.add_parser(
        "check",
        help="Verificar estado de los archivos",
        description="Muestra información de los archivos generados sin validar"
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
        
        # Si se especifica --url, validar solo esa URL
        if hasattr(args, 'url') and args.url:
            result = validator.validate_single_url(args.url)
            
            # Mostrar resultado
            print("\n" + "=" * 70)
            print("RESULTADO DE VALIDACIÓN DE URL")
            print("=" * 70)
            print(f"URL: {result['url']}")
            print(f"Válido: {'✓ SÍ' if result['success'] else '✗ NO'}")
            
            if result['success']:
                # Métricas básicas
                print(f"Latencia: {result['latency']:.2f}s")
                bitrate_bytes = result['bitrate']
                bitrate_kb = bitrate_bytes / 1024
                bitrate_mb = bitrate_bytes / (1024 * 1024)
                print(f"Bitrate: {bitrate_bytes:.0f} B/s ({bitrate_kb:.1f} KB/s, {bitrate_mb:.2f} MB/s)")
                print(f"Estable: {'✓ SÍ' if result['stable'] else '✗ NO'}")
                
                # Métricas avanzadas (si están disponibles)
                if result.get('resolution'):
                    print(f"Resolución: {result['resolution']}")
                if result.get('fps') and result['fps'] > 0:
                    print(f"FPS: {result['fps']:.1f}")
                if result.get('video_codec'):
                    print(f"Video Codec: {result['video_codec']}")
                if result.get('audio_codec'):
                    print(f"Audio Codec: {result['audio_codec']}")
                if result.get('analysis_method'):
                    print(f"Método de análisis: {result['analysis_method']}")
                
                print(f"Puntuación de calidad: {result['quality_score']:.1f}/100")
            else:
                print(f"Error: {result['error']}")
            
            print(f"Duración: {result['duration']:.2f}s")
            print("=" * 70)
            
            return 0 if result['success'] else 1
        
        # Sistema de confianza: validar por tier o todos los tiers
        tiers_to_validate = [args.list] if hasattr(args, 'list') and args.list else ['premium', 'good', 'suspect', 'fail']
        
        logger.info(f"Validando tiers: {', '.join(tiers_to_validate)}")
        
        all_stats = []
        for tier in tiers_to_validate:
            logger.info(f"Procesando tier: {tier}")
            result = validator.validate_by_tier(tier=tier)
            
            if not result['success']:
                logger.error(f"Error durante la validación del tier {tier}: {result.get('error', 'Error desconocido')}")
                return 1
            
            all_stats.append((tier, result.get('statistics', {})))
        
        # Mostrar estadísticas consolidadas
        print("\n" + "=" * 70)
        print("ESTADÍSTICAS DE VALIDACIÓN POR TIERS")
        print("=" * 70)
        
        for tier, stats in all_stats:
            print(f"\n[{tier.upper()}]")
            print(f"  Streams validados: {stats.get('validated_count', 0)}")
            print(f"  Éxitos: {stats.get('success_count', 0)}")
            print(f"  Fallos: {stats.get('fail_count', 0)}")
        
        # Estadísticas globales (usar las últimas que son las más actualizadas)
        if all_stats:
            _, final_stats = all_stats[-1]
            print("\n" + "-" * 70)
            print("ESTADÍSTICAS GLOBALES")
            print("-" * 70)
            print(f"Total streams en sistema: {final_stats.get('total_streams', 0)}")
            for tier, count in final_stats.get('by_tier', {}).items():
                print(f"  - {tier.capitalize()}: {count}")
            print(f"Confianza promedio: {final_stats.get('avg_confidence', 0):.1f}%")
        
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
        print(f"  Archivo de confianza: {config.get_confidence_path()}")
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
