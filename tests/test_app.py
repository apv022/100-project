import os
import tempfile
import unittest
from datetime import datetime, timedelta

os.environ["PILL_DRIVER"] = "sim"
import config  # noqa: E402

config.DATA_DIR = tempfile.mkdtemp()
config.SIM_DISPENSE_SECONDS = 0.0
config.PAUSE_BETWEEN_PILLS = 0.0

from app import doses, notify, prescriptions, scheduler, storage  # noqa: E402
from app.app import create_app  # noqa: E402
from app.dispenser import Dispenser, dispenser  # noqa: E402
from app.hardware import DispenseError, Driver, SimulatedDriver  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        for f in os.listdir(config.DATA_DIR):
            os.unlink(os.path.join(config.DATA_DIR, f))
        dispenser._driver = SimulatedDriver()
        self.c = create_app(start_scheduler=False).test_client()

    def state(self):
        return self.c.get("/api/state").get_json()

    def container(self, cid):
        return next(c for c in self.state()["containers"] if c["id"] == cid)


class AppTest(Base):
    def test_pages_and_state(self):
        self.assertEqual(self.c.get("/").status_code, 200)
        s = self.state()
        self.assertEqual(len(s["containers"]), 3)
        self.assertEqual(s["containers"][0]["remaining"], 30)
        self.assertEqual(s["containers"][0]["label"], "Container A")

    def test_manual_dispense_counts_used_and_left(self):
        r = self.c.post("/api/dispense", json={"pill": "pill2"})
        self.assertEqual((r.status_code, r.get_json()["remaining"]), (200, 29))
        c = self.container("pill2")
        self.assertEqual((c["remaining"], c["used"]), (29, 1))
        h = self.c.get("/api/history").get_json()
        self.assertEqual((h[0]["pill"], h[0]["status"], h[0]["source"]), ("pill2", "ok", "manual"))
        self.assertEqual(self.c.post("/api/dispense", json={"pill": "nope"}).status_code, 404)

    def test_empty_container_notifies(self):
        self.c.post("/api/prescriptions/pill1/refill", json={"count": 0})
        r = self.c.post("/api/dispense", json={"pill": "pill1"})
        self.assertEqual(r.get_json()["status"], "empty")
        self.assertEqual(notify.all_()[0]["kind"], "empty")

    def test_prescription_edit_refill_adjust(self):
        r = self.c.put("/api/prescriptions/pill1", json={"name": "Metformin", "strength": "500 mg",
                                                         "quantity": 60, "refills_left": 2, "dose_qty": 2})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.container("pill1")["label"], "Metformin 500 mg")
        self.assertEqual(self.c.put("/api/prescriptions/pill1", json={"quantity": -1}).status_code, 400)
        self.assertEqual(self.c.put("/api/prescriptions/pill1", json={"dose_qty": 0}).status_code, 400)
        rx = self.c.post("/api/prescriptions/pill1/refill", json={"use_refill": True}).get_json()
        self.assertEqual((rx["remaining"], rx["refills_left"], rx["used"]), (60, 1, 0))
        rx = self.c.post("/api/prescriptions/pill1/adjust", json={"delta": -5}).get_json()
        self.assertEqual(rx["remaining"], 55)

    def test_schedule_crud_validation_defaults(self):
        self.c.put("/api/prescriptions/pill1", json={"dose_qty": 2})
        bad = [{"time": "25:00", "pill": "pill1"}, {"time": "08:00", "pill": "x"},
               {"time": "08:00", "pill": "pill1", "qty": 0}, {"time": "08:00", "pill": "pill1", "days": []}]
        for b in bad:
            self.assertEqual(self.c.post("/api/schedule", json=b).status_code, 400, b)
        e = self.c.post("/api/schedule", json={"time": "08:00", "pill": "pill1"}).get_json()
        self.assertEqual((e["qty"], e["days"]), (2, list(range(7))))   # qty from prescription
        self.c.put(f"/api/schedule/{e['id']}", json={"time": "09:15", "enabled": False, "days": [0, 2]})
        got = self.state()["schedule"][0]
        self.assertEqual((got["time"], got["enabled"], got["days"]), ("09:15", False, [0, 2]))
        self.assertEqual(self.c.delete(f"/api/schedule/{e['id']}").status_code, 204)
        self.assertEqual(self.state()["schedule"], [])

    def test_replace_container_schedule(self):
        self.c.post("/api/schedule", json={"time": "07:00", "pill": "pill1"})
        self.c.post("/api/schedule", json={"time": "07:00", "pill": "pill2"})
        r = self.c.post("/api/prescriptions/pill1/schedule", json={"times": ["08:00", "20:00"], "qty": 1})
        self.assertEqual(r.status_code, 201)
        sched = self.state()["schedule"]
        self.assertEqual(sorted((e["pill"], e["time"]) for e in sched),
                         [("pill1", "08:00"), ("pill1", "20:00"), ("pill2", "07:00")])

    def test_settings(self):
        r = self.c.put("/api/settings", json={"refill_reminder_time": "19:30", "refill_warn_days": 5})
        self.assertEqual(r.get_json()["refill_reminder_time"], "19:30")
        self.assertEqual(self.c.put("/api/settings", json={"alarm_after_min": 1}).status_code, 400)
        self.assertEqual(self.c.put("/api/settings", json={"refill_reminder_time": "x"}).status_code, 400)

    def test_notifications_read(self):
        self.c.post("/api/test/notify")
        self.assertEqual(self.state()["unread"], 1)
        self.c.post("/api/notifications/read")
        self.assertEqual(self.state()["unread"], 0)

    def test_scan_without_image(self):
        self.assertEqual(self.c.post("/api/scan").status_code, 400)


class DoseFlowTest(Base):
    def setUp(self):
        super().setUp()
        self.now = datetime(2026, 11, 26, 8, 0, 5)   # a Thursday

    def add(self, **kw):
        return self.c.post("/api/schedule", json={"time": "08:00", "pill": "pill1", **kw}).get_json()

    def test_scheduled_dose_with_qty_beeps_and_waits(self):
        beeps = []
        dispenser.driver.beep = beeps.append
        self.add(qty=2)
        self.add(pill="pill3")
        self.c.post("/api/schedule", json={"time": "06:00", "pill": "pill2"})   # too old: skipped
        self.assertEqual(scheduler.run_due(self.now), 2)
        self.assertEqual(scheduler.run_due(self.now), 0)                        # once per day
        self.assertEqual(self.container("pill1")["remaining"], 28)
        self.assertEqual(self.container("pill3")["remaining"], 29)
        self.assertEqual(self.container("pill2")["remaining"], 30)
        self.assertEqual(beeps, ["dose", "dose"])
        self.assertEqual(len(doses.pending()), 2)

    def test_days_of_week(self):
        self.add(days=[0])                                 # Mondays only
        self.assertEqual(scheduler.run_due(self.now), 0)
        nxt = scheduler.next_dose(storage.get_schedule(), self.now)
        self.assertEqual(nxt["at"][:10], "2026-11-30")      # next Monday

    def test_escalation_then_not_taken(self):
        self.add()
        scheduler.run_due(self.now)
        drv = dispenser.driver
        scheduler.tick(self.now + timedelta(minutes=6))
        self.assertEqual(doses.pending()[0]["level"], 1)
        self.assertFalse(drv.alarming)
        scheduler.tick(self.now + timedelta(minutes=16))
        self.assertTrue(drv.alarming)
        self.assertTrue(self.state()["alarm"])
        scheduler.tick(self.now + timedelta(minutes=61))
        self.assertEqual(doses.pending(), [])
        self.assertFalse(drv.alarming)
        kinds = [n["kind"] for n in notify.all_()]
        self.assertEqual(kinds[:4], ["missed", "alarm", "reminder", "dose"])
        self.assertEqual(storage.get_history()[0]["status"], "not_taken")

    def test_taken_button_stops_alarm(self):
        self.add()
        scheduler.run_due(self.now)
        scheduler.tick(self.now + timedelta(minutes=16))
        self.assertTrue(dispenser.driver.alarming)
        did = doses.pending()[0]["id"]
        self.assertEqual(self.c.post(f"/api/doses/{did}/taken").status_code, 200)
        self.assertFalse(dispenser.driver.alarming)
        self.assertEqual(self.c.post(f"/api/doses/{did}/taken").status_code, 404)
        self.assertEqual(storage.get_history()[0]["status"], "taken")

    def test_cup_sensor_marks_taken(self):
        self.add()
        scheduler.run_due(self.now)
        dispenser.driver.cup_state = lambda: "empty"
        scheduler.tick(self.now + timedelta(minutes=1))
        self.assertEqual(doses.pending(), [])

    def test_failed_dispense_makes_failed_dose(self):
        class Broken(SimulatedDriver):
            def dispense_one(self, pill):
                raise DispenseError("jam")
        dispenser._driver = Broken()
        self.add()
        scheduler.run_due(self.now)
        self.assertEqual(doses.pending(), [])
        self.assertEqual(storage.read("doses", [])[0]["state"], "failed")
        self.assertIn("error", [n["kind"] for n in notify.all_()])

    def test_driver_no_pill_and_error(self):
        class Fake(Driver):
            def __init__(self, result): self.result = result
            def dispense_one(self, pill):
                if isinstance(self.result, Exception):
                    raise self.result
                return self.result
        r = Dispenser(Fake(False)).dispense("pill1")
        self.assertEqual((r["status"], r["remaining"]), ("no_pill", 30))
        r = Dispenser(Fake(DispenseError("jam"))).dispense("pill1")
        self.assertEqual(r["status"], "error")


class RefillTest(Base):
    def test_refill_reminder_once_a_day(self):
        self.c.put("/api/prescriptions/pill1", json={"name": "Metformin", "refills_left": 0})
        self.c.post("/api/prescriptions/pill1/refill", json={"count": 6})
        self.c.post("/api/schedule", json={"time": "08:00", "pill": "pill1", "qty": 2})   # 2/day -> 3 days
        c = self.container("pill1")
        self.assertEqual((c["daily_use"], c["days_left"], c["refill_due"]), (2.0, 3.0, True))
        s = storage.get_settings()
        sched = storage.get_schedule()
        at = datetime(2026, 11, 26, 18, 0, 30)
        self.assertEqual(prescriptions.check_refills(at - timedelta(hours=1), sched, s), [])   # not yet
        sent = prescriptions.check_refills(at, sched, s)
        self.assertEqual(len(sent), 1)
        self.assertIn("No refills left", sent[0]["message"])
        self.assertEqual(prescriptions.check_refills(at, sched, s), [])                        # once per day


if __name__ == "__main__":
    unittest.main()
