"""
Lógica principal del watcher de listas IPTV
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests

from iptvListWatcher.config import Config
from iptvListWatcher.utils import (
    calculate_file_hash,
    calculate_content_hash,
    replace_ip_in_content,
    get_file_info
)


class IPTVWatcher:
    """Clase principal para monitorear y gestionar listas IPTV."""
    
    def __init__(self, config: Config, logger: Optional[logging.Logger] = None):
        """
        Inicializa el watcher.
        
        Args:
            config: Configuración del watcher
            logger: Logger opcional (se crea uno por defecto si no se proporciona)
        """
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        
        # Validar configuración
        self.config.validate()
        
        # Asegurar que los directorios existen
        self.config.ensure_directories()
    
    def download_and_check(
        self,
        force: bool = False,
        create_backup: bool = True
    ) -> Dict:
        """
        Descarga la lista IPTV, reemplaza IPs y detecta cambios.
        
        Args:
            force: Si es True, guarda el archivo aunque no haya cambios
            create_backup: Si es True, crea backup del archivo anterior
            
        Returns:
            Diccionario con el resultado:
            {
                'success': bool,
                'changed': bool,
                'file_path': Path,
                'backup_path': Path (opcional),
                'hash': str,
                'error': str (opcional)
            }
        """
        try:
            # Descargar contenido
            self.logger.info(f"Descargando lista desde: {self.config.list_url}")
            content = self._download_content()
            
            # Reemplazar IPs
            self.logger.debug(
                f"Reemplazando {self.config.generic_ip} por {self.config.host_ip}"
            )
            content = replace_ip_in_content(
                content,
                self.config.generic_ip,
                self.config.host_ip
            )
            
            # Calcular hash del nuevo contenido
            new_hash = calculate_content_hash(content)
            self.logger.debug(f"Hash del nuevo contenido: {new_hash}")
            
            # Verificar si hay cambios
            output_path = self.config.get_output_path()
            has_changed = True
            
            if output_path.exists():
                old_hash = calculate_file_hash(output_path)
                self.logger.debug(f"Hash del archivo actual: {old_hash}")
                has_changed = (new_hash != old_hash)
            else:
                self.logger.info("No existe archivo anterior")
            
            # Si no hay cambios y no es forzado, no hacer nada
            if not has_changed and not force:
                self.logger.info("No hay cambios en la lista")
                return {
                    'success': True,
                    'changed': False,
                    'file_path': output_path,
                    'hash': new_hash
                }
            
            # Crear backup si es necesario
            backup_path = None
            if create_backup and output_path.exists() and has_changed:
                backup_path = self._create_backup(output_path)
                self.logger.info(f"Backup creado: {backup_path}")
            
            # Guardar nuevo archivo
            self._save_content(content, output_path)
            self.logger.info(f"Lista guardada: {output_path}")
            
            return {
                'success': True,
                'changed': has_changed,
                'file_path': output_path,
                'backup_path': backup_path,
                'hash': new_hash
            }
            
        except Exception as e:
            self.logger.exception(f"Error en download_and_check: {e}")
            return {
                'success': False,
                'changed': False,
                'error': str(e)
            }
    
    def _download_content(self) -> str:
        """
        Descarga el contenido de la lista IPTV.
        Usa proxy SOCKS5 de WARP si está disponible.
        
        Returns:
            Contenido del archivo como string
            
        Raises:
            requests.RequestException: Si hay error en la descarga
        """
        # Configurar proxy SOCKS5 de WARP si está disponible
        proxies = {
            'http': 'socks5h://warp:9091',
            'https': 'socks5h://warp:9091'
        }
        
        try:
            response = requests.get(
                self.config.list_url,
                timeout=self.config.download_timeout,
                proxies=proxies,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
                }
            )
        except requests.exceptions.ProxyError:
            # Si falla el proxy, intentar sin él
            self.logger.warning("Proxy WARP no disponible, descargando sin proxy")
            response = requests.get(
                self.config.list_url,
                timeout=self.config.download_timeout,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
                }
            )
        
        response.raise_for_status()
        
        # Intentar detectar encoding
        if response.encoding:
            content = response.text
        else:
            # Por defecto UTF-8
            content = response.content.decode('utf-8', errors='replace')
        
        return content
    
    def _save_content(self, content: str, file_path: Path) -> None:
        """
        Guarda contenido en un archivo.
        
        Args:
            content: Contenido a guardar
            file_path: Ruta del archivo
        """
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _create_backup(self, file_path: Path) -> Path:
        """
        Crea un backup del archivo en la carpeta olds/.
        
        Args:
            file_path: Ruta del archivo a respaldar
            
        Returns:
            Ruta del archivo de backup
        """
        # Generar nombre con timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d')
        backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
        backup_path = self.config.olds_dir / backup_name
        
        # Si ya existe un backup con el mismo nombre, agregar contador
        counter = 1
        while backup_path.exists():
            backup_name = f"{file_path.stem}_{timestamp}_{counter}{file_path.suffix}"
            backup_path = self.config.olds_dir / backup_name
            counter += 1
        
        # Copiar archivo
        shutil.copy2(file_path, backup_path)
        
        return backup_path
    
    def get_current_status(self) -> Dict:
        """
        Obtiene el estado actual de la lista.
        
        Returns:
            Diccionario con información del estado actual
        """
        output_path = self.config.get_output_path()
        
        if not output_path.exists():
            return {
                'current_file': output_path,
                'exists': False,
                'backup_count': self._count_backups()
            }
        
        info = get_file_info(output_path)
        info['backup_count'] = self._count_backups()
        
        return info
    
    def _count_backups(self) -> int:
        """Cuenta el número de backups disponibles."""
        if not self.config.olds_dir.exists():
            return 0
        
        return len(list(self.config.olds_dir.glob('*.m3u')))
    
    def clean_old_files(
        self,
        keep: int = 5,
        dry_run: bool = False
    ) -> Dict:
        """
        Limpia archivos antiguos de la carpeta olds/.
        
        Args:
            keep: Número de archivos a mantener
            dry_run: Si es True, no elimina archivos (solo simula)
            
        Returns:
            Diccionario con información de la limpieza
        """
        if not self.config.olds_dir.exists():
            return {
                'deleted_count': 0,
                'kept_count': 0,
                'deleted_files': []
            }
        
        # Obtener todos los archivos .m3u ordenados por fecha de modificación
        files = list(self.config.olds_dir.glob('*.m3u'))
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        
        # Determinar qué archivos eliminar
        files_to_keep = files[:keep]
        files_to_delete = files[keep:]
        
        deleted_files = []
        
        if not dry_run:
            for file in files_to_delete:
                try:
                    file.unlink()
                    deleted_files.append(file.name)
                    self.logger.debug(f"Eliminado: {file.name}")
                except Exception as e:
                    self.logger.error(f"Error eliminando {file.name}: {e}")
        else:
            deleted_files = [f.name for f in files_to_delete]
        
        return {
            'deleted_count': len(deleted_files),
            'kept_count': len(files_to_keep),
            'deleted_files': deleted_files
        }
    
    def get_backup_list(self) -> List[Dict]:
        """
        Obtiene la lista de backups disponibles.
        
        Returns:
            Lista de diccionarios con información de cada backup
        """
        if not self.config.olds_dir.exists():
            return []
        
        backups = []
        for file in self.config.olds_dir.glob('*.m3u'):
            info = get_file_info(file)
            backups.append(info)
        
        # Ordenar por fecha de modificación (más reciente primero)
        backups.sort(key=lambda x: x['last_modified'], reverse=True)
        
        return backups
