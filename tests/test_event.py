import pytest
from data_tools.schema.event import Event
from datetime import datetime, timezone


@pytest.fixture
def event_datetime():
    naive_datetime_1 = datetime(2024, 10, 9, 15, 10, 10)
    naive_datetime_2 = datetime(2024, 10, 9, 16, 10, 10)

    aware_datetime_1 = datetime(2024, 10, 9, 22, 10, 10, tzinfo=timezone.utc)
    aware_datetime_2 = datetime(2024, 10, 9, 23, 10, 10, tzinfo=timezone.utc)

    return naive_datetime_1, naive_datetime_2, aware_datetime_1, aware_datetime_2


@pytest.fixture
def event_strs():
    naive_str_1 = "2024-10-09T15:10:10"
    naive_str_2 = "2024-10-09T16:10:10"

    aware_str_1 = "2024-10-09T22:10:10Z"
    aware_str_2 = "2024-10-09T23:10:10Z"

    return naive_str_1, naive_str_2, aware_str_1, aware_str_2


@pytest.fixture
def create_events(event_datetime, event_strs):
    _, _, aware_datetime_1, aware_datetime_2 = event_datetime
    _, _, aware_str_1, aware_str_2 = event_strs

    event_dt = Event(aware_datetime_1, aware_datetime_2, "test_1")
    event_str = Event(aware_str_1, aware_str_2, "test_2")

    return event_dt, event_str


def test_event_creation(event_datetime, event_strs, create_events):
    _, _, aware_datetime_1, aware_datetime_2 = event_datetime
    _, _, aware_str_1, aware_str_2 = event_strs
    event_dt, event_str = create_events

    assert event_dt.start == event_str.start == aware_datetime_1, "Start datetimes do not match!"
    assert event_dt.stop == event_str.stop == aware_datetime_2, "End datetimes do not match!"

    assert event_dt.start_as_iso_str == event_str.start_as_iso_str == aware_str_1, "Start strings do not match!"
    assert event_dt.stop_as_iso_str == event_str.stop_as_iso_str == aware_str_2, "End strings do not match!"

    assert event_dt.name == "test_1", "Name of event_dt is not correct!"
    assert event_str.name == "test_2", "Name of event_str is not correct!"


def test_event_creation_from_dict(event_datetime):
    # Test that an empty dictionary raises a KeyError
    with pytest.raises(KeyError):
        event = Event.from_dict({})

    # Test that an incomplete dictionary raises a KeyError
    with pytest.raises(KeyError):
        event = Event.from_dict({"start_time": datetime(2024, 10, 9, 23, 10, 10, tzinfo=timezone.utc)})

    _, _, aware_datetime_1, aware_datetime_2 = event_datetime

    str_dict = {
        "start": "2024-10-09T15:10:10Z",
        "stop": "2024-10-09T16:10:10Z",
        "name": "test_1"
    }

    datetime_dict = {
        "start": datetime(2024, 10, 9, 15, 10, 10, tzinfo=timezone.utc),
        "stop": datetime(2024, 10, 9, 16, 10, 10, tzinfo=timezone.utc),
        "name": "test_2"
    }

    mixed_dict = {
        "start": "2024-10-09T15:10:10Z",
        "stop": datetime(2024, 10, 9, 16, 10, 10, tzinfo=timezone.utc),
        "name": "test_3"
    }

    event_1 = Event.from_dict(str_dict)
    event_2 = Event.from_dict(datetime_dict)
    event_3 = Event.from_dict(mixed_dict)

    assert event_1.start == event_2.start == event_3.start == datetime(2024, 10, 9, 15, 10, 10, tzinfo=timezone.utc)
    assert event_1.stop == event_2.stop == event_3.stop == datetime(2024, 10, 9, 16, 10, 10, tzinfo=timezone.utc)


def test_event_to_dict(event_datetime):
    _, _, aware_datetime_1, aware_datetime_2 = event_datetime

    event = Event(aware_datetime_1, aware_datetime_2, "test_1")

    desired_dict = {
        "start": "2024-10-09T22:10:10Z",
        "stop": "2024-10-09T23:10:10Z",
        "name": "test_1"
    }

    event_dict = event.to_dict()

    for key, value in event_dict.items():
        assert value == desired_dict[key]


def test_event_creation_failure(event_datetime, event_strs):
    naive_datetime_1, naive_datetime_2, _, _ = event_datetime
    naive_str_1, naive_str_1, _, _ = event_strs

    # Ensure that naive datetime.datetime raise an error
    with pytest.raises(ValueError):
        Event(naive_datetime_1, naive_datetime_2, "test_1")

    # Ensure that naive ISO8601 string raises an error
    with pytest.raises(ValueError):
        Event(naive_str_1, naive_str_1, "test_2")


