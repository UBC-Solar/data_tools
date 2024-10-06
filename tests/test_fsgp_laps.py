import pytest
from data_tools import FSGPDayLaps


def test_lap_start_finish():
    day_1_laps = FSGPDayLaps(1)
    assert day_1_laps.get_start_utc(1) == "2024-07-16T15:00:00Z"
    assert day_1_laps.get_finish_utc(1) == "2024-07-16T15:07:04Z"
    assert day_1_laps.get_start_utc(5) == "2024-07-16T15:27:21Z"
    assert day_1_laps.get_start_utc(33) == "2024-07-16T18:56:36Z"
    day_2_laps = FSGPDayLaps(2)
    assert day_2_laps.get_start_utc(1) == "2024-07-17T18:22:09Z"
    assert day_2_laps.get_start_utc(3) == "2024-07-17T18:47:04Z"
    assert day_2_laps.get_finish_utc(3) == "2024-07-17T18:59:09Z"
    day_3_laps = FSGPDayLaps(3)
    assert day_3_laps.get_start_utc(24) == "2024-07-18T17:04:40Z"
    assert day_3_laps.get_start_utc(47) == "2024-07-18T21:15:00Z"
    assert day_3_laps.get_finish_utc(49) == "2024-07-18T21:57:05Z"


def test_lap_count():
    day_3_laps = FSGPDayLaps(3)
    assert day_3_laps.get_lap_count() == 49, "Should have 49 laps in day 3"


def test_invalid_day():
    with pytest.raises(FileNotFoundError) as nf_error:
        day_4_laps = FSGPDayLaps(4)
    assert "No such file or directory" in str(nf_error.value)
    assert "fsgp_timing_day_4.csv" in str(nf_error.value)


def test_invalid_lap():
    day_3_laps = FSGPDayLaps(3)
    with pytest.raises(KeyError):
        zeroth_lap_start = day_3_laps.get_start_utc(0)
    with pytest.raises(KeyError):
        hundredth_lap_driver = day_3_laps.get_lap_driver(100)
