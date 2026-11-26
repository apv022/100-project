"""Notifications: stored for the app's bell, and optionally pushed via ntfy."""
import json
import logging
import threading
import urllib.request
import uuid
from datetime import datetime

import config
from . import storage

log = logging.getLogger("notify")


def add(kind, title, message, now=None):
    """kind: dose | reminder | alarm | missed | refill | empty | error | info"""
    n = {"id": uuid.uuid4().hex[:10],
         "ts": (now or datetime.now()).isoformat(timespec="seconds"),
         "kind": kind, "title": title, "message": message, "read": False}

    def push(lst):
        lst.insert(0, n)
        del lst[config.NOTIFICATION_LIMIT:]
    storage.update("notifications", [], push)
    log.info("notify [%s] %s: %s", kind, title, message)
    if config.NTFY_URL:
        threading.Thread(target=_ntfy, args=(n,), daemon=True).start()
    return n


def all_():
    return storage.read("notifications", [])


def mark_all_read():
    def mark(lst):
        for n in lst:
            n["read"] = True
    storage.update("notifications", [], mark)


def _ntfy(n):
    prio = {"alarm": "urgent", "missed": "high", "refill": "default"}.get(n["kind"], "default")
    req = urllib.request.Request(
        config.NTFY_URL, data=n["message"].encode(), method="POST",
        headers={"Title": n["title"], "Priority": prio, "Tags": "pill"})
    try:
        urllib.request.urlopen(req, timeout=8).close()
    except Exception as exc:
        log.warning("ntfy push failed: %s", exc)


def dumps(n):  # for logs/tests
    return json.dumps(n)
