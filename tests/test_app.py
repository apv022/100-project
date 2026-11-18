import os
import tempfile
import unittest
from datetime import datetime

os.environ["PILL_SIMULATION"] = "1"
import config  # noqa: E402

config.DATA_DIR = tempfile.mkdtemp()
config.SERVO_MOVE_TIME = config.SERVO_HOLD_TIME = 0.01
config.PAUSE_BETWEEN_PILLS = 0.01

from app import scheduler, storage  # noqa: E402
from app.app import create_app  # noqa: E402


class AppTest(unittest.TestCase):
    def setUp(self):
        for f in os.listdir(config.DATA_DIR):
            os.unlink(os.path.join(config.DATA_DIR, f))
        self.c = create_app(start_scheduler=False).test_client()

    def test_pages_and_state(self):
        self.assertEqual(self.c.get("/").status_code, 200)
        s = self.c.get("/api/state").get_json()
        self.assertEqual(len(s["pills"]), 3)
        self.assertEqual(s["pills"][0]["remaining"], 30)

    def test_dispense_updates_inventory_and_history(self):
        r = self.c.post("/api/dispense", json={"pill": "pill2"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["remaining"], 29)
        h = self.c.get("/api/history").get_json()
        self.assertEqual((h[0]["pill"], h[0]["status"], h[0]["source"]), ("pill2", "ok", "manual"))
        self.assertEqual(self.c.post("/api/dispense", json={"pill": "nope"}).status_code, 404)

    def test_empty_hopper(self):
        self.c.post("/api/pills/pill1/refill", json={"count": 0})
        r = self.c.post("/api/dispense", json={"pill": "pill1"})
        self.assertEqual(r.get_json()["status"], "empty")
        self.assertEqual(self.c.get("/api/history").get_json()[0]["status"], "empty")
        self.c.post("/api/pills/pill1/refill", json={})
        self.assertEqual(self.c.get("/api/state").get_json()["pills"][0]["remaining"], 30)

    def test_schedule_crud_and_validation(self):
        self.assertEqual(self.c.post("/api/schedule", json={"time": "25:00", "pill": "pill1"}).status_code, 400)
        self.assertEqual(self.c.post("/api/schedule", json={"time": "08:00", "pill": "x"}).status_code, 400)
        e = self.c.post("/api/schedule", json={"time": "08:00", "pill": "pill1"}).get_json()
        self.c.put(f"/api/schedule/{e['id']}", json={"time": "09:15", "enabled": False})
        got = self.c.get("/api/state").get_json()["schedule"][0]
        self.assertEqual((got["time"], got["enabled"]), ("09:15", False))
        self.assertEqual(self.c.delete(f"/api/schedule/{e['id']}").status_code, 204)
        self.assertEqual(self.c.get("/api/state").get_json()["schedule"], [])

    def test_scheduler_fires_once_and_handles_simultaneous(self):
        now = datetime.now().replace(hour=12, minute=0, second=1, microsecond=0)
        for pill in ("pill1", "pill3"):
            self.c.post("/api/schedule", json={"time": "12:00", "pill": pill})
        self.c.post("/api/schedule", json={"time": "06:00", "pill": "pill2"})  # too old: skipped
        self.assertEqual(scheduler.run_due(now), 2)
        self.assertEqual(scheduler.run_due(now), 0)  # not again today
        inv = storage.get_inventory()
        self.assertEqual((inv["pill1"], inv["pill2"], inv["pill3"]), (29, 30, 29))

    def test_next_dose(self):
        now = datetime(2026, 1, 1, 10, 0)
        sched = [{"time": "09:00", "pill": "pill1", "enabled": True},
                 {"time": "18:00", "pill": "pill2", "enabled": True}]
        self.assertEqual(scheduler.next_dose(sched, now)["pill"], "pill2")
        self.assertIsNone(scheduler.next_dose([], now))


if __name__ == "__main__":
    unittest.main()
