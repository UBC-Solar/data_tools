# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas"]
# ///
"""
Side-by-side diff of the UBC and Berkeley schemas, joined through the translation table.

Usage: uv run scripts/diff_schemas.py
Reads mapping/ubc_schema.csv, mapping/berkeley_schema.csv and mapping/berkeley_to_ubc.csv
(no InfluxDB access needed). Writes mapping/schema_diff.csv with one row per series, where
status is one of:
  mapped        UBC series with a direct Berkeley source
  derived       computed from other Berkeley series, or no source yet (see conversion)
  ubc_only      UBC series with no Berkeley equivalent in the translation table
  berkeley_only Berkeley series that no translation row uses directly
and name_status says what the UBC name is:
  canonical     has a data_tools canonical name (what sunbeam / data_tools query)
  existing      a field our car already logs, with no canonical name
  new           a proposed UBC-style name we have never logged
Berkeley stats are raw and unfiltered (garbage samples included), in Berkeley's units.
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MAPPING = ROOT / "mapping"

ubc = pd.read_csv(MAPPING / "ubc_schema.csv")
berk = pd.read_csv(MAPPING / "berkeley_schema.csv")
trans = pd.read_csv(MAPPING / "berkeley_to_ubc.csv")

stats = ["count", "min", "max", "mean", "avg_hz"]
ubc = ubc[["measurement", "field"] + stats].rename(columns={"measurement": "ubc_measurement", "field": "ubc_field"})
ubc = ubc.rename(columns={c: f"ubc_{c}" for c in stats})
berk = berk[["measurement", "field"] + stats].rename(columns={"measurement": "berkeley_measurement", "field": "berkeley_field"})
berk = berk.rename(columns={c: f"berkeley_{c}" for c in stats})

# Translation rows that name a UBC signal or a derived value; the "n/a" rows only describe Berkeley-only groups.
trans = trans[trans["ubc_canonical_name"].notna() | trans["ubc_measurement"].notna()]
trans = trans.drop(columns=["ubc_hz"])  # config rate; measured rate comes from ubc_schema
trans = trans.rename(columns={"berkeley_hz": "berkeley_driving_hz"})

ukey, bkey = ["ubc_measurement", "ubc_field"], ["berkeley_measurement", "berkeley_field"]
out = trans.merge(ubc, on=ukey, how="outer", indicator="_ubc").merge(berk, on=bkey, how="outer", indicator="_berk")

direct = (out["_berk"] == "both") & out["ubc_field"].notna()
in_trans = out["ubc_canonical_name"].notna() | out["conversion_to_ubc"].notna()
out["status"] = "berkeley_only"
out.loc[out["ubc_field"].notna() & ~in_trans, "status"] = "ubc_only"
out.loc[in_trans & ~direct, "status"] = "derived"
out.loc[in_trans & direct, "status"] = "mapped"

name_status = pd.Series("new", index=out.index)
name_status[out["_ubc"] != "left_only"] = "existing"  # left_only = translation row with no UBC series
name_status[out["ubc_canonical_name"].notna()] = "canonical"
out["name_status"] = name_status.where(out["ubc_field"].notna() | out["ubc_canonical_name"].notna())

order = {"mapped": 0, "derived": 1, "ubc_only": 2, "berkeley_only": 3}
out = out.sort_values(["status", "ubc_measurement", "ubc_field", "berkeley_measurement", "berkeley_field"],
                      key=lambda s: s.map(order) if s.name == "status" else s)
cols = ["status", "confidence", "name_status", "ubc_canonical_name",
        "ubc_measurement", "ubc_field", "ubc_units",
        "berkeley_measurement", "berkeley_field", "berkeley_units", "conversion_to_ubc",
        "ubc_avg_hz", "berkeley_driving_hz", "berkeley_avg_hz",
        "ubc_count", "ubc_min", "ubc_max", "ubc_mean",
        "berkeley_count", "berkeley_min", "berkeley_max", "berkeley_mean", "notes"]
out = out[cols]

dest = MAPPING / "schema_diff.csv"
out.to_csv(dest, index=False)
print(out["status"].value_counts().reindex(order).to_string())
print(out["name_status"].value_counts().to_string())
print(f"{len(out)} rows -> {dest}")
