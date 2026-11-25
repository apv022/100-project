"""The dispense routine: stock check, call the hardware driver, log the result.
Only one dispense runs at a time."""
import logging
import threading
from datetime import datetime

import config
from . import storage
from .hardware import DispenseError, make_driver

log = logging.getLogger("dispenser")

PILLS = {p["id"]: p for p in config.PILLS}


class Dispenser:
    def __init__(self, driver=None):
        self._lock = threading.Lock()
        self._driver = driver
        self.active = None  # pill id currently being dispensed

    @property
    def driver(self):
        if self._driver is None:
            self._driver = make_driver()
        return self._driver

    def dispense(self, pill_id, source="manual", wait=False):
        """Dispense one pill. Returns {"ok", "status", "message", "remaining"}.

        status: ok | busy | empty | missed | error | unknown
        wait=False returns "busy" at once if another dispense is running;
        wait=True (scheduler) queues behind it."""
        pill = PILLS.get(pill_id)
        if pill is None:
            return _result(False, "unknown", "Unknown pill.")
        if not self._lock.acquire(blocking=wait):
            return _result(False, "busy", "Dispenser is busy, try again in a moment.")
        try:
            self.active = pill_id
            remaining = storage.get_inventory()[pill_id]
            if remaining <= 0:
                _log(pill, source, "empty")
                return _result(False, "empty", f"{pill['name']} container is empty.", 0)
            try:
                dropped = self.driver.dispense_one(pill)
            except Exception as exc:  # DispenseError or anything unexpected
                if not isinstance(exc, DispenseError):
                    log.exception("dispense failed")
                _log(pill, source, "error")
                return _result(False, "error", f"Hardware error: {exc}", remaining)
            if not dropped:
                _log(pill, source, "missed")
                return _result(False, "missed", f"No {pill['name']} came out. Check the container.", remaining)
            remaining -= 1
            storage.update("inventory", {}, lambda inv: {**storage.get_inventory(), pill_id: remaining})
            _log(pill, source, "ok")
            return _result(True, "ok", f"{pill['name']} dispensed.", remaining)
        finally:
            self.active = None
            self._lock.release()


def _log(pill, source, status):
    storage.add_history({
        "ts": datetime.now().isoformat(timespec="seconds"),
        "pill": pill["id"], "name": pill["name"],
        "source": source, "status": status,
    })


def _result(ok, status, message, remaining=None):
    return {"ok": ok, "status": status, "message": message, "remaining": remaining}


dispenser = Dispenser()
