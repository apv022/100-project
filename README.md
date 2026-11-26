# Pill Dispenser Web App

A Flask web app for a three-pill dispenser on a Raspberry Pi: dispense on demand, run a daily schedule, keep a history, and track pills remaining. It runs on the Pi on `127.0.0.1` only. Reach it from your phone over Tailscale.

> **Safety: this is a class prototype. It is NOT safe for dispensing real medication to people.**

## Install / update (on the Pi)

Raspberry Pi OS (32-bit, headless is fine). Needs internet for the install only.

```bash
git clone <this repo's URL> pill-dispenser && cd pill-dispenser
```
```bash
./install.sh
```

The script installs Tesseract OCR and the Python packages into `venv/`, installs a systemd service (`pill-dispenser`) that starts on boot and restarts on crash, and checks the app answers. To update later:

```bash
git pull && ./install.sh
```

## Open it from your phone (Tailscale)

The app only listens on `127.0.0.1:5000`. If `tailscale serve` isn't already pointing at it, run once on the Pi:

```bash
sudo tailscale serve --bg 5000
```

Then open `https://<pi-name>.<your-tailnet>.ts.net/` on the phone (tailnet devices only). Check with `sudo tailscale serve status`. Never use `tailscale funnel`, because the app has no login.

## What it does

- **Home:** doses waiting in the cup with a big **I took it** button (and Skip), the next dose, refill warnings, and a *Dispense Now* button per container.
- **Schedule:** times of day, each with a container, pills per dose and days of the week. Each time fires once a day, up to 10 minutes late. Doses due together go one pill at a time.
- **Meds:** one prescription per container: name, strength, directions, pills per dose, quantity per fill, refills left, Rx number, prescriber, pharmacy. It shows pills **left**, pills **used**, **days of supply** left (worked out from the schedule) and when it runs out. *Refill* when a new bottle goes in, or *-1 / +1* to correct the count.
- **Scan label:** take a photo of the pharmacy label with the phone. The Pi reads it with OCR (Tesseract, offline) and fills the prescription form: name, strength, directions, pills per dose, quantity, refills, Rx #, prescriber, pharmacy, date. It also suggests times ("twice daily" means 08:00 and 20:00). **You review every field before saving**; nothing is scheduled without a tick. The photo is deleted right after reading. Works best on a flat, well-lit, straight-on photo of a printed label.
- **History:** every dispense, taken, skipped and not-taken dose, and problems.
- **Settings:** refill reminder time, warning threshold, the reminder/alarm/not-taken timings, sound and notifications on this phone, and test buttons.

### Dose reminders and alarm

When a scheduled dose is dispensed, the speaker beeps and a notification is sent. If it isn't marked taken:

| After (default) | What happens |
|-----------------|--------------|
| 5 min | reminder beep + notification |
| 15 min | **alarm on** (speaker), urgent notification, the app turns red |
| 60 min | dose logged as **not taken**, alarm off, notification |

*I took it* (or the cup sensor, once it exists) stops it. All timings are in Settings.

### Refill reminders

Every day at the refill reminder time (default 18:00) the app checks each container. If it is at or below 5 pills, or the schedule says it runs out within the warning days (default 3), you get a notification. It says how many refills are left on the prescription, or to contact the prescriber if none.

### Notifications

- **In the app:** the bell shows unread notifications.
- **On the phone while the page is open:** Settings > *Turn on phone notifications* and *Play sounds*.
- **On the phone when the page is closed:** optional, through [ntfy](https://ntfy.sh). Install the ntfy app, subscribe to a long random topic name, then on the Pi:

  ```bash
  echo "PILL_NTFY_URL=https://ntfy.sh/your-long-random-topic" >> data/pill.env
  ```
  ```bash
  sudo systemctl restart pill-dispenser
  ```

  Heads up: this sends notification text (medication names) to the ntfy server. Use a self-hosted ntfy on your tailnet if that matters.

Times use the Pi's clock. Set the timezone with `sudo raspi-config` > Localisation.

## Hardware hooks (not wired yet)

The app runs on a **simulated driver** (yellow SIM badge): dispensing waits a second and succeeds, and beeps and alarms are just logged. Everything hardware goes through one class in `app/hardware.py`. Fill in `GpioDriver`:

| Method | Called when | Return |
|--------|-------------|--------|
| `dispense_one(pill)` | one pill is needed from a container | `True` if a pill came out, `False` if a sensor saw nothing, or raise `DispenseError` |
| `beep(pattern)` | `"dose"`, `"reminder"`, `"error"`, `"test"` | nothing |
| `alarm_on()` / `alarm_off()` | dose not taken / taken or given up | nothing |
| `cup_state()` | every few seconds while a dose waits | `"empty"` (counts as taken), `"full"`, or `None` if there is no sensor |

Only `dispense_one` is required. The rest can stay as no-ops. Pins go in each container's `hw` dict in `config.py`. Then set `PILL_DRIVER=gpio` in `data/pill.env` and restart. Add any GPIO libraries to `requirements.txt` and run `./install.sh` again.

## Config

Everything is in `config.py`: pill names, colours, container capacity, port, scheduler timing. Environment overrides, in `data/pill.env` on the Pi: `PILL_PORT`, `PILL_HOST`, `PILL_DRIVER`, `PILL_DATA_DIR`, `PILL_NTFY_URL`.

## Develop on a laptop

```bash
python3 -m venv venv && venv/bin/pip install -r requirements.txt
```
```bash
venv/bin/python -m app.app
```

Open http://127.0.0.1:5000. Run the tests with `venv/bin/python -m unittest`. For label scanning, install Tesseract (`sudo apt install tesseract-ocr` or `brew install tesseract`).

## Layout

| Path | Purpose |
|------|---------|
| `install.sh` | one-shot installer and updater |
| `config.py` | all settings |
| `app/app.py` | Flask routes and JSON API |
| `app/dispenser.py` | dispense routine: stock check, driver call, history |
| `app/hardware.py` | hardware drivers: simulated now, GPIO stub for motors, speaker and cup sensor |
| `app/prescriptions.py` | prescriptions, pill counts, days of supply, refill reminders |
| `app/doses.py` | doses waiting to be taken: reminder, alarm, not taken |
| `app/notify.py` | notifications (in-app and optional ntfy push) |
| `app/ocr.py` | label scanning: Tesseract OCR and the label parser |
| `app/scheduler.py` | background schedule checker |
| `app/storage.py` | JSON files with safe writes (temp file then rename) |
| `app/templates`, `app/static` | the UI (Alpine JS bundled locally, works offline) |
| `data/` | JSON data (schedule, prescriptions, doses, history, notifications, settings) and the optional `pill.env`, git-ignored |
| `deploy/` | systemd unit template |

## Troubleshooting

- **Phone shows 502:** Tailscale works but the app isn't running. Check `systemctl status pill-dispenser` and `journalctl -u pill-dispenser -e`.
- **Phone can't resolve `*.ts.net`:** turn off Secure DNS / DoH in the phone's browser.
- **Install failed:** check the internet connection and run `./install.sh` again (safe to repeat).
- **Wrong times:** set the Pi's timezone (see above).
- **Label scan got fields wrong:** fix them in the form before saving. Retake the photo closer, flat and well lit, with no glare. Handwriting won't work. *Text read from the label* in the form shows what OCR saw.
- **Scan says OCR not installed:** run `./install.sh` again, or `sudo apt install tesseract-ocr`.
- **No phone alerts when the page is closed:** browser notifications need the page open. Set up ntfy (above).
- **History says "Hardware error: GPIO driver not implemented yet":** `DRIVER` is set to `gpio` before the driver is written. Set it back to `sim`.
