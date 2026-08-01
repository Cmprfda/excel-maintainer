import hashlib
import base64
import secrets
import json
import time
import logging
import urllib.parse

import requests

from maintainer import config

logger = logging.getLogger(__name__)

CLIENT_ID = '04b07795-8ddb-461a-bbee-02f9e1bf7b46'
SCOPE = 'https://graph.microsoft.com/.default'
AUTH_URL = 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize'
TOKEN_URL = 'https://login.microsoftonline.com/common/oauth2/v2.0/token'
REDIRECT_URI = f'http://localhost:{config.SERVER_PORT}'

# In-memory store: state -> code_verifier
_pending_states: dict[str, str] = {}


def _generate_pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode('ascii')).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')
    return verifier, challenge


def get_auth_url(state: str) -> tuple[str, str]:
    verifier, challenge = _generate_pkce()
    _pending_states[state] = verifier
    params = {
        'client_id': CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': REDIRECT_URI,
        'scope': SCOPE,
        'state': state,
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
    }
    url = AUTH_URL + '?' + urllib.parse.urlencode(params)
    return url, verifier


def exchange_code(code: str, state: str) -> dict:
    verifier = _pending_states.pop(state, None)
    if not verifier:
        raise ValueError('Unknown or expired state')
    data = {
        'client_id': CLIENT_ID,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI,
        'code_verifier': verifier,
        'scope': SCOPE,
    }
    resp = requests.post(TOKEN_URL, data=data)
    resp.raise_for_status()
    token_data = resp.json()
    token_data['obtained_at'] = time.time()
    _save_token(token_data)
    logger.info('Graph token obtained successfully')
    return token_data


def get_valid_token() -> str | None:
    token_data = _load_token()
    if not token_data:
        return None
    expires_in = token_data.get('expires_in', 3600)
    obtained_at = token_data.get('obtained_at', 0)
    expires_at = obtained_at + expires_in
    if time.time() > expires_at - 300:
        if 'refresh_token' in token_data:
            try:
                token_data = refresh_token(token_data)
            except Exception as e:
                logger.error(f'Token refresh failed: {e}')
                return None
        else:
            return None
    return token_data.get('access_token')


def refresh_token(token_data: dict) -> dict:
    data = {
        'client_id': CLIENT_ID,
        'grant_type': 'refresh_token',
        'refresh_token': token_data['refresh_token'],
        'scope': SCOPE,
    }
    resp = requests.post(TOKEN_URL, data=data)
    resp.raise_for_status()
    new_token = resp.json()
    new_token['obtained_at'] = time.time()
    if 'refresh_token' not in new_token:
        new_token['refresh_token'] = token_data['refresh_token']
    _save_token(new_token)
    logger.info('Graph token refreshed')
    return new_token


SEARCHABLE_EXTENSIONS = ('.xlsx', '.xlsm')


def search_files(query: str) -> list[dict]:
    """Search the user's OneDrive for Excel files matching `query`.

    Returns a list of {id, name, path} dicts (path is for display only).
    """
    token = get_valid_token()
    if not token:
        raise RuntimeError('Not authenticated')

    # A literal '/' or '\' breaks Graph's search query grammar; degrade a
    # pasted path-like fragment into a plain multi-word search instead.
    cleaned = query.replace('/', ' ').replace('\\', ' ')
    # OData string literal: single quotes are escaped by doubling them.
    literal = urllib.parse.quote(cleaned.replace("'", "''"), safe='')
    url = f"https://graph.microsoft.com/v1.0/me/drive/root/search(q='{literal}')?$top=50"
    resp = requests.get(url, headers={'Authorization': f'Bearer {token}'})
    if not resp.ok:
        detail = _graph_error(resp)
        logger.error(f'OneDrive search failed for "{query}": {detail}')
        raise RuntimeError(detail)

    results = []
    for item in resp.json().get('value', []):
        if 'file' not in item:
            continue
        name = item.get('name') or ''
        if not name.lower().endswith(SEARCHABLE_EXTENSIONS):
            continue
        results.append(_item_to_result(item))

    logger.info(f'OneDrive search "{query}": {len(results)} Excel file(s)')
    return results


def _item_to_result(item: dict) -> dict:
    """Reduce a Graph driveItem to the {id, name, path} shape the UI uses."""
    raw_path = (item.get('parentReference') or {}).get('path') or ''
    # '/drive/root:/Documents/Sub' -> '/Documents/Sub'
    display_path = raw_path.split(':', 1)[1] if ':' in raw_path else raw_path
    return {
        'id': item.get('id'),
        'name': item.get('name') or '',
        'path': urllib.parse.unquote(display_path) or '/',
    }


def resolve_share_link(url: str) -> dict:
    """Resolve a OneDrive/SharePoint sharing URL to its drive item.

    Uses the Graph shares API, which does not depend on the search index.
    Returns a single {id, name, path} dict.
    """
    token = get_valid_token()
    if not token:
        raise RuntimeError('Not authenticated')

    # Sharing token: base64 of the URL, unpadded, URL-safe alphabet, 'u!' prefix.
    encoded = base64.b64encode(url.encode('utf-8')).decode('ascii')
    encoded = 'u!' + encoded.rstrip('=').replace('/', '_').replace('+', '-')

    api_url = f'https://graph.microsoft.com/v1.0/shares/{encoded}/driveItem'
    resp = requests.get(api_url, headers={'Authorization': f'Bearer {token}'})
    if not resp.ok:
        detail = _graph_error(resp)
        # Improve error message for common cases
        if 'file not found' in detail.lower() or '0x80070002' in detail:
            detail = (
                'A ligação fornecida não parece completa ou não aponta a um ficheiro válido. '
                'Verifique que a ligação termina com um nome de ficheiro (ex: .xlsx) e tente novamente.'
            )
        elif 'accessdenied' in detail.lower():
            detail = (
                'Acesso negado. Verifique que tem permissão para aceder ao ficheiro '
                'e que a ligação está correta. Se for um ficheiro partilhado, '
                'peça que lhe seja reenviada a ligação de partilha.'
            )
        logger.error(f'Share link resolution failed for "{url}": {detail}')
        raise RuntimeError(detail)

    item = resp.json()
    result = _item_to_result(item)
    if 'file' not in item or not result['name'].lower().endswith(SEARCHABLE_EXTENSIONS):
        raise RuntimeError('Este ficheiro não é uma folha de cálculo Excel (.xlsx/.xlsm).')

    logger.info(f'Share link resolved to {result["id"]} ({result["name"]})')
    return result


def create_embed_link(item_id: str) -> str:
    """Create (or fetch) an embed sharing link for a drive item.

    This is a write action on sharing permissions; if the tenant has not
    consented to it the Graph error message is raised verbatim so the user
    or admin can act on it.
    """
    token = get_valid_token()
    if not token:
        raise RuntimeError('Not authenticated')

    url = f'https://graph.microsoft.com/v1.0/me/drive/items/{item_id}/createLink'
    resp = requests.post(
        url,
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        json={'type': 'embed'},
    )
    if not resp.ok:
        detail = _graph_error(resp)
        logger.error(f'createLink failed for {item_id}: {detail}')
        raise RuntimeError(detail)

    web_url = ((resp.json().get('link') or {}).get('webUrl') or '').strip()
    if not web_url:
        raise RuntimeError('Graph did not return an embed webUrl for this file')
    logger.info(f'Embed link created for {item_id}')
    return web_url


def _graph_error(resp) -> str:
    """Extract the most useful error text out of a Graph error response."""
    try:
        err = (resp.json() or {}).get('error') or {}
        message = (err.get('message') or '').strip()
        code = (err.get('code') or '').strip()
        if message and code:
            return f'{code}: {message}'
        if message:
            return message
        if code:
            return code
    except Exception:
        pass
    text = (resp.text or '').strip()
    if text:
        return f'HTTP {resp.status_code} — {text[:300]}'
    return f'HTTP {resp.status_code}'


def download_file(item_id: str) -> bytes:
    token = get_valid_token()
    if not token:
        raise RuntimeError('Not authenticated')
    url = f'https://graph.microsoft.com/v1.0/me/drive/items/{item_id}/content'
    resp = requests.get(url, headers={'Authorization': f'Bearer {token}'}, allow_redirects=True)
    resp.raise_for_status()
    logger.info(f'Downloaded file {item_id}: {len(resp.content)} bytes')
    return resp.content


def is_authenticated() -> bool:
    return get_valid_token() is not None


def _load_token() -> dict | None:
    try:
        with open(config.GRAPH_TOKEN_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _save_token(token_data: dict):
    with open(config.GRAPH_TOKEN_JSON, 'w', encoding='utf-8') as f:
        json.dump(token_data, f, ensure_ascii=False, indent=2)
