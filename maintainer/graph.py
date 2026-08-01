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
