"""
Parser de archivos M3U con soporte para múltiples formatos.

Estrategia de parsing en 2 niveles:
1. Parseo estricto: formato esperado con #EXTM3U, #EXTGRP, #EXTINF + URL
2. Fallback resiliente: extrae el máximo de canales posibles de cualquier formato
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field


logger = logging.getLogger(__name__)

# --- Regex patterns ---

# #EXTM3U con atributos opcionales (url-tvg="...", refresh="...")
RE_EXTM3U = re.compile(r"^#EXTM3U\b(.*)", re.IGNORECASE)

# #EXTVLCOPT:key=value
RE_VLCOPT = re.compile(r"^#EXTVLCOPT:(.+)", re.IGNORECASE)

# #EXTGRP: group-title="TITULO" group-logo="URL_LOGO"
RE_EXTGRP = re.compile(
    r'^#EXTGRP:\s*group-title="([^"]*)"(?:\s+group-logo="([^"]*)")?',
    re.IGNORECASE,
)

# #EXTINF:-1 tvg-id="..." tvg-logo="..." group-title="...",Nombre canal
RE_EXTINF = re.compile(
    r"^#EXTINF:\s*(-?\d+)\s*(.*?),\s*(.+)$",
    re.IGNORECASE,
)

# URL de stream (http/https, puede ser acestream u otro)
RE_STREAM_URL = re.compile(r"^https?://.+", re.IGNORECASE)

# Acestream URL específica
RE_ACESTREAM = re.compile(
    r"https?://[^/]+(?::\d+)?/ace/getstream\?id=([a-fA-F0-9]+)",
    re.IGNORECASE,
)


@dataclass
class Channel:
    """Representa un canal IPTV."""

    name: str
    url: str
    duration: int = -1
    tvg_id: str = ""
    tvg_logo: str = ""
    group_title: str = ""
    extra_attrs: str = ""

    def to_m3u_line(self) -> str:
        """Genera las líneas #EXTINF + URL para este canal."""
        attrs_parts: list[str] = []
        if self.tvg_id:
            attrs_parts.append(f'tvg-id="{self.tvg_id}"')
        if self.tvg_logo:
            attrs_parts.append(f'tvg-logo="{self.tvg_logo}"')
        if self.group_title:
            attrs_parts.append(f'group-title="{self.group_title}"')
        if self.extra_attrs:
            attrs_parts.append(self.extra_attrs)

        attrs_str = " ".join(attrs_parts)
        if attrs_str:
            attrs_str = " " + attrs_str

        return f"#EXTINF:{self.duration}{attrs_str},{self.name}\n{self.url}"


@dataclass
class GroupDef:
    """Definición de un grupo (#EXTGRP)."""

    title: str
    logo: str = ""

    def to_m3u_line(self) -> str:
        """Genera la línea #EXTGRP."""
        parts = f'group-title="{self.title}"'
        if self.logo:
            parts += f' group-logo="{self.logo}"'
        return f"#EXTGRP: {parts}"


@dataclass
class M3UPlaylist:
    """Representa un archivo M3U parseado."""

    header: str = "#EXTM3U"
    vlc_opts: list[str] = field(default_factory=list)
    groups: list[GroupDef] = field(default_factory=list)
    channels: list[Channel] = field(default_factory=list)
    parse_mode: str = "strict"  # "strict" o "fallback"
    raw_lines_skipped: int = 0

    @property
    def channel_count(self) -> int:
        return len(self.channels)

    def to_m3u(self) -> str:
        """Reconstruye el archivo M3U completo."""
        lines: list[str] = [self.header]

        for opt in self.vlc_opts:
            lines.append(f"#EXTVLCOPT:{opt}")

        if self.vlc_opts or self.groups:
            lines.append("")  # línea en blanco separadora

        for group in self.groups:
            lines.append(group.to_m3u_line())

        if self.groups:
            lines.append("")  # línea en blanco separadora

        for channel in self.channels:
            lines.append(channel.to_m3u_line())

        # Terminar con newline
        return "\n".join(lines) + "\n"

    def replace_ip(self, old_ip: str, new_ip: str) -> None:
        """Reemplaza una IP en todas las URLs de los canales."""
        for channel in self.channels:
            channel.url = channel.url.replace(old_ip, new_ip)


def _parse_extinf_attrs(attrs_str: str) -> dict[str, str]:
    """
    Extrae atributos key="value" de una línea #EXTINF.

    Ejemplo: 'tvg-id="DAZN 1 HD" tvg-logo="url" group-title="DAZN"'
    """
    result: dict[str, str] = {}
    for match in re.finditer(r'([\w-]+)="([^"]*)"', attrs_str):
        result[match.group(1)] = match.group(2)
    return result


def parse_strict(content: str) -> M3UPlaylist | None:
    """
    Parseo estricto del formato M3U esperado.

    Formato esperado:
    - Línea 1: #EXTM3U con atributos opcionales
    - Opcionales: #EXTVLCOPT:...
    - Opcionales: #EXTGRP: group-title="..." group-logo="..."
    - Pares: #EXTINF:... + URL

    Returns:
        M3UPlaylist si el formato es válido, None si no lo es
    """
    lines = content.strip().split("\n")
    if not lines:
        return None

    # Verificar cabecera
    header_match = RE_EXTM3U.match(lines[0].strip())
    if not header_match:
        return None

    playlist = M3UPlaylist(
        header=lines[0].strip(),
        parse_mode="strict",
    )

    i = 1
    total_lines = len(lines)

    # Parsear VLC opts y grupos (van antes de los canales)
    while i < total_lines:
        line = lines[i].strip()
        i += 1

        if not line:
            continue

        vlc_match = RE_VLCOPT.match(line)
        if vlc_match:
            playlist.vlc_opts.append(vlc_match.group(1).strip())
            continue

        grp_match = RE_EXTGRP.match(line)
        if grp_match:
            playlist.groups.append(
                GroupDef(
                    title=grp_match.group(1),
                    logo=grp_match.group(2) or "",
                )
            )
            continue

        # Si encontramos un #EXTINF, retrocedemos para procesarlo en el bucle de canales
        if line.startswith("#EXTINF"):
            i -= 1
            break

        # Línea desconocida antes de canales — en modo estricto, la ignoramos
        # pero la contamos
        playlist.raw_lines_skipped += 1

    # Parsear canales (#EXTINF + URL)
    while i < total_lines:
        line = lines[i].strip()
        i += 1

        if not line:
            continue

        extinf_match = RE_EXTINF.match(line)
        if not extinf_match:
            playlist.raw_lines_skipped += 1
            continue

        duration = int(extinf_match.group(1))
        attrs_raw = extinf_match.group(2).strip()
        name = extinf_match.group(3).strip()

        attrs = _parse_extinf_attrs(attrs_raw)

        # Buscar la URL en la siguiente línea no vacía
        url = ""
        while i < total_lines:
            next_line = lines[i].strip()
            i += 1
            if not next_line:
                continue
            if RE_STREAM_URL.match(next_line):
                url = next_line
                break
            # Si encontramos otro #EXTINF sin URL previa, canal huérfano
            if next_line.startswith("#EXTINF"):
                i -= 1
                break
            # Línea desconocida entre EXTINF y URL, la saltamos
            playlist.raw_lines_skipped += 1

        if url:
            playlist.channels.append(
                Channel(
                    name=name,
                    url=url,
                    duration=duration,
                    tvg_id=attrs.get("tvg-id", ""),
                    tvg_logo=attrs.get("tvg-logo", ""),
                    group_title=attrs.get("group-title", ""),
                )
            )

    return playlist


def parse_fallback(content: str) -> M3UPlaylist:
    """
    Parseo resiliente: extrae el máximo de canales posibles
    de cualquier formato de texto.

    Estrategia:
    1. Busca pares #EXTINF + URL
    2. Busca URLs de acestream sueltas
    3. Busca cualquier URL http(s) que parezca un stream

    Returns:
        M3UPlaylist con los canales rescatados
    """
    playlist = M3UPlaylist(
        header="#EXTM3U",
        parse_mode="fallback",
    )

    lines = content.strip().split("\n")
    total_lines = len(lines)
    rescued_urls: set[str] = set()  # Evitar duplicados

    # Preservar cabecera si existe
    if lines and RE_EXTM3U.match(lines[0].strip()):
        playlist.header = lines[0].strip()

    # Paso 1: Buscar pares #EXTINF + URL
    i = 0
    while i < total_lines:
        line = lines[i].strip()
        i += 1

        extinf_match = RE_EXTINF.match(line)
        if not extinf_match:
            continue

        duration = int(extinf_match.group(1))
        attrs_raw = extinf_match.group(2).strip()
        name = extinf_match.group(3).strip()
        attrs = _parse_extinf_attrs(attrs_raw)

        # Buscar URL en las siguientes 3 líneas (tolerancia)
        url = ""
        lookahead = min(i + 3, total_lines)
        for j in range(i, lookahead):
            candidate = lines[j].strip()
            if RE_STREAM_URL.match(candidate):
                url = candidate
                i = j + 1
                break

        if url and url not in rescued_urls:
            rescued_urls.add(url)
            playlist.channels.append(
                Channel(
                    name=name,
                    url=url,
                    duration=duration,
                    tvg_id=attrs.get("tvg-id", ""),
                    tvg_logo=attrs.get("tvg-logo", ""),
                    group_title=attrs.get("group-title", "") or "OTROS",
                )
            )

    # Paso 2: Buscar URLs de acestream sueltas (sin #EXTINF previo)
    for line in lines:
        line = line.strip()
        if not RE_STREAM_URL.match(line):
            continue
        if line in rescued_urls:
            continue

        ace_match = RE_ACESTREAM.match(line)
        if ace_match:
            stream_id = ace_match.group(1)
            rescued_urls.add(line)
            playlist.channels.append(
                Channel(
                    name=f"Acestream {stream_id[:8]}",
                    url=line,
                    group_title="OTROS",
                )
            )

    playlist.raw_lines_skipped = total_lines - (len(playlist.channels) * 2)

    return playlist


def parse_m3u(content: str) -> M3UPlaylist:
    """
    Parsea contenido M3U con fallback resiliente.

    1. Intenta parseo estricto
    2. Si falla o no encuentra canales, usa fallback
    3. Logea el resultado y estadísticas

    Args:
        content: Contenido raw del archivo M3U

    Returns:
        M3UPlaylist con los canales parseados
    """
    # Intentar parseo estricto
    strict_result = parse_strict(content)

    if strict_result and strict_result.channel_count > 0:
        logger.info(
            "Parseo estricto OK: %d canales, %d grupos, %d líneas ignoradas",
            strict_result.channel_count,
            len(strict_result.groups),
            strict_result.raw_lines_skipped,
        )
        return strict_result

    # Fallback resiliente
    logger.warning(
        "Parseo estricto falló (canales=%d). Usando fallback resiliente...",
        strict_result.channel_count if strict_result else 0,
    )

    fallback_result = parse_fallback(content)

    if fallback_result.channel_count > 0:
        logger.warning(
            "Fallback rescató %d canales de %d líneas totales",
            fallback_result.channel_count,
            len(content.strip().split("\n")),
        )
    else:
        logger.error(
            "No se pudieron extraer canales del contenido (%d líneas)",
            len(content.strip().split("\n")),
        )

    return fallback_result
