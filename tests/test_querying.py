from data_tools.query import InfluxDBClient
from data_tools.localization import CanonicalName
from data_tools.collections import TimeSeries
from datetime import datetime, timezone


def test_query():
    start_time = datetime(2024, 7, 12, 10, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2024, 7, 14, 23, 0, 0, tzinfo=timezone.utc)

    client = InfluxDBClient()

    pack_voltage: TimeSeries = client.query_time_series(start_time, end_time, CanonicalName.VehicleSpeed)
    assert pack_voltage.units == "m/s"

    start_time = datetime(2026, 1, 19, 0, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2026, 1, 22, 0, 0, 0, tzinfo=timezone.utc)

    client = InfluxDBClient()

    pack_voltage: TimeSeries = client.query_time_series(start_time, end_time, CanonicalName.VehicleSpeed)
    assert pack_voltage.units == "km/h"
