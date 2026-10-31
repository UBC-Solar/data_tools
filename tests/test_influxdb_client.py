from datetime import datetime, timedelta, timezone

import pytest

from data_tools.query import InfluxDBClient

START = datetime(2024, 7, 16, 14, 0, tzinfo=timezone.utc)
STOP = datetime(2024, 7, 16, 15, 0, tzinfo=timezone.utc)
# temporal_localization.toml's shift for July 2024: InfluxDB's times are 7 hours behind
SHIFT = timedelta(hours=7)


class FakeRecord:
    def __init__(self, field, time, value):
        self._field, self._time, self._value = field, time, value

    def get_field(self):
        return self._field

    def get_time(self):
        return self._time

    def get_value(self):
        return self._value


class FakeInflux:
    """ Stands in for influxdb_client.InfluxDBClient. """

    def __init__(self, records=(), bucket=object(), ping=True):
        self.records = list(records)
        self.bucket = bucket
        self._ping = ping
        self.queries = []

    def ping(self):
        return self._ping

    def buckets_api(self):
        return self

    def find_bucket_by_name(self, name):
        return self.bucket

    def query_api(self):
        return self

    def query_stream(self, query, org=None):
        self.queries.append(query)
        return iter(self.records)


def make_client(fake: FakeInflux) -> InfluxDBClient:
    client = InfluxDBClient(influxdb_org="org", influxdb_token="token", url="http://influx:8086")
    client._client = fake
    return client


def test_timeout_and_gzip_reach_the_underlying_client():
    client = InfluxDBClient(influxdb_org="org", influxdb_token="token", url="http://influx:8086", timeout=1.5)

    assert client._client.api_client.configuration.timeout == 1500
    assert client._client.api_client.configuration.enable_gzip is False


def test_ping_and_bucket_exists():
    assert make_client(FakeInflux()).ping() is True
    assert make_client(FakeInflux(ping=False)).ping() is False
    assert make_client(FakeInflux()).bucket_exists("CAN_log") is True
    assert make_client(FakeInflux(bucket=None)).bucket_exists("CAN_log") is False


def test_has_data_reads_one_point_from_the_localized_range():
    fake = FakeInflux(records=[FakeRecord("PackCurrent", START, 1.0)])

    assert make_client(fake).has_data("CAN_log", START, STOP) is True
    assert fake.queries[0] == (
        'from(bucket: "CAN_log") '
        '|> range(start: 2024-07-16T07:00:00Z, stop: 2024-07-16T08:00:00Z) '
        '|> limit(n: 1) '
    )
    assert make_client(FakeInflux()).has_data("CAN_log", START, STOP) is False


def test_naive_times_are_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        make_client(FakeInflux()).has_data("CAN_log", START.replace(tzinfo=None), STOP)


def test_query_last_values():
    stored = STOP - SHIFT
    fake = FakeInflux(records=[FakeRecord("PackCurrent", stored, 2.5), FakeRecord("Unrequested", stored, 0.0)])

    values = make_client(fake).query_last_values("CAN_log", ["PackCurrent", "VehicleVelocity"], START, STOP)

    # Returned times are shifted back to true time
    assert values == {"PackCurrent": (STOP, 2.5), "VehicleVelocity": None}
    assert fake.queries[0] == (
        'from(bucket: "CAN_log") '
        '|> range(start: 2024-07-16T07:00:00Z, stop: 2024-07-16T08:00:00Z) '
        '|> filter(fn:(r) => r._field == "PackCurrent" or r._field == "VehicleVelocity") '
        '|> last() '
        '|> keep(columns: ["_field", "_value", "_time"]) '
    )


def test_query_last_values_without_fields_skips_the_query():
    fake = FakeInflux()

    assert make_client(fake).query_last_values("CAN_log", [], START, STOP) == {}
    assert fake.queries == []
