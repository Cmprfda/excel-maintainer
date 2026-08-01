import json
import os
import logging
import threading

from maintainer import config

logger = logging.getLogger(__name__)

# The server is threaded, so read-modify-write of files.json must be serialised.
_write_lock = threading.Lock()


def load_files() -> list[dict]:
    if not os.path.exists(config.FILES_JSON):
        return []
    try:
        with open(config.FILES_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f'Failed to load files.json: {e}')
        return []


def save_files(files: list[dict]):
    with open(config.FILES_JSON, 'w', encoding='utf-8') as f:
        json.dump(files, f, ensure_ascii=False, indent=2)


def get_file(file_id: str) -> dict | None:
    for entry in load_files():
        if entry.get('id') == file_id:
            return entry
    return None


class DuplicateFileError(Exception):
    """Raised when a record with the same id is already registered."""


def add_file(record: dict) -> dict:
    """Append a new record to files.json. The record id is the OneDrive item id."""
    file_id = record.get('id')
    if not file_id:
        raise ValueError('Record is missing an id')

    with _write_lock:
        current = load_files()
        if any(entry.get('id') == file_id for entry in current):
            raise DuplicateFileError(f'File already registered: {file_id}')

        current.append(record)
        save_files(current)

    logger.info(f'Added file {file_id} -> {record.get("local_path")}')
    return record


def remove_file(file_id: str) -> bool:
    """Remove a record by id. Returns True if something was removed."""
    with _write_lock:
        current = load_files()
        remaining = [entry for entry in current if entry.get('id') != file_id]
        if len(remaining) == len(current):
            logger.warning(f'Remove requested for unknown file id: {file_id}')
            return False

        save_files(remaining)

    logger.info(f'Removed file {file_id}')
    return True
