# /// script
# requires-python = ">=3.10"
# dependencies = ["influxdb-client", "pandas", "python-dotenv"]
# ///
"""
Inventory every (measurement, field) in the restored Berkeley bucket with basic stats.

Usage: uv run scripts/inventory_berkeley.py
Writes mapping/berkeley_schema.csv. Per-measurement results are cached in
mapping/.inventory_cache/ so a rerun resumes where it stopped.
"""
from pathlib import Path
import os

import pandas as pd
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient

ROOT = Path(__file__).resolve().parent.parent
BUCKET = "berkeley_asc_2026"
ORG = "calsol"
START, STOP = "2026-07-20T00:00:00Z", "2026-08-03T00:00:00Z"

load_dotenv(ROOT / ".env")
client = InfluxDBClient(url=os.environ["INFLUX_URL"], token=os.environ["INFLUX_TOKEN"], org=ORG, timeout=600_000)
query_api = client.query_api()


def table(flux: str) -> pd.DataFrame:
    df = query_api.query_data_frame(flux, org=ORG)
    if isinstance(df, list):
        df = pd.concat(df, ignore_index=True) if df else pd.DataFrame()
    return df


measurements = table(
    f'import "influxdata/influxdb/schema"\nschema.measurements(bucket: "{BUCKET}", start: {START}, stop: {STOP})'
)["_value"].tolist()

keys = ["_measurement", "_field"]
cache = ROOT / "mapping" / ".inventory_cache"
cache.mkdir(exist_ok=True)

rows = []
for i, m in enumerate(measurements, 1):
    cached = cache / (m.replace("/", "_") + ".csv")
    if cached.exists():
        rows.append(pd.read_csv(cached))
        continue
    print(f"[{i}/{len(measurements)}] {m}", flush=True)
    base = f'from(bucket: "{BUCKET}") |> range(start: {START}, stop: {STOP}) |> filter(fn: (r) => r._measurement == "{m}")'
    out = table(f"{base} |> count()")[keys + ["_value"]].rename(columns={"_value": "count"})
    first = table(f"{base} |> first()")[keys + ["_time", "_value"]].rename(columns={"_time": "first_time", "_value": "first_value"})
    last = table(f"{base} |> last()")[keys + ["_time"]].rename(columns={"_time": "last_time"})
    out = out.merge(first, on=keys, how="left").merge(last, on=keys, how="left")
    numeric = f'import "types"\n{base} |> filter(fn: (r) => types.isNumeric(v: r._value))'
    for fn in ("min", "max", "mean"):
        df = table(f"{numeric} |> {fn}()")
        if not df.empty:
            out = out.merge(df[keys + ["_value"]].rename(columns={"_value": fn}), on=keys, how="left")
    out.to_csv(cached, index=False)
    rows.append(out)

out = pd.concat(rows, ignore_index=True)
span = (pd.to_datetime(out["last_time"]) - pd.to_datetime(out["first_time"])).dt.total_seconds()
out["avg_hz"] = (out["count"] / span.where(span > 0)).round(3)
out = out.rename(columns={"_measurement": "measurement", "_field": "field"}).sort_values(["measurement", "field"])

dest = ROOT / "mapping" / "berkeley_schema.csv"
out.to_csv(dest, index=False)
print(f"{len(out)} series -> {dest}")
