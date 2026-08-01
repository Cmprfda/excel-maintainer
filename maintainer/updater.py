import subprocess
import sys
import os
import logging

logger = logging.getLogger(__name__)


def check_and_update():
    """Fetch remote tags; if HEAD is not on the latest tag, pull and restart."""
    from maintainer import config
    if config.DEV_MODE:
        return

    base_dir = config.BASE_DIR
    try:
        subprocess.run(
            ['git', 'fetch', 'origin', '--tags', '--quiet'],
            cwd=base_dir, capture_output=True, timeout=10
        )

        result = subprocess.run(
            ['git', 'tag', '--sort=-version:refname'],
            cwd=base_dir, capture_output=True, text=True, timeout=5
        )
        tags = [t.strip() for t in result.stdout.strip().splitlines() if t.strip()]
        if not tags:
            return  # No releases published yet

        latest_tag = tags[0]

        tag_commit = subprocess.run(
            ['git', 'rev-list', '-n1', latest_tag],
            cwd=base_dir, capture_output=True, text=True, timeout=5
        ).stdout.strip()

        head_commit = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=base_dir, capture_output=True, text=True, timeout=5
        ).stdout.strip()

        if tag_commit == head_commit:
            logger.info(f'Already on latest version ({latest_tag}).')
            return

        logger.info(f'New version available: {latest_tag}. Updating...')

        pull = subprocess.run(
            ['git', 'pull', 'origin', 'master'],
            cwd=base_dir, capture_output=True, text=True, timeout=30
        )
        if pull.returncode != 0:
            logger.error(f'Auto-update failed: {pull.stderr.strip()}')
            return

        logger.info(f'Updated to {latest_tag}. Restarting...')
        os.execv(sys.executable, [sys.executable] + sys.argv)

    except Exception as e:
        logger.warning(f'Auto-update check skipped: {e}')
