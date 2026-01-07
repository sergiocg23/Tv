"""
Gestión de configuración del módulo iptvListValidator
"""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """Configuración del validador de listas IPTV."""
    
    # IP del host donde está Acestream
    host_ip: str
    
    # Directorio de entrada (donde está la lista a validar)
    input_dir: Path
    
    # Nombre del archivo de entrada
    input_filename: str
    
    # Directorio de salida (donde se guardarán los válidos/inválidos)
    output_dir: Path
    
    # Directorio de backups
    olds_dir: Path
    
    # Timeouts (en segundos)
    timeout_connect: int = 5
    timeout_stream: int = 10
    
    # Duración del test de estabilidad (segundos)
    stability_test_duration: int = 5
    
    # Bitrate mínimo esperado (bytes/segundo)
    min_bitrate: int = 500000
    
    # Nombres de archivos de salida
    valid_filename: str = "iptvListValidatorValid.m3u"
    fail_filename: str = "iptvListValidatorFail.m3u"
    
    @classmethod
    def from_env(cls, env_file: Optional[Path] = None) -> "Config":
        """
        Crea una instancia de Config desde variables de entorno.
        
        Args:
            env_file: Ruta opcional a un archivo .env para cargar
            
        Returns:
            Instancia de Config configurada
            
        Raises:
            ValueError: Si faltan variables de entorno requeridas
        """
        # Si se proporciona un archivo .env, cargarlo
        if env_file and env_file.exists():
            cls._load_env_file(env_file)
        
        # IP del host
        host_ip = os.getenv("HOST_IP")
        if not host_ip:
            raise ValueError(
                "HOST_IP no está configurado en las variables de entorno. "
                "Por favor, define HOST_IP en el archivo .env o como variable de entorno."
            )
        
        # Directorio de entrada
        input_dir_str = os.getenv("IPTV_OUTPUT_DIR")
        if not input_dir_str:
            raise ValueError(
                "IPTV_OUTPUT_DIR no está configurado en las variables de entorno. "
                "Por favor, define IPTV_OUTPUT_DIR en el archivo .env o como variable de entorno."
            )
        input_dir = Path(input_dir_str)
        
        # Nombre del archivo de entrada
        input_filename = os.getenv("IPTV_FILENAME")
        if not input_filename:
            raise ValueError(
                "IPTV_FILENAME no está configurado en las variables de entorno. "
                "Por favor, define IPTV_FILENAME en el archivo .env o como variable de entorno."
            )
        
        # Directorio de salida
        output_dir_str = os.getenv("VALIDATOR_OUTPUT_DIR")
        if not output_dir_str:
            raise ValueError(
                "VALIDATOR_OUTPUT_DIR no está configurado en las variables de entorno. "
                "Por favor, define VALIDATOR_OUTPUT_DIR en el archivo .env o como variable de entorno."
            )
        output_dir = Path(output_dir_str)
        
        # Directorio de backups
        olds_dir = output_dir / "olds"
        
        # Timeout de conexión
        timeout_connect_str = os.getenv("VALIDATOR_TIMEOUT_CONNECT", "5")
        try:
            timeout_connect = int(timeout_connect_str)
        except ValueError:
            raise ValueError(
                f"VALIDATOR_TIMEOUT_CONNECT debe ser un número entero, recibido: {timeout_connect_str}"
            )
        
        # Timeout de stream
        timeout_stream_str = os.getenv("VALIDATOR_TIMEOUT_STREAM", "10")
        try:
            timeout_stream = int(timeout_stream_str)
        except ValueError:
            raise ValueError(
                f"VALIDATOR_TIMEOUT_STREAM debe ser un número entero, recibido: {timeout_stream_str}"
            )
        
        # Duración del test de estabilidad
        stability_duration_str = os.getenv("VALIDATOR_STABILITY_TEST_DURATION", "5")
        try:
            stability_test_duration = int(stability_duration_str)
        except ValueError:
            raise ValueError(
                f"VALIDATOR_STABILITY_TEST_DURATION debe ser un número entero, recibido: {stability_duration_str}"
            )
        
        # Bitrate mínimo
        min_bitrate_str = os.getenv("VALIDATOR_MIN_BITRATE", "500000")
        try:
            min_bitrate = int(min_bitrate_str)
        except ValueError:
            raise ValueError(
                f"VALIDATOR_MIN_BITRATE debe ser un número entero, recibido: {min_bitrate_str}"
            )
        
        return cls(
            host_ip=host_ip,
            input_dir=input_dir,
            input_filename=input_filename,
            output_dir=output_dir,
            olds_dir=olds_dir,
            timeout_connect=timeout_connect,
            timeout_stream=timeout_stream,
            stability_test_duration=stability_test_duration,
            min_bitrate=min_bitrate
        )
    
    @staticmethod
    def _load_env_file(env_file: Path) -> None:
        """
        Carga variables de entorno desde un archivo .env
        
        Args:
            env_file: Ruta al archivo .env
        """
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Ignorar líneas vacías y comentarios
                if not line or line.startswith('#'):
                    continue
                
                # Parsear línea KEY=VALUE
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    # Solo establecer si no existe ya (las vars de entorno tienen prioridad)
                    if key and not os.getenv(key):
                        os.environ[key] = value
    
    def get_input_path(self) -> Path:
        """Retorna la ruta completa del archivo de entrada."""
        return self.input_dir / self.input_filename
    
    def get_valid_output_path(self) -> Path:
        """Retorna la ruta completa del archivo de válidos."""
        return self.output_dir / self.valid_filename
    
    def get_fail_output_path(self) -> Path:
        """Retorna la ruta completa del archivo de inválidos."""
        return self.output_dir / self.fail_filename
    
    def validate(self) -> None:
        """
        Valida que la configuración sea correcta.
        
        Raises:
            ValueError: Si hay algún problema con la configuración
        """
        # Validar timeouts
        if self.timeout_connect <= 0:
            raise ValueError(
                f"timeout_connect debe ser mayor que 0, recibido: {self.timeout_connect}"
            )
        
        if self.timeout_stream <= 0:
            raise ValueError(
                f"timeout_stream debe ser mayor que 0, recibido: {self.timeout_stream}"
            )
        
        if self.stability_test_duration <= 0:
            raise ValueError(
                f"stability_test_duration debe ser mayor que 0, recibido: {self.stability_test_duration}"
            )
        
        if self.min_bitrate < 0:
            raise ValueError(
                f"min_bitrate no puede ser negativo, recibido: {self.min_bitrate}"
            )
        
        # Validar que el archivo de entrada existe
        input_path = self.get_input_path()
        if not input_path.exists():
            raise ValueError(
                f"El archivo de entrada no existe: {input_path}\n"
                f"Asegúrate de que iptvListWatcher haya descargado la lista primero."
            )
    
    def ensure_directories(self) -> None:
        """Crea los directorios necesarios si no existen."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.olds_dir.mkdir(parents=True, exist_ok=True)
    
    def to_dict(self) -> dict:
        """
        Convierte la configuración a diccionario para logging/display.
        
        Returns:
            Diccionario con la configuración
        """
        return {
            'host_ip': self.host_ip,
            'input_file': str(self.get_input_path()),
            'output_dir': str(self.output_dir),
            'valid_output': str(self.get_valid_output_path()),
            'fail_output': str(self.get_fail_output_path()),
            'olds_dir': str(self.olds_dir),
            'timeout_connect': self.timeout_connect,
            'timeout_stream': self.timeout_stream,
            'stability_test_duration': self.stability_test_duration,
            'min_bitrate': self.min_bitrate,
        }
