# /// script
# requires-python = ">=3.10"
# dependencies = ["influxdb-client", "pandas", "numpy", "python-dotenv"]
# ///
"""
Wheel diameter implied by Berkeley's own speed calculation: left/right_speed_mph vs left/right_mcc_rpm,
and how calculated_values.speed_mph relates to the two sides.
Usage: uv run scripts/investigate_wheel.py   (reads the local berkeley_asc_2026 bucket)
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


def field(measurement: str, lo: float, hi: float) -> pd.Series:
    df = query_api.query_data_frame(
        f'from(bucket: "{BUCKET}") |> {RANGE} |> filter(fn: (r) => r._measurement == "{measurement}" and r._field == "value") '
        f'|> filter(fn: (r) => r._value >= {lo} and r._value <= {hi}) |> keep(columns: ["_time", "_value"])', org=ORG)
    if isinstance(df, list):
        df = pd.concat(df)
    return df.set_index("_time")["_value"].astype(float).sort_index().groupby(level=0).mean()


for side in ("left", "right"):
    rpm = field(f"{side}_mcc.{side}_mcc_rpm", 0, 2000)
    mph = field(f"calculated_values.{side}_speed_mph", 0, 100)
    df = pd.merge_asof(mph.rename("mph").to_frame(), rpm.rename("rpm").to_frame(), left_index=True, right_index=True,
                       direction="nearest", tolerance=pd.Timedelta("50ms")).dropna()
    df = df[(df.rpm > 100) & (df.mph > 5)]
    dia = df.mph * MPH * 60 / (np.pi * df.rpm)  # v = pi * d * rpm / 60
    exact = (dia.round(4) == dia.median().round(4)).mean()
    print(f"{side}: n={len(df):,}  implied diameter median {dia.median():.4f} m  IQR {dia.quantile(.25):.4f}-{dia.quantile(.75):.4f}  "
          f"share within 0.1 mm of median {exact:.0%}  -> km/h per rpm {dia.median() * np.pi * 60 / 1000:.5f}")

mph = field("calculated_values.speed_mph", 0, 100)
left_s, right_s = field("calculated_values.left_speed_mph", 0, 100), field("calculated_values.right_speed_mph", 0, 100)
df = pd.concat([mph.resample("1s").mean().rename("speed"), left_s.resample("1s").mean().rename("left"),
                right_s.resample("1s").mean().rename("right")], axis=1).dropna()
df = df[df.speed > 5]
print(f"\nspeed_mph vs sides: n={len(df):,} s; days present: {sorted(set(mph.index.strftime('%m-%d')))}")
for name, ref in [("left", df.left), ("right", df.right), ("mean(l,r)", (df.left + df.right) / 2), ("max(l,r)", df[["left", "right"]].max(axis=1))]:
    d = df.speed - ref
    print(f"  speed - {name:9}: median {d.median():+.3f} mph, median |diff| {d.abs().median():.3f}")
print(f"  left vs right: median |diff| {(df.left - df.right).abs().median():.3f} mph")
