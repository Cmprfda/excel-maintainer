import subprocess
import sys
import os
import time
import threading
import logging

logger = logging.getLogger(__name__)

_update_lock = threading.Lock()


def _fetch_tags(base_dir):
    return subprocess.run(
        ['git', 'fetch', 'origin', '--tags', '--quiet'],
        cwd=base_dir, capture_output=True, text=True, timeout=10
    )


def _latest_tag_state(base_dir):
    """Return (latest_tag, up_to_date) from the local tag list. latest_tag is None when no tags exist.
    up_to_date is True when the tag's commit is already an ancestor of HEAD — not just equal to it —
    so a working tree sitting on unreleased commits ahead of the last tag (the normal state of a dev
    checkout between releases) is correctly treated as up to date rather than "behind"."""
    result = subprocess.run(
        ['git', 'tag', '--sort=-version:refname'],
        cwd=base_dir, capture_output=True, text=True, timeout=5
    )
    tags = [t.strip() for t in result.stdout.strip().splitlines() if t.strip()]
    if not tags:
        return None, True

    latest_tag = tags[0]

    tag_commit = subprocess.run(
        ['git', 'rev-list', '-n1', latest_tag],
        cwd=base_dir, capture_output=True, text=True, timeout=5
    ).stdout.strip()

    is_ancestor = subprocess.run(
        ['git', 'merge-base', '--is-ancestor', tag_commit, 'HEAD'],
        cwd=base_dir, timeout=5
    )

    return latest_tag, is_ancestor.returncode == 0


def _pull(base_dir):
    return subprocess.run(
        ['git', 'pull', 'origin', 'master'],
        cwd=base_dir, capture_output=True, text=True, timeout=30
    )


def _restart_soon():
    # Gives the HTTP response time to reach the UI before the process image is replaced.
    time.sleep(0.7)
    os.execv(sys.executable, [sys.executable] + sys.argv)


def check_and_update():
    """Fetch remote tags; if HEAD is not on the latest tag, pull and restart."""
    from maintainer import config
    if config.DEV_MODE:
        return

    base_dir = config.BASE_DIR
    try:
        _fetch_tags(base_dir)

        latest_tag, up_to_date = _latest_tag_state(base_dir)
        if latest_tag is None:
            return  # No releases published yet

        if up_to_date:
            logger.info(f'Already on latest version ({latest_tag}).')
            return

        logger.info(f'New version available: {latest_tag}. Updating...')

        pull = _pull(base_dir)
        if pull.returncode != 0:
            logger.error(f'Auto-update failed: {pull.stderr.strip()}')
            return

        logger.info(f'Updated to {latest_tag}. Restarting...')
        os.execv(sys.executable, [sys.executable] + sys.argv)

    except Exception as e:
        logger.warning(f'Auto-update check skipped: {e}')


def manual_update():
    """User-triggered version of check_and_update(): runs even in DEV_MODE, reports the outcome,
    and restarts from a background thread so the caller can answer the request first."""
    if not _update_lock.acquire(blocking=False):
        return {'error': 'Já existe uma verificação de atualizações em curso.'}

    from maintainer import config
    base_dir = config.BASE_DIR
    try:
        try:
            fetch = _fetch_tags(base_dir)
        except Exception as e:
            logger.error(f'Update fetch failed: {e}')
            return {'error': 'Não foi possível ligar ao servidor de atualizações. Verifique a ligação à internet.'}

        if fetch.returncode != 0:
            logger.error(f'Update fetch failed: {fetch.stderr.strip()}')
            return {'error': 'Não foi possível ligar ao servidor de atualizações. Verifique a ligação à internet.'}

        latest_tag, up_to_date = _latest_tag_state(base_dir)
        if latest_tag is None:
            return {'updated': False, 'up_to_date': True}

        if up_to_date:
            logger.info(f'Already on latest version ({latest_tag}).')
            return {'updated': False, 'up_to_date': True, 'version': latest_tag}

        logger.info(f'New version available: {latest_tag}. Updating...')

        pull = _pull(base_dir)
        if pull.returncode != 0:
            logger.error(f'Manual update failed: {pull.stderr.strip()}')
            return {'error': 'Falha ao aplicar a atualização.'}

        logger.info(f'Updated to {latest_tag}. Restarting...')
        threading.Thread(target=_restart_soon, daemon=True).start()
        return {'updated': True, 'version': latest_tag}

    except Exception as e:
        logger.error(f'Manual update failed: {e}')
        return {'error': str(e)}

    finally:
        _update_lock.release()
