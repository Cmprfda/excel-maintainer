import json
import os
import logging
import webbrowser
import mimetypes
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from maintainer import config, settings, sync

logger = logging.getLogger(__name__)

# Set while the native pywebview window is open; None in browser-fallback mode.
_window = None


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/':
            self._serve_file(os.path.join(config.BASE_DIR, 'index.html'), 'text/html')
        elif path.startswith('/static/'):
            rel = path[len('/static/'):]
            filepath = os.path.join(config.BASE_DIR, 'static', rel.replace('/', os.sep))
            # Prevent path traversal
            real = os.path.realpath(filepath)
            static_root = os.path.realpath(os.path.join(config.BASE_DIR, 'static'))
            if not real.startswith(static_root):
                self._error(403, 'Forbidden')
                return
            content_type, _ = mimetypes.guess_type(filepath)
            self._serve_file(filepath, content_type or 'application/octet-stream')
        elif path == '/api/files':
            self._json_response(sync.list_files())
        elif path == '/api/settings':
            self._handle_get_settings()
        else:
            self._error(404, 'Not Found')

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/api/sync':
            self._handle_sync()
        elif path == '/api/sync-all':
            self._json_response({'results': sync.sync_all()})
        elif path == '/api/settings':
            self._handle_save_settings()
        elif path == '/api/pick-folder':
            self._handle_pick_folder()
        elif path == '/api/update':
            self._handle_update()
        else:
            self._error(404, 'Not Found')

    def _handle_get_settings(self):
        self._json_response({'original_dir': config.ORIGINAL_DIR, 'server_dir': config.SERVER_DIR})

    def _handle_save_settings(self):
        data = self._read_json_body()
        if data is None:
            return

        original_dir = data.get('original_dir')
        server_dir = data.get('server_dir')
        if not isinstance(original_dir, str) or not isinstance(server_dir, str):
            self._json_response({'error': 'Indique as duas pastas.'}, status=400)
            return

        try:
            settings.save(original_dir, server_dir)
        except ValueError as e:
            self._json_response({'error': str(e)}, status=400)
            return
        except Exception as e:
            logger.error(f'Failed to save settings: {e}')
            self._json_response({'error': str(e)}, status=500)
            return

        self._json_response({'original_dir': config.ORIGINAL_DIR, 'server_dir': config.SERVER_DIR})

    def _handle_update(self):
        from maintainer import updater
        result = updater.manual_update()
        self._json_response(result, status=500 if result.get('error') else 200)

    def _handle_pick_folder(self):
        if _window is None:
            # Browser-fallback mode: no native dialog available.
            self._json_response({'error': 'unsupported'})
            return

        try:
            import webview
            result = _window.create_file_dialog(webview.FOLDER_DIALOG)
        except Exception as e:
            logger.error(f'Folder dialog failed: {e}')
            self._json_response({'error': str(e)}, status=500)
            return

        if not result:
            self._json_response({'cancelled': True})
            return

        folder = result[0] if isinstance(result, (list, tuple)) else result
        self._json_response({'path': str(folder)})

    def _handle_sync(self):
        data = self._read_json_body()
        if data is None:
            return

        name = data.get('name')
        if not isinstance(name, str):
            self._json_response({'error': 'Nome de ficheiro inválido.'}, status=400)
            return
        name = name.strip()

        try:
            path = sync.sync_file(name)
        except (ValueError, FileNotFoundError) as e:
            logger.error(f'Sync rejected for {name!r}: {e}')
            self._json_response({'error': str(e)}, status=400)
            return
        except Exception as e:
            logger.error(f'Sync failed for {name!r}: {e}')
            self._json_response({'error': str(e)}, status=500)
            return

        self._json_response({'ok': True, 'path': path})

    def _read_json_body(self):
        """Read and parse a JSON request body. Responds with 400 and returns None on failure."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
            if not isinstance(data, dict):
                raise ValueError('Body must be a JSON object')
            return data
        except Exception as e:
            logger.error(f'Bad request body: {e}')
            self._json_response({'error': 'Pedido inválido.'}, status=400)
            return None

    def _serve_file(self, filepath: str, content_type: str):
        if not os.path.isfile(filepath):
            self._error(404, 'Not Found')
            return
        with open(filepath, 'rb') as f:
            content = f.read()
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _json_response(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, code: int, message: str):
        self.send_response(code)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(message.encode('utf-8'))

    def log_message(self, format, *args):
        logger.info(f'{self.client_address[0]} - {format % args}')


def run():
    global _window
    port = config.SERVER_PORT
    # Threading: a sync request can take a while on large files; a single-threaded
    # server would leave the UI unable to fetch anything else meanwhile.
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    url = f'http://localhost:{port}/'
    logger.info(f'Server running at {url}')

    try:
        import webview
        import threading

        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()

        _window = webview.create_window('Excel Maintainer', url, width=1280, height=800)
        webview.start()
        _window = None
        server.shutdown()
        logger.info('Server stopped')

    except ImportError:
        logger.warning('pywebview not installed — falling back to browser. Run setup.bat to install it.')
        webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            logger.info('Server stopped')
            server.server_close()
