"""The dispense routine: stock check, call the hardware driver, log the result.
Only one dispense runs at a time."""
import logging
import threading
from datetime import datetime

import config
from . import notify, prescriptions, storage
from .hardware import DispenseError, make_driver, safe

log = logging.getLogger("dispenser")

PILLS = {p["id"]: p for p in config.PILLS}


class Dispenser:
    def __init__(self, driver=None):
        self._lock = threading.Lock()
        self._driver = driver
        self.active = None  # container id currently being dispensed

    @property
    def driver(self):
        if self._driver is None:
            self._driver = make_driver()
        return self._driver

    def dispense(self, pill_id, source="manual", wait=False):
        """Dispense one pill. Returns {"ok", "status", "message", "remaining"}.

        status: ok | busy | empty | no_pill | error | unknown
        wait=False returns "busy" at once if another dispense is running;
        wait=True (scheduler) queues behind it."""
        pill = PILLS.get(pill_id)
        if pill is None:
            return _result(False, "unknown", "Unknown container.")
        if not self._lock.acquire(blocking=wait):
            return _result(False, "busy", "Dispenser is busy, try again in a moment.")
        try:
            self.active = pill_id
            name = prescriptions.label(pill_id)
            remaining = prescriptions.get(pill_id)["remaining"]
            if remaining <= 0:
                log_event(pill_id, source, "empty")
                notify.add("empty", f"{name} is empty", f"Could not dispense {name}: the container is empty.")
                return _result(False, "empty", f"{name} container is empty.", 0)
            try:
                dropped = self.driver.dispense_one(pill)
            except Exception as exc:  # DispenseError or anything unexpected
                if not isinstance(exc, DispenseError):
                    log.exception("dispense failed")
                log_event(pill_id, source, "error")
                safe(self.driver.beep, "error")
                notify.add("error", "Dispenser problem", f"{name}: {exc}")
                return _result(False, "error", f"Hardware error: {exc}", remaining)
            if not dropped:
                log_event(pill_id, source, "no_pill")
                return _result(False, "no_pill", f"No {name} came out. Check the container.", remaining)
            remaining = prescriptions.consume(pill_id)
            log_event(pill_id, source, "ok")
            return _result(True, "ok", f"{name} dispensed.", remaining)
        finally:
            self.active = None
            self._lock.release()


def log_event(pill_id, source, status, **extra):
    storage.add_history({
        "ts": datetime.now().isoformat(timespec="seconds"),
        "pill": pill_id, "name": prescriptions.label(pill_id),
        "source": source, "status": status, **extra,
    })


def _result(ok, status, message, remaining=None):
    return {"ok": ok, "status": status, "message": message, "remaining": remaining}


dispenser = Dispenser()
