"""Flask app: serves the UI and a small JSON API."""
import logging
import re
import uuid
from datetime import datetime

from flask import Flask, jsonify, render_template, request

import config
from . import doses, notify, ocr, prescriptions, scheduler, storage
from .dispenser import PILLS, dispenser
from .hardware import safe

TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
ALL_DAYS = list(range(7))


def _err(msg, code=400):
    return jsonify(error=msg), code


def _containers(schedule, settings):
    out = []
    for cid, rx in prescriptions.get_all().items():
        c = PILLS[cid]
        out.append({"id": cid, "color": c["color"], "label": prescriptions.label(cid, rx),
                    "rx": rx, "remaining": rx["remaining"], "used": rx["used"],
                    **prescriptions.supply(cid, rx, schedule, settings)})
    return out


def _entry_from(body, existing=None):
    """Validate a schedule entry from request JSON. Returns (entry, error)."""
    entry = dict(existing or {"id": uuid.uuid4().hex[:8], "enabled": True, "last_run": None,
                              "qty": None, "days": ALL_DAYS})
    t = body.get("time", entry.get("time"))
    pill = body.get("pill", entry.get("pill"))
    if not isinstance(t, str) or not TIME_RE.match(t):
        return None, "Time must look like 08:30."
    if pill not in PILLS:
        return None, "Choose one of the containers."
    qty = body.get("qty", entry.get("qty"))
    if qty is None:
        qty = prescriptions.get(pill)["dose_qty"]
    if not isinstance(qty, int) or isinstance(qty, bool) or not 1 <= qty <= 10:
        return None, "Pills per dose must be 1 to 10."
    days = body.get("days", entry.get("days", ALL_DAYS))
    if (not isinstance(days, list) or not days
            or any(not isinstance(d, int) or isinstance(d, bool) or not 0 <= d <= 6 for d in days)):
        return None, "Choose at least one day."
    entry.update(time=t, pill=pill, qty=qty, days=sorted(set(days)))
    if "enabled" in body:
        entry["enabled"] = bool(body["enabled"])
    if existing and t != existing.get("time"):
        entry["last_run"] = None  # a changed time may fire again today
    return entry, None


def _clean_settings(body):
    out = {}
    if "refill_reminder_time" in body:
        if not isinstance(body["refill_reminder_time"], str) or not TIME_RE.match(body["refill_reminder_time"]):
            return None, "Reminder time must look like 18:00."
        out["refill_reminder_time"] = body["refill_reminder_time"]
    for k, lo, hi in (("refill_warn_days", 0, 60), ("remind_after_min", 1, 240),
                      ("alarm_after_min", 1, 480), ("missed_after_min", 5, 1440)):
        if k in body:
            v = body[k]
            if not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= hi:
                return None, f"{k} must be {lo} to {hi}."
            out[k] = v
    merged = {**storage.get_settings(), **out}
    if not merged["remind_after_min"] < merged["alarm_after_min"] < merged["missed_after_min"]:
        return None, "Reminder must come before the alarm, and the alarm before 'not taken'."
    return out, None


def create_app(start_scheduler=True):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_MB * 1024 * 1024

    @app.errorhandler(413)
    def too_big(_):
        return _err(f"Image too large (max {config.MAX_UPLOAD_MB} MB).", 413)

    @app.get("/")
    def index():
        return render_template("index.html")

    # ---- overview -----------------------------------------------------
    @app.get("/api/state")
    def state():
        now = datetime.now()
        sched = sorted(storage.get_schedule(), key=lambda e: e["time"])
        settings = storage.get_settings()
        notes = notify.all_()
        return jsonify(
            driver=config.DRIVER,
            now=now.isoformat(timespec="seconds"),
            busy=dispenser.active,
            containers=_containers(sched, settings),
            schedule=sched,
            next=scheduler.next_dose(sched, now),
            pending=doses.pending(),
            alarm=doses.alarm_active(),
            unread=sum(1 for n in notes if not n["read"]),
            latest=notes[:5],
            settings=settings,
            ocr=ocr.available(),
            push=bool(config.NTFY_URL),
        )

    # ---- dispensing ---------------------------------------------------
    @app.post("/api/dispense")
    def dispense():
        pill = (request.get_json(silent=True) or {}).get("pill")
        res = dispenser.dispense(pill, source="manual", wait=False)
        code = 200 if res["ok"] else {"busy": 409, "unknown": 404}.get(res["status"], 422)
        return jsonify(res), code

    @app.post("/api/doses/<did>/<action>")
    def dose_action(did, action):
        state = {"taken": "taken", "skip": "skipped"}.get(action)
        if not state:
            return _err("Unknown action.", 404)
        d = doses.resolve(did, state)
        return jsonify(d) if d else _err("That dose is no longer waiting.", 404)

    # ---- schedule -----------------------------------------------------
    @app.post("/api/schedule")
    def schedule_add():
        sched = storage.get_schedule()
        if len(sched) >= config.MAX_SCHEDULE_ENTRIES:
            return _err("Schedule is full.")
        entry, err = _entry_from(request.get_json(silent=True) or {})
        if err:
            return _err(err)
        sched.append(entry)
        storage.write("schedule", sched)
        return jsonify(entry), 201

    @app.put("/api/schedule/<eid>")
    def schedule_edit(eid):
        body = request.get_json(silent=True) or {}
        out = {}

        def edit(sched):
            for i, e in enumerate(sched):
                if e["id"] == eid:
                    entry, err = _entry_from(body, e)
                    out["entry"], out["err"] = entry, err
                    if entry:
                        sched[i] = entry
                    return
            out["err"] = "not found"

        storage.update("schedule", [], edit)
        if out.get("err"):
            return _err(out["err"], 404 if out["err"] == "not found" else 400)
        return jsonify(out["entry"])

    @app.delete("/api/schedule/<eid>")
    def schedule_delete(eid):
        storage.update("schedule", [], lambda s: [e for e in s if e["id"] != eid])
        return "", 204

    # ---- prescriptions ------------------------------------------------
    def _known(cid):
        return cid in PILLS

    @app.put("/api/prescriptions/<cid>")
    def rx_edit(cid):
        if not _known(cid):
            return _err("Unknown container.", 404)
        fields, err = prescriptions.clean(request.get_json(silent=True) or {})
        if err:
            return _err(err)
        return jsonify(prescriptions.update(cid, fields))

    @app.post("/api/prescriptions/<cid>/refill")
    def rx_refill(cid):
        if not _known(cid):
            return _err("Unknown container.", 404)
        body = request.get_json(silent=True) or {}
        count = body.get("count")
        if count is not None and (not isinstance(count, int) or isinstance(count, bool) or not 0 <= count <= 9999):
            return _err("Count must be 0 to 9999.")
        return jsonify(prescriptions.refill(cid, count, bool(body.get("use_refill"))))

    @app.post("/api/prescriptions/<cid>/adjust")
    def rx_adjust(cid):
        if not _known(cid):
            return _err("Unknown container.", 404)
        delta = (request.get_json(silent=True) or {}).get("delta")
        if not isinstance(delta, int) or isinstance(delta, bool) or abs(delta) > 999:
            return _err("delta must be a whole number.")
        rx = prescriptions.get(cid)
        return jsonify(prescriptions.update(cid, {"remaining": max(0, min(9999, rx["remaining"] + delta))}))

    @app.post("/api/prescriptions/<cid>/schedule")
    def rx_schedule(cid):
        """Replace this container's schedule with the given times."""
        if not _known(cid):
            return _err("Unknown container.", 404)
        body = request.get_json(silent=True) or {}
        times = body.get("times")
        if not isinstance(times, list) or not times or len(times) > 8:
            return _err("Give 1 to 8 times.")
        entries = []
        for t in times:
            e, err = _entry_from({"time": t, "pill": cid, "qty": body.get("qty"),
                                  "days": body.get("days", ALL_DAYS)})
            if err:
                return _err(err)
            entries.append(e)
        storage.update("schedule", [], lambda s: [e for e in s if e["pill"] != cid] + entries)
        return jsonify(entries), 201

    @app.post("/api/scan")
    def scan():
        f = request.files.get("image")
        if not f:
            return _err("No image uploaded.")
        try:
            text = ocr.image_to_text(f.read())
        except ocr.OcrError as e:
            return _err(str(e), 503 if "not installed" in str(e) else 422)
        result = ocr.parse_label(text)
        if not text.strip():
            result["warnings"].insert(0, "No text found. Try a closer, well-lit, straight-on photo.")
        return jsonify(text=text, **result)

    # ---- history, notifications, settings ------------------------------
    @app.get("/api/history")
    def history():
        return jsonify(storage.get_history()[:300])

    @app.get("/api/notifications")
    def notifications():
        return jsonify(notify.all_()[:100])

    @app.post("/api/notifications/read")
    def notifications_read():
        notify.mark_all_read()
        return "", 204

    @app.put("/api/settings")
    def settings_edit():
        fields, err = _clean_settings(request.get_json(silent=True) or {})
        if err:
            return _err(err)
        storage.update("settings", {}, lambda s: s.update(fields))
        return jsonify(storage.get_settings())

    @app.post("/api/test/<what>")
    def hw_test(what):
        drv = dispenser.driver
        if what == "beep":
            safe(drv.beep, "test")
        elif what == "notify":
            notify.add("info", "Test notification", "Notifications are working.")
        else:
            return _err("Unknown test.", 404)
        return "", 204

    if start_scheduler:
        scheduler.start()
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.info("Pill dispenser on http://%s:%s (driver=%s, ocr=%s)",
                 config.HOST, config.PORT, config.DRIVER, ocr.available())
    create_app().run(host=config.HOST, port=config.PORT, threaded=True)
