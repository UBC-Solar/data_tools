from data_tools.collections import collect_lap_data, TimeSeries, FSGPDayLaps
from data_tools.query import DBClient
import datetime
import numpy as np

client = DBClient()

DAY_1_LAP_COUNT = 46
DAY_2_LAP_COUNT = 3
DAY_3_LAP_COUNT = 49

def test_example_usage():
    """
    Define a query func, and ensure collect_lap_data performs as expected.

    Since the query function's validity is the client's responsibility, we only test that the values match
    the output of the function.
    """

    def get_middle_lap_time(start_time: datetime.datetime, end_time: datetime.datetime, data_client: DBClient):
        start: float = start_time.timestamp()
        end: float = end_time.timestamp()
        return np.mean([start, end])

    average_speeds = collect_lap_data(get_middle_lap_time, client, verbose=True)

    assert len(average_speeds) == DAY_1_LAP_COUNT + DAY_3_LAP_COUNT, "incorrect number of values queried"

    average_speeds_all_days = collect_lap_data(get_middle_lap_time, client, include_day_2=True, verbose=True)
    assert len(average_speeds_all_days) == DAY_1_LAP_COUNT + DAY_2_LAP_COUNT + DAY_3_LAP_COUNT, \
        "incorrect number of values queried"

    assert np.all(
        average_speeds[:DAY_1_LAP_COUNT] == average_speeds_all_days[:DAY_1_LAP_COUNT]
    ), "day 1 query results should match"
    assert np.all(
        average_speeds[DAY_1_LAP_COUNT + 1:] == average_speeds_all_days[DAY_1_LAP_COUNT + DAY_2_LAP_COUNT + 1:]
    ), "day 3 query results should match"

    day_1_laps = FSGPDayLaps(1)
    assert average_speeds[4] == get_middle_lap_time(
        day_1_laps.get_start_utc(5),
        day_1_laps.get_finish_utc(5),
        client
    )
    assert average_speeds[10] == get_middle_lap_time(
        day_1_laps.get_start_utc(11),
        day_1_laps.get_finish_utc(11),
        client
    )
    assert average_speeds[44] == get_middle_lap_time(
        day_1_laps.get_start_utc(45),
        day_1_laps.get_finish_utc(45),
        client
    )

    day_3_laps = FSGPDayLaps(3)
    assert average_speeds[DAY_1_LAP_COUNT] == get_middle_lap_time(
        day_3_laps.get_start_utc(1),
        day_3_laps.get_finish_utc(1),
        client
    )
    assert average_speeds[DAY_1_LAP_COUNT + 21] == get_middle_lap_time(
        day_3_laps.get_start_utc(22),
        day_3_laps.get_finish_utc(22),
        client
    )
