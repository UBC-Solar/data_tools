# /// script
# requires-python = ">=3.11"
# dependencies = ["influxdb-client", "pandas", "numpy", "python-dotenv"]
# ///
"""
Translate Berkeley's telemetry into our format and write it to the local CAN_log bucket.

Usage (from berkeley_data_translation/; --with-editable .. provides data_tools for the time shift):
  uv run --with-editable .. scripts/translate_berkeley.py --dry-run        # convert and report, write nothing
  uv run --with-editable .. scripts/translate_berkeley.py                  # replace all car="Berkeley" data in local CAN_log
  uv run --with-editable .. scripts/translate_berkeley.py --only SOC,GPSAltitude --dry-run   # --only always needs --dry-run

Reads mapping/berkeley_to_ubc.csv (the raw_type / scale / offset / keep_min / keep_max / drop_raw /
transform columns) and the local berkeley_asc_2026 bucket. The assumptions behind each mapping are in
that file's notes column; the time shift, filters and estimates are explained next to their code below.
Every day is converted before anything is deleted or written, so a conversion error leaves CAN_log as it was.
A real (non-dry) run writes mapping/translation_report.csv with read / dropped / written counts per UBC
field, which check_counts.py compares against the database.
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import argparse
import os
import warnings

import numpy as np
import pandas as pd
from data_tools.localization import TemporalLocalization
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient
from influxdb_client.client.warnings import MissingPivotFunction
from influxdb_client.client.write_api import SYNCHRONOUS

warnings.simplefilter("ignore", MissingPivotFunction)

ROOT = Path(__file__).resolve().parent.parent
SRC_BUCKET, ORG = "berkeley_asc_2026", "calsol"
DEST_BUCKET, CAR = "CAN_log", "Berkeley"
FIRST_DAY, LAST_DAY = datetime(2026, 7, 25, tzinfo=timezone.utc), datetime(2026, 8, 1, tzinfo=timezone.utc)
ALIGN = pd.Timedelta("1s")  # nearest-sample tolerance when combining different Berkeley messages

# Sanity limits on the raw inputs of the estimates (after unit conversion)
PACK_V = (50.001, 160)
PACK_I = (-60, 60)
MPPT_P = (0, 1500)       # W per MPPT
MPPT_VOUT = (10, 160)    # V; below 10 V the division blows up


def our_shift() -> timedelta:
    """The shift data_tools adds back to our timestamps on these dates (stored = real UTC - shift)."""
    shifts = {TemporalLocalization.localize(FIRST_DAY + timedelta(days=d)) for d in range((LAST_DAY - FIRST_DAY).days + 1)}
    if len(shifts) != 1:
        raise SystemExit(f"Berkeley's dates straddle a temporal_localization period: {sorted(shifts)}")
    return shifts.pop()


def read(query_api, measurement: str, fields: list[str], start: datetime, stop: datetime) -> pd.DataFrame:
    field_filter = " or ".join(f'r._field == "{f}"' for f in fields)
    df = query_api.query_data_frame(
        f'from(bucket: "{SRC_BUCKET}") |> range(start: {start.isoformat()}, stop: {stop.isoformat()}) '
        f'|> filter(fn: (r) => r._measurement == "{measurement}" and ({field_filter})) '
        f'|> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")', org=ORG)
    if isinstance(df, list):
        df = pd.concat(df) if df else pd.DataFrame()
    if df.empty:  # keep a datetime index so merges with other series still work
        return pd.DataFrame(columns=fields, index=pd.DatetimeIndex([], tz="UTC", name="_time"), dtype=float)
    df = df.set_index("_time").sort_index()
    df = df[~df.index.duplicated()]
    return df.reindex(columns=fields).astype(float)


def to_signed(v: pd.Series, raw_type: str) -> pd.Series:
    if raw_type == "s16":
        return v.where(v <= 32767, v - 65536)
    if raw_type == "s32":
        return v.where(v <= 2147483647, v - 4294967296)
    return v


def in_range(v: pd.Series, lo: float, hi: float) -> pd.Series:
    return (v >= lo) & (v <= hi)


# Measurements whose fields arrive in one CAN frame and are checked together (all fields are always read)
JOINT_FIELDS = {
    "sensors.gps_position_deg": ["lat", "lon"],
    "sensors.imu_accelerometer_m/s^2": ["val_1", "val_2", "val_3"],
    "sensors.imu_quaternions": ["val_1", "val_2", "val_3", "val_4"],
}


def joint_mask(measurement: str, df: pd.DataFrame) -> pd.Series:
    """Samples to drop as a whole, because their fields came from one corrupted frame."""
    if measurement == "sensors.gps_position_deg":
        return ((df.lat == 0) & (df.lon == 0)) | (df.lat.abs() > 90) | (df.lon.abs() > 180)
    if measurement == "sensors.imu_accelerometer_m/s^2":
        return (to_signed(df[["val_1", "val_2", "val_3"]], "s16").abs() > 5000).any(axis=1)
    if measurement == "sensors.imu_quaternions":
        q = to_signed(df[["val_1", "val_2", "val_3", "val_4"]], "s16") / 16384
        norm = np.sqrt((q ** 2).sum(axis=1))
        return (norm < 0.98) | (norm > 1.02)
    return pd.Series(False, index=df.index)


# Spike filter: GPS samples that are in range but far from their neighbours (lone corrupted frames).
SPIKE_WINDOW = "10s"     # centred time window, so samples across a GPS dropout are not compared
SPIKE_KM = 1.0           # lat/lon: max distance from the rolling-median track
SPIKE_ALT_M = 300.0      # altitude: max difference from the rolling median. 50-300 m jumps (~130) are kept:
                         # they may be real GPS vertical error, useful for location analysis


def spike_mask(measurement: str, df: pd.DataFrame, bad_frame: pd.Series) -> dict[str, pd.Series]:
    """Per Berkeley field, samples to drop because they jump away from their neighbours."""
    good = df[~bad_frame]
    if measurement == "sensors.gps_position_deg":
        med = good[["lat", "lon"]].rolling(SPIKE_WINDOW, center=True, min_periods=5).median()
        km = np.hypot((good.lat - med.lat) * 111.0, (good.lon - med.lon) * 111.0 * np.cos(np.radians(med.lat)))
        spike = (km > SPIKE_KM).reindex(df.index, fill_value=False)
        return {"lat": spike, "lon": spike}
    if measurement == "sensors.gps_altitude_status_mm" and "altitude" in df:  # not read by e.g. --only GPSFixType
        alt = to_signed(good.altitude.dropna(), "s32") / 1000
        alt = alt[(alt > -500) & (alt < 9000)]
        med = alt.rolling(SPIKE_WINDOW, center=True, min_periods=5).median()
        return {"altitude": ((alt - med).abs() > SPIKE_ALT_M).reindex(df.index, fill_value=False)}
    return {}


def nearest(base: pd.DatetimeIndex, s: pd.Series, name: str) -> pd.Series:
    """Values of s at the timestamps in base (nearest within ALIGN), NaN where none."""
    left = pd.DataFrame(index=base).reset_index(names="t")
    right = s.dropna().rename(name).to_frame().reset_index(names="t")
    return pd.merge_asof(left, right, on="t", direction="nearest", tolerance=ALIGN).set_index("t")[name]


def write(client, converted: list, shift: timedelta):
    """Replace all car=Berkeley data in CAN_log with the converted series."""
    buckets = client.buckets_api()
    if buckets.find_bucket_by_name(DEST_BUCKET) is None:
        org_id = client.organizations_api().find_organizations(org=ORG)[0].id
        buckets.create_bucket(bucket_name=DEST_BUCKET, org_id=org_id)
    client.delete_api().delete(FIRST_DAY - shift - timedelta(days=1), LAST_DAY - shift + timedelta(days=2),
                               f'car="{CAR}"', bucket=DEST_BUCKET, org=ORG)
    write_api = client.write_api(write_options=SYNCHRONOUS)
    print(f"Writing {len(converted)} series", flush=True)
    try:
        for board, field, values, estimated in converted:
            df = values.rename(field).to_frame()
            df.index = df.index - shift
            df["car"] = CAR
            tags = ["car"]
            if estimated:
                df["estimated"] = "true"
                tags.append("estimated")
            for i in range(0, len(df), 200_000):
                write_api.write(DEST_BUCKET, ORG, record=df.iloc[i:i + 200_000], data_frame_measurement_name=board,
                                data_frame_tag_columns=tags)
    except BaseException:
        print(f"\nWrite stopped partway: CAN_log holds only part of car={CAR}. Rerun to replace it.")
        raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="convert and report, write nothing")
    ap.add_argument("--only", help="comma-separated UBC fields to process")
    args = ap.parse_args()
    if args.only and not args.dry_run:
        ap.error("--only needs --dry-run: each write first deletes ALL car=Berkeley data, and InfluxDB can't delete by field")

    load_dotenv(ROOT / ".env")
    client = InfluxDBClient(url=os.environ["INFLUX_URL"], token=os.environ["INFLUX_TOKEN"], org=ORG, timeout=600_000)
    query_api = client.query_api()
    shift = our_shift()
    print(f"Shifting Berkeley timestamps by -{shift} (from data_tools temporal localization)")

    table = pd.read_csv(ROOT / "mapping" / "berkeley_to_ubc.csv", dtype=str, keep_default_na=False)
    table = table[table["transform"] != "skip"]
    if args.only:
        table = table[table.ubc_field.isin(args.only.split(","))]
    linear = table[table["transform"].isin(["", "threshold>0"])]
    estimates = table[table["transform"].str.startswith("estimate")]

    report = defaultdict(lambda: defaultdict(int))
    converted = []  # (board, field, values, estimated); written only after every day has converted

    def emit(board: str, field: str, values: pd.Series, estimated: bool):
        values = values.dropna()
        report[field]["written"] += len(values)
        if not args.dry_run and not values.empty:
            converted.append((board, field, values, estimated))

    day = FIRST_DAY
    while day <= LAST_DAY:
        start, stop = day, day + timedelta(days=1)
        print(f"{start:%Y-%m-%d}", end=" ", flush=True)
        day_reads = {}  # Berkeley measurement -> DataFrame, so the estimates reuse what the linear rows read

        def read_day(measurement: str, field: str) -> pd.Series:
            df = day_reads.get(measurement)
            if df is None or field not in df:
                df = read(query_api, measurement, [field], start, stop)
            return df[field]

        # Linear rows, one read per Berkeley measurement
        for measurement, rows in linear.groupby("berkeley_measurement"):
            fields = sorted(set(rows.berkeley_field) | set(JOINT_FIELDS.get(measurement, [])))
            df = day_reads[measurement] = read(query_api, measurement, fields, start, stop)
            if df.empty:
                continue
            bad_frame = joint_mask(measurement, df)
            spikes = spike_mask(measurement, df, bad_frame)
            for _, r in rows.iterrows():
                raw = df[r.berkeley_field].dropna()
                f = r.ubc_field
                report[f]["read"] += len(raw)
                if r.drop_raw:
                    sentinel = raw.isin([float(x) for x in r.drop_raw.split(";")])
                    report[f]["dropped_placeholder"] += int(sentinel.sum())
                    raw = raw[~sentinel]
                joint = bad_frame.reindex(raw.index, fill_value=False)
                report[f]["dropped_bad_frame"] += int(joint.sum())
                raw = raw[~joint]
                if r.berkeley_field in spikes:
                    spike = spikes[r.berkeley_field].reindex(raw.index, fill_value=False)
                    report[f]["dropped_spike"] += int(spike.sum())
                    raw = raw[~spike]
                if r["transform"] == "threshold>0":
                    ok = in_range(raw, 0, 255)
                    value = (raw[ok] > 0).astype(float)
                else:
                    value = to_signed(raw, r.raw_type) * float(r.scale) + float(r.offset)
                    ok = in_range(value, float(r.keep_min), float(r.keep_max))
                    value = value[ok]
                report[f]["dropped_out_of_range"] += int((~ok).sum())
                emit(r.ubc_measurement, f, value, estimated=False)

        # Estimates
        if not estimates.empty:
            power, vout = {}, {}
            for n in "123":
                p = read_day(f"mppt{n}.calculated_power", "value")
                power[n] = p[in_range(p, *MPPT_P)]
                v = read_day(f"mppt{n}.telem", "Vout_10mV")
                v = v[v != 65535] * 0.01
                vout[n] = v[in_range(v, *MPPT_VOUT)]
            for _, r in estimates[estimates["transform"] == "estimate_mppt_out_current"].iterrows():
                n = {"A": "1", "B": "2", "C": "3"}[r.ubc_field[-1]]
                p = power[n]
                report[r.ubc_field]["read"] += len(p)
                i_out = p / nearest(p.index, vout[n], "v")
                report[r.ubc_field]["dropped_unaligned"] += int(i_out.isna().sum())
                ok = in_range(i_out, float(r.keep_min), float(r.keep_max))
                report[r.ubc_field]["dropped_out_of_range"] += int((i_out.notna() & ~ok).sum())
                emit(r.ubc_measurement, r.ubc_field, i_out[ok], estimated=True)

            motor = estimates[estimates["transform"].isin(["estimate_motor_current", "estimate_motor_direction"])]
            if not motor.empty:
                i_pack = read_day("riedon.riedon_current_mA", "value") * -0.001
                v_pack = read_day("bms.pack_voltage_V", "value")
                n_read = len(i_pack)
                i_pack = i_pack[in_range(i_pack, *PACK_I)]
                v_pack = v_pack[in_range(v_pack, *PACK_V)]
                p_array = sum(nearest(i_pack.index, power[n], f"p{n}") for n in "123")  # NaN unless all three MPPTs report
                i_bus = i_pack + p_array / nearest(i_pack.index, v_pack, "v")
                for _, r in motor.iterrows():
                    report[r.ubc_field]["read"] += n_read
                    report[r.ubc_field]["dropped_out_of_range"] += n_read - len(i_pack)
                    report[r.ubc_field]["dropped_unaligned"] += int(i_bus.isna().sum())
                    value = i_bus.abs() if r["transform"] == "estimate_motor_current" else (i_bus < 0).astype(float).where(i_bus.notna())
                    ok = value.isna() | in_range(value, float(r.keep_min), float(r.keep_max))
                    report[r.ubc_field]["dropped_out_of_range"] += int((~ok).sum())
                    emit(r.ubc_measurement, r.ubc_field, value[ok], estimated=True)
        day = stop
    print()

    if not args.dry_run:
        write(client, converted, shift)

    out = pd.DataFrame(report).T.fillna(0).astype(int)
    cols = ["read", "dropped_placeholder", "dropped_bad_frame", "dropped_spike", "dropped_out_of_range", "dropped_unaligned", "written"]
    out = out.reindex(columns=cols, fill_value=0)
    out["written_pct"] = (100 * out.written / out["read"].where(out["read"] > 0)).round(1)
    meta = table.drop_duplicates("ubc_field").set_index("ubc_field")[["ubc_measurement", "berkeley_measurement", "berkeley_field", "transform"]]
    out = meta.join(out, how="right").rename_axis("ubc_field").sort_values(["ubc_measurement", "written_pct"])
    if not args.dry_run:  # the report records what is in the database, so a dry run leaves it alone
        out.to_csv(ROOT / "mapping" / "translation_report.csv")
    with pd.option_context("display.width", 200, "display.max_rows", 200):
        print(out[cols + ["written_pct"]].sort_values("written_pct").head(25).to_string())
    print(f"{'DRY RUN - nothing written. ' if args.dry_run else ''}{int(out.written.sum()):,} points "
          f"across {len(out)} fields ({'would be ' if args.dry_run else ''}written to {DEST_BUCKET}, car={CAR})")
    client.close()


if __name__ == "__main__":
    main()
