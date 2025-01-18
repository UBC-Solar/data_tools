from data_tools.lap_tools.fsgp_2024_laps import FSGPDayLaps
from data_tools.query.influxdb_query import DBClient
from typing import Callable
import numpy as np

def collect_lap_data(query_func: Callable, client: DBClient, include_day_2=False,
                     verbose=False) -> np.ndarray:
    """
    Higher order function - computes `query_func` for each lap in FSGP 2024 and returns the resulting array.

    Set `include_day_2` to True to include the day 2 laps, which were driven slowly & under heavy rain.

    Example usage:

    ```python
    from data_tools.collections import collect_lap_data, TimeSeries
    from data_tools.query import DBClient
    import datetime
    import numpy as np


    def get_average_speed(start_time: datetime.datetime, end_time: datetime.datetime, data_client: DBClient):
        lap_speed: TimeSeries = data_client.query_time_series(start_time, end_time, "VehicleVelocity")
        return np.mean(lap_speed)


    client = DBClient()

    average_speeds = collect_lap_data(get_average_speed, client)
    ```

    :param Callable query_func: must take in parameters (lap_start: datetime, lap_end:datetime, data_client:DBClient)
    :param DBClient client: client to use for querying
    :param include_day_2: flag to include the three day 2 laps, driven slowly & under heavy rain
    :param verbose: if True, print out queried data during execution
    :return: a NumPy ndarray of `query_func` results for all laps
    """

    if include_day_2:
        laps = (FSGPDayLaps(1),  # Corresponds to July 16th
                FSGPDayLaps(2),  # Corresponds to July 17th
                FSGPDayLaps(3))  # Corresponds to July 18th
    else:
        laps = (FSGPDayLaps(1),
                FSGPDayLaps(3))

    indices = [range(day_laps.get_lap_count()) for day_laps in laps]

    lap_data = []
    # Iterate through all selected laps
    for day_laps, lap_indices in zip(laps, indices):
        for lap_idx in lap_indices:
            lap_num = lap_idx + 1
            lap_start = day_laps.get_start_utc(lap_num)
            lap_end = day_laps.get_finish_utc(lap_num)
            lap_data.append(query_func(lap_start, lap_end, client))
            if verbose:
                print(f"Processed data for day {day_laps.day} lap {lap_num}")
                print(f"{lap_start=}\n{lap_end=}")
                print(f"{query_func.__name__} result for lap {lap_num}: {lap_data[-1]}\n")

    return np.array(lap_data)
