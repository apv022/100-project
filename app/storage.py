"""Tiny JSON store. Writes go to a temp file, then an atomic rename, so a
power cut can never leave a half-written file."""
import copy
import json
import os
import tempfile
import threading

import config

_lock = threading.RLock()
lock = _lock  # public: hold it for multi-step read-modify-write


def _path(name):
    return os.path.join(config.DATA_DIR, name + ".json")


def read(name, default):
    with _lock:
        try:
            with open(_path(name)) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return copy.deepcopy(default)


def write(name, data):
    with _lock:
        os.makedirs(config.DATA_DIR, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=config.DATA_DIR, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, _path(name))
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise


def update(name, default, fn):
    """Read, let fn(data) modify it (or return a replacement), write back."""
    with _lock:
        data = read(name, default)
        result = fn(data)
        if result is not None:
            data = result
        write(name, data)
        return data


# --- typed helpers -------------------------------------------------------

def get_schedule():
    return read("schedule", [])


def get_history():
    return read("history", [])


def add_history(entry):
    def add(h):
        h.insert(0, entry)
        del h[config.HISTORY_LIMIT:]
    update("history", [], add)


def get_settings():
    return {**config.DEFAULT_SETTINGS, **read("settings", {})}
