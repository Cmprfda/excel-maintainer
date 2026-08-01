import json
import os
import logging
import secrets
import webbrowser
import mimetypes
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote

from maintainer import config, files, graph, hyperlinks

logger = logging.getLogger(__name__)

# Set in run() when pywebview is available; stays None in browser-fallback mode.
_window = None


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == '/':
            # Auth callback lands here when Microsoft redirects back with ?code=
            if 'code' in query:
                self._handle_auth_callback(query)
                return
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
            self._handle_api_files()
        elif path == '/api/onedrive/search':
            self._handle_onedrive_search(query)
        elif path == '/api/default-folder':
            self._handle_default_folder()
        elif path == '/api/auth/status':
            self._json_response({'authenticated': graph.is_authenticated()})
        elif path == '/auth/login':
            self._handle_auth_login()
        else:
            self._error(404, 'Not Found')

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/api/save':
            self._handle_save()
        elif path == '/api/files':
            self._handle_add_file()
        elif path == '/api/pick-folder':
            self._handle_pick_folder()
        else:
            self._error(404, 'Not Found')

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith('/api/files/'):
            file_id = unquote(path[len('/api/files/'):]).strip('/')
            self._handle_remove_file(file_id)
        else:
            self._error(404, 'Not Found')

    def _handle_api_files(self):
        all_files = files.load_files()
        safe = []
        for f in all_files:
            safe.append({
                'id': f.get('id'),
                'label': f.get('label'),
                'onedrive_embed_url': f.get('onedrive_embed_url'),
                'local_path': f.get('local_path'),
            })
        self._json_response(safe)

    def _handle_onedrive_search(self, query: dict):
        term = (query.get('q', [''])[0] or '').strip()
        if not term:
            self._json_response({'error': 'Escreva parte do nome do ficheiro.'}, status=400)
            return

        try:
            if not graph.is_authenticated():
                self._json_response({'error': 'not_authenticated'}, status=401)
                return
            if term.lower().startswith(('http://', 'https://')):
                # A pasted share link resolves directly, bypassing the search index.
                results = [graph.resolve_share_link(term)]
            else:
                results = graph.search_files(term)
        except Exception as e:
            logger.error(f'OneDrive search failed: {e}')
            self._json_response({'error': str(e)}, status=500)
            return

        self._json_response(results)

    def _handle_add_file(self):
        data = self._read_json_body()
        if data is None:
            return

        item_id = (data.get('onedrive_item_id') or '').strip()
        name = (data.get('name') or '').strip()
        label = (data.get('label') or '').strip() or name or item_id
        local_path = (data.get('local_path') or '').strip()

        if not item_id:
            self._json_response({'error': 'Nenhum ficheiro do OneDrive selecionado.'}, status=400)
            return
        if not local_path:
            self._json_response({'error': 'Indique onde guardar o ficheiro no computador.'}, status=400)
            return

        # A folder was given instead of a full file path — append the file name.
        if name and (local_path.endswith(('\\', '/')) or os.path.isdir(local_path)):
            local_path = os.path.join(local_path, name)
        local_path = os.path.abspath(local_path)

        try:
            if not graph.is_authenticated():
                self._json_response({'error': 'not_authenticated'}, status=401)
                return
        except Exception as e:
            logger.error(f'Auth check failed: {e}')
            self._json_response({'error': str(e)}, status=500)
            return

        # Reject duplicates before touching Graph sharing permissions.
        if files.get_file(item_id):
            self._json_response(
                {'error': 'Este ficheiro já está na lista.'}, status=409)
            return

        try:
            embed_url = graph.create_embed_link(item_id)
        except Exception as e:
            logger.error(f'Embed link creation failed for {item_id}: {e}')
            self._json_response(
                {'error': f'Não foi possível criar a ligação de visualização: {e}'},
                status=502)
            return

        record = {
            'id': item_id,
            'label': label,
            'name': name,
            'onedrive_item_id': item_id,
            'onedrive_embed_url': embed_url,
            'local_path': local_path,
            'link_map': [],
        }

        try:
            files.add_file(record)
        except files.DuplicateFileError as e:
            logger.warning(f'Duplicate file rejected: {e}')
            self._json_response({'error': 'Este ficheiro já está na lista.'}, status=409)
            return
        except Exception as e:
            logger.error(f'Failed to add file {item_id}: {e}')
            self._json_response({'error': str(e)}, status=500)
            return

        self._json_response(record, status=201)

    def _handle_remove_file(self, file_id: str):
        if not file_id:
            self._json_response({'error': 'Ficheiro não indicado.'}, status=400)
            return

        try:
            removed = files.remove_file(file_id)
        except Exception as e:
            logger.error(f'Failed to remove file {file_id}: {e}')
            self._json_response({'error': str(e)}, status=500)
            return

        if not removed:
            self._json_response({'error': 'Ficheiro não encontrado.'}, status=404)
            return

        self.send_response(204)
        self.end_headers()

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

    def _handle_default_folder(self):
        home = os.path.expanduser('~')
        documents = os.path.join(home, 'Documents')
        self._json_response({'path': documents if os.path.isdir(documents) else home})

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

    def _handle_auth_login(self):
        state = secrets.token_urlsafe(32)
        auth_url, _ = graph.get_auth_url(state)
        self.send_response(302)
        self.send_header('Location', auth_url)
        self.end_headers()

    def _handle_auth_callback(self, query: dict):
        code = query.get('code', [None])[0]
        state = query.get('state', [None])[0]
        if not code or not state:
            self._error(400, 'Missing code or state')
            return
        try:
            graph.exchange_code(code, state)
            self.send_response(302)
            self.send_header('Location', '/')
            self.end_headers()
        except Exception as e:
            logger.error(f'Auth callback error: {e}')
            self._error(500, str(e))

    def _handle_save(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
        except Exception as e:
            logger.error(f'Bad request body: {e}')
            self._json_response({'error': 'Invalid request body'}, status=400)
            return

        file_id = data.get('id')
        if not file_id:
            self._json_response({'error': 'Missing file id'}, status=400)
            return

        try:
            if not graph.is_authenticated():
                self._json_response({'error': 'not_authenticated'}, status=401)
                return
        except Exception as e:
            logger.error(f'Auth check failed: {e}')
            self._json_response({'error': str(e)}, status=500)
            return

        record = files.get_file(file_id)
        if not record:
            self._json_response({'error': 'File not found'}, status=404)
            return

        try:
            item_id = record.get('onedrive_item_id')
            if not item_id:
                raise ValueError('No onedrive_item_id configured for this file')

            xlsx_bytes = graph.download_file(item_id)

            link_map = record.get('link_map', [])
            repaired = hyperlinks.repair(xlsx_bytes, link_map)

            local_path = record.get('local_path')
            if not local_path:
                raise ValueError('No local_path configured for this file')

            os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
            with open(local_path, 'wb') as f:
                f.write(repaired)

            logger.info(f'Saved file {file_id} to {local_path}')
            self._json_response({'ok': True, 'path': local_path})

        except Exception as e:
            logger.error(f'Save failed for {file_id}: {e}')
            self._json_response({'error': str(e)}, status=500)

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
    # Threading: the native folder dialog (/api/pick-folder) blocks its handler
    # thread until dismissed; a single-threaded server would freeze the whole UI.
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    url = f'http://localhost:{port}/'
    logger.info(f'Server running at {url}')

    try:
        import webview
        import threading

        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()

        # Keep the reference so /api/pick-folder can open a native dialog.
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
