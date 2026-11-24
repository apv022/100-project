# Pill Dispenser (Raspberry Pi 3 B+)

A timed dispenser for **three different pills**. Three identical units sit side by side: a hopper of one pill on a servo-turned disc with a single pill-sized pocket. The servo rotates the pocket over an exit hole, the pill drops into a shared chute and cup, then the disc turns back. A touchscreen web app sets the schedule, dispenses on demand, logs history and tracks pills remaining. No microcontroller, no weight sensor, no vibration.

> **Safety: this is a class prototype. It is NOT safe for dispensing real medication to people.** Test with candy or dummy pills only.

## Install (on the Pi)

Raspberry Pi OS Desktop, 32-bit, Pi 3 B+, internet needed for install only.

```bash
git clone <this repo's URL> pill-dispenser && cd pill-dispenser
```
```bash
./install.sh
```

Then `sudo reboot`. The app starts on boot and Chromium opens full-screen on the touchscreen. The app listens on `127.0.0.1` only. To reach it from a phone or laptop, see *Remote access* below.

## Update

```bash
git pull && ./update.sh
```

## Wiring

Each servo has its own signal wire; power comes from a **separate 5 V supply (at least 2 A)**, never from the Pi.

| Servo | Signal (orange/yellow) | Power red | Ground brown/black |
|-------|------------------------|-----------|--------------------|
| Pill A | GPIO 18 | supply +5 V | supply GND |
| Pill B | GPIO 12 | supply +5 V | supply GND |
| Pill C | GPIO 13 | supply +5 V | supply GND |

- **Common ground:** connect the supply's GND to a Pi ground pin. Without it the signals do nothing.
- **Do not** connect the supply's +5 V to the Pi's 5 V pin. The Pi keeps its own power supply.
- The software moves one servo at a time, never all three at once.
- Pins, angles, names and hopper capacity are in `config.py`.

## Using it

- **Home:** next dose time and a big *Dispense Now* button per pill (asks for confirmation).
- **Schedule:** add, edit, switch on/off, delete times, each tied to one pill. Pills due at the same minute dispense one after another.
- **History:** every dispense with timestamp, pill, scheduled or manual, and failures (empty hopper, servo error).
- **Settings:** pills remaining per hopper, with Refill (sets to full) and +/- 1.

Each scheduled time fires once per day, up to 10 minutes late (so a reboot does not fire old doses). Check the Pi's timezone: `sudo raspi-config` > Localisation.

## Run on a laptop (simulation)

No servos needed. Simulation turns on automatically when not on a Raspberry Pi.

```bash
python3 -m venv venv && venv/bin/pip install -r requirements.txt
```
```bash
PILL_SIMULATION=1 venv/bin/python -m app.app
```

Open http://localhost:5000. Run the tests with `PILL_SIMULATION=1 venv/bin/python -m unittest`.

## Layout

| Path | Purpose |
|------|---------|
| `config.py` | all constants: pills, pins, angles, timing, simulation, port |
| `app/app.py` | Flask routes and JSON API |
| `app/dispenser.py` | servo control (gpiozero + pigpio) and the dispense routine |
| `app/scheduler.py` | background schedule checker |
| `app/storage.py` | JSON files, safe write (temp file then rename) |
| `app/templates`, `app/static` | touchscreen UI (Alpine JS vendored locally, fully offline) |
| `data/` | `schedule.json`, `history.json`, `inventory.json`, created on first run, git-ignored |
| `deploy/` | systemd unit, kiosk launcher, autostart entry |
| `cad/` | parametric OpenSCAD source, STLs and previews (see `cad/README.md`) |
| `tests/` | unit tests |

## Remote access (Tailscale) and headless Pis

The app binds to `127.0.0.1` (set `PILL_HOST` to change it, not recommended). Do not expose it on `0.0.0.0` or the public internet; there is no login.

With Tailscale installed on the Pi, share it to your tailnet over HTTPS:

```bash
sudo tailscale serve --bg 5000
```

Then open `https://<pi-name>.<your-tailnet>.ts.net/` from any device on the tailnet. Check or undo with `sudo tailscale serve status` and `sudo tailscale serve reset`. Never use `tailscale funnel`, which makes it public. A 502 means serve works but the app is not running (`systemctl status pill-dispenser`). If the browser cannot resolve `*.ts.net`, turn off Secure DNS / DoH in the browser.

If the Pi is headless (no touchscreen yet), `install.sh` still works; the kiosk autostart entry is simply never triggered, and you use the app through the tailnet URL. `./install.sh` and `./update.sh` need SSH access, so run them over `ssh` via the tailnet. Keep ufw's default-deny incoming rule; no extra inbound port is needed because `tailscale serve` handles it.

## Planned: OCR prescription scanning

*Not implemented yet. This is the design for a future feature.*

Goal: point a camera at a prescription label and pre-fill a schedule entry (pill name, doses per day, times), instead of typing it in.

- **Hardware:** a Raspberry Pi Camera Module or any USB webcam. Good lighting and a plain background matter more than resolution.
- **OCR engine:** Tesseract (`apt install tesseract-ocr`, with `pytesseract` and `opencv-python-headless` in `requirements.txt`). It runs fully offline on the Pi 3 B+, so the no-internet rule still holds. Expect a few seconds per scan.
- **Flow:** a *Scan label* button on the Schedule screen takes a photo, then the app crops it, converts to greyscale, thresholds it and runs OCR. Text is parsed for the drug name and directions such as "1 tablet twice daily" or "every 8 hours". The result goes to a review screen.
- **Mapping to hoppers:** the scanned drug name is matched against the pill names in `config.py` and the user picks which hopper (A, B or C) it belongs to. Directions are turned into suggested times: once daily 08:00, twice daily 08:00 and 20:00, three times daily 08:00, 14:00 and 20:00.
- **Human confirmation is mandatory:** OCR misreads often, so nothing is ever scheduled automatically. The user sees the scanned text next to the suggested entries, edits them, and taps *Save*. A low-confidence scan is rejected with a "retake photo" message.
- **Code layout:** a new `app/ocr.py` (capture, preprocess, parse) and one endpoint, `POST /api/scan`, returning the raw text plus suggested entries. Scan images are deleted right after processing and never stored, because prescriptions are private data.
- **Limits:** printed labels only, not handwriting. It cannot check that the right pill is in the hopper.

The safety note above still applies: this is a class prototype and OCR output must never be trusted for real medication.

## Troubleshooting

- **Servo jitters or does nothing:** `systemctl status pigpiod`; start it with `sudo systemctl enable --now pigpiod`. Check the common ground.
- **Pi reboots or freezes when servos move:** servos must use the separate 5 V supply. Check the supply is at least 2 A.
- **History shows "Error" with a servo message:** pigpiod is not running, or the wrong pin in `config.py`.
- **Pills jam or double-drop:** adjust pocket depth and diameter first, then add a paddle, then steepen the hopper. Tune each pocket separately. Open/closed angles are in `config.py`.
- **Blank screen or no browser:** reboot after install; run `deploy/kiosk.sh` from a terminal on the desktop to see errors. The app itself: `journalctl -u pill-dispenser -e`.
- **Screen goes dark:** `sudo raspi-config` > Display > Screen Blanking > Off.
- **Install failed:** check internet, then run `./install.sh` again (it is safe to repeat).
- **Wrong times:** set the Pi timezone (see above).
