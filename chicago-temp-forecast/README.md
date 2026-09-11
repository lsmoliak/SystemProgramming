# Chicago next-day temperature forecast

A statistical temperature forecaster for Chicago, built from the historical
record alone. No third-party Python packages.

**Station:** NOAA GHCN-Daily `USW00094846` — Chicago O'Hare International
Airport (41.960 N, 87.932 W, 205 m).
**Record:** 24,786 quality-controlled days, 1958-11-01 → present.

## The model

Surface temperature decomposes naturally into three pieces:

```
T(t) = seasonal climatology(day-of-year) + warming trend + anomaly(t)
```

1. **Climatology and trend** are fit together by ordinary least squares on
   Fourier features of the annual cycle — 4 harmonics, so the fundamental plus
   three overtones, which is enough to capture the asymmetry between Chicago's
   slow spring warm-up and its faster autumn cool-down — plus a linear term in
   calendar year.

2. **The anomaly** is what remains: how far a day ran above or below its
   seasonal normal. It is strongly autocorrelated, because weather systems
   persist for several days, and that autocorrelation is the only real source
   of forecast skill available here.

3. **A vector autoregression** on the `(tmax, tmin)` anomaly pair — 3 lags,
   each day's high and low predicted from the previous three days' highs *and*
   lows — supplies the forecast. Multi-day forecasts iterate it, feeding each
   predicted anomaly back in as the next lag.

The linear algebra is a ridge-regularized normal equation solved by Gaussian
elimination with partial pivoting (`model.solve`). Nothing is imported that
isn't in the standard library.

### What the fit recovers

The trend term comes out at **+0.39 °F/decade for daily highs and
+0.77 °F/decade for daily lows**. Nights warming about twice as fast as days is
the expected signature of combined greenhouse and urban-heat-island warming,
and it falls out of the regression without being put there.

## Validation

`backtest.py` refits the model at the start of each test year using only data
that existed before it, then scores that year's days out of sample. 2011–2026,
5,716 scored days:

| horizon +1 day | MAE high | RMSE high | MAE low | RMSE low | skill |
|---|---|---|---|---|---|
| persistence  | 6.28 | 8.40 | 4.89 | 6.59 | — |
| climatology  | 7.89 | 10.03 | 6.79 | 8.74 | −31.5% |
| **model (3 lags)** | **5.76** | **7.43** | **4.27** | **5.64** | **+10.2%** |

| horizon +2 days | MAE high | RMSE high | MAE low | RMSE low | skill |
|---|---|---|---|---|---|
| persistence  | 8.74 | 11.31 | 6.97 | 9.12 | — |
| climatology  | 7.90 | 10.04 | 6.78 | 8.73 | +6.5% |
| **model (3 lags)** | **7.32** | **9.29** | **5.89** | **7.61** | **+15.9%** |

Skill is the reduction in mean MAE against persistence. Skill saturates at 3
lags — 4, 5 and 7 lags are indistinguishable — so 3 is what ships.

Prediction intervals are empirical, taken from backtest residuals within ±21
days of the target's day-of-year rather than assumed Gaussian. Chicago's
forecast uncertainty is strongly seasonal (January is far less predictable than
July), and pooling the whole year would overstate winter confidence and
understate summer's.

## The honest limit

This model beats persistence and climatology, which is the bar it was built to
clear. It does **not** approach a real weather forecast, and it cannot.

A numerical weather prediction model ingests the current three-dimensional
state of the atmosphere — pressure fields, upper-level winds, moisture, the
position of every front — and integrates the physics forward. Day-1 MAE for
NWP is typically 2–3 °F. This model sees one number per day at one point on the
ground. It has no way to know a warm air mass is moving in until it arrives,
so it always regresses toward the seasonal normal.

`predict.py` prints the current NWP forecast alongside its own output for
exactly this reason. When the two disagree sharply, the NWP is the one to
believe.

## Usage

```sh
python3 fetch_data.py   # download NOAA record, normalize to data/chicago_daily.csv
python3 backtest.py     # walk-forward validation table
python3 predict.py      # next-day forecast with calibrated intervals
```

`fetch_data.py` gap-fills the 2–3 day lag in the NOAA archive from the
Open-Meteo reanalysis at the same coordinates, bias-corrected against the
overlapping period (the measured offset is small — about 0.2 °F — which is
itself a useful check that the two sources agree).
