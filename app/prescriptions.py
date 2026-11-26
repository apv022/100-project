"""One prescription per container: what it is, how many are left/used, refills."""
from datetime import datetime, timedelta

import config
from . import notify, storage

CONTAINERS = {c["id"]: c for c in config.PILLS}
ALL_DAYS = list(range(7))

STR_FIELDS = ["name", "strength", "instructions", "rx_number", "prescriber", "pharmacy", "filled_on"]
INT_FIELDS = ["dose_qty", "quantity", "refills_left", "remaining", "used"]


def _default(c):
    return {"name": "", "strength": "", "instructions": "", "rx_number": "",
            "prescriber": "", "pharmacy": "", "filled_on": "",
            "dose_qty": 1, "quantity": c["capacity"], "refills_left": 0,
            "remaining": c["capacity"], "used": 0}


def get_all():
    data = storage.read("prescriptions", {})
    old_inv = storage.read("inventory", {})          # data from older versions
    out = {}
    for cid, c in CONTAINERS.items():
        d = _default(c)
        if cid in old_inv and cid not in data:
            d["remaining"] = old_inv[cid]
        d.update(data.get(cid, {}))
        out[cid] = d
    return out


def get(cid):
    return get_all()[cid]


def label(cid, rx=None):
    rx = rx or get(cid)
    if rx["name"]:
        return (rx["name"] + " " + rx["strength"]).strip()
    return CONTAINERS[cid]["name"]


def clean(body):
    """Validate a (partial) prescription from JSON. Returns (fields, error)."""
    out = {}
    for k in STR_FIELDS:
        if k in body:
            v = body[k]
            if v is None:
                v = ""
            if not isinstance(v, str) or len(v) > 300:
                return None, f"{k} must be text (max 300 characters)."
            out[k] = v.strip()
    for k in INT_FIELDS:
        if k in body:
            v = body[k]
            if isinstance(v, str) and v.strip().isdigit():
                v = int(v)
            if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 9999:
                return None, f"{k} must be a whole number from 0 to 9999."
            out[k] = v
    if out.get("dose_qty") == 0:
        return None, "dose_qty must be at least 1."
    return out, None


def _save(fn):
    with storage.lock:
        data = get_all()
        result = fn(data)
        storage.write("prescriptions", data)
        return result


def update(cid, fields):
    return _save(lambda d: d[cid].update(fields) or d[cid])


def consume(cid, n=1):
    """Take n pills out of stock. Returns the new remaining count."""
    def f(d):
        d[cid]["remaining"] = max(0, d[cid]["remaining"] - n)
        d[cid]["used"] += n
        return d[cid]["remaining"]
    return _save(f)


def refill(cid, count=None, use_refill=False, now=None):
    """New bottle poured into the container."""
    def f(d):
        rx = d[cid]
        rx["remaining"] = rx["quantity"] if count is None else count
        rx["used"] = 0
        if use_refill and rx["refills_left"] > 0:
            rx["refills_left"] -= 1
        rx["filled_on"] = (now or datetime.now()).date().isoformat()
        return rx
    return _save(f)


# --- supply maths -------------------------------------------------------

def daily_use(cid, schedule):
    """Average pills per day from the enabled schedule."""
    total = 0.0
    for e in schedule:
        if e["pill"] == cid and e.get("enabled", True):
            total += e.get("qty", 1) * len(e.get("days", ALL_DAYS)) / 7
    return total


def supply(cid, rx, schedule, settings):
    use = daily_use(cid, schedule)
    days = rx["remaining"] / use if use else None
    low = rx["remaining"] <= config.LOW_STOCK_THRESHOLD or (days is not None and days <= settings["refill_warn_days"])
    runs_out = (datetime.now() + timedelta(days=days)).date().isoformat() if days is not None else None
    return {"daily_use": round(use, 2), "days_left": None if days is None else round(days, 1),
            "refill_due": low, "runs_out": runs_out}


def check_refills(now, schedule, settings):
    """Once a day at the reminder time, notify about containers running low."""
    h, m = map(int, settings["refill_reminder_time"].split(":"))
    at = now.replace(hour=h, minute=m, second=0, microsecond=0)
    today = now.date().isoformat()
    late = (now - at).total_seconds()
    if not (0 <= late <= config.SCHEDULE_GRACE_MINUTES * 60):
        return []
    if storage.read("state", {}).get("last_refill_check") == today:
        return []
    storage.update("state", {}, lambda s: s.update(last_refill_check=today))
    sent = []
    for cid, rx in get_all().items():
        sup = supply(cid, rx, schedule, settings)
        if not sup["refill_due"]:
            continue
        days = f" (about {sup['days_left']:g} days)" if sup["days_left"] is not None else ""
        tail = (f" {rx['refills_left']} refill(s) left on the prescription."
                if rx["refills_left"] else " No refills left: contact the prescriber.")
        sent.append(notify.add("refill", f"Refill {label(cid, rx)}",
                               f"{rx['remaining']} pills left{days}.{tail}", now))
    return sent
