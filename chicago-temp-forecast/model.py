"""A climatology + autoregression model for next-day Chicago temperature.

The decomposition is the standard one for surface temperature:

    T(t) = climatology(day-of-year) + warming trend + anomaly(t)

Climatology and trend are fit together by ordinary least squares on Fourier
features of the annual cycle. What is left is the anomaly -- how far today ran
above or below its seasonal normal -- and that residual is strongly
autocorrelated, because weather systems persist for days. A vector
autoregression on the (tmax, tmin) anomaly pair captures that persistence and
supplies the actual forecast skill over bare climatology.

No third-party dependencies: the linear algebra is a ridge-regularized normal
equation solved by Gaussian elimination with partial pivoting.
"""

import csv
import math
import os
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
DAILY_CSV = os.path.join(HERE, "data", "chicago_daily.csv")

N_HARMONICS = 4        # annual cycle + 3 overtones
TREND_EPOCH = 1993.0   # centers the trend term near the middle of the record
RIDGE = 1e-8


# --------------------------------------------------------------------------
# linear algebra
# --------------------------------------------------------------------------

def solve(a, b):
    """Solve a*x = b for square a, by Gaussian elimination with pivoting."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-14:
            raise ValueError("singular normal matrix at column %d" % col)
        m[col], m[piv] = m[piv], m[col]
        inv = 1.0 / m[col][col]
        for r in range(col + 1, n):
            f = m[r][col] * inv
            if f:
                for c in range(col, n + 1):
                    m[r][c] -= f * m[col][c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        s = m[r][n] - sum(m[r][c] * x[c] for c in range(r + 1, n))
        x[r] = s / m[r][r]
    return x


def ols(rows, targets):
    """Least-squares fit of targets on design rows, via ridged normal equations."""
    p = len(rows[0])
    ata = [[0.0] * p for _ in range(p)]
    atb = [0.0] * p
    for row, y in zip(rows, targets):
        for i in range(p):
            ri = row[i]
            if ri:
                atb[i] += ri * y
                ai = ata[i]
                for j in range(i, p):
                    ai[j] += ri * row[j]
    for i in range(p):                      # mirror the symmetric half
        ata[i][i] += RIDGE
        for j in range(i):
            ata[i][j] = ata[j][i]
    return solve(ata, atb)


def dot(w, row):
    return sum(wi * xi for wi, xi in zip(w, row))


# --------------------------------------------------------------------------
# data
# --------------------------------------------------------------------------

def load(path=DAILY_CSV):
    """Return [(date, tmax_f, tmin_f), ...] sorted ascending."""
    out = []
    with open(path) as f:
        for row in csv.DictReader(f):
            out.append((date.fromisoformat(row["date"]),
                        float(row["tmax_f"]), float(row["tmin_f"])))
    out.sort()
    return out


def season_features(d):
    """Fourier features of the annual cycle, plus intercept and linear trend.

    The phase uses the fraction of the actual year elapsed, so Feb 29 and the
    365/366-day year length are handled without a discontinuity.
    """
    jan1 = date(d.year, 1, 1)
    year_len = (date(d.year + 1, 1, 1) - jan1).days
    phase = 2.0 * math.pi * ((d - jan1).days / year_len)
    year_frac = d.year + (d - jan1).days / year_len

    row = [1.0, year_frac - TREND_EPOCH]
    for k in range(1, N_HARMONICS + 1):
        row.append(math.cos(k * phase))
        row.append(math.sin(k * phase))
    return row


# --------------------------------------------------------------------------
# model
# --------------------------------------------------------------------------

class Model(object):
    """Climatology + trend + VAR(p) on the (tmax, tmin) anomaly pair."""

    def __init__(self, lags=3):
        self.lags = lags

    def fit(self, series):
        # --- stage 1: seasonal climatology and secular trend -----------------
        design = [season_features(d) for d, _, _ in series]
        self.w_max = ols(design, [mx for _, mx, _ in series])
        self.w_min = ols(design, [mn for _, _, mn in series])

        anom = {}
        for (d, mx, mn), row in zip(series, design):
            anom[d] = (mx - dot(self.w_max, row), mn - dot(self.w_min, row))
        self.anom = anom

        # --- stage 2: autoregression on the anomalies ------------------------
        # Rows need an unbroken run of `lags` preceding days; the station record
        # has occasional gaps, and an AR row spanning one would be meaningless.
        rows, y_max, y_min = [], [], []
        for d, _, _ in series:
            hist = self._lag_row(anom, d)
            if hist is None:
                continue
            rows.append(hist)
            y_max.append(anom[d][0])
            y_min.append(anom[d][1])
        self.ar_max = ols(rows, y_max)
        self.ar_min = ols(rows, y_min)
        self.n_ar_rows = len(rows)
        return self

    def _lag_row(self, anom, d):
        """[1, max(t-1), min(t-1), max(t-2), min(t-2), ...] or None if gapped."""
        row = [1.0]
        for k in range(1, self.lags + 1):
            prev = anom.get(d - timedelta(days=k))
            if prev is None:
                return None
            row.extend(prev)
        return row

    def climatology(self, d):
        row = season_features(d)
        return dot(self.w_max, row), dot(self.w_min, row)

    def predict(self, target, anom=None):
        """Forecast (tmax, tmin) for `target`, iterating the AR across any gap.

        Days beyond the end of the record are produced by feeding each predicted
        anomaly back in as the next lag, so a two-day-ahead forecast is the
        one-day model applied twice.
        """
        anom = dict(self.anom if anom is None else anom)
        last = max(anom)
        if target <= last:
            raise ValueError("target %s is not beyond the data (%s)" % (target, last))

        d = last + timedelta(days=1)
        while True:
            row = self._lag_row(anom, d)
            if row is None:
                raise ValueError("gap in anomaly history before %s" % d)
            a = (dot(self.ar_max, row), dot(self.ar_min, row))
            if d == target:
                cmx, cmn = self.climatology(d)
                return cmx + a[0], cmn + a[1], a
            anom[d] = a
            d += timedelta(days=1)
