"""Walk-forward validation of the forecast model against naive baselines.

A model that is fit and scored on the same years tells you nothing. Here the
parameters are refit at the start of each test year using only the data that
existed before it, then scored on that year's out-of-sample days. Refitting
annually rather than daily keeps the run tractable in pure Python and costs
almost nothing in realism: 60+ years of climatology barely moves in a year.

Scored against the two baselines any weather forecast has to beat:
  persistence  -- tomorrow will be like today
  climatology  -- tomorrow will be the seasonal normal
"""

import math
import sys
from datetime import date, timedelta

from model import load, ols, dot, season_features

FIRST_TEST_YEAR = 2011
HORIZONS = (1, 2)


def rmse(e):
    return math.sqrt(sum(x * x for x in e) / len(e))


def mae(e):
    return sum(abs(x) for x in e) / len(e)


def anomalies(series, w_max, w_min):
    out = {}
    for d, mx, mn in series:
        row = season_features(d)
        out[d] = (mx - dot(w_max, row), mn - dot(w_min, row))
    return out


def fit_ar(anom, dates, lags):
    rows, y_max, y_min = [], [], []
    for d in dates:
        row = [1.0]
        for k in range(1, lags + 1):
            prev = anom.get(d - timedelta(days=k))
            if prev is None:
                row = None
                break
            row.extend(prev)
        if row is None:
            continue
        rows.append(row)
        y_max.append(anom[d][0])
        y_min.append(anom[d][1])
    return ols(rows, y_max), ols(rows, y_min)


def ar_forecast(anom, origin, horizon, lags, ar_max, ar_min):
    """Iterate the AR `horizon` steps past `origin`. None if history is gapped."""
    work = {}
    for k in range(lags):
        prev = anom.get(origin - timedelta(days=k))
        if prev is None:
            return None
        work[origin - timedelta(days=k)] = prev
    for h in range(1, horizon + 1):
        d = origin + timedelta(days=h)
        row = [1.0]
        for k in range(1, lags + 1):
            row.extend(work[d - timedelta(days=k)])
        a = (dot(ar_max, row), dot(ar_min, row))
        if h == horizon:
            return a
        work[d] = a


def run(lag_orders=(1, 2, 3, 4, 5, 7), verbose=True):
    series = load()
    obs = {d: (mx, mn) for d, mx, mn in series}
    last_year = max(obs).year

    # errors[key][horizon] -> {"max": [...], "min": [...]}
    errors = {}

    def record(key, h, target, emax, emin):
        slot = errors.setdefault(key, {}).setdefault(h, {"max": [], "min": [],
                                                         "dates": []})
        slot["max"].append(emax)
        slot["min"].append(emin)
        slot["dates"].append(target)

    for year in range(FIRST_TEST_YEAR, last_year + 1):
        cutoff = date(year, 1, 1)
        train = [r for r in series if r[0] < cutoff]
        design = [season_features(d) for d, _, _ in train]
        w_max = ols(design, [mx for _, mx, _ in train])
        w_min = ols(design, [mn for _, _, mn in train])

        anom = anomalies(series, w_max, w_min)          # frozen weights, all days
        train_dates = [d for d, _, _ in train]
        ars = {p: fit_ar(anom, train_dates, p) for p in lag_orders}

        test_days = [d for d in obs if d.year == year]
        for origin in sorted(test_days):
            for h in HORIZONS:
                target = origin + timedelta(days=h)
                truth = obs.get(target)
                if truth is None or target.year != year:
                    continue          # keep every scored day inside the test year

                crow = season_features(target)
                cmx, cmn = dot(w_max, crow), dot(w_min, crow)
                record("climatology", h, target, cmx - truth[0], cmn - truth[1])

                here = obs.get(origin)
                if here:
                    record("persistence", h, target,
                           here[0] - truth[0], here[1] - truth[1])

                for p, (ar_max, ar_min) in ars.items():
                    a = ar_forecast(anom, origin, h, p, ar_max, ar_min)
                    if a is None:
                        continue
                    record("model(lags=%d)" % p, h, target,
                           cmx + a[0] - truth[0], cmn + a[1] - truth[1])

        if verbose:
            print("  ... %d done" % year, file=sys.stderr)

    return errors


def report(errors):
    order = (["persistence", "climatology"]
             + sorted(k for k in errors if k.startswith("model")))
    for h in HORIZONS:
        print("\n=== horizon +%d day%s ===" % (h, "" if h == 1 else "s"))
        print("%-18s %8s %8s %8s %8s %7s" %
              ("method", "MAEmax", "RMSEmax", "MAEmin", "RMSEmin", "n"))
        base = None
        for key in order:
            slot = errors.get(key, {}).get(h)
            if not slot:
                continue
            am, rm = mae(slot["max"]), rmse(slot["max"])
            an, rn = mae(slot["min"]), rmse(slot["min"])
            combined = (am + an) / 2
            if key == "persistence":
                base = combined
            skill = "" if base is None else "  %+5.1f%%" % (-100 * (combined - base) / base)
            print("%-18s %8.2f %8.2f %8.2f %8.2f %7d%s"
                  % (key, am, rm, an, rn, len(slot["max"]), skill))
        print("  (skill % = reduction in mean MAE vs persistence)")


if __name__ == "__main__":
    print("backtesting %d-%s, annual refit, expanding window..."
          % (FIRST_TEST_YEAR, "present"), file=sys.stderr)
    report(run())
