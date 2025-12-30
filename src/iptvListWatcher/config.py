"""
Gestión de configuración del módulo iptvListWatcher
"""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """Configuración del watcher de listas IPTV."""
    
    # URL de descarga de la lista IPTV
    list_url: str
    
    # IP del host donde está Acestream
    host_ip: str
    
    # Directorios
    output_dir: Path
    olds_dir: Path
    
    # Nombre del archivo de salida
    filename: str = "iptv.m3u"
    
    # IP genérica a reemplazar
    generic_ip: str = "127.0.0.1"
    
    # Timeout para descargas (segundos)
    download_timeout: int = 30
    
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
        
        # URL de la lista IPTV
        list_url = os.getenv("IPTV_LIST_URL")
        if not list_url:
            raise ValueError(
                "IPTV_LIST_URL no está configurado en las variables de entorno. "
                "Por favor, define IPTV_LIST_URL en el archivo .env o como variable de entorno."
            )
        
        # IP del host
        host_ip = os.getenv("HOST_IP")
        if not host_ip:
            raise ValueError(
                "HOST_IP no está configurado en las variables de entorno. "
                "Por favor, define HOST_IP en el archivo .env o como variable de entorno."
            )
        
        # Directorio de salida
        output_dir_str = os.getenv("IPTV_OUTPUT_DIR")
        if not output_dir_str:
            raise ValueError(
                "IPTV_OUTPUT_DIR no está configurado en las variables de entorno. "
                "Por favor, define IPTV_OUTPUT_DIR en el archivo .env o como variable de entorno."
            )
        output_dir = Path(output_dir_str)
        
        # Directorio de backups
        olds_dir = output_dir / "olds"
        
        # Nombre del archivo
        filename = os.getenv("IPTV_FILENAME")
        if not filename:
            raise ValueError(
                "IPTV_FILENAME no está configurado en las variables de entorno. "
                "Por favor, define IPTV_FILENAME en el archivo .env o como variable de entorno."
            )
        
        # IP genérica
        generic_ip = os.getenv("IPTV_GENERIC_IP")
        if not generic_ip:
            raise ValueError(
                "IPTV_GENERIC_IP no está configurado en las variables de entorno. "
                "Por favor, define IPTV_GENERIC_IP en el archivo .env o como variable de entorno."
            )
        
        # Timeout
        timeout_str = os.getenv("IPTV_DOWNLOAD_TIMEOUT")
        if not timeout_str:
            raise ValueError(
                "IPTV_DOWNLOAD_TIMEOUT no está configurado en las variables de entorno. "
                "Por favor, define IPTV_DOWNLOAD_TIMEOUT en el archivo .env o como variable de entorno."
            )
        try:
            timeout = int(timeout_str)
        except ValueError:
            raise ValueError(
                f"IPTV_DOWNLOAD_TIMEOUT debe ser un número entero, se recibió: {timeout_str}"
            )
        
        return cls(
            list_url=list_url,
            host_ip=host_ip,
            output_dir=output_dir,
            olds_dir=olds_dir,
            filename=filename,
            generic_ip=generic_ip,
            download_timeout=timeout
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
                    
                    # Remover comillas si existen
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    
                    # Establecer variable de entorno si no existe
                    if key and not os.getenv(key):
                        os.environ[key] = value
    
    def ensure_directories(self) -> None:
        """Crea los directorios necesarios si no existen."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.olds_dir.mkdir(parents=True, exist_ok=True)
    
    def get_output_path(self) -> Path:
        """Retorna la ruta completa del archivo de salida."""
        return self.output_dir / self.filename
    
    def validate(self) -> None:
        """
        Valida la configuración.
        
        Raises:
            ValueError: Si la configuración no es válida
        """
        if not self.list_url:
            raise ValueError("list_url no puede estar vacío")
        
        if not self.host_ip:
            raise ValueError("host_ip no puede estar vacío")
        
        if not self.list_url.startswith(('http://', 'https://')):
            raise ValueError("list_url debe ser una URL válida (http:// o https://)")
        
        # Validar formato IP básico
        ip_parts = self.host_ip.split('.')
        if len(ip_parts) != 4:
            raise ValueError(f"host_ip no tiene formato válido: {self.host_ip}")
        
        try:
            for part in ip_parts:
                num = int(part)
                if not 0 <= num <= 255:
                    raise ValueError()
        except ValueError:
            raise ValueError(f"host_ip no tiene formato válido: {self.host_ip}")
