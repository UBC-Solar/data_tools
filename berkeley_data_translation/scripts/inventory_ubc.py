# /// script
# requires-python = ">=3.10"
# dependencies = ["influxdb-client", "pandas", "python-dotenv"]
# ///
"""
Inventory every (measurement, field) in our CAN_log bucket for Brightside on one driving day,
with the same stats as inventory_berkeley.py. Fields are queried a few at a time because
querying a whole measurement (e.g. all BMS cell fields) times out the team server's proxy.

Usage: uv run scripts/inventory_ubc.py
Needs UBC_INFLUX_URL, UBC_INFLUX_TOKEN and UBC_INFLUX_ORG (the team org's ID) in .env. Writes mapping/ubc_schema.csv. Per-batch
results are cached in mapping/.inventory_cache_ubc/ so a rerun resumes where it stopped.
"""
from pathlib import Path
import os
import warnings

import pandas as pd
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient
from influxdb_client.client.warnings import MissingPivotFunction
from influxdb_client.rest import ApiException

warnings.simplefilter("ignore", MissingPivotFunction)

ROOT = Path(__file__).resolve().parent.parent
BUCKET = "CAN_log"
CAR = "Brightside"
START, STOP = "2026-04-02T00:00:00Z", "2026-04-03T00:00:00Z"  # busiest 2026 driving day
BATCH = 10  # fields per query

load_dotenv(ROOT / ".env")
ORG_ID = os.environ["UBC_INFLUX_ORG"]
client = InfluxDBClient(url=os.environ["UBC_INFLUX_URL"], token=os.environ["UBC_INFLUX_TOKEN"], org=ORG_ID, timeout=600_000)
query_api = client.query_api()


def table(flux: str) -> pd.DataFrame:
    df = query_api.query_data_frame(flux, org=ORG_ID)
    if isinstance(df, list):
        df = pd.concat(df, ignore_index=True) if df else pd.DataFrame()
    return df


def tag_values(tag: str, predicate: str) -> list[str]:
    df = table(f'import "influxdata/influxdb/schema"\n'
               f'schema.tagValues(bucket: "{BUCKET}", tag: "{tag}", start: {START}, stop: {STOP}, predicate: (r) => {predicate})')
    return sorted(df["_value"].tolist()) if not df.empty else []


def stats(m: str, fields: list[str]) -> pd.DataFrame:
    field_filter = " or ".join(f'r._field == "{f}"' for f in fields)
    base = (f'from(bucket: "{BUCKET}") |> range(start: {START}, stop: {STOP}) '
            f'|> filter(fn: (r) => r._measurement == "{m}" and r.car == "{CAR}" and ({field_filter})) '
            f'|> group(columns: ["_measurement", "_field"])')
    out = table(f"{base} |> count()")
    if out.empty:
        return out
    out = out[keys + ["_value"]].rename(columns={"_value": "count"})
    first = table(f"{base} |> first()")[keys + ["_time", "_value"]].rename(columns={"_time": "first_time", "_value": "first_value"})
    last = table(f"{base} |> last()")[keys + ["_time"]].rename(columns={"_time": "last_time"})
    out = out.merge(first, on=keys, how="left").merge(last, on=keys, how="left")
    # Plain aggregates are pushed down to storage and are fast; the numeric filter/cast is ~30x
    # slower, so only use it when a batch has string or mixed-type fields.
    numeric = f'import "types"\n{base} |> filter(fn: (r) => types.isNumeric(v: r._value)) |> map(fn: (r) => ({{r with _value: float(v: r._value)}}))'
    for fn in ("min", "max", "mean"):
        try:
            df = table(f"{base} |> {fn}()")
        except ApiException:
            df = table(f"{numeric} |> {fn}()")
        if not df.empty:
            out = out.merge(df[keys + ["_value"]].rename(columns={"_value": fn}), on=keys, how="left")
    return out


keys = ["_measurement", "_field"]
cache = ROOT / "mapping" / ".inventory_cache_ubc"
cache.mkdir(exist_ok=True)

measurements = tag_values("_measurement", f'r.car == "{CAR}"')
rows = []
for i, m in enumerate(measurements, 1):
    fields = tag_values("_field", f'r._measurement == "{m}" and r.car == "{CAR}"')
    print(f"[{i}/{len(measurements)}] {m}: {len(fields)} fields", flush=True)
    for j in range(0, len(fields), BATCH):
        batch = fields[j:j + BATCH]
        cached = cache / f"{m}_{j:04d}_{batch[0]}.csv"
        if cached.exists():
            try:
                rows.append(pd.read_csv(cached))
            except pd.errors.EmptyDataError:  # a batch with no data was cached as an empty file
                rows.append(pd.DataFrame())
            continue
        out = stats(m, batch)
        out.to_csv(cached, index=False)
        rows.append(out)

rows = [r for r in rows if not r.empty]
if not rows:
    raise SystemExit(f"No {CAR} data in {BUCKET} between {START} and {STOP}: check UBC_INFLUX_ORG and the dates")
out = pd.concat(rows, ignore_index=True)
span = (pd.to_datetime(out["last_time"]) - pd.to_datetime(out["first_time"])).dt.total_seconds()
out["avg_hz"] = (out["count"] / span.where(span > 0)).round(3)
out = out.rename(columns={"_measurement": "measurement", "_field": "field"}).sort_values(["measurement", "field"])
out = out[["measurement", "field", "count", "first_time", "first_value", "last_time", "min", "max", "mean", "avg_hz"]]

dest = ROOT / "mapping" / "ubc_schema.csv"
out.to_csv(dest, index=False)
print(f"{len(out)} series -> {dest}")
