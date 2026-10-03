# /// script
# requires-python = ">=3.10"
# dependencies = ["influxdb-client", "pandas", "numpy", "python-dotenv"]
# ///
"""
Two checks on Berkeley's data:
  1. Altitude: how do calculated_values.altitude_ft / imu_altitude_ft relate to GPS altitude? (Berkeley question 7)
  2. Brake: which of mechBrake > threshold / brakePos > 0 best matches the car actually slowing down?
Usage: uv run scripts/investigate_altitude_brake.py   (reads the local berkeley_asc_2026 bucket)
"""
from pathlib import Path
import os
import warnings

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient
from influxdb_client.client.warnings import MissingPivotFunction

warnings.simplefilter("ignore", MissingPivotFunction)

ROOT = Path(__file__).resolve().parent.parent
BUCKET, ORG = "berkeley_asc_2026", "calsol"
RANGE = "range(start: 2026-07-25T00:00:00Z, stop: 2026-08-02T00:00:00Z)"
FT, MPH = 0.3048, 0.44704

load_dotenv(ROOT / ".env")
query_api = InfluxDBClient(url=os.environ["INFLUX_URL"], token=os.environ["INFLUX_TOKEN"], org=ORG, timeout=600_000).query_api()


def field(measurement: str, name: str, lo: float, hi: float) -> pd.Series:
    df = query_api.query_data_frame(
        f'from(bucket: "{BUCKET}") |> {RANGE} |> filter(fn: (r) => r._measurement == "{measurement}" and r._field == "{name}") '
        f'|> map(fn: (r) => ({{r with _value: float(v: r._value)}})) '
        f'|> filter(fn: (r) => r._value >= {lo} and r._value <= {hi}) |> keep(columns: ["_time", "_value"])', org=ORG)
    if isinstance(df, list):
        df = pd.concat(df)
    return df.set_index("_time")["_value"].sort_index().groupby(level=0).mean()


print("== 1. Altitude ==")
raw = field("sensors.gps_altitude_status_mm", "altitude", 0, 4294967295)
gps_alt = pd.Series(np.where(raw > 2147483647, raw - 4294967296, raw) / 1000, index=raw.index)
gps_alt = gps_alt[(gps_alt > -500) & (gps_alt < 9000)]
fix = field("sensors.gps_altitude_status_mm", "fixType", 0, 5)
alt = pd.concat({"gps_m": gps_alt.resample("1s").mean(),
                 "calc_m": field("calculated_values.altitude_ft", "value", -2000, 30000).resample("1s").mean() * FT,
                 "imu_m": field("calculated_values.imu_altitude_ft", "value", -2000, 30000).resample("1s").mean() * FT,
                 "fix": fix.resample("1s").max()}, axis=1)
print("samples (1 s):", alt.notna().sum().to_dict())
print("fixType share:", fix.value_counts(normalize=True).round(3).sort_index().to_dict())
both = alt.dropna(subset=["gps_m", "calc_m", "imu_m"])
for c in ["calc_m", "imu_m"]:
    d = both[c] - both.gps_m
    lags = {lag: both[c].diff().corr(both.gps_m.diff().shift(lag)) for lag in range(-10, 11)}
    best = max(lags, key=lags.get)
    print(f"  {c}: corr with GPS {both[c].corr(both.gps_m):.3f}, mean offset {d.mean():+.1f} m, "
          f"median |diff| {d.abs().median():.1f} m, best lag {best:+d} s (corr of 1 s changes {lags[best]:.2f})")
print("  roughness (median |1 s change|, m):", both[["gps_m", "calc_m", "imu_m"]].diff().abs().median().round(3).to_dict())
gaps = alt[alt.gps_m.isna() & alt.calc_m.notna()]
print(f"  seconds with calc_m but no GPS altitude: {len(gaps):,} (does calc keep going when GPS drops?)")

print("\n== 2. Brake ==")
ped = pd.concat({"mech": field("petals.can_pedal_pos", "mechBrake", 0, 255).resample("1s").max(),
                 "brakePos": field("petals.can_pedal_pos", "brakePos", 0, 255).resample("1s").max(),
                 "accel": field("petals.can_pedal_pos", "accelPos", 0, 255).resample("1s").mean()}, axis=1)
v = field("calculated_values.left_speed_mph", "value", 0, 100).resample("1s").mean() * MPH
dv = v.rolling(3, center=True, min_periods=1).mean().diff().rename("dvdt")
df = pd.concat([ped, dv, v.rename("v")], axis=1).dropna()
df = df[df.v > 3]
decel = df.dvdt < -0.3  # clearly slowing
print(f"{len(df):,} moving seconds; {decel.mean():.1%} clearly slowing (< -0.3 m/s^2)")
print("mechBrake distribution when > 0:", df.mech[df.mech > 0].quantile([.1, .25, .5, .75, .9]).round(0).to_dict())
print(f"{'rule':24} {'flagged':>8} {'P(slowing|flag)':>16} {'P(flag|slowing)':>16} {'accel>20 while flagged':>23} {'median dv/dt':>13}")
rules = {f"mechBrake > {t}": df.mech > t for t in (0, 5, 20, 50, 100)}
rules["brakePos > 0"] = df.brakePos > 0
rules["accel == 0 (coasting)"] = (df.accel == 0) & (df.mech == 0)
for name, flag in rules.items():
    print(f"{name:24} {flag.mean():8.1%} {decel[flag].mean():16.1%} {flag[decel].mean():16.1%} "
          f"{(df.accel[flag] > 20).mean():23.1%} {df.dvdt[flag].median():13.2f}")
