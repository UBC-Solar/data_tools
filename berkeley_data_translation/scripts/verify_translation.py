# /// script
# requires-python = ">=3.11"
# dependencies = ["python-dotenv", "ubc-solar-data-tools"]
# [tool.uv.sources]
# ubc-solar-data-tools = { path = "../..", editable = true }
# ///
"""
Check the translated Berkeley data the way our tools will see it: through data_tools.

Usage: uv run scripts/verify_translation.py [START_UTC]   e.g. 2026-07-30T18:00
Queries the local CAN_log with car="Berkeley" for one real race hour (default 2026-07-30 18:00-19:00 UTC,
13:00 CDT). Times passed in are REAL UTC; data_tools applies the 7 h shift itself.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import sys

from dotenv import load_dotenv
from data_tools.localization import CanonicalName
from data_tools.query import InfluxDBClient

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
client = InfluxDBClient(url=os.environ["INFLUX_URL"], influxdb_org="calsol", influxdb_token=os.environ["INFLUX_TOKEN"])

START = (datetime.fromisoformat(sys.argv[1]).replace(tzinfo=timezone.utc) if len(sys.argv) > 1
         else datetime(2026, 7, 30, 18, tzinfo=timezone.utc))  # Jul 29's MPPTs were mostly silent
STOP = START + timedelta(hours=1)

checks = [  # (what to query, expected)
    (CanonicalName.PackVoltage, "~120-130 V"),
    (CanonicalName.PackCurrent, "mostly positive while driving (A)"),
    (CanonicalName.VehicleSpeed, "~20-60 km/h"),
    (CanonicalName.MotorCurrent, "0-60 A, estimated"),
    (CanonicalName.MotorCurrentDirection, "0/1"),
    (CanonicalName.AcceleratorPosition, "0-100 %"),
    (CanonicalName.MinimumModuleVoltage, "~3.5-4.1 V"),
    (CanonicalName.MPPTInputVoltageA, "~20-100 V"),
    (CanonicalName.LatitudeRaw, "~38-45 deg"),
    (CanonicalName.LongitudeRaw, "positive ~90-95 (degrees west)"),
    (CanonicalName.Acceleration_X, "~-1000 mg (gravity, X down)"),
    (CanonicalName.Acceleration_Z, "~0 mg +- a few hundred (forward)"),
    (("GPSAltitude", "TEL"), "a few hundred m"),
    (("Orientation_W", "TEL"), "-1..1"),
]

print(f"car=Berkeley, {START:%Y-%m-%d %H:%M}-{STOP:%H:%M} UTC (real time)\n")
for target, expected in checks:
    try:
        if isinstance(target, tuple):
            ts = client.query_time_series(START, STOP, target[0], measurement=target[1], car="Berkeley", granularity=1.0)
            name = f"{target[1]}/{target[0]}"
        else:
            ts = client.query_time_series(START, STOP, target, car="Berkeley")
            name = str(target)
        v = ts.to_numpy() if hasattr(ts, "to_numpy") else ts
        print(f"{name:24} n={len(v):6}  min {v.min():9.3f}  median {float(sorted(v)[len(v) // 2]):9.3f}  "
              f"max {v.max():9.3f}  span {ts.start:%H:%M}-{ts.stop:%H:%M} UTC   expect {expected}")
    except Exception as e:  # report and carry on
        print(f"{str(target):24} FAILED: {e}   expect {expected}")
client.close()
