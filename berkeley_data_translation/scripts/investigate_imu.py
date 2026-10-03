# /// script
# requires-python = ">=3.10"
# dependencies = ["influxdb-client", "pandas", "numpy", "python-dotenv"]
# ///
"""
Work out Berkeley's IMU mounting and quaternion order from their own data (Berkeley questions 1 and 8).

Usage: uv run scripts/investigate_imu.py
Reads the local berkeley_asc_2026 bucket. Prints:
  - accelerometer sanity (is gravity really removed?)
  - quaternion norm, and which component is w (the one that makes gravity fixed in the sensor frame)
  - the IMU axis that points up (from the quaternions)
  - the forward axis (correlation with d(speed)/dt) and the sideways axis (correlation with speed x GPS yaw rate)
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
MPH = 0.44704

load_dotenv(ROOT / ".env")
query_api = InfluxDBClient(url=os.environ["INFLUX_URL"], token=os.environ["INFLUX_TOKEN"], org=ORG, timeout=600_000).query_api()


def series(measurement: str) -> pd.DataFrame:
    df = query_api.query_data_frame(
        f'from(bucket: "{BUCKET}") |> {RANGE} |> filter(fn: (r) => r._measurement == "{measurement}") '
        f'|> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")', org=ORG)
    if isinstance(df, list):
        df = pd.concat(df)
    return df.set_index("_time").drop(columns=["result", "table", "_start", "_stop", "_measurement"], errors="ignore").sort_index()


def s16(v):
    return np.where(v > 32767, v - 65536, v)


def per_second(df: pd.DataFrame, smooth: int = 3) -> pd.DataFrame:
    """1 s means, then a centred rolling mean to take the edge off ~2 Hz noise."""
    return df.resample("1s").mean().rolling(smooth, center=True, min_periods=1).mean()


def quat_to_up(q: np.ndarray) -> np.ndarray:
    """World 'up' (0, 0, 1) expressed in the sensor frame, for unit quaternions (w, x, y, z) sensor->world."""
    w, x, y, z = q.T
    # Third row of the rotation matrix R(q) = R^T applied to (0,0,1)
    return np.stack([2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)], axis=1)


print("== Loading ==", flush=True)
acc = series("sensors.imu_accelerometer_m/s^2")[["val_1", "val_2", "val_3"]]
acc = pd.DataFrame(s16(acc.to_numpy()) / 100, index=acc.index, columns=["a1", "a2", "a3"])
acc = acc[(acc.abs() <= 50).all(axis=1)]
quat = series("sensors.imu_quaternions")[["val_1", "val_2", "val_3", "val_4"]]
quat = pd.DataFrame(s16(quat.to_numpy()) / 16384, index=quat.index, columns=["q1", "q2", "q3", "q4"])
speed = series("calculated_values.left_speed_mph")["value"]
speed = speed[(speed >= 0) & (speed <= 100)] * MPH
gps = series("sensors.gps_position_deg")[["lat", "lon"]]
gps = gps[(gps.lat.abs() <= 90) & (gps.lon.abs() <= 180) & (gps.lat != 0)]
gps = gps[(gps.lat - gps.lat.median()).abs() < 10]  # drop stray points far from the route
print(f"accel {len(acc):,}  quat {len(quat):,}  speed {len(speed):,}  gps {len(gps):,}")

print("\n== 1. Accelerometer: is gravity removed? ==")
print(acc.describe().loc[["mean", "std", "50%"]].round(3).to_string())

print("\n== 2. Quaternions ==")
norm = np.sqrt((quat ** 2).sum(axis=1))
print(f"norm: median {norm.median():.4f}, within 0.98-1.02: {((norm > 0.98) & (norm < 1.02)).mean():.1%}")
quat = quat[(norm > 0.98) & (norm < 1.02)]
moving_q = quat.loc[quat.index.isin(speed[speed > 5].index.floor("1s"))] if False else quat
print("If a component is w, 'up' in the sensor frame should stay fixed while the car turns through every heading:")
best = None
for w_pos in range(4):
    order = [w_pos] + [i for i in range(4) if i != w_pos]
    up = quat_to_up(quat.to_numpy()[:, order])
    mean_up = up.mean(axis=0)
    spread = np.linalg.norm(up - mean_up, axis=1).mean()
    print(f"  w = q{w_pos + 1}: mean up = ({mean_up[0]:+.2f}, {mean_up[1]:+.2f}, {mean_up[2]:+.2f})  "
          f"|mean| = {np.linalg.norm(mean_up):.3f}  spread = {spread:.3f}")
    if best is None or spread < best[0]:
        best = (spread, w_pos, mean_up)
_, w_pos, up = best
axis = int(np.argmax(np.abs(up)))
print(f"-> w is q{w_pos + 1}. Up is sensor axis {axis + 1} ({'+' if up[axis] > 0 else '-'}), "
      f"{np.degrees(np.arccos(min(1, abs(up[axis]) / np.linalg.norm(up)))):.1f} deg off that axis.")

print("\n== 3. Forward and sideways axes ==")
v = per_second(speed.to_frame("v"))["v"]
a = per_second(acc)
dvdt = v.diff()  # m/s per s
g = per_second(gps)
lat0 = np.radians(g.lat.median())
east = np.radians(g.lon) * 6_371_000 * np.cos(lat0)
north = np.radians(g.lat) * 6_371_000
heading = np.arctan2(north.diff(2), east.diff(2))  # maths angle, CCW positive
yaw_rate = pd.Series(np.angle(np.exp(1j * heading.diff())), index=heading.index)  # rad/s (1 s steps), wrapped
lateral = v * yaw_rate  # + = turning left
df = pd.concat([a, dvdt.rename("dvdt"), lateral.rename("lat"), v.rename("v")], axis=1).dropna()
df = df[(df.v > 5) & (df.lat.abs() < 8) & (df.dvdt.abs() < 5)]
print(f"{len(df):,} moving seconds with all signals")
straight = df[df.lat.abs() < 0.5]
turning = df[df.dvdt.abs() < 0.3]
rows = []
for c in ["a1", "a2", "a3"]:
    rows.append({"axis": c,
                 "corr with dv/dt (straight)": straight[c].corr(straight.dvdt),
                 "slope vs dv/dt": np.polyfit(straight.dvdt, straight[c], 1)[0],
                 "corr with v*yaw (steady speed)": turning[c].corr(turning.lat),
                 "slope vs v*yaw": np.polyfit(turning.lat, turning[c], 1)[0]})
print(pd.DataFrame(rows).set_index("axis").round(2).to_string())
print("A slope near +1 means that axis points forward (dv/dt) or left (v*yaw); near -1 means backward or right.")

print("\n== 3b. Same, averaged over 10 s windows (vibration averages out) ==")
w10 = pd.concat([acc.resample("10s").mean(), v.resample("10s").mean().rename("v"),
                 (v.resample("10s").last() - v.resample("10s").first()).div(10).rename("dvdt"),
                 lateral.resample("10s").mean().rename("lat")], axis=1).dropna()
w10 = w10[(w10.v > 5) & (w10.lat.abs() < 8) & (w10.dvdt.abs() < 3)]
print(f"{len(w10):,} moving 10 s windows")
rows = []
for c in ["a1", "a2", "a3"]:
    st, tu = w10[w10.lat.abs() < 0.3], w10[w10.dvdt.abs() < 0.1]
    rows.append({"axis": c, "corr dv/dt": st[c].corr(st.dvdt), "slope dv/dt": np.polyfit(st.dvdt, st[c], 1)[0],
                 "corr v*yaw": tu[c].corr(tu.lat), "slope v*yaw": np.polyfit(tu.lat, tu[c], 1)[0]})
print(pd.DataFrame(rows).set_index("axis").round(2).to_string())

print("\n== 3c. 10 s windows with each axis's slow bias removed (5 min rolling median) ==")
bias = acc.resample("10s").mean().rolling(30, center=True, min_periods=10).median()
d10 = w10.copy()
for c in ["a1", "a2", "a3"]:
    d10[c] = w10[c] - bias[c].reindex(w10.index)
d10 = d10.dropna()
rows = []
for c in ["a1", "a2", "a3"]:
    st, tu = d10[d10.lat.abs() < 0.3], d10[d10.dvdt.abs() < 0.1]
    rows.append({"axis": c, "corr dv/dt": st[c].corr(st.dvdt), "slope dv/dt": np.polyfit(st.dvdt, st[c], 1)[0],
                 "corr v*yaw": tu[c].corr(tu.lat), "slope v*yaw": np.polyfit(tu.lat, tu[c], 1)[0]})
print(pd.DataFrame(rows).set_index("axis").round(2).to_string())
print(f"(slow bias std per axis: {bias.std().round(2).to_dict()} m/s^2)")

print("\n== 4. Independent check: quaternion heading vs GPS course ==")
qo = quat.to_numpy()[:, [w_pos] + [i for i in range(4) if i != w_pos]]
qs = pd.DataFrame(qo, index=quat.index, columns=["w", "x", "y", "z"]).resample("1s").mean().dropna()
qs = qs.div(np.sqrt((qs ** 2).sum(axis=1)), axis=0)
course = np.arctan2(north.diff(2), east.diff(2)).rename("course")  # maths angle (CCW from east)
both = pd.concat([qs, course, v.rename("v"), lateral.rename("lat")], axis=1).dropna()
both = both[(both.v > 8) & (both.lat.abs() < 0.3)]  # fast and straight: course is reliable
w_, x_, y_, z_ = both.w, both.x, both.y, both.z
for name, vec in [("axis 1", (1 - 2 * (y_ ** 2 + z_ ** 2), 2 * (x_ * y_ + w_ * z_))),
                  ("axis 2", (2 * (x_ * y_ - w_ * z_), 1 - 2 * (x_ ** 2 + z_ ** 2)))]:
    ang = np.arctan2(vec[1], vec[0])  # horizontal direction of the sensor axis in the IMU world frame
    off = np.angle(np.exp(1j * (both.course - ang)))
    R = np.abs(np.exp(1j * off).mean())  # 1 = perfectly constant offset
    print(f"  {name}: course - axis heading = {np.degrees(np.angle(np.exp(1j * off).mean())):+.0f} deg, "
          f"consistency {R:.2f} (n={len(both):,})")
print("A consistent offset (near 1) means the quaternion heading tracks the car; its value says which way that axis\n"
      "points relative to travel, up to the IMU world-frame convention (0 = forward if the frame is x-east, y-north).")

# Yaw rate from quaternions vs GPS: sign tells whether the up axis is really +3 (right-handed frame)
q1, q2 = qs.shift(1), qs
dq_z = (q1.w * q2.z - q1.z * q2.w + q1.x * q2.y - q1.y * q2.x)  # z part of conj(q1)*q2, ~ half the yaw step
qyaw = (2 * dq_z).rename("qyaw")
yy = pd.concat([qyaw, yaw_rate.rename("gyaw"), v.rename("v")], axis=1).dropna()
yy = yy[(yy.v > 5) & (yy.gyaw.abs() < 0.5) & (yy.qyaw.abs() < 0.5)]
print(f"  yaw rate: corr(quaternion, GPS) = {yy.qyaw.corr(yy.gyaw):.2f}, slope = {np.polyfit(yy.gyaw, yy.qyaw, 1)[0]:.2f}")

print("\n== 5. Sideways axis in clear turns (centripetal accel from quaternion yaw rate x speed) ==")
cent = (v * qyaw).rename("cent")  # + = turning left
t = pd.concat([acc.resample("1s").mean() - acc.resample("1s").mean().rolling(300, center=True, min_periods=60).median(),
               cent, v.rename("v")], axis=1).dropna()
t = t[(t.v > 5)]
for lo in (0.5, 1.0, 2.0):
    left, right = t[t.cent > lo], t[t.cent < -lo]
    print(f"  |centripetal| > {lo} m/s^2: left turns n={len(left):5} mean a1/a2/a3 = {left[['a1','a2','a3']].mean().round(2).tolist()}"
          f" | right turns n={len(right):5} mean = {right[['a1','a2','a3']].mean().round(2).tolist()}")
