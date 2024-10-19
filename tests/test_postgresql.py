import pytest
from data_tools.query.postgresql_query import _get_db_url, PostgresClient


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
