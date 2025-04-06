from data_tools.query import SolcastOutput, SolcastPeriod, SolcastClient
from solcast.unmetered_locations import UNMETERED_LOCATIONS
import pytest
import os
import datetime
from datetime import datetime, timedelta, UTC
from dotenv import load_dotenv
import numpy as np

load_dotenv()


@pytest.mark.parametrize("period, expected_frequency", [
    (SolcastPeriod.PT5M, 12),
    (SolcastPeriod.PT10M, 6),
    (SolcastPeriod.PT15M, 4),
    (SolcastPeriod.PT20M, 3),
    (SolcastPeriod.PT30M, 2),
    (SolcastPeriod.PT60M, 1),
])
def test_as_frequency(period, expected_frequency):
    assert period.as_frequency() == expected_frequency


def test_invalid_period():
    with pytest.raises(ValueError):
        SolcastPeriod("PT25M")


@pytest.fixture
def solcast_client():
    api_key = os.getenv("SOLCAST_API_KEY")
    return SolcastClient(api_key)


@pytest.mark.parametrize("input_seconds, expected_hours", [
    (0, 0),             # Less than a minute
    (59, 0),            # Still less than a minute
    (60, 1),            # Exactly one minute, still rounds down
    (3599, 1),          # 1 second before 1 hour, within threshold
    (3600, 1),          # Exactly 1 hour
    (3601, 1),          # Just 1 second past 1 hour, but > threshold, round up
    (3659, 1),          # Just under threshold, still rounds down
    (3660, 1),          # Just under threshold, still rounds down
    (3661, 2),          # Exactly threshold: 1 minute into next hour, round up
    (7199, 2),          # 1 second before 2 hours
    (7200, 2),          # Exactly 2 hours
    (7260, 2),          # 1 minute past 2 hours, round up
])
def test_round_to_hour(input_seconds, expected_hours):
    assert SolcastClient._round_to_hour(input_seconds) == expected_hours


@pytest.mark.parametrize("start_offset, end_offset, expected_past_hours, expected_future_hours", [
    (timedelta(hours=3, minutes=30), timedelta(hours=3, minutes=30), 4, 4),
    (timedelta(hours=3, minutes=0), timedelta(hours=3, minutes=0), 3, 3),
    (timedelta(hours=2, minutes=59), None, 3, 0),
    (None, timedelta(hours=2, minutes=59), 0, 3)
])
def test_solcast_time_resolution(start_offset, end_offset, expected_past_hours, expected_future_hours, solcast_client):
    start_time = (datetime.now(UTC) - start_offset) if start_offset else datetime.now(UTC)
    end_time = (datetime.now(UTC) + end_offset) if end_offset else datetime.now(UTC)

    num_past_hours, num_future_hours = solcast_client._parse_num_hours(start_time, end_time)
    assert num_past_hours == expected_past_hours, f"Expected {expected_past_hours} past hours, got {num_past_hours}"
    assert num_future_hours == expected_future_hours, f"Expected {expected_future_hours} future hours, got {num_future_hours}"


def test_solcast_query():
    api_key = os.getenv("SOLCAST_API_KEY")
    client = SolcastClient(api_key)

    test_location = UNMETERED_LOCATIONS["Sydney Opera House"]

    start_time = datetime.now(UTC) - timedelta(hours=3)
    end_time = datetime.now(UTC) + timedelta(hours=3)

    desired_outputs = [SolcastOutput(output) for output in ["ghi", "ghi10"]]

    time, ghi, ghi10 = client.query(
        latitude=test_location["latitude"],
        longitude=test_location["longitude"],
        period=SolcastPeriod.PT60M,
        output_parameters=desired_outputs,
        tilt=0,
        azimuth=0,
        start_time=start_time,
        end_time=end_time,
    )
