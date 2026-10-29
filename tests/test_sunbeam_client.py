from datetime import datetime, timezone

import pytest
import requests

from data_tools.query import SunbeamClient

START_MS = 1_720_000_000_000  # 10 Hz samples from here


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body
        self.reason = "Not Found" if status_code == 404 else "Error"

    def json(self):
        return self._body


class FakeServer:
    """ Serves one signal the way Sunbeam's data endpoint does: the most recent ``limit`` samples before ``end``. """

    def __init__(self, count=25, limit=10, frequency=10.0, unit="W", values=None, inclusive_end=False):
        self.timestamps = [START_MS + 100 * i for i in range(count)]
        self.values = values if values is not None else [float(i) for i in range(count)]
        self.limit = limit
        self.frequency = frequency
        self.unit = unit
        self.inclusive_end = inclusive_end
        self.requests = []

    def get(self, url, params=None, timeout=None):
        self.requests.append((url, dict(params or {})))

        if url.endswith("/events"):
            return FakeResponse(200, [{"name": "FSGP_2024_Day_1"}, {"name": "realtime"}])
        if url.endswith("/signals"):
            # PackPower is defined for the event but no worker has written it
            with_data = (params or {}).get("with_data") == "true"
            return FakeResponse(200, [{"name": "MotorPower"}] + ([] if with_data else [{"name": "PackPower"}]))
        if "/nope/" in url:
            return FakeResponse(404, {"detail": "Event 'FSGP_2024_Day_1' has no signal named 'nope'."})

        end = params.get("end") if params else None
        end_ms = datetime.fromisoformat(end).timestamp() * 1000 if end else float("inf")
        rows = [
            (t, v) for t, v in zip(self.timestamps, self.values)
            if t < end_ms or (self.inclusive_end and t == end_ms)
        ]
        truncated = len(rows) > self.limit
        rows = rows[-self.limit:]

        return FakeResponse(200, {
            "event_name": "FSGP_2024_Day_1", "signal": "MotorPower",
            "unit": self.unit, "frequency": self.frequency, "source": "derived", "description": "Motor power",
            "start": "2024-07-03T09:46:40Z", "end": "2024-07-03T10:00:00Z",
            "count": len(rows), "truncated": truncated,
            "timestamps": [t for t, _ in rows], "values": [v for _, v in rows],
        })


@pytest.fixture
def server(monkeypatch):
    fake = FakeServer()
    monkeypatch.setattr(requests, "get", fake.get)
    return fake


def test_url_defaults_and_scheme(monkeypatch):
    monkeypatch.delenv("SUNBEAM_URL", raising=False)
    assert SunbeamClient()._base_url == "http://localhost:8000"
    assert SunbeamClient("sunbeam.local:8000/")._base_url == "http://sunbeam.local:8000"


def test_lists_events_and_signals(server):
    client = SunbeamClient("http://sunbeam:8000")

    assert client.list_events() == ["FSGP_2024_Day_1", "realtime"]
    assert client.list_signals("FSGP_2024_Day_1") == ["MotorPower"]
    assert client.list_signals("FSGP_2024_Day_1", with_data=False) == ["MotorPower", "PackPower"]


def test_time_series_pages_through_everything(server):
    series = SunbeamClient("http://sunbeam:8000").get_time_series("FSGP_2024_Day_1", "MotorPower")

    assert list(series) == pytest.approx([float(i) for i in range(25)])
    assert len(server.requests) == 3
    assert series.period == pytest.approx(0.1)
    assert series.start == datetime.fromtimestamp(START_MS / 1000, tz=timezone.utc)
    assert series.length == pytest.approx(2.4)
    assert str(series.units) == "watt"
    assert series.meta == {
        "event": "FSGP_2024_Day_1", "signal": "MotorPower", "source": "derived",
        "description": "Motor power", "frequency": 10.0,
    }


def test_a_sample_in_two_pages_is_kept_once(monkeypatch):
    # As when a sample's sub-millisecond time rounds up to the next page's first timestamp
    fake = FakeServer(inclusive_end=True)
    monkeypatch.setattr(requests, "get", fake.get)

    series = SunbeamClient("http://sunbeam:8000").get_time_series("FSGP_2024_Day_1", "MotorPower")

    assert list(series) == pytest.approx([float(i) for i in range(25)])


def test_names_are_url_encoded(server):
    SunbeamClient("http://sunbeam:8000").get_time_series("FSGP 2024/Day 1", "MotorPower")

    assert server.requests[0][0] == "http://sunbeam:8000/events/FSGP%202024%2FDay%201/signals/MotorPower/data"


def test_missing_values_are_interpolated_across(monkeypatch):
    fake = FakeServer(count=3, values=[1.0, None, 3.0])
    monkeypatch.setattr(requests, "get", fake.get)

    series = SunbeamClient("http://sunbeam:8000").get_time_series("FSGP_2024_Day_1", "MotorPower")

    assert list(series) == pytest.approx([1.0, 2.0, 3.0])


def test_unknown_frequency_uses_the_sample_spacing(monkeypatch):
    fake = FakeServer(count=5, frequency=None, unit="")
    monkeypatch.setattr(requests, "get", fake.get)

    series = SunbeamClient("http://sunbeam:8000").get_time_series("FSGP_2024_Day_1", "MotorPower")

    assert series.period == pytest.approx(0.1)
    assert series.units.dimensionless


def test_unknown_signal_raises_key_error(server):
    with pytest.raises(KeyError, match="no signal named 'nope'"):
        SunbeamClient("http://sunbeam:8000").get_time_series("FSGP_2024_Day_1", "nope")


def test_no_data_raises_value_error(monkeypatch):
    fake = FakeServer(count=0)
    monkeypatch.setattr(requests, "get", fake.get)

    with pytest.raises(ValueError, match="no data"):
        SunbeamClient("http://sunbeam:8000").get_time_series("FSGP_2024_Day_1", "MotorPower")
