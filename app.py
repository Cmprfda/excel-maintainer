import sys
import os
import logging

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from maintainer import config

config.DEV_MODE = os.environ.get('DEV') == '1'

# Must run before anything reads config.ORIGINAL_DIR / config.SERVER_DIR.
from maintainer import settings
settings.load()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)


def main():
    args = sys.argv[1:]

    if len(args) >= 1 and args[0] == 'sync':
        from maintainer import sync
        name = args[1] if len(args) >= 2 else None
        if name:
            dst = sync.sync_file(name)
            logger.info(f'Synced {name} -> {dst}')
        else:
            results = sync.sync_all()
            for r in results:
                if r['ok']:
                    logger.info(f"Synced {r['name']} -> {r['path']}")
                else:
                    logger.error(f"Failed {r['name']}: {r['error']}")
    else:
        from maintainer.updater import check_and_update
        check_and_update()
        from maintainer.server import run
        run()


if __name__ == '__main__':
    main()
