"""
Gestión de configuración del módulo iptvListWatcher.

Soporta URL override dinámico via url_config.json (ver url_manager.py).
Jerarquía de resolución de URL:
  1. CLI flag --url (máxima prioridad)
  2. url_config.json → active_url (override persistente)
  3. Variable de entorno IPTV_LIST_URL (fallback por defecto)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from iptvListWatcher.url_manager import UrlManager


logger = logging.getLogger(__name__)


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

    # Fuente de la URL activa ("env", "override" o "cli")
    url_source: str = "env"

    def validate(self) -> None:
        """
        Valida la configuración.

        Raises:
            ValueError: Si la configuración no es válida.
        """
        if not self.list_url:
            raise ValueError("list_url no puede estar vacío")

        if not self.host_ip:
            raise ValueError("host_ip no puede estar vacío")

        if not self.list_url.startswith(("http://", "https://")):
            raise ValueError("list_url debe ser una URL válida (http:// o https://)")

        # Validar formato IP
        self._validate_ip(self.host_ip, "host_ip")
        self._validate_ip(self.generic_ip, "generic_ip")

        if self.download_timeout <= 0:
            raise ValueError(
                "download_timeout debe ser positivo: %d" % self.download_timeout
            )

    def ensure_directories(self) -> None:
        """Crea los directorios de salida y backups si no existen."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.olds_dir.mkdir(parents=True, exist_ok=True)

    def get_output_path(self) -> Path:
        """Devuelve la ruta completa del archivo de salida."""
        return self.output_dir / self.filename

    def get_url_manager(self) -> UrlManager:
        """Devuelve un UrlManager vinculado al directorio de salida."""
        return UrlManager(self.output_dir)

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> Config:
        """
        Crea una instancia de Config desde variables de entorno.

        Aplica el override de URL si existe url_config.json en el
        directorio de salida.

        Args:
            env_file: Ruta opcional a un archivo .env para cargar.

        Returns:
            Instancia de Config configurada.

        Raises:
            ValueError: Si faltan variables de entorno requeridas.
        """
        if env_file and env_file.exists():
            cls._load_env_file(env_file)

        list_url = _require_env("IPTV_LIST_URL")
        host_ip = _require_env("HOST_IP")
        output_dir = Path(_require_env("IPTV_OUTPUT_DIR"))
        olds_dir = output_dir / "olds"
        filename = _require_env("IPTV_FILENAME")
        generic_ip = _require_env("IPTV_GENERIC_IP")

        timeout_str = _require_env("IPTV_DOWNLOAD_TIMEOUT")
        try:
            timeout = int(timeout_str)
        except ValueError as exc:
            raise ValueError(
                "IPTV_DOWNLOAD_TIMEOUT debe ser un número entero, "
                "se recibió: %s" % timeout_str
            ) from exc

        # Resolver URL override
        url_manager = UrlManager(output_dir)
        resolved_url, url_source = url_manager.get_active_url(list_url)

        return cls(
            list_url=resolved_url,
            host_ip=host_ip,
            output_dir=output_dir,
            olds_dir=olds_dir,
            filename=filename,
            generic_ip=generic_ip,
            download_timeout=timeout,
            url_source=url_source,
        )

    @staticmethod
    def _load_env_file(env_file: Path) -> None:
        """Carga variables de entorno desde un archivo .env."""
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                if not line or line.startswith("#"):
                    continue

                if "=" not in line:
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Remover comillas
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]

                # No sobrescribir variables ya existentes
                if key and not os.getenv(key):
                    os.environ[key] = value

    @staticmethod
    def _validate_ip(ip: str, field_name: str) -> None:
        """Valida formato IPv4."""
        parts = ip.split(".")
        if len(parts) != 4:
            raise ValueError("%s no tiene formato IP válido: %s" % (field_name, ip))
        for part in parts:
            try:
                num = int(part)
            except ValueError:
                raise ValueError("%s no tiene formato IP válido: %s" % (field_name, ip))
            if not 0 <= num <= 255:
                raise ValueError("%s no tiene formato IP válido: %s" % (field_name, ip))


def _require_env(name: str) -> str:
    """Lee una variable de entorno requerida o lanza ValueError."""
    value = os.getenv(name)
    if not value:
        raise ValueError(
            "%s no está configurado en las variables de entorno. "
            "Por favor, define %s en el archivo .env o como variable de entorno."
            % (name, name)
        )
    return value
