import io
import os
import zipfile
import logging
from urllib.parse import quote

logger = logging.getLogger(__name__)


def repair(xlsx_bytes: bytes, link_map: list[dict]) -> bytes:
    if not link_map:
        return xlsx_bytes

    src = io.BytesIO(xlsx_bytes)
    dst = io.BytesIO()

    with zipfile.ZipFile(src, 'r') as zin, zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if _should_repair(item.filename):
                text = data.decode('utf-8')
                for entry in link_map:
                    text = text.replace(entry['from'], entry['to'])
                data = text.encode('utf-8')
            zout.writestr(item, data)

    result = dst.getvalue()
    if not zipfile.is_zipfile(io.BytesIO(result)):
        raise RuntimeError('Repaired file is not a valid zip')

    count = len(link_map)
    logger.info(f'Hyperlink repair applied ({count} substitution rules)')
    return result


def build_link_map(original_dir: str, server_dir: str) -> list[dict]:
    """Build substitution pairs that rewrite absolute-path hyperlinks pointing at
    original_dir so they point at server_dir instead, covering the path spellings
    Excel might have stored a local-file hyperlink with (native backslash path,
    forward-slash path, and a percent-encoded file:// URI form)."""
    original_dir = os.path.normpath(original_dir)
    server_dir = os.path.normpath(server_dir)

    def variants(path):
        forward = path.replace('\\', '/')
        return [path, forward, quote(forward, safe='/:')]

    link_map = []
    seen = set()
    for frm, to in zip(variants(original_dir), variants(server_dir)):
        if frm == to or frm in seen:
            continue
        seen.add(frm)
        link_map.append({'from': frm, 'to': to})
    return link_map


def _should_repair(filename: str) -> bool:
    lower = filename.lower()
    if lower.startswith('xl/worksheets/') and lower.endswith('.xml'):
        return True
    if lower == 'xl/sharedstrings.xml':
        return True
    return False
