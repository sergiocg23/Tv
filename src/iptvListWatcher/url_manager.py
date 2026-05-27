"""
Gestión de URL override con historial persistente.

Permite cambiar la URL de descarga IPTV en runtime sin reiniciar
el contenedor, usando un fichero JSON en el directorio de salida
(montado como volumen Docker).

Jerarquía de resolución:
  1. url_config.json → active_url (si existe y tiene valor)
  2. Variable de entorno IPTV_LIST_URL (fallback por defecto)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path


logger = logging.getLogger(__name__)

URL_CONFIG_FILENAME = "url_config.json"


@dataclass
class UrlHistoryEntry:
    """Entrada del historial de URLs."""

    url: str
    used_from: str
    used_until: str | None = None
    reason: str = ""

    def to_dict(self) -> dict[str, str | None]:
        return {
            "url": self.url,
            "used_from": self.used_from,
            "used_until": self.used_until,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str | None]) -> UrlHistoryEntry:
        return cls(
            url=str(data.get("url", "")),
            used_from=str(data.get("used_from", "")),
            used_until=data.get("used_until"),
            reason=str(data.get("reason", "")),
        )


@dataclass
class UrlConfig:
    """Configuración de URL con override y historial."""

    active_url: str | None = None
    updated_at: str | None = None
    history: list[UrlHistoryEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "active_url": self.active_url,
            "updated_at": self.updated_at,
            "history": [entry.to_dict() for entry in self.history],
        }

    @classmethod
    def from_dict(cls, data: dict) -> UrlConfig:
        history = [
            UrlHistoryEntry.from_dict(entry) for entry in data.get("history", [])
        ]
        return cls(
            active_url=data.get("active_url"),
            updated_at=data.get("updated_at"),
            history=history,
        )


class UrlManager:
    """Gestiona el override de URL y su historial persistente."""

    def __init__(self, config_dir: Path) -> None:
        self._config_path = config_dir / URL_CONFIG_FILENAME

    @property
    def config_path(self) -> Path:
        return self._config_path

    def load(self) -> UrlConfig:
        """Carga la configuración de URL desde disco."""
        if not self._config_path.exists():
            return UrlConfig()

        try:
            raw = self._config_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            return UrlConfig.from_dict(data)
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning(
                "Error leyendo %s, se ignora el override: %s",
                self._config_path,
                exc,
            )
            return UrlConfig()

    def save(self, config: UrlConfig) -> None:
        """Persiste la configuración de URL a disco."""
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(config.to_dict(), indent=2, ensure_ascii=False)
        self._config_path.write_text(payload + "\n", encoding="utf-8")
        logger.info("URL config guardada en %s", self._config_path)

    def get_active_url(self, env_url: str) -> tuple[str, str]:
        """
        Resuelve la URL activa según la jerarquía de override.

        Args:
            env_url: URL por defecto desde la variable de entorno.

        Returns:
            Tupla (url_activa, fuente) donde fuente es "override" o "env".
        """
        url_config = self.load()

        if url_config.active_url:
            logger.info(
                "Usando URL override: %s (desde %s)",
                url_config.active_url,
                self._config_path.name,
            )
            return url_config.active_url, "override"

        return env_url, "env"

    def set_url(self, new_url: str, reason: str = "") -> UrlConfig:
        """
        Establece una nueva URL override.

        Cierra la entrada previa del historial y crea una nueva.

        Args:
            new_url: Nueva URL a usar.
            reason: Motivo del cambio (opcional).

        Returns:
            UrlConfig actualizada.
        """
        now = _now_iso()
        url_config = self.load()

        # Cerrar la entrada activa del historial
        if url_config.history:
            last = url_config.history[-1]
            if last.used_until is None:
                last.used_until = now

        # Nueva entrada
        url_config.history.append(
            UrlHistoryEntry(
                url=new_url,
                used_from=now,
                reason=reason,
            )
        )

        url_config.active_url = new_url
        url_config.updated_at = now

        self.save(url_config)
        logger.info("URL override establecida: %s", new_url)

        return url_config

    def reset_url(self, reason: str = "") -> UrlConfig:
        """
        Elimina el override y vuelve a usar la URL del .env.

        Args:
            reason: Motivo del reset (opcional).

        Returns:
            UrlConfig actualizada.
        """
        now = _now_iso()
        url_config = self.load()

        if not url_config.active_url:
            logger.info("No hay URL override activa, nada que resetear")
            return url_config

        # Cerrar la entrada activa del historial
        if url_config.history:
            last = url_config.history[-1]
            if last.used_until is None:
                last.used_until = now
                if reason:
                    last.reason = (
                        f"{last.reason} | reset: {reason}"
                        if last.reason
                        else f"reset: {reason}"
                    )

        url_config.active_url = None
        url_config.updated_at = now

        self.save(url_config)
        logger.info("URL override eliminada, se usará la URL del .env")

        return url_config

    def get_history(self) -> list[UrlHistoryEntry]:
        """Devuelve el historial completo de URLs."""
        return self.load().history


def _now_iso() -> str:
    """Timestamp ISO 8601 en UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
