import os
import logging

from maintainer import config, hyperlinks

logger = logging.getLogger(__name__)


def _resolve_within(root: str, rel_path: str) -> str:
    """Resolve rel_path (forward-slash-separated) against root, guaranteeing the result stays inside
    root. Raises ValueError on anything traversal-shaped, absolute, or not ending in .xlsx."""
    if not isinstance(rel_path, str) or not rel_path or not rel_path.lower().endswith('.xlsx'):
        raise ValueError('Nome de ficheiro inválido.')

    normalized = rel_path.replace('/', os.sep)
    if os.path.isabs(normalized):
        raise ValueError('Nome de ficheiro inválido.')

    root = os.path.realpath(root)
    candidate = os.path.realpath(os.path.join(root, normalized))

    try:
        common = os.path.commonpath([root, candidate])
    except ValueError:
        # Different drives on Windows, etc. — definitely not "within root".
        raise ValueError('Nome de ficheiro inválido.')

    if common != root:
        raise ValueError('Nome de ficheiro inválido.')

    return candidate


def list_files() -> list[dict]:
    """Recursively list every .xlsx under ORIGINAL_DIR, each with its sync status against SERVER_DIR.
    'name' is a '/'-separated path relative to ORIGINAL_DIR (may include subfolders)."""
    root = config.ORIGINAL_DIR
    if not os.path.isdir(root):
        return []

    entries = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith('.')]
        for name in filenames:
            if not name.lower().endswith('.xlsx'):
                continue

            original_path = os.path.join(dirpath, name)
            rel_path = os.path.relpath(original_path, root).replace(os.sep, '/')
            server_path = os.path.join(config.SERVER_DIR, rel_path.replace('/', os.sep))

            try:
                original_mtime = os.path.getmtime(original_path)
                server_mtime = os.path.getmtime(server_path) if os.path.isfile(server_path) else None
            except OSError as e:
                logger.warning(f'Skipping {rel_path}: {e}')
                continue

            if server_mtime is None:
                status = 'new'
            elif server_mtime >= original_mtime:
                status = 'synced'
            else:
                status = 'outdated'

            entries.append({
                'name': rel_path,
                'status': status,
                'original_modified': original_mtime,
                'server_modified': server_mtime,
            })

    entries.sort(key=lambda e: e['name'].lower())
    return entries


def sync_file(rel_path: str) -> str:
    """Copy one file from ORIGINAL_DIR to SERVER_DIR (mirroring its subfolder path), repairing
    hyperlinks. Returns the destination path."""
    src = _resolve_within(config.ORIGINAL_DIR, rel_path)
    if not os.path.isfile(src):
        raise FileNotFoundError(f'Ficheiro não encontrado na pasta original: {rel_path}')

    with open(src, 'rb') as f:
        data = f.read()

    link_map = hyperlinks.build_link_map(config.ORIGINAL_DIR, config.SERVER_DIR)
    repaired = hyperlinks.repair(data, link_map)

    dst = _resolve_within(config.SERVER_DIR, rel_path)
    os.makedirs(os.path.dirname(dst), exist_ok=True)

    # Write to a temp file first and swap it in with an atomic rename, so a process
    # restart (e.g. the update button) or crash mid-write can never leave a truncated
    # file behind in the server folder.
    tmp = dst + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(repaired)
    os.replace(tmp, dst)

    logger.info(f'Synced {rel_path} -> {dst}')
    return dst


def sync_all() -> list[dict]:
    """Sync every file in ORIGINAL_DIR; never raises — each failure is captured per-file."""
    results = []
    for entry in list_files():
        name = entry['name']
        try:
            path = sync_file(name)
            results.append({'name': name, 'ok': True, 'path': path})
        except Exception as e:
            logger.error(f'Sync failed for {name}: {e}')
            results.append({'name': name, 'ok': False, 'error': str(e)})
    return results
