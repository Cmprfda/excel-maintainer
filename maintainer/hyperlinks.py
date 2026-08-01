import io
import zipfile
import logging

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


def _should_repair(filename: str) -> bool:
    lower = filename.lower()
    if lower.startswith('xl/worksheets/') and lower.endswith('.xml'):
        return True
    if lower == 'xl/sharedstrings.xml':
        return True
    return False
