from data_tools.utils.times import parse_iso_datetime, iso_string_from_datetime, ensure_utc
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pytest


def test_ensure_utc():
    """
    Test that timezone-aware timestamps are properly converted to UTC.
    """
    utc_datetime = datetime(2024, 10, 9, 15, 10, 10, tzinfo=timezone.utc)

    assert isinstance(ensure_utc(utc_datetime), datetime)
    assert ensure_utc(utc_datetime).timestamp() == 1728486610.0


def test_ensure_utc_converstion():
    """
    Test that an aware datetime is properly converted to UTC
    """
    pst_datetime = datetime(2024, 10, 9, 15, 10, 10, tzinfo=ZoneInfo("America/Los_Angeles"))

    # Expected timestamp before conversion
    assert pst_datetime.timestamp() == 1728511810.0

    expected_timestamp_after_conversion = datetime(2024, 10, 9, 22, 10, 10, tzinfo=timezone.utc).timestamp()

    assert ensure_utc(pst_datetime).timestamp() == expected_timestamp_after_conversion


def test_ensure_utc_failure():
    """
    Test that naive datetime gets rejected
    """
    naive_datetime = datetime(2024, 10, 9, 15, 10, 10)

    with pytest.raises(ValueError):
        ensure_utc(naive_datetime)


def test_parse_iso_datetime():
    dt_1 = parse_iso_datetime("2024-01-01T15:30:00Z")
    assert dt_1 == datetime(2024, 1, 1, 15, 30, 00).replace(tzinfo=ZoneInfo('UTC'))

    # Other timezones are converted to UTC
    dt_2 = parse_iso_datetime("2024-01-01T15:30:00+02:00")
    assert dt_2 == datetime(2024, 1, 1, 13, 30, 00).replace(tzinfo=ZoneInfo('UTC'))

    # Naive datetimes are not allowed
    with pytest.raises(ValueError):
        dt_3 = parse_iso_datetime("2024-01-01T15:30:00")


def test_iso_format_from_str():
    dt = datetime(2024, 11, 7, 15, 30, 45, tzinfo=timezone.utc)
    assert iso_string_from_datetime(dt) == "2024-11-07T15:30:45Z"

    dt = datetime(2024, 11, 7, 15, 30, 45, 123456, tzinfo=timezone.utc)
    assert iso_string_from_datetime(dt) == "2024-11-07T15:30:45.123456Z"
