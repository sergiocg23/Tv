"""
Lógica principal del watcher de listas IPTV.
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path

import requests

from iptvListWatcher.config import Config
from iptvListWatcher.parser import parse_m3u
from iptvListWatcher.utils import (
    calculate_content_hash,
    calculate_file_hash,
    get_file_info,
)

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
_WARP_PROXY = "socks5h://warp:9091"


class IPTVWatcher:
    """Clase principal para monitorear y gestionar listas IPTV."""

    def __init__(
        self,
        config: Config,
        logger: logging.Logger | None = None,
    ) -> None:
        self.config = config
        self.logger = logger or logging.getLogger(__name__)

        self.config.validate()
        self.config.ensure_directories()

    def download_and_check(
        self,
        force: bool = False,
        create_backup: bool = True,
    ) -> dict:
        """
        Descarga la lista IPTV, reemplaza IPs y detecta cambios.

        Returns:
            Diccionario con success, changed, file_path, backup_path, hash, error.
        """
        try:
            self.logger.info(
                "Descargando lista desde: %s (fuente: %s)",
                self.config.list_url,
                self.config.url_source,
            )
            raw_content = self._download_content()

            # Parsear M3U (estricto con fallback resiliente)
            playlist = parse_m3u(raw_content)

            if playlist.channel_count == 0:
                self.logger.error("No se encontraron canales en la lista descargada")
                return {
                    "success": False,
                    "changed": False,
                    "error": "No se encontraron canales en la lista descargada",
                }

            self.logger.info(
                "Parseados %d canales (modo: %s, grupos: %d)",
                playlist.channel_count,
                playlist.parse_mode,
                len(playlist.groups),
            )

            # Reemplazar IPs en los canales parseados
            self.logger.debug(
                "Reemplazando %s por %s",
                self.config.generic_ip,
                self.config.host_ip,
            )
            playlist.replace_ip(self.config.generic_ip, self.config.host_ip)

            # Reconstruir M3U
            content = playlist.to_m3u()

            # Calcular hash del nuevo contenido
            new_hash = calculate_content_hash(content)
            self.logger.debug("Hash del nuevo contenido: %s", new_hash)

            # Verificar si hay cambios
            output_path = self.config.get_output_path()
            has_changed = True

            if output_path.exists():
                old_hash = calculate_file_hash(output_path)
                self.logger.debug("Hash del archivo actual: %s", old_hash)
                has_changed = new_hash != old_hash
            else:
                self.logger.info("No existe archivo anterior")

            # Si no hay cambios y no es forzado, no hacer nada
            if not has_changed and not force:
                self.logger.info("No hay cambios en la lista")
                return {
                    "success": True,
                    "changed": False,
                    "file_path": output_path,
                    "hash": new_hash,
                }

            # Crear backup si es necesario
            backup_path = None
            if create_backup and output_path.exists() and has_changed:
                backup_path = self._create_backup(output_path)
                self.logger.info("Backup creado: %s", backup_path)

            # Guardar nuevo archivo
            self._save_content(content, output_path)
            self.logger.info("Lista guardada: %s", output_path)

            return {
                "success": True,
                "changed": has_changed,
                "file_path": output_path,
                "backup_path": backup_path,
                "hash": new_hash,
            }

        except Exception:
            self.logger.exception("Error en download_and_check")
            return {
                "success": False,
                "changed": False,
                "error": "Error inesperado (ver logs)",
            }

    def _download_content(self) -> str:
        """
        Descarga el contenido de la lista IPTV.

        Usa proxy SOCKS5 de WARP si está disponible.

        Returns:
            Contenido del archivo como string.

        Raises:
            requests.RequestException: Si hay error en la descarga.
        """
        proxies = {"http": _WARP_PROXY, "https": _WARP_PROXY}
        headers = {"User-Agent": _DEFAULT_USER_AGENT}

        try:
            response = requests.get(
                self.config.list_url,
                timeout=self.config.download_timeout,
                proxies=proxies,
                headers=headers,
            )
        except requests.exceptions.ProxyError:
            self.logger.warning("Proxy WARP no disponible, descargando sin proxy")
            response = requests.get(
                self.config.list_url,
                timeout=self.config.download_timeout,
                headers=headers,
            )

        response.raise_for_status()

        if response.encoding:
            return response.text
        return response.content.decode("utf-8", errors="replace")

    def _save_content(self, content: str, file_path: Path) -> None:
        """Guarda contenido en un archivo."""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _create_backup(self, file_path: Path) -> Path:
        """Crea un backup del archivo en la carpeta olds/."""
        timestamp = datetime.now().strftime("%Y-%m-%d")
        backup_name = "%s_%s%s" % (file_path.stem, timestamp, file_path.suffix)
        backup_path = self.config.olds_dir / backup_name

        counter = 1
        while backup_path.exists():
            backup_name = "%s_%s_%d%s" % (
                file_path.stem,
                timestamp,
                counter,
                file_path.suffix,
            )
            backup_path = self.config.olds_dir / backup_name
            counter += 1

        shutil.copy2(file_path, backup_path)
        return backup_path

    def get_current_status(self) -> dict:
        """Obtiene el estado actual de la lista."""
        output_path = self.config.get_output_path()

        if not output_path.exists():
            return {
                "current_file": output_path,
                "exists": False,
                "backup_count": self._count_backups(),
            }

        info = get_file_info(output_path)
        info["backup_count"] = self._count_backups()
        return info

    def _count_backups(self) -> int:
        """Cuenta el número de backups disponibles."""
        if not self.config.olds_dir.exists():
            return 0
        return len(list(self.config.olds_dir.glob("*.m3u")))

    def clean_old_files(
        self,
        keep: int = 5,
        dry_run: bool = False,
    ) -> dict:
        """Limpia archivos antiguos de la carpeta olds/."""
        if not self.config.olds_dir.exists():
            return {
                "deleted_count": 0,
                "kept_count": 0,
                "deleted_files": [],
            }

        files = list(self.config.olds_dir.glob("*.m3u"))
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        files_to_keep = files[:keep]
        files_to_delete = files[keep:]

        deleted_files: list[str] = []

        if not dry_run:
            for file in files_to_delete:
                try:
                    file.unlink()
                    deleted_files.append(file.name)
                    self.logger.debug("Eliminado: %s", file.name)
                except OSError as exc:
                    self.logger.error("Error eliminando %s: %s", file.name, exc)
        else:
            deleted_files = [f.name for f in files_to_delete]

        return {
            "deleted_count": len(deleted_files),
            "kept_count": len(files_to_keep),
            "deleted_files": deleted_files,
        }

    def get_backup_list(self) -> list[dict]:
        """Obtiene la lista de backups disponibles."""
        if not self.config.olds_dir.exists():
            return []

        backups = []
        for file in self.config.olds_dir.glob("*.m3u"):
            info = get_file_info(file)
            backups.append(info)

        backups.sort(key=lambda x: x["last_modified"], reverse=True)
        return backups
