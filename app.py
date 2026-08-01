import sys
import os
import logging

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from maintainer import config

config.DEV_MODE = os.environ.get('DEV') == '1'

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

    if len(args) >= 2 and args[0] == 'download':
        file_id = args[1]
        from maintainer import graph
        token = graph.get_valid_token()
        if not token:
            logger.error('Not authenticated. Run the server and log in first.')
            sys.exit(1)
        data = graph.download_file(file_id)
        out_path = os.path.join(config.BASE_DIR, f'{file_id}.xlsx')
        with open(out_path, 'wb') as f:
            f.write(data)
        logger.info(f'Downloaded {len(data)} bytes to {out_path}')
    else:
        from maintainer.updater import check_and_update
        check_and_update()
        from maintainer.server import run
        run()


if __name__ == '__main__':
    main()
