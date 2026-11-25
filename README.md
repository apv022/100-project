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

The script installs Python packages into `venv/`, installs a systemd service (`pill-dispenser`) that starts on boot and restarts on crash, and checks the app answers. To update later:

```bash
git pull && ./install.sh
```

## Open it from your phone (Tailscale)

The app only listens on `127.0.0.1:5000`. If `tailscale serve` isn't already pointing at it, run once on the Pi:

```bash
sudo tailscale serve --bg 5000
```

Then open `https://<pi-name>.<your-tailnet>.ts.net/` on the phone (tailnet devices only). Check with `sudo tailscale serve status`. Never use `tailscale funnel`, because the app has no login.

## Screens

- **Home:** next dose and a big *Dispense Now* button per pill, with a confirmation.
- **Schedule:** add, edit, switch on or off, and delete times, each tied to one pill. Each time fires once a day, up to 10 minutes late, and pills due together go one after another.
- **History:** every dispense with time, pill, scheduled or manual, and problems (empty, nothing came out, hardware error).
- **Settings:** pills remaining per container, with Refill and +/- 1.

Times use the Pi's clock. Set the timezone with `sudo raspi-config` > Localisation.

## Hardware hook (not wired yet)

Right now the app uses a **simulated driver**: it waits a second and pretends a pill came out. A yellow SIMULATION badge shows in the header. Real hardware plugs in at one place:

- `app/hardware.py`: fill in `GpioDriver.dispense_one(pill)`. It must release one pill and return `True`. Return `False` if a sensor saw nothing come out, or raise `DispenseError` on a fault. The app handles locking, stock counts, history and the UI.
- `config.py`: put each pill's pins and settings in its `hw` dict, then set `DRIVER = "gpio"` (or `Environment=PILL_DRIVER=gpio` in the service).
- Add any GPIO libraries to `requirements.txt` and run `./install.sh` again.

## Config

Everything is in `config.py`: pill names, colours, container capacity, port, scheduler timing. Environment overrides: `PILL_PORT`, `PILL_HOST`, `PILL_DRIVER`, `PILL_DATA_DIR`.

## Develop on a laptop

```bash
python3 -m venv venv && venv/bin/pip install -r requirements.txt
```
```bash
venv/bin/python -m app.app
```

Open http://127.0.0.1:5000. Run the tests with `venv/bin/python -m unittest`.

## Layout

| Path | Purpose |
|------|---------|
| `install.sh` | one-shot installer and updater |
| `config.py` | all settings |
| `app/app.py` | Flask routes and JSON API |
| `app/dispenser.py` | dispense routine: stock check, driver call, history |
| `app/hardware.py` | hardware drivers (simulated now, GPIO stub for later) |
| `app/scheduler.py` | background schedule checker |
| `app/storage.py` | JSON files with safe writes (temp file then rename) |
| `app/templates`, `app/static` | the UI (Alpine JS bundled locally, works offline) |
| `data/` | `schedule.json`, `history.json`, `inventory.json`, created on first run, git-ignored |
| `deploy/` | systemd unit template |

## Troubleshooting

- **Phone shows 502:** Tailscale works but the app isn't running. Check `systemctl status pill-dispenser` and `journalctl -u pill-dispenser -e`.
- **Phone can't resolve `*.ts.net`:** turn off Secure DNS / DoH in the phone's browser.
- **Install failed:** check the internet connection and run `./install.sh` again (safe to repeat).
- **Wrong times:** set the Pi's timezone (see above).
- **History says "Hardware error: GPIO driver not implemented yet":** `DRIVER` is set to `gpio` before the driver is written. Set it back to `sim`.

## Planned: OCR prescription scanning

*Not implemented yet.* A *Scan label* button on the Schedule screen would take a photo with a Pi camera or webcam and run Tesseract OCR offline. It would parse the drug name and directions ("twice daily"), then suggest schedule entries. The user always reviews and confirms; nothing is scheduled automatically. Images are deleted right after processing. Printed labels only.
