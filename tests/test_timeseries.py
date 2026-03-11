from data_tools.collections import TimeSeries
import numpy as np
import math
import pytest
import datetime

# Helper Function for testing
def quick_gen_timeseries(x_data, y_data, units = "m"):
    time_series = TimeSeries(y_data, 
                             datetime.datetime.fromtimestamp(x_data[0], tz = datetime.timezone.utc),
                             datetime.datetime.fromtimestamp(x_data[-1], tz = datetime.timezone.utc),
                             period = 1.0,
                             length = x_data[-1] - x_data[0],
                             units=units)
    
    return time_series

# There's alot of tests...
def test_align_with_same_granularity():
    y_data_1 = [1, 2, 3, 3, 3, 2, 4, 4, 4, 1]
    x_data_1 = np.array([4, 5, 6, 7, 8, 9, 10, 11, 12, 13]) + 946684800.0
    # x_data_1 = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

    y_data_2 = [1, 2, 1, 2, 7, 8, 3, 2, 4, 4, 4, 1, 4, 3]
    x_data_2 = np.array([2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]) + 946684800.0

    time_series_1 = TimeSeries(y_data_1, 
                               datetime.datetime.fromtimestamp(x_data_1[0], tz = datetime.timezone.utc),
                               datetime.datetime.fromtimestamp(x_data_1[-1], tz = datetime.timezone.utc),
                               period = 1.0,
                               length = x_data_1[-1] - x_data_1[0],)

    time_series_2 = TimeSeries(y_data_2, 
                               datetime.datetime.fromtimestamp(x_data_2[0], tz = datetime.timezone.utc),
                               datetime.datetime.fromtimestamp(x_data_2[-1], tz = datetime.timezone.utc),
                               period = 1.0,
                               length = x_data_2[-1] - x_data_2[0],)

    time_series_1_aligned, time_series_2_aligned = TimeSeries.align(time_series_1, time_series_2)

    assert np.allclose(time_series_1_aligned, [1, 2, 3, 3, 3, 2, 4, 4, 4, 1])
    assert np.allclose(time_series_2_aligned, [1, 2, 7, 8, 3, 2, 4, 4, 4, 1])

def test_align_with_different_granularity():
    y_data_1 = [1, 2, 3, 3, 3, 2, 4,  4,  4,  1]
    x_data_1 = np.array([4, 5, 6, 7, 8, 9, 10, 11, 12, 13]) + 946684800.0  # January 1st, 2000 in UNIX time

    y_data_2 = [1, 2, 1, 2, 7, 8, 3, 2,  4, 4, 4, 1, 4, 3, 1, 2, 1, 2, 7, 8, 3, 2, 4, 4, 4, 1, 1]
    x_data_2 = np.array([2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6, 6.5, 7, 7.5, 8, 8.5, 9, 9.5, 10, 10.5, 11, 11.5, 12, 12.5, 13, 13.5, 14, 14.5, 15]) + 946684800.0

    time_series_1 = TimeSeries(y_data_1, 
                               datetime.datetime.fromtimestamp(x_data_1[0], tz = datetime.timezone.utc),
                               datetime.datetime.fromtimestamp(x_data_1[-1], tz = datetime.timezone.utc),
                               period = 1.0,
                               length = x_data_1[-1] - x_data_1[0],)

    time_series_2 = TimeSeries(y_data_2, 
                               datetime.datetime.fromtimestamp(x_data_2[0], tz = datetime.timezone.utc),
                               datetime.datetime.fromtimestamp(x_data_2[-1], tz = datetime.timezone.utc),
                               period = 0.5,
                               length = x_data_2[-1] - x_data_2[0],)

    time_series_1_aligned, time_series_2_aligned = TimeSeries.align(time_series_1, time_series_2)

    assert np.allclose(time_series_1_aligned, [1, 1.5, 2, 2.5, 3, 3.0, 3, 3.0, 3, 2.5, 2, 3.0, 4, 4.0, 4, 4.0, 4, 2.5, 1])
    assert np.allclose(time_series_2_aligned, [7, 8, 3, 2, 4, 4, 4, 1, 4, 3, 1, 2, 1, 2, 7, 8, 3, 2, 4])

def test_interpolate_index():
    y_data_1 = [1, 2, 3, 3, 3, 2, 4,  4,  4,  1]
    x_data_1 = np.array([4, 5, 6, 7, 8, 9, 10, 11, 12, 13]) + 946684800.0  # January 1st, 2000 in UNIX time

    time_series_1 = TimeSeries(y_data_1, 
                               datetime.datetime.fromtimestamp(x_data_1[0], tz = datetime.timezone.utc),
                               datetime.datetime.fromtimestamp(x_data_1[-1], tz = datetime.timezone.utc),
                               period = 1.0,
                               length = x_data_1[-1] - x_data_1[0],)
    
    assert math.isclose(time_series_1.interpolate_indices(1.3), y_data_1[1] * 0.7 + y_data_1[2] * 0.3)
    assert time_series_1.interpolate_indices(2.4) == 3
    assert math.isclose(time_series_1.interpolate_indices(8.8), y_data_1[8] * 0.2 + y_data_1[9] * 0.8)

def test_datetime_index(): 
    epsilon = 0.0001
    y_data_1 = [1, 2, 3, 3, 3, 2, 4,  5,  4,  1]
    x_data_1 = np.array([4, 5, 6, 7, 8, 9, 10, 11, 12, 13]) + 946684800.0  # January 1st, 2000 in UNIX time

    time_series_1 = TimeSeries(y_data_1, 
                               datetime.datetime.fromtimestamp(x_data_1[0], tz = datetime.timezone.utc),
                               datetime.datetime.fromtimestamp(x_data_1[-1], tz = datetime.timezone.utc),
                               period = 1.0,
                               length = x_data_1[-1] - x_data_1[0],)

    time1 = datetime.datetime.fromtimestamp(946684800.0 + 4, tz = datetime.timezone.utc)
    time2 = datetime.datetime.fromtimestamp(946684800.0 + 11, tz = datetime.timezone.utc)
    time3 = datetime.datetime.fromtimestamp(946684800.0 + 12.5, tz = datetime.timezone.utc)
    time4 = datetime.datetime.fromtimestamp(946684800.0 + 8.2, tz = datetime.timezone.utc)

    # Should throw error for being out of bounds
    time5 = datetime.datetime.fromtimestamp(946684800.0 + 16, tz = datetime.timezone.utc)
    
    # Check if values are correct for those in bounds
    assert math.isclose(time_series_1[time1], 1)
    assert math.isclose(time_series_1[time2], 5)
    assert math.isclose(time_series_1[time3], 2.5)
    assert abs(time_series_1[time4] - 2.8) < epsilon

    with pytest.raises(IndexError): 
        _ = time_series_1[time5]

def test_datetime_slice(): 
    y_data_1 = [1, 2, 3, 3, 3, 2, 4, 5, 4, 1, 3, 4, 6, 7, 3, 4]
    x_data_1 = np.array([4, 19])

    time_series_1 = quick_gen_timeseries(x_data_1, y_data_1)

    t1 = datetime.datetime.fromtimestamp(5, tz = datetime.timezone.utc)
    t2 = datetime.datetime.fromtimestamp(18, tz = datetime.timezone.utc)
    t3 = datetime.datetime.fromtimestamp(11.5, tz = datetime.timezone.utc)
    t4 = datetime.datetime.fromtimestamp(17.8, tz = datetime.timezone.utc)
    t5 = datetime.datetime.fromtimestamp(2, tz = datetime.timezone.utc)
    t6 = datetime.datetime.fromtimestamp(23, tz = datetime.timezone.utc)
    t7 = datetime.datetime.fromtimestamp(20, tz = datetime.timezone.utc)
    t8 = datetime.datetime.fromtimestamp(3, tz = datetime.timezone.utc)

    test_series_1 = time_series_1.slice_datetime(t1, t2)
    test_series_2 = time_series_1.slice_datetime(t3, t4)

    # Out of bounds tests
    # Slice start before start time
    test_series_3 = time_series_1.slice_datetime(t5, t2)

    # Slice end after stop time
    test_series_4 = time_series_1.slice_datetime(t1, t6)

    # Slice start is before start time and slice end is after stop time
    test_series_7 = time_series_1.slice_datetime(t5, t6)

    assert np.allclose(test_series_1, [2, 3, 3, 3, 2, 4, 5, 4, 1, 3, 4, 6, 7, 3])
    assert np.allclose(test_series_2, [4, 1, 3, 4, 6, 7])
    assert np.allclose(test_series_3, [1, 2, 3, 3, 3, 2, 4, 5, 4, 1, 3, 4, 6, 7, 3])
    assert np.allclose(test_series_4, [2, 3, 3, 3, 2, 4, 5, 4, 1, 3, 4, 6, 7, 3, 4])
    assert np.allclose(test_series_7, [1, 2, 3, 3, 3, 2, 4, 5, 4, 1, 3, 4, 6, 7, 3, 4])

    #  Slice start and end both before start time
    with pytest.raises(ValueError): 
        _ = time_series_1.slice_datetime(t5, t8)

    # Slice start and end both after stop time
    with pytest.raises(ValueError): 
        _ = time_series_1.slice_datetime(t7, t6)

    # Slice start is after slice end 
    with pytest.raises(ValueError): 
        _ = time_series_1.slice_datetime(t6, t5)

def test_addition_auto_align():
    y1 = [1, 2, 3, 4]
    x1 = np.array([0, 1, 2, 3]) + 946684800.0

    y2 = [10, 20, 30]
    x2 = np.array([1, 2, 3]) + 946684800.0

    ts1 = quick_gen_timeseries(x1, y1)
    ts2 = quick_gen_timeseries(x2, y2)

    result = ts1 + ts2

    assert isinstance(result, TimeSeries)
    assert np.allclose(result, [2 + 10, 3 + 20, 4 + 30])

def test_multiplication_auto_align_different_granularity():
    y1 = [1, 2, 3, 4]
    x1 = np.array([0, 1, 2, 3]) + 946684800.0

    y2 = [10, 20, 30, 40, 50, 60, 70]
    x2 = np.array([0, 0.5, 1, 1.5, 2, 2.5, 3]) + 946684800.0

    ts1 = TimeSeries(y1, 
                     datetime.datetime.fromtimestamp(x1[0]),
                     datetime.datetime.fromtimestamp(x1[-1]),
                     period = 1.0,
                     length = x1[-1] - x1[0],
                     units="m")

    ts2 = TimeSeries(y2, 
                     datetime.datetime.fromtimestamp(x2[0]), 
                     datetime.datetime.fromtimestamp(x2[-1]), 
                     period = 0.5, 
                     length = x2[-1] - x2[0],
                     units="m")

    result = ts1 * ts2

    # Should align to min period = 0.5
    assert len(result) == 7
    assert np.allclose(result, np.array(result))  # sanity: numeric output
    assert np.allclose(result, [10, 20*1.5, 2*30, 2.5*40, 3*50, 3.5*60, 4*70])
 
def test_units_and_operations():
    x = [0, 1, 2]
    # Addition with same units
    ts1 = quick_gen_timeseries(x, [1, 2, 3], units = "m")
    ts2 = quick_gen_timeseries(x, [4, 5, 6], units = "m")

    result_add = ts1 + ts2

    assert str(result_add.units) == "meter"
    assert np.allclose(result_add, [5, 7, 9])

    # Addition with different units should fail
    ts3 = quick_gen_timeseries(x, [1, 2, 3], units = "m")
    ts4 = quick_gen_timeseries(x, [1, 2, 3], units = "s")

    with pytest.raises(ValueError):
        _ = ts3 + ts4

    # Multiplication should compose units
    ts5 = quick_gen_timeseries(x, [1, 2, 3], units = "m")
    ts6 = quick_gen_timeseries(x, [4, 5, 6], units = "s")

    result_mul = ts5 * ts6

    # Pint composes units automatically
    assert result_mul.units == ts5.units * ts6.units
    assert np.allclose(result_mul, [4, 10, 18])

    # Dimensionless operations allowed
    ts7 = quick_gen_timeseries(x, [1, 3, 5], units = "")
    ts8 = quick_gen_timeseries(x, [4, 5, 6], units = "kg")

    result_dimless = ts7 * ts8

    assert result_dimless.units == ts8.units
    assert np.allclose(result_dimless, [4, 15, 30])

def test_addition_different_units():
    # Testing if units transfer expectedly: Expected behaviour is that the one on the left is transferred
    # Test add across different units of the same dimensionality
    y1 = [1, 2, 3]
    x1 = np.array([0, 1, 2]) + 946684800.0

    y2 = [4, 5, 6]
    x2 = np.array([0, 1, 2]) + 946684800.0

    ts1 = TimeSeries(y1, 
                     datetime.datetime.fromtimestamp(x1[0]),
                     datetime.datetime.fromtimestamp(x1[-1]),
                     period = 1.0,
                     length = x1[-1] - x1[0]
                     )

    ts2 = TimeSeries(y2, 
                     datetime.datetime.fromtimestamp(x2[0]), 
                     datetime.datetime.fromtimestamp(x2[-1]), 
                     period = 1.0, 
                     length = x2[-1] - x2[0]
                     )

    ts1.units = "km"
    ts2.units = "m"

    result_add1 =  ts1 + ts2

    assert result_add1.units == ts1.units
    assert np.allclose(result_add1, [1.004, 2.005, 3.006])

    result_add2 =  ts2 + ts1

    assert result_add2.units == ts2.units
    assert np.allclose(result_add2, [1004, 2005, 3006])

def test_subtraction_operations():
    x = [0, 1, 2]
    # subtraction with same units
    ts1 = quick_gen_timeseries(x, [10, 20, 30], units="m")
    ts2 = quick_gen_timeseries(x, [1, 2, 3], units="m")
    
    result_sub = ts1 - ts2
    assert str(result_sub.units) == "meter"
    assert np.allclose(result_sub, [9, 18, 27])

    # Subtraction with different units should fail
    ts3 = quick_gen_timeseries(x, [10, 20, 30], units="kg")
    with pytest.raises(ValueError):
        _ = ts1 - ts3

    # Subtraction with scalars 
    ts_dimless = quick_gen_timeseries(x, [5, 10, 15], units="")
    result_scalar_sub = ts_dimless - 2
    assert np.allclose(result_scalar_sub, [3, 8, 13])

def test_reflected_addition_radd():
    x = [0, 1, 2]
    ts = quick_gen_timeseries(x, [1, 2, 3], units="")
    
    # Testing scalar + TimeSeries
    result = 5 + ts
    
    assert np.allclose(result, [6, 7, 8])
    assert result.units == ts.units

    # Testing numpy array + TimeSeries
    arr = np.array([10, 10, 10])
    result_arr = arr + ts
    assert np.allclose(result_arr, [11, 12, 13])

def test_reflected_multiplication():
    x = [0, 1, 2]
    ts = quick_gen_timeseries(x, [2, 4, 6], units="m")
    
    # Testing scalar * TimeSeries (rmul)
    # 10 * [2, 4, 6] meters should be [20, 40, 60] meters
    result = 10 * ts
    
    assert np.allclose(result, [20, 40, 60])
    assert str(result.units) == "meter"

    # Testing reflected multiplication with different types
    factor = np.array([1, 0, 1])
    result_vec = factor * ts
    assert np.allclose(result_vec, [2, 0, 6])
    assert str(result_vec.units) == "meter"

def test_div():
    x = [0, 1, 2]
    
    # Division test between two timeseries
    ts_dist = quick_gen_timeseries(x, [10, 20, 30], units="m")
    ts_time = quick_gen_timeseries(x, [2, 4, 5], units="s")
    
    result_div = ts_dist / ts_time
    
    assert str(result_div.units) == "meter / second"
    assert np.allclose(result_div, [5, 5, 6])

    # Division by scalar
    ts_mass = quick_gen_timeseries(x, [10, 20, 30], units="kg")
    result_scalar_div = ts_mass / 2
    
    assert result_scalar_div.units == ts_mass.units
    assert np.allclose(result_scalar_div, [5, 10, 15])

def test_rdiv():
    x = [0, 1, 2]
    # Timeseries dividing a scalar
    ts_period = quick_gen_timeseries(x, [2, 4, 8], units="s")
    result_rdiv = 1 / ts_period
    
    assert result_rdiv.units == 1 / ts_period.units
    assert np.allclose(result_rdiv, [0.5, 0.25, 0.125])

def test_division_dimensionless_units():
    x = [0, 1, 2]
    # Division with Dimensionless units
    ts_val = quick_gen_timeseries(x, [10, 20, 30], units="m")
    ts_ratio = quick_gen_timeseries(x, [2, 2, 2], units="")
    
    result_dim = ts_val / ts_ratio
    assert result_dim.units == ts_val.units
    assert np.allclose(result_dim, [5, 10, 15])

    # Dimensionless result (same units cancel out)
    ts_a = quick_gen_timeseries(x, [10, 20, 30], units="m")
    ts_b = quick_gen_timeseries(x, [2, 2, 2], units="m")
    
    result_cancel = ts_a / ts_b
    # Check if result is dimensionless (unitless)
    assert result_cancel.units.dimensionless
    assert np.allclose(result_cancel, [5, 10, 15])

def test_complex_unit_chaining():
    # This one is mostly just for funsies
    x = [0, 1, 2]
    # (ts1 - ts2) * ts3
    ts1 = quick_gen_timeseries(x, [10, 10, 10], units="m")
    ts2 = quick_gen_timeseries(x, [1, 1, 1], units="m")
    ts3 = quick_gen_timeseries(x, [2, 2, 2], units="s")
    
    result = (ts1 - ts2) * ts3
    
    # Units should be meter * second
    assert np.allclose(result, [18, 18, 18])
    assert "meter" in str(result.units)
    assert "second" in str(result.units)

def test_time_shift_behavior():
    # Forward shift
    y1 = [1, 2, 3]
    x1 = np.array([0, 1, 2]) + 946684800.0

    ts1 = quick_gen_timeseries(x1, y1)
    shifted_forward = ts1.shift(5)

    assert shifted_forward.start.timestamp() == ts1.start.timestamp() + 5
    assert shifted_forward.stop.timestamp() == ts1.stop.timestamp() + 5
    assert np.allclose(shifted_forward, y1)

    # Backward shift
    y2 = [1, 2, 3]
    x2 = np.array([10, 11, 12]) + 946684800.0

    ts2 = quick_gen_timeseries(x2, y2)
    shifted_backward = ts2.shift(-3)

    assert shifted_backward.start.timestamp() == ts2.start.timestamp() - 3
    assert shifted_backward.stop.timestamp() == ts2.stop.timestamp() - 3

    # Preserve metadata test
    ts3 = TimeSeries([1, 2, 3], 
                      datetime.datetime.fromtimestamp(1 + 946684800.0, tz = datetime.timezone.utc),
                      datetime.datetime.fromtimestamp(3 + 946684800.0, tz = datetime.timezone.utc),
                      1,
                      3,
                      "m"
    )

    shifted_meta = ts3.shift(10)

    assert shifted_meta.period == ts3.period
    assert shifted_meta.units == "meter"

    ts3 = quick_gen_timeseries(x1, y1)
    shifted_forward_timedelta = ts1.shift(datetime.timedelta(minutes=2))

    assert shifted_forward_timedelta.start.timestamp() == ts1.start.timestamp() + 120
    assert shifted_forward_timedelta.stop.timestamp() == ts1.stop.timestamp() + 120
    assert np.allclose(shifted_forward_timedelta, y1)
