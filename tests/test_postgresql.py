import pytest
from data_tools.query.postgresql_query import _get_db_url, PostgresClient, _ensure_utc
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def test_db_url():
    """
    Test that, given a set of valid inputs, _get_db_url returns the expected output.
    """
    username = "user"
    password = "password"
    db_name = "db"
    address = "localhost"

    assert _get_db_url(db_name, address, username, password) == "postgresql://user:password@localhost:5432/db"


def test_db_url_validation():
    """
    Test that all the inputs to _get_db_url are properly validated
    and raise ValueError when invalid input is provided.
    """
    username = "user"
    password = "password"
    db_name = "db"
    address = "localhost"

    with pytest.raises(AssertionError):
        _get_db_url(None, address, username, password)

    with pytest.raises(AssertionError):
        _get_db_url(db_name, address, 0, password)

    with pytest.raises(AssertionError):
        _get_db_url(db_name, address, username, [])

    with pytest.raises(AssertionError):
        _get_db_url(db_name, {}, username, password)


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
