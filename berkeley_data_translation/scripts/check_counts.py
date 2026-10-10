# /// script
# requires-python = ">=3.10"
# dependencies = ["influxdb-client", "pandas", "python-dotenv"]
# ///
"""
Check that the local CAN_log holds exactly what translate_berkeley.py says it wrote.

Usage: uv run scripts/check_counts.py
Counts car="Berkeley" points per field in the local CAN_log and compares them with
mapping/translation_report.csv ("written"). Any mismatch means a partial or duplicated write.
"""
from pathlib import Path
import os
import warnings

import pandas as pd
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient
from influxdb_client.client.warnings import MissingPivotFunction

warnings.simplefilter("ignore", MissingPivotFunction)

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
query_api = InfluxDBClient(url=os.environ["INFLUX_URL"], token=os.environ["INFLUX_TOKEN"], org="calsol", timeout=600_000).query_api()

df = query_api.query_data_frame(
    'from(bucket: "CAN_log") |> range(start: 2026-07-20T00:00:00Z, stop: 2026-08-05T00:00:00Z) '
    '|> filter(fn: (r) => r.car == "Berkeley") |> group(columns: ["_measurement", "_field"]) |> count()')
db = df.set_index("_field")["_value"] if not df.empty else pd.Series(dtype=int)  # empty = nothing written yet
report_path = ROOT / "mapping" / "translation_report.csv"
if not report_path.exists():
    raise SystemExit(f"No {report_path.name}: the last translate_berkeley.py write did not finish. Rerun it.")
report = pd.read_csv(report_path, index_col="ubc_field")["written"]
cmp = pd.concat({"db": db, "report": report}, axis=1).fillna(0).astype(int)
bad = cmp[cmp.db != cmp.report]
print(f"{len(cmp)} fields; db total {cmp.db.sum():,}, report total {cmp.report.sum():,}; mismatches: {len(bad)}")
if len(bad):
    print(bad.to_string())
