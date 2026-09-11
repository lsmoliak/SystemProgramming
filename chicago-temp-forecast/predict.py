"""Produce the next-day Chicago temperature forecast and its error bars.

Point forecast comes from model.Model fit on the full record. The uncertainty
is empirical rather than assumed Gaussian: it is read off the walk-forward
backtest residuals, restricted to days near the same time of year as the
target. That restriction matters -- a January forecast for Chicago is far
more uncertain than a July one, and pooling them would understate summer
confidence and overstate winter's.
"""

import json
import subprocess
import sys
from datetime import date, timedelta

from backtest import run
from model import Model, load

LAGS = 3                 # backtest showed skill saturates here
DOY_WINDOW = 21          # +/- days around the target's day-of-year
OHARE_LAT, OHARE_LON = 41.96017, -87.93164


def doy_distance(a, b):
    """Circular distance in days between two dates' positions in the year."""
    d = abs(a.timetuple().tm_yday - b.timetuple().tm_yday)
    return min(d, 365 - d)


def quantile(xs, q):
    xs = sorted(xs)
    if not xs:
        return float("nan")
    pos = q * (len(xs) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (pos - lo) * (xs[hi] - xs[lo])


def seasonal_errors(errors, horizon, target):
    """Backtest residuals for this horizon, near this target's day-of-year."""
    slot = errors["model(lags=%d)" % LAGS][horizon]
    out = {"max": [], "min": []}
    for d, em, en in zip(slot["dates"], slot["max"], slot["min"]):
        if doy_distance(d, target) <= DOY_WINDOW:
            out["max"].append(em)
            out["min"].append(en)
    return out


def nwp_reference(days=4):
    """Current physics-based forecast, for comparison only -- never an input."""
    url = ("https://api.open-meteo.com/v1/forecast"
           "?latitude=%.5f&longitude=%.5f"
           "&daily=temperature_2m_max,temperature_2m_min"
           "&temperature_unit=fahrenheit&timezone=America%%2FChicago"
           "&forecast_days=%d" % (OHARE_LAT, OHARE_LON, days))
    p = subprocess.run(["curl", "-sS", "--fail", "--max-time", "30", url],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        return {}
    dd = json.loads(p.stdout)["daily"]
    return {date.fromisoformat(t): (mx, mn) for t, mx, mn
            in zip(dd["time"], dd["temperature_2m_max"], dd["temperature_2m_min"])}


def main():
    series = load()
    last = series[-1][0]
    print("station record through %s (%d days)\n" % (last, len(series)))

    print("calibrating error bars from walk-forward backtest...", file=sys.stderr)
    errors = run(lag_orders=(LAGS,), verbose=False)

    model = Model(lags=LAGS).fit(series)
    nwp = nwp_reference()

    for h in (1, 2):
        target = last + timedelta(days=h)
        mx, mn, anom = model.predict(target)
        cmx, cmn = model.climatology(target)
        se = seasonal_errors(errors, h, target)

        print("=" * 66)
        print("%s   (+%d day%s from last observation)"
              % (target.strftime("%A, %B %d, %Y"), h, "" if h == 1 else "s"))
        print("=" * 66)
        for label, val, a, errs in (("HIGH", mx, anom[0], se["max"]),
                                    ("LOW", mn, anom[1], se["min"])):
            lo80 = val - quantile(errs, 0.90)
            hi80 = val - quantile(errs, 0.10)
            lo95 = val - quantile(errs, 0.975)
            hi95 = val - quantile(errs, 0.025)
            clim = cmx if label == "HIGH" else cmn
            print("  %-5s %6.1f F   (%.1f C)" % (label, val, (val - 32) * 5 / 9))
            print("        seasonal normal %.1f F, anomaly %+.1f F" % (clim, a))
            print("        80%% interval  %.1f - %.1f F" % (lo80, hi80))
            print("        95%% interval  %.1f - %.1f F" % (lo95, hi95))
            print("        backtest MAE  %.2f F  (n=%d nearby days)"
                  % (sum(abs(e) for e in errs) / len(errs), len(errs)))
        if target in nwp:
            print("  --- physics-based NWP forecast for the same day: "
                  "high %.1f F, low %.1f F" % nwp[target])
        print()


if __name__ == "__main__":
    main()
