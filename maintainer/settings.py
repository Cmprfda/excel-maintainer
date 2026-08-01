import json
import os
import logging
import threading

from maintainer import config

logger = logging.getLogger(__name__)

SETTINGS_JSON = os.path.join(config.BASE_DIR, "paths.json")

_lock = threading.Lock()


def load():
    """Apply persisted original/server dirs onto config.ORIGINAL_DIR/config.SERVER_DIR (falling back to
    the defaults config.py already set at import time), then ensure both directories exist."""
    original_dir, server_dir = config.ORIGINAL_DIR, config.SERVER_DIR

    if os.path.exists(SETTINGS_JSON):
        try:
            with open(SETTINGS_JSON, 'r', encoding='utf-8') as f:
                data = json.load(f)
            original_dir = data.get('original_dir') or original_dir
            server_dir = data.get('server_dir') or server_dir
        except Exception as e:
            logger.error(f'Failed to load {SETTINGS_JSON}: {e}')

    config.ORIGINAL_DIR = original_dir
    config.SERVER_DIR = server_dir
    os.makedirs(config.ORIGINAL_DIR, exist_ok=True)
    os.makedirs(config.SERVER_DIR, exist_ok=True)


def _is_nested(a: str, b: str) -> bool:
    a = os.path.normcase(os.path.normpath(a)) + os.sep
    b = os.path.normcase(os.path.normpath(b)) + os.sep
    return a.startswith(b) or b.startswith(a)


def save(original_dir: str, server_dir: str):
    """Validate, apply, and persist new original/server directories. Raises ValueError on bad input."""
    if not original_dir or not server_dir:
        raise ValueError('Indique as duas pastas.')

    original_dir = os.path.abspath(original_dir)
    server_dir = os.path.abspath(server_dir)

    if _is_nested(original_dir, server_dir):
        raise ValueError('As pastas não podem estar uma dentro da outra.')

    try:
        os.makedirs(original_dir, exist_ok=True)
    except OSError as e:
        raise ValueError(
            f'Não foi possível aceder à pasta original "{original_dir}". '
            'Verifique se o caminho está correto, se tem permissões de acesso e, '
            'no caso de ser uma pasta de rede, se há ligação à rede.'
        ) from e

    try:
        os.makedirs(server_dir, exist_ok=True)
    except OSError as e:
        raise ValueError(
            f'Não foi possível aceder à pasta do servidor "{server_dir}". '
            'Verifique se o caminho está correto, se tem permissões de acesso e, '
            'no caso de ser uma pasta de rede, se há ligação à rede.'
        ) from e

    with _lock:
        config.ORIGINAL_DIR = original_dir
        config.SERVER_DIR = server_dir
        with open(SETTINGS_JSON, 'w', encoding='utf-8') as f:
            json.dump({'original_dir': original_dir, 'server_dir': server_dir}, f, ensure_ascii=False, indent=2)

    logger.info(f'Paths updated: original={original_dir} server={server_dir}')
