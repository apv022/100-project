"""Background loop: scheduled doses, untaken-dose escalation, refill reminders.

Schedule entry: {id, time "HH:MM", pill, qty, days [0=Mon..6=Sun], enabled,
last_run "YYYY-MM-DD"}. An entry fires once per day on its days, within
SCHEDULE_GRACE_MINUTES after its time."""
import logging
import threading
import time
from datetime import datetime, timedelta

import config
from . import doses, notify, prescriptions, storage
from .dispenser import dispenser
from .hardware import safe

log = logging.getLogger("scheduler")
ALL_DAYS = list(range(7))


def _at(day, hhmm):
    h, m = map(int, hhmm.split(":"))
    return day.replace(hour=h, minute=m, second=0, microsecond=0)


def is_due(entry, now):
    if not entry.get("enabled", True) or entry.get("last_run") == now.date().isoformat():
        return False
    if now.weekday() not in entry.get("days", ALL_DAYS):
        return False
    late = (now - _at(now, entry["time"])).total_seconds()
    return 0 <= late <= config.SCHEDULE_GRACE_MINUTES * 60


def next_dose(schedule, now):
    """The soonest upcoming enabled entry, as {time, pill, qty, at}, or None."""
    best = None
    for e in schedule:
        if not e.get("enabled", True) or not e.get("days", ALL_DAYS):
            continue
        for k in range(8):
            at = _at(now + timedelta(days=k), e["time"])
            if at > now and at.weekday() in e.get("days", ALL_DAYS):
                if best is None or at < best["at"]:
                    best = {"time": e["time"], "pill": e["pill"], "qty": e.get("qty", 1), "at": at}
                break
    if best:
        best["at"] = best["at"].isoformat(timespec="seconds")
    return best


def run_due(now=None):
    """Dispense every due entry, one pill at a time. Returns the number of doses."""
    now = now or datetime.now()
    due = sorted((e for e in storage.get_schedule() if is_due(e, now)), key=lambda e: e["time"])
    for i, e in enumerate(due):
        def mark(sched, eid=e["id"]):   # mark first so it can never fire twice
            for s in sched:
                if s["id"] == eid:
                    s["last_run"] = now.date().isoformat()
        storage.update("schedule", [], mark)
        qty, got = e.get("qty", 1), 0
        for k in range(qty):
            if i or k:
                time.sleep(config.PAUSE_BETWEEN_PILLS)
            res = dispenser.dispense(e["pill"], source="schedule", wait=True)
            if not res["ok"]:
                break
            got += 1
        dose = doses.create(e["pill"], qty, got, schedule_id=e["id"], now=now)
        name = dose["name"]
        if got:
            safe(dispenser.driver.beep, "dose")
            short = f" (only {got} of {qty}: {res['message']})" if got < qty else ""
            notify.add("dose", "Time for your pills", f"{got} x {name} is in the cup{short}.", now)
        else:
            notify.add("error", "Scheduled dose failed", f"{name} at {e['time']}: {res['message']}", now)
        log.info("scheduled %s x%s at %s: dispensed %s", e["pill"], qty, e["time"], got)
    return len(due)


def tick(now=None):
    now = now or datetime.now()
    for step in (lambda: run_due(now), lambda: doses.check(now),
                 lambda: prescriptions.check_refills(now, storage.get_schedule(), storage.get_settings())):
        try:
            step()
        except Exception:
            log.exception("scheduler step failed")


def _loop():
    while True:
        tick()
        time.sleep(config.SCHEDULER_INTERVAL)


def start():
    threading.Thread(target=_loop, name="scheduler", daemon=True).start()
