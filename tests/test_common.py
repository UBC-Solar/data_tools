from datetime import datetime, timezone
from data_tools.query.common import _ensure_utc


def test_ensure_utc():
    """
    Test that timezone-aware timestamps are properly converted to UTC.
    """
    utc_datetime = datetime(2024, 10, 9, 15, 10, 10, tzinfo=timezone.utc)

    assert isinstance(_ensure_utc(utc_datetime), datetime)
    assert _ensure_utc(utc_datetime).timestamp() == 1728486610.0


def test_ensure_utc_converstion():
    """
    Test that an aware datetime is properly converted to UTC
    """
    pst_datetime = datetime(2024, 10, 9, 15, 10, 10, tzinfo=ZoneInfo("America/Los_Angeles"))

    # Expected timestamp before conversion
    assert pst_datetime.timestamp() == 1728511810.0

    expected_timestamp_after_conversion = datetime(2024, 10, 9, 22, 10, 10, tzinfo=timezone.utc).timestamp()

    assert _ensure_utc(pst_datetime).timestamp() == expected_timestamp_after_conversion


def test_ensure_utc_failure():
    """
    Test that naive datetime gets rejected
    """
    naive_datetime = datetime(2024, 10, 9, 15, 10, 10)

    with pytest.raises(ValueError):
        _ensure_utc(naive_datetime)
