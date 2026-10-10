# /// script
# requires-python = ">=3.10"
# dependencies = ["influxdb-client", "pandas", "numpy", "python-dotenv"]
# ///
"""
Which of our TEL Acceleration_Y / _Z points forward and which sideways (counterpart to investigate_imu.py).

Usage: uv run scripts/investigate_imu_ubc.py [START STOP]   (default: 2026-04-02, our busiest 2026 day)
Reads CAN_log on the team server (UBC_INFLUX_URL / UBC_INFLUX_TOKEN / UBC_INFLUX_ORG in .env).
Our accelerations are milli-g WITH gravity; our longitude is degrees west, positive.
"""
from pathlib import Path
import os
import sys
import warnings

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient
from influxdb_client.client.warnings import MissingPivotFunction

warnings.simplefilter("ignore", MissingPivotFunction)

ROOT = Path(__file__).resolve().parent.parent
CAR = "Brightside"
START, STOP = (sys.argv[1], sys.argv[2]) if len(sys.argv) == 3 else ("2026-04-02T00:00:00Z", "2026-04-03T00:00:00Z")
G = 9.80665

load_dotenv(ROOT / ".env")
ORG_ID = os.environ["UBC_INFLUX_ORG"]
query_api = InfluxDBClient(url=os.environ["UBC_INFLUX_URL"], token=os.environ["UBC_INFLUX_TOKEN"], org=ORG_ID, timeout=600_000).query_api()


def field(measurement: str, name: str) -> pd.Series:
    df = query_api.query_data_frame(
        f'from(bucket: "CAN_log") |> range(start: {START}, stop: {STOP}) '
        f'|> filter(fn: (r) => r._measurement == "{measurement}" and r._field == "{name}" and r.car == "{CAR}") '
        f'|> keep(columns: ["_time", "_value"])', org=ORG_ID)
    if isinstance(df, list):
        df = pd.concat(df)
    return df.set_index("_time")["_value"].astype(float).sort_index().groupby(level=0).mean().rename(name)


# X, Y and Z arrive in separate CAN frames, so put each on a 1 s grid before combining.
acc = pd.concat([(f := field("TEL", f"Acceleration_{a}") / 1000 * G)[(f.abs() < 50) & (f != 0)].resample("1s").mean()
                 for a in "XYZ"], axis=1).dropna()  # m/s^2, gravity included
v = field("MC", "MotorRotatingSpeed") / 3.6
lat, lon = field("TEL", "GPSLatitude"), field("TEL", "GPSLongitude")
gps = pd.concat([lat, lon], axis=1).dropna()
gps = gps[(gps.GPSLatitude > 1) & (gps.GPSLongitude > 1)]
print(f"accel {len(acc):,}  speed {len(v):,}  gps {len(gps):,}")
print("mean accel (m/s^2, gravity included):", acc.mean().round(2).to_dict())

v1 = v.resample("1s").mean().rolling(3, center=True, min_periods=1).mean()
g1 = gps.resample("1s").mean().rolling(3, center=True, min_periods=1).mean()
lat0 = np.radians(g1.GPSLatitude.median())
east = -np.radians(g1.GPSLongitude) * 6_371_000 * np.cos(lat0)  # degrees west -> east metres
north = np.radians(g1.GPSLatitude) * 6_371_000
heading = np.arctan2(north.diff(2), east.diff(2))
yaw = pd.Series(np.angle(np.exp(1j * heading.diff())), index=heading.index)
a1 = acc.copy()
a1 = a1 - a1.rolling(300, center=True, min_periods=30).median()  # remove gravity and slow bias
df = pd.concat([a1, v1.diff().rename("dvdt"), (v1 * yaw).rename("cent"), v1.rename("v")], axis=1).dropna()
df = df[(df.v > 3) & (df.dvdt.abs() < 4) & (df.cent.abs() < 8)]
print(f"{len(df):,} moving seconds with all signals")

print("\nForward axis: slope and correlation vs d(speed)/dt (+1 = points forward)")
st = df[df.cent.abs() < 0.3]
for c in ["Acceleration_X", "Acceleration_Y", "Acceleration_Z"]:
    print(f"  {c}: corr {st[c].corr(st.dvdt):+.2f}  slope {np.polyfit(st.dvdt, st[c], 1)[0]:+.2f}")

print("\nSideways axis: mean reading in turns (+ in left turns = points left)")
for lo in (0.5, 1.0, 2.0):
    left, right = df[df.cent > lo], df[df.cent < -lo]
    cols = ["Acceleration_X", "Acceleration_Y", "Acceleration_Z"]
    print(f"  |cent| > {lo}: left n={len(left):4} {left[cols].mean().round(2).tolist()} | right n={len(right):4} {right[cols].mean().round(2).tolist()}")
