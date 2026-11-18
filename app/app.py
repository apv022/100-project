"""Flask app: serves the touchscreen UI and a small JSON API."""
import logging
import re
import uuid
from datetime import datetime

from flask import Flask, jsonify, render_template, request

import config
from . import scheduler, storage
from .dispenser import PILLS, dispenser

TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _pill_view():
    inv = storage.get_inventory()
    return [{
        "id": p["id"], "name": p["name"], "color": p["color"],
        "remaining": inv[p["id"]], "capacity": p["capacity"],
        "low": inv[p["id"]] <= config.LOW_STOCK_THRESHOLD,
    } for p in config.PILLS]


def _entry_from(body, existing=None):
    """Validate a schedule entry from request JSON. Returns (entry, error)."""
    entry = dict(existing or {"id": uuid.uuid4().hex[:8], "enabled": True, "last_run": None})
    t = body.get("time", entry.get("time"))
    pill = body.get("pill", entry.get("pill"))
    if not isinstance(t, str) or not TIME_RE.match(t):
        return None, "Time must look like 08:30."
    if pill not in PILLS:
        return None, "Choose one of the pills."
    entry.update(time=t, pill=pill)
    if "enabled" in body:
        entry["enabled"] = bool(body["enabled"])
    if existing and (t != existing.get("time")):
        entry["last_run"] = None  # a changed time may fire again today
    return entry, None


def create_app(start_scheduler=True):
    app = Flask(__name__)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/state")
    def state():
        now = datetime.now()
        sched = sorted(storage.get_schedule(), key=lambda e: e["time"])
        return jsonify(
            simulation=config.SIMULATION,
            now=now.isoformat(timespec="seconds"),
            busy=dispenser.active,
            pills=_pill_view(),
            schedule=sched,
            next=scheduler.next_dose(sched, now),
        )

    @app.post("/api/dispense")
    def dispense():
        pill = (request.get_json(silent=True) or {}).get("pill")
        res = dispenser.dispense(pill, source="manual", wait=False)
        code = 200 if res["ok"] else {"busy": 409, "unknown": 404}.get(res["status"], 422)
        return jsonify(res), code

    @app.post("/api/schedule")
    def schedule_add():
        sched = storage.get_schedule()
        if len(sched) >= config.MAX_SCHEDULE_ENTRIES:
            return jsonify(error="Schedule is full."), 400
        entry, err = _entry_from(request.get_json(silent=True) or {})
        if err:
            return jsonify(error=err), 400
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
            return jsonify(error=out["err"]), 404 if out["err"] == "not found" else 400
        return jsonify(out["entry"])

    @app.delete("/api/schedule/<eid>")
    def schedule_delete(eid):
        storage.update("schedule", [], lambda s: [e for e in s if e["id"] != eid])
        return "", 204

    @app.get("/api/history")
    def history():
        return jsonify(storage.get_history()[:200])

    @app.post("/api/pills/<pid>/refill")
    def refill(pid):
        if pid not in PILLS:
            return jsonify(error="Unknown pill."), 404
        body = request.get_json(silent=True) or {}
        count = body.get("count", PILLS[pid]["capacity"])
        if not isinstance(count, int) or not 0 <= count <= 999:
            return jsonify(error="Count must be 0 to 999."), 400
        storage.update("inventory", {}, lambda inv: {**storage.get_inventory(), pid: count})
        return jsonify(remaining=count)

    if start_scheduler:
        scheduler.start()
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.info("Pill dispenser on port %s (simulation=%s)", config.PORT, config.SIMULATION)
    create_app().run(host=config.HOST, port=config.PORT, threaded=True)
