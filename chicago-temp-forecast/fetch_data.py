"""Download and normalize the Chicago O'Hare daily temperature record.

Primary source: NOAA GHCN-Daily, station USW00094846 (Chicago O'Hare Intl AP).
That archive runs ~3 days behind, so the tail is gap-filled from the Open-Meteo
forecast API's `past_days` window, bias-corrected against the overlap.

Output: data/chicago_daily.csv with columns date,tmax_f,tmin_f,source
"""

import csv
import io
import json
import os
import subprocess
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

STATION = "USW00094846"                 # Chicago O'Hare Intl AP
GHCN_URL = ("https://www.ncei.noaa.gov/data/"
            "global-historical-climatology-network-daily/access/%s.csv" % STATION)
# O'Hare coordinates, matching the station rather than downtown Chicago.
OHARE_LAT, OHARE_LON = 41.96017, -87.93164
OM_URL = ("https://api.open-meteo.com/v1/forecast"
          "?latitude=%.5f&longitude=%.5f"
          "&daily=temperature_2m_max,temperature_2m_min"
          "&temperature_unit=fahrenheit&timezone=America%%2FChicago"
          "&past_days=%d&forecast_days=1")


def c10_to_f(v):
    """GHCN stores temperatures in tenths of a degree Celsius."""
    return (float(v) / 10.0) * 9.0 / 5.0 + 32.0


def fetch(url, timeout=120):
    """Fetch over HTTPS via curl.

    urllib does not negotiate this environment's egress proxy cleanly, and curl
    is already configured with the right CA bundle, so shell out rather than
    reimplement proxy handling.
    """
    p = subprocess.run(
        ["curl", "-sSL", "--fail", "--max-time", str(timeout), url],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise SystemExit("fetch failed (%d): %s\n  %s"
                         % (p.returncode, url, p.stderr.decode().strip()))
    return p.stdout


def load_ghcn(path=None):
    """Parse the GHCN station CSV into {date: (tmax_f, tmin_f)}."""
    if path and os.path.exists(path):
        raw = open(path, "rb").read()
    else:
        raw = fetch(GHCN_URL)
        with open(os.path.join(DATA, "ghcn_raw.csv"), "wb") as f:
            f.write(raw)

    rdr = csv.DictReader(io.StringIO(raw.decode("utf-8", "replace")))
    out = {}
    for row in rdr:
        tmax, tmin = row.get("TMAX", "").strip(), row.get("TMIN", "").strip()
        if not tmax or not tmin:
            continue
        # Reject values flagged as failing NCEI quality control. The QFLAG is
        # the second field of the comma-separated attributes string.
        for col in ("TMAX_ATTRIBUTES", "TMIN_ATTRIBUTES"):
            parts = (row.get(col) or "").split(",")
            if len(parts) > 1 and parts[1].strip():
                break
        else:
            d = date.fromisoformat(row["DATE"])
            out[d] = (c10_to_f(tmax), c10_to_f(tmin))
    return out


def load_recent(days=92):
    """Recent daily extremes from Open-Meteo, used to gap-fill the GHCN tail."""
    blob = json.loads(fetch(OM_URL % (OHARE_LAT, OHARE_LON, days), timeout=60))
    daily = blob["daily"]
    return {date.fromisoformat(t): (mx, mn)
            for t, mx, mn in zip(daily["time"],
                                 daily["temperature_2m_max"],
                                 daily["temperature_2m_min"])
            if mx is not None and mn is not None}


def build():
    ghcn = load_ghcn(os.path.join(DATA, "ghcn_raw.csv"))
    recent = load_recent()
    last_ghcn = max(ghcn)

    # Open-Meteo is a reanalysis grid cell, not the O'Hare thermometer. Measure
    # the offset where the two overlap so the gap-filled days sit on the same
    # scale as the 80 years of station data the model is trained on.
    overlap = sorted(set(ghcn) & set(recent))
    if len(overlap) < 14:
        raise SystemExit("only %d overlapping days; refusing to gap-fill" % len(overlap))
    bias_max = sum(ghcn[d][0] - recent[d][0] for d in overlap) / len(overlap)
    bias_min = sum(ghcn[d][1] - recent[d][1] for d in overlap) / len(overlap)

    rows = [(d, ghcn[d][0], ghcn[d][1], "ghcn") for d in sorted(ghcn)]
    filled = 0
    for d in sorted(recent):
        if d > last_ghcn and d <= date.today():
            rows.append((d, recent[d][0] + bias_max, recent[d][1] + bias_min, "openmeteo"))
            filled += 1

    with open(os.path.join(DATA, "chicago_daily.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "tmax_f", "tmin_f", "source"])
        for d, mx, mn, src in rows:
            w.writerow([d.isoformat(), "%.2f" % mx, "%.2f" % mn, src])

    print("GHCN     : %s .. %s  (%d days)" % (min(ghcn), last_ghcn, len(ghcn)))
    print("overlap  : %d days, bias tmax %+.2f F, tmin %+.2f F"
          % (len(overlap), bias_max, bias_min))
    print("gap-fill : %d days appended through %s" % (filled, rows[-1][0]))
    print("total    : %d rows -> data/chicago_daily.csv" % len(rows))


if __name__ == "__main__":
    build()
