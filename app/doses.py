"""Scheduled doses waiting to be taken, with reminder -> alarm -> "not taken"
escalation. A dose is confirmed by the "I took it" button, or automatically if
the hardware's cup sensor reports the cup empty."""
import uuid
from datetime import datetime

import config
from . import notify, prescriptions, storage
from .dispenser import dispenser, log_event
from .hardware import safe


def _all():
    return storage.read("doses", [])


def pending():
    return [d for d in _all() if d["state"] == "pending"]


def create(cid, qty_requested, qty_dispensed, schedule_id=None, now=None):
    now = now or datetime.now()
    d = {"id": uuid.uuid4().hex[:10], "pill": cid, "name": prescriptions.label(cid),
         "schedule_id": schedule_id, "ts": now.isoformat(timespec="seconds"),
         "qty_requested": qty_requested, "qty": qty_dispensed,
         "state": "pending" if qty_dispensed else "failed", "level": 0, "resolved_at": None}

    def add(lst):
        lst.insert(0, d)
        del lst[config.DOSE_LIMIT:]
    storage.update("doses", [], add)
    return d


def _set(dose_id, **fields):
    out = {}

    def f(lst):
        for d in lst:
            if d["id"] == dose_id:
                d.update(fields)
                out["d"] = d
    storage.update("doses", [], f)
    return out.get("d")


def resolve(dose_id, state, now=None):
    """state: taken | skipped | not_taken. Returns the dose or None."""
    now = now or datetime.now()
    d = next((x for x in _all() if x["id"] == dose_id), None)
    if not d or d["state"] != "pending":
        return None
    d = _set(dose_id, state=state, resolved_at=now.isoformat(timespec="seconds"))
    log_event(d["pill"], "dose", state, qty=d["qty"])
    _update_alarm()
    return d


def alarm_active():
    return any(d["level"] >= 2 for d in pending())


def _update_alarm():
    drv = dispenser.driver
    safe(drv.alarm_on) if alarm_active() else safe(drv.alarm_off)


def check(now=None):
    """Escalate doses that haven't been taken. Called by the scheduler loop."""
    now = now or datetime.now()
    s = storage.get_settings()
    drv = dispenser.driver
    cup = safe(drv.cup_state)
    for d in pending():
        if cup == "empty":
            resolve(d["id"], "taken", now)
            continue
        age = (now - datetime.fromisoformat(d["ts"])).total_seconds() / 60
        name = d["name"]
        if age >= s["missed_after_min"]:
            resolve(d["id"], "not_taken", now)
            notify.add("missed", "Dose not taken", f"{name} from {d['ts'][11:16]} was not taken.", now)
        elif age >= s["alarm_after_min"] and d["level"] < 2:
            _set(d["id"], level=2)
            notify.add("alarm", "Take your pills!", f"{name} has been waiting since {d['ts'][11:16]}.", now)
        elif age >= s["remind_after_min"] and d["level"] < 1:
            _set(d["id"], level=1)
            safe(drv.beep, "reminder")
            notify.add("reminder", "Reminder", f"{name} is waiting in the cup.", now)
    _update_alarm()
