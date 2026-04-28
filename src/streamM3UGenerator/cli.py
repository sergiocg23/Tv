"""
CLI - Interfaz de línea de comandos para streamM3UGenerator
"""

import argparse
import sys

from streamM3UGenerator import __version__, __description__
from streamM3UGenerator.generator import StreamGenerator, M3UGenerator
from streamM3UGenerator.utils import check_stream_health, print_info, validate_environment


def create_parser() -> argparse.ArgumentParser:
    """
    Crea y configura el parser de argumentos de la CLI.
    
    Returns:
        ArgumentParser configurado
    """
    parser = argparse.ArgumentParser(
        prog="streamM3UGenerator",
        description=__description__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  # Iniciar stream en background y generar M3U
  streamM3UGenerator start
  
  # Detener stream
  streamM3UGenerator stop
  
  # Ver estado del stream
  streamM3UGenerator status
  
  # Generar solo el archivo M3U
  streamM3UGenerator generate
  
  # Verificar configuración
  streamM3UGenerator info
        """
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles")
    
    # Comando: start
    start_parser = subparsers.add_parser("start", help="Iniciar el stream")
    start_parser.add_argument(
        "--foreground",
        action="store_true",
        help="Ejecutar en primer plano (por defecto: background)"
    )
    start_parser.add_argument(
        "--no-generate",
        action="store_true",
        help="No generar el archivo M3U automáticamente"
    )
    
    # Comando: stop
    subparsers.add_parser("stop", help="Detener el stream")
    
    # Comando: status
    subparsers.add_parser("status", help="Ver estado del stream")
    
    # Comando: generate
    subparsers.add_parser("generate", help="Generar archivo M3U")
    
    # Comando: health
    subparsers.add_parser("health", help="Verificar salud del stream")
    
    # Comando: info
    subparsers.add_parser("info", help="Mostrar información de configuración")
    
    return parser


def cmd_start(args) -> int:
    """Comando start"""
    if not validate_environment():
        return 1
    
    generator = StreamGenerator()
    
    # Iniciar stream
    if not generator.start(background=not args.foreground):
        return 1
    
    # Generar M3U si no se especificó --no-generate
    if not args.no_generate:
        if not M3UGenerator.generate():
            print("⚠️  Stream iniciado pero no se pudo generar el M3U")
            return 1
    
    return 0


def cmd_stop(args) -> int:
    """Comando stop"""
    generator = StreamGenerator()
    
    if not generator.stop():
        return 1
    
    return 0


def cmd_status(args) -> int:
    """Comando status"""
    generator = StreamGenerator()
    status = generator.status()
    
    print("=" * 60)
    print("  streamM3UGenerator - Estado")
    print("=" * 60)
    print(f"Stream corriendo: {'✅ SÍ' if status['running'] else '❌ NO'}")
    
    if status.get('pid'):
        print(f"PID: {status['pid']}")
    
    print(f"Video: {status['video']}")
    print(f"Video existe: {'✅' if status['video_exists'] else '❌'}")
    print(f"Stream URL: {status['stream_url']}")
    print(f"M3U generado: {'✅' if status['m3u_exists'] else '❌'}")
    print(f"M3U path: {status['m3u_path']}")
    
    # Verificar salud si está corriendo
    if status['running']:
        is_healthy, message = check_stream_health()
        print(f"Salud del stream: {'✅' if is_healthy else '❌'} {message}")
    
    print("=" * 60)
    
    return 0 if status['running'] else 1


def cmd_generate(args) -> int:
    """Comando generate"""
    if not M3UGenerator.generate():
        return 1
    return 0


def cmd_health(args) -> int:
    """Comando health"""
    generator = StreamGenerator()
    
    if not generator.is_running():
        print("❌ Stream no está corriendo")
        return 1
    
    is_healthy, message = check_stream_health()
    
    if is_healthy:
        print(f"✅ {message}")
        return 0
    else:
        print(f"❌ {message}")
        return 1


def cmd_info(args) -> int:
    """Comando info"""
    print_info()
    return 0


def main():
    """Función principal de la CLI"""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    # Ejecutar comando
    commands = {
        "start": cmd_start,
        "stop": cmd_stop,
        "status": cmd_status,
        "generate": cmd_generate,
        "health": cmd_health,
        "info": cmd_info,
    }
    
    cmd_func = commands.get(args.command)
    if cmd_func:
        try:
            return cmd_func(args)
        except KeyboardInterrupt:
            print("\n⚠️  Interrumpido por el usuario")
            return 130
        except Exception as e:
            print(f"❌ Error inesperado: {e}")
            return 1
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
