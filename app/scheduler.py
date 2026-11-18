"""Schedule checking. Each entry: {id, time "HH:MM", pill, enabled, last_run "YYYY-MM-DD"}.
An entry fires once per day, within SCHEDULE_GRACE_MINUTES after its time."""
import logging
import threading
import time
from datetime import datetime, timedelta

import config
from . import storage
from .dispenser import dispenser

log = logging.getLogger("scheduler")


def _at(now, hhmm):
    h, m = map(int, hhmm.split(":"))
    return now.replace(hour=h, minute=m, second=0, microsecond=0)


def is_due(entry, now):
    if not entry.get("enabled", True) or entry.get("last_run") == now.date().isoformat():
        return False
    late = (now - _at(now, entry["time"])).total_seconds()
    return 0 <= late <= config.SCHEDULE_GRACE_MINUTES * 60


def next_dose(schedule, now):
    """The soonest upcoming enabled entry, as {time, pill, at}, or None."""
    best = None
    for e in schedule:
        if not e.get("enabled", True):
            continue
        at = _at(now, e["time"])
        if at <= now:
            at += timedelta(days=1)
        if best is None or at < best["at"]:
            best = {"time": e["time"], "pill": e["pill"], "at": at}
    if best:
        best["at"] = best["at"].isoformat(timespec="seconds")
    return best


def run_due(now=None):
    """Fire every due entry, one after another. Returns the number fired."""
    now = now or datetime.now()
    due = sorted((e for e in storage.get_schedule() if is_due(e, now)), key=lambda e: e["time"])
    for i, e in enumerate(due):
        # Mark first so a slow dispense can never fire the same entry twice.
        def mark(sched, eid=e["id"]):
            for s in sched:
                if s["id"] == eid:
                    s["last_run"] = now.date().isoformat()
        storage.update("schedule", [], mark)
        if i:
            time.sleep(config.PAUSE_BETWEEN_PILLS)
        res = dispenser.dispense(e["pill"], source="schedule", wait=True)
        log.info("scheduled %s at %s: %s", e["pill"], e["time"], res["status"])
    return len(due)


def _loop():
    while True:
        try:
            run_due()
        except Exception:
            log.exception("scheduler error")
        time.sleep(config.SCHEDULER_INTERVAL)


def start():
    threading.Thread(target=_loop, name="scheduler", daemon=True).start()
