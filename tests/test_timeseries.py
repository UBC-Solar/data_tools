import pytest
from data_tools import TimeSeries
import numpy as np
import datetime


def create_time_series():
    pass


def test_align_with_same_granularity():
    y_data_1 = [1, 2, 3, 3, 3, 2, 4, 4, 4, 1]
    x_data_1 = np.array([4, 5, 6, 7, 8, 9, 10, 11, 12, 13]) + 946684800.0
    # x_data_1 = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

    y_data_2 = [1, 2, 1, 2, 7, 8, 3, 2, 4, 4, 4, 1, 4, 3]
    x_data_2 = np.array([2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]) + 946684800.0

    time_series_1 = TimeSeries(y_data_1, meta={
            "start": datetime.datetime.fromtimestamp(x_data_1[0]),
            "stop": datetime.datetime.fromtimestamp(x_data_1[-1]),
            "car": "",
            "measurement": "",
            "field": "",
            "period": 1.0,
            "length": x_data_1[-1] - x_data_1[0],
            "units": "",
        })

    time_series_2 = TimeSeries(y_data_2, meta={
            "start": datetime.datetime.fromtimestamp(x_data_2[0]),
            "stop": datetime.datetime.fromtimestamp(x_data_2[-1]),
            "car": "",
            "measurement": "",
            "field": "",
            "period": 1.0,
            "length": x_data_2[-1] - x_data_2[0],
            "units": "",
        })

    time_series_1_aligned, time_series_2_aligned = TimeSeries.align(time_series_1, time_series_2)

    assert np.allclose(time_series_1_aligned, [1, 2, 3, 3, 3, 2, 4, 4, 4, 1])
    assert np.allclose(time_series_2_aligned, [1, 2, 7, 8, 3, 2, 4, 4, 4, 1])


def test_align_with_different_granularity():
    y_data_1 = [1, 2, 3, 3, 3, 2, 4,  4,  4,  1]
    x_data_1 = np.array([4, 5, 6, 7, 8, 9, 10, 11, 12, 13]) + 946684800.0  # January 1st, 2000 in UNIX time

    y_data_2 = [1, 2,   1, 2,   7, 8,   3, 2,   4, 4,   4, 1,   4, 3,   1, 2,   1,  2,    7,  8,    3,  2,    4,  4,    4,  1,    1]
    x_data_2 = np.array([2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6, 6.5, 7, 7.5, 8, 8.5, 9, 9.5, 10, 10.5, 11, 11.5, 12, 12.5, 13, 13.5, 14, 14.5, 15]) + 946684800.0

    time_series_1 = TimeSeries(y_data_1, meta={
            "start": datetime.datetime.fromtimestamp(x_data_1[0]),
            "stop": datetime.datetime.fromtimestamp(x_data_1[-1]),
            "car": "",
            "measurement": "",
            "field": "",
            "period": 1.0,
            "length": x_data_1[-1] - x_data_1[0],
            "units": "",
        })

    time_series_2 = TimeSeries(y_data_2, meta={
            "start": datetime.datetime.fromtimestamp(x_data_2[0]),
            "stop": datetime.datetime.fromtimestamp(x_data_2[-1]),
            "car": "",
            "measurement": "",
            "field": "",
            "period": 0.5,
            "length": x_data_2[-1] - x_data_2[0],
            "units": "",
        })

    time_series_1_aligned, time_series_2_aligned = TimeSeries.align(time_series_1, time_series_2)

    assert np.allclose(time_series_1_aligned, [1, 1.5, 2, 2.5, 3, 3.0, 3, 3.0, 3, 2.5, 2, 3.0, 4, 4.0, 4, 4.0, 4, 2.5, 1])
    assert np.allclose(time_series_2_aligned, [7, 8, 3, 2, 4, 4, 4, 1, 4, 3, 1, 2, 1, 2, 7, 8, 3, 2, 4])
