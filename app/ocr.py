"""Prescription label scanning: OCR with the tesseract command, then a
best-effort parser that turns the text into prescription fields and suggested
dose times. The user always reviews the result before anything is saved."""
import os
import re
import shutil
import subprocess
import tempfile

import config


class OcrError(Exception):
    pass


def available():
    return shutil.which(config.TESSERACT_CMD) is not None


def image_to_text(data):
    """Run OCR on image bytes. The image only exists on disk during the call."""
    if not available():
        raise OcrError("OCR is not installed on the Pi. Run: sudo apt install tesseract-ocr")
    fd, path = tempfile.mkstemp(suffix=".img")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        best = ""
        for psm in ("4", "6"):   # 4: columns of text, 6: one block. Keep the longer read.
            try:
                out = subprocess.run([config.TESSERACT_CMD, path, "stdout", "-l", "eng", "--psm", psm],
                                     capture_output=True, text=True, timeout=config.OCR_TIMEOUT)
            except subprocess.TimeoutExpired:
                raise OcrError("OCR took too long. Try a closer, sharper photo.")
            if out.returncode != 0 and not best:
                raise OcrError("Could not read that image: " + (out.stderr.strip().splitlines() or ["unknown error"])[-1])
            if len(re.sub(r"\W", "", out.stdout)) > len(re.sub(r"\W", "", best)):
                best = out.stdout
        return best
    finally:
        os.unlink(path)


# ---------------------------------------------------------------- parsing
WORDNUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "a": 1, "an": 1}
FREQS = [  # checked in order: more specific first
    (4, r"four times (?:a|per|each) day|4 times (?:a|per|each) day|\bqid\b|every 6 hours|\bq6h\b"),
    (3, r"three times (?:a|per|each) day|3 times (?:a|per|each) day|\btid\b|every 8 hours|\bq8h\b"),
    (2, r"twice (?:a |per |each )?day|twice daily|two times (?:a|per|each) day|2 times (?:a|per|each) day"
        r"|\bbid\b|every 12 hours|\bq12h\b|morning and (?:evening|night|bedtime)"),
    (1, r"once (?:a |per |each )?day|once daily|\bdaily\b|every day|each day|\bqd\b|every morning"
        r"|every (?:night|evening)|at bedtime|in the morning|\bqhs\b|nightly"),
]
TIMES = {1: ["08:00"], 2: ["08:00", "20:00"], 3: ["08:00", "14:00", "20:00"], 4: ["08:00", "12:00", "16:00", "20:00"]}
STRENGTH = re.compile(r"(\d+(?:[.,]\d+)?)\s?(mg|mcg|µg|g|ml|iu|units?)\b", re.I)
NOT_NAME = re.compile(r"pharmacy|\brx\b|take|qty|quantity|refill|\bdr\b|doctor|prescriber|date|phone|tel\b|"
                      r"street|\bst\b|\bave\b|road|patient|\bfor\b|expires|discard|warning|caution", re.I)
DIRECTION = re.compile(r"\b(take|chew|dissolve|place|use|swallow)\b.{3,200}?(?=\.|\bqty\b|\bquantity\b|\brefills?\b"
                       r"|\brx\b|\bdr\b\.?|\bdiscard\b|$)", re.I)


def _num(word):
    word = word.lower()
    return int(word) if word.isdigit() else WORDNUM.get(word)


def parse_label(text):
    """Return {"fields": {...}, "times": [...], "times_per_day": n|None, "warnings": [...]}."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    flat = " ".join(lines)
    low = flat.lower()
    f, warnings = {}, []

    # name + strength: the text before the first strength on its line
    for ln in lines:
        m = STRENGTH.search(ln)
        if m and not re.match(r"\s*(take|qty|quantity)", ln, re.I):
            name = re.sub(r"[^A-Za-z\- ]", " ", ln[:m.start()]).strip(" -")
            name = re.sub(r"\s+", " ", name)
            if len(name) >= 3 and not NOT_NAME.search(name):
                f["name"] = name.title()
                f["strength"] = m.group(1).replace(",", ".") + " " + m.group(2).lower()
                break
    if "name" not in f:
        for ln in lines:
            word = re.sub(r"[^A-Za-z\- ]", " ", ln).strip()
            if len(word) >= 4 and ln.isupper() and not NOT_NAME.search(ln):
                f["name"] = re.sub(r"\s+", " ", word).title()
                break
        warnings.append("Medication name/strength not found clearly. Check them.")

    m = DIRECTION.search(flat)
    if m:
        f["instructions"] = m.group(0).strip().rstrip(".") + "."
        d = re.search(r"\b(?:take|chew|dissolve|place|use|swallow)\s+(\d+|one|two|three|four|five|a|an)\b",
                      m.group(0), re.I)
        if d and _num(d.group(1)):
            f["dose_qty"] = _num(d.group(1))
        if re.search(r"\b(half|1/2|½)\b", m.group(0), re.I):
            warnings.append("Half tablets can't be dispensed automatically.")

    m = re.search(r"\b(?:qty|quantity|quan|disp(?:ensed)?)\s*[:.#]?\s*(\d{1,4})\b", flat, re.I)
    if m:
        f["quantity"] = int(m.group(1))
    if re.search(r"\bno refills?\b|\brefills?\s*[:.]?\s*(?:no|none|zero)\b", low):
        f["refills_left"] = 0
    else:
        m = (re.search(r"\brefills?\s*(?:left|remaining|rem)?\s*[:.#]?\s*(\d{1,2})\b", low)
             or re.search(r"\b(\d{1,2})\s+refills?\b", low))
        if m:
            f["refills_left"] = int(m.group(1))
    m = re.search(r"\brx\s*(?:#|no\.?|num(?:ber)?)?\s*[:.#]?\s*([0-9][0-9-]{4,})", flat, re.I)
    if m:
        f["rx_number"] = m.group(1)
    for ln in lines:
        m = re.search(r"\b(?:dr\.?|prescriber|doctor|physician)\s*[:.]?\s+([A-Za-z][A-Za-z.' -]{2,40})", ln, re.I)
        if m:
            f["prescriber"] = ("Dr. " if re.match(r"dr", ln[m.start():], re.I) else "") + m.group(1).strip(" .").title()
            break
    m = re.search(r"\b(?:date filled|filled|fill date|date)\s*[:.]?\s*(\d{1,4}[/.-]\d{1,2}[/.-]\d{1,4})", flat, re.I)
    if m:
        f["filled_on"] = m.group(1)
    for ln in lines[:3]:
        if re.search(r"pharmacy|drug ?mart|apothecary|chemist", ln, re.I):
            f["pharmacy"] = ln.strip()
            break

    n, times = None, []
    if re.search(r"as needed|\bprn\b|when required|if needed", low):
        warnings.append("'As needed' medication: no automatic schedule suggested.")
    else:
        for count, pat in FREQS:
            if re.search(pat, low):
                n = count
                times = list(TIMES[count])
                if count == 1 and re.search(r"bedtime|night|evening|\bqhs\b", low):
                    times = ["21:00"]
                break
        if n is None:
            warnings.append("How often to take it wasn't found. Add the times yourself.")
    if "quantity" not in f:
        warnings.append("Quantity not found.")
    return {"fields": f, "times": times, "times_per_day": n, "warnings": warnings}
