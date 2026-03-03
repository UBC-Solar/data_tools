import numpy as np
import datetime
from dateutil import parser
import matplotlib.pyplot as plt
import math
from warnings import warn
import pandas as pd
import re
import warnings
import pint


class TimeSeries(np.ndarray):
    """
    This class encapsulates time-series data with units, a temporal x–axis, and metadata.

    Data is homogenous and evenly-spaced, such that temporal granularity between subsequent elements is constant.

    TimeSeries can be indexed with a ``float`` or slice with ``float`` components in order to index by relative time.
    For example, for some ``timeSeries``, ``timeSeries[10.43]`` is equivalent to
    ``timeSeries[timeSeries.index_of(10.43)]``.
    """

    # __new__ and __array_finalize__ are mandatory to ensure that
    # `TimeSeries` properly acts like a ndarray when necessary.
    def __new__(cls, input_array, 
                start_time: datetime.datetime = None, 
                stop_time: datetime.datetime = None,
                period: float = None,
                length: float = None,
                units = None,
                meta: dict = None):
        obj = np.asarray(input_array).view(cls)
        obj._start = start_time
        obj._stop = stop_time
        obj._units = units
        obj._period = period
        obj._length = length
        obj._meta = meta
        return obj

    def __array_finalize__(self, obj):
        if obj is None:
            return
        self._start = getattr(obj, '_start', None)
        self._stop = getattr(obj, '_stop', None)
        self._units = getattr(obj, '_units', None)
        self._length = getattr(obj, '_length', None)
        self._period = getattr(obj, '_period', None)
        self._meta = getattr(obj, '_meta', None)

    def __init__(self, input_array, 
                 start_time: datetime.datetime = None, 
                 stop_time: datetime.datetime = None,
                 period: float = None,
                 length: float = None,
                 units = None,
                 meta: dict = None):
        
        self.ureg = pint.UnitRegistry() # Unit Registry for Pint

        # Check if the start and stop are not naive
        if start_time.tzinfo is None:
            warnings.warn("Start time does not have a listed timezone, defaulting to UTC")
            start_time = start_time.replace(tzinfo=datetime.timezone.utc)
        
        if stop_time.tzinfo is None:
            warnings.warn("Stop time does not have a listed timezone, defaulting to UTC")
            stop_time = stop_time.replace(tzinfo=datetime.timezone.utc)

        self._start: datetime.datetime = start_time
        self._stop: datetime.datetime = stop_time

        # Setting units
        if units is None:
            self._units = units
        elif isinstance(units, str): # Eg. "meter/second**2" or "J"
            self._units = self.ureg.parse_units(units)
        elif isinstance(units, self.ureg.Unit):
            self._units = units

        self._period: float = period

        self._length: float = length

        self._meta = meta

    def __add__(self, other):
        if isinstance(other, TimeSeries):
            self_aligned, other_aligned = TimeSeries.align(self, other)

            # Call ndarray's add directly to avoid recursion
            raw_sum = np.ndarray.__add__(self_aligned, other_aligned)

            return self_aligned.promote(raw_sum)
        
        else:
            raw_sum = np.ndarray.__add__(self, other)
            return self.promote(raw_sum)
        
    def __mul__(self, other):
        if isinstance(other, TimeSeries):
            self_aligned, other_aligned = TimeSeries.align(self, other)

            # Call ndarray's add directly to avoid recursion
            raw_sum = np.ndarray.__mul__(self_aligned, other_aligned)

            return self_aligned.promote(raw_sum)
        
        else:
            raw_sum = np.ndarray.__mul__(self, other)
            return self.promote(raw_sum)
        
    @property
    def x_axis(self) -> np.ndarray:
        """
        This wave's x–axis in relative seconds, such that the first element is ``t=0``.
        """
        relative_x_axis = np.linspace(0.0, self._length, len(self))

        return relative_x_axis

    @property
    def unix_x_axis(self) -> np.ndarray:
        """
        This wave's x–axis as UTC UNIX timestamps.
        """
        return self.x_axis + self.start.timestamp()

    @property
    def datetime_x_axis(self) -> np.ndarray:
        """
        This wave's x–axis as ``datetime``s, in UTC.
        """

        return pd.to_datetime(self.unix_x_axis, unit='s')

    @property
    def length(self) -> float:
        """
        Total time between the first and last element of this wave's data
        """

        return self._length

    @property
    def granularity(self) -> float:
        """
        Temporal granularity (delta t) between each element of this wave's data in seconds
        """
        warn("Please use TimeSeries.period instead of TimeSeries.granularity", DeprecationWarning, stacklevel=2)
        return self._period

    @property
    def period(self) -> float:
        """
        Get the period, in seconds, between data points of this TimeSeries.

        :return: period, in seconds.
        """
        return self._period

    @property
    def units(self) -> str:
        """
        The units of this wave's data
        """
        return self._units

    @units.setter
    def units(self, value: str):
        assert isinstance(value, str), f"Units should be a string, not {type(value)}!"
        self._units = value

    @property
    def start(self) -> datetime.datetime:
        """
        UTC datetime of the first data element
        """
        return self._start

    @property
    def stop(self) -> datetime.datetime:
        """
        UTC datetime of the last data element
        """
        return self._stop

    def __getitem__(self, item):
        data_to_slice = self

        if isinstance(item, float):
            index = self.index_of(item)
            return super(TimeSeries, data_to_slice).__getitem__(index)

        elif isinstance(item, slice):
            if isinstance(item.start, float):
                start_index = self.index_of(item.start)
            else:
                start_index = item.start

            if isinstance(item.stop, float):
                stop_index = self.index_of(item.stop)
            else:
                stop_index = item.stop

            item = slice(start_index, stop_index, item.step)

            unix_x_axis = data_to_slice.unix_x_axis
            new_start_timestamp: float = unix_x_axis[start_index]
            new_stop_timestamp: float = unix_x_axis[stop_index - 1]

            new_start: datetime.datetime = datetime.datetime.fromtimestamp(new_start_timestamp)
            new_stop: datetime.datetime = datetime.datetime.fromtimestamp(new_stop_timestamp)
            new_length: float = new_stop_timestamp - new_start_timestamp

            new_meta = data_to_slice.meta
            
            new_time_series = TimeSeries(self,
                                         new_start,
                                         new_stop,
                                         data_to_slice.period,
                                         new_length,
                                         data_to_slice.units,
                                         new_meta)

            data_to_slice = new_time_series

        elif isinstance(item, datetime.datetime):
            unix_x_axis = data_to_slice.unix_x_axis
            item_ts = item.timestamp()

            start_timestamp: float = unix_x_axis[0]
            stop_timestamp: float = unix_x_axis[-1]

            if item_ts > stop_timestamp or item_ts < start_timestamp:
                raise IndexError(
                    f"Datetime {item} is out of bounds! "
                    f"Range: [{datetime.datetime.fromtimestamp(start_timestamp)}, "
                    f"{datetime.datetime.fromtimestamp(stop_timestamp)}]"
                )
            
            if item.tzinfo is None:
                raise ValueError(f"The index does not have an assigned timezone!")

            dt = stop_timestamp - start_timestamp

            if dt == 0:
                return data_to_slice[0]

            interpolation_index = (item_ts - start_timestamp) * (len(data_to_slice) - 1)/dt

            return data_to_slice.interpolate_indices(interpolation_index)

        return super(TimeSeries, data_to_slice).__getitem__(item)

    @property
    def meta(self) -> dict:
        """
        Metadata such as the field, measurement, and car.
        """
        return self._meta

    @meta.setter
    def meta(self, new_meta: dict):
        assert isinstance(new_meta, dict), f"New metadata should be a dictionary, not {type(new_meta)}!"
        self._meta = new_meta

    def plot(self, show=True) -> None:
        """
        Make a simple plot this data.
        :param bool show: Show plots (disable if you want to stack multiple plots, for example).
        """

        fig, ax = plt.subplots()

        ax.set_title(f"{self.meta['measurement']}: {self.meta['field']}")
        ax.set_ylabel(self.units if self.units != "" else "Arbitrary Units")
        ax.set_xlabel("Time (s)")
        ax.plot(self.datetime_x_axis, self, label=self.meta['field'])

        if show:
            plt.show()

    def index_of(self, time: float) -> int:
        """
        Return the index of the data element that represents the time closest to ``time``.

        :param float time: time (in seconds) that will be evaluated against
        :raises: ValueError if ``time`` falls outside of x–axis
        """
        if not (0.0 <= time <= self.length):
            raise ValueError(f"Relative time {time} falls outside of x–axis! {self.length}")

        return np.argmin(np.abs(self.x_axis - time))

    def relative_time(self, unix_time: float) -> float:
        """
        Return the relative time of the UNIX timestamp ``time``.
        :param float unix_time: UNIX timestamp that will be converted
        """
        if not (self.start.timestamp() <= unix_time <= self.stop.timestamp()):
            raise ValueError(f"UNIX time {unix_time} falls outside of x–axis, which is {self.start.timestamp()}–{self.stop.timestamp()}!")

        return unix_time - self.start.timestamp()

    def promote(self, array: np.ndarray):
        """
        Promote a plain ndarray, ``array``, to a TimeSeries with the same properties
        as this TimeSeries.

        This method is particularly useful for interfacing
        with libraries such as SciPy and NumPy, which will return an ndarray even when
        given a TimeSeries.

        :param array: plain ndarray to be promoted
        :return: new, promoted TimeSeries with the same properties as this TimeSeries
        """
        meta: dict = self.meta

        return TimeSeries(array, 
                          self.start, 
                          self.stop,  
                          self.period, 
                          self.length, 
                          self.units,
                          meta)
    
    def interpolate_indices(self, i: float) -> float:
        """
        Takes in a float which represents a value between indices and iterpolates those indices to return an interpolated value
        """
        i1 = math.floor(i)
        i2 = math.ceil(i)

        inter = i - i1

        value1 = self[i1]
        value2 = self[i2]

        return value1*(1-inter) + value2*inter
    
    def slice_datetime(self, start_time: datetime.datetime, end_time: datetime.datetime):
        """
        Returns all values in a time series between the requested start and end time.
        
        The output has the same period and the function does not generate any new values
        """

        if (start_time.tzinfo is None) or (end_time.tzinfo is None): # Throw error if start or stop time is naive
            raise ValueError(f"The start or end time does not have an assigned timezone!")

        if (end_time < start_time): # Throw error if the end time is before stop time
            raise ValueError(f"Start time {start_time} is after stop time {end_time}!")
        
        if (end_time < self.start):
            raise ValueError(f"Slice ends before timeseries starts!")
        
        if (start_time > self.stop):
            raise ValueError(f"Slice starts after timeseries ends!")

        dt = self.stop - self.start

        # Values used for indexxing
        relative_start = start_time - self.start
        relative_stop = end_time - self.start

        if (relative_start < datetime.timedelta(0)):
            relative_start = datetime.timedelta(0)

        if (relative_stop > dt):
            relative_stop = dt

        # Finding indexes to slice with
        start_index = math.ceil((relative_start/self.period).total_seconds()) 
        stop_index = math.floor((relative_stop/self.period).total_seconds())

        # Find new start and end time
        new_start_time = datetime.timedelta(seconds = start_index * self.period) + self.start
        new_stop_time = datetime.timedelta(seconds = stop_index * self.period) + self.start

        new_series: TimeSeries = []
        y_data = []
        for i in range(start_index, stop_index + 1):
            y_data.append(self[i])
        
        if self.start.tzinfo is not None:
            new_start_time = new_start_time.replace(tzinfo = self.start.tzinfo)
            new_stop_time = new_stop_time.replace(tzinfo = self.stop.tzinfo)

        new_series = TimeSeries(y_data, 
                                new_start_time,
                                new_stop_time,
                                self._period,
                                length = (new_stop_time - new_start_time).total_seconds(),
                                units = self.units)
        return new_series
    
    def shift(self, milliseconds):
        return 0

    @staticmethod
    def align(*args) -> list:
        start_time = max(arg.start.timestamp() for arg in args)
        end_time = min(arg.stop.timestamp() for arg in args)
        period = min(arg.period for arg in args)

        new_length = end_time - start_time
        num_points = math.ceil(new_length / period) + 1
        new_x_axis = np.linspace(start_time, end_time, num_points)

        new_args = []
        for array in args:
            start_index = array.index_of(array.relative_time(start_time))
            stop_index = array.index_of(array.relative_time(end_time))

            new_array: TimeSeries = array[start_index:stop_index + 1]
            if array.start.tzinfo is not None:
                tz = array.start.tzinfo
                new_array._start = datetime.datetime.fromtimestamp(start_time, tz)
                new_array._stop = datetime.datetime.fromtimestamp(end_time, tz)
            else:
                new_array._start = datetime.datetime.fromtimestamp(start_time)
                new_array._stop = datetime.datetime.fromtimestamp(end_time)

            new_array._period = period
            new_array._length = new_length

            interpolated_values = np.interp(new_x_axis, new_array.unix_x_axis, new_array)
            new_array_interpolated = new_array.promote(interpolated_values)

            new_args.append(new_array_interpolated)

        return new_args

    @staticmethod
    def from_query_dataframe(query_df: pd.DataFrame, granularity: float, field: str, units: str):
        # Transform the DataFrame into a nicer format where we have our time-series data indexed by time
        query_df['_time'] = pd.to_datetime(query_df['_time'])
        query_df.set_index('_time', inplace=True)

        # Get the x-axis in relative seconds (first element is t=0)
        x_axis = query_df.index.map(lambda x: x.timestamp()).to_numpy()
        x_axis -= x_axis[0]  # Subtract off first time, so the x_axis starts at 0 with units of seconds

        # Reshape the x-axis to have the right number of elements for our needed granularity
        temporal_length: float = x_axis[-1]  # Total time of the query in seconds
        desired_num_elements: int = math.ceil(temporal_length / granularity)
        desired_x_axis = np.linspace(0, temporal_length, desired_num_elements, endpoint=True)

        # Re-interpolate our data on desired x-axis
        wave = query_df[[field]].to_numpy().reshape(-1)
        wave_interpolated = np.interp(desired_x_axis, x_axis, wave)

        actual_granularity = np.mean(np.diff(desired_x_axis))

        # Compile metadata
        meta: dict = {
            "start": query_df.index.to_numpy()[0].to_pydatetime(),
            "stop": query_df.index.to_numpy()[-1].to_pydatetime(),
            "car": query_df["car"].to_numpy()[0],
            "measurement": query_df["_measurement"].to_numpy()[0],
            "field": field,
            "period": actual_granularity,
            "length": temporal_length,
            "units": units,
        }

        new_wave = TimeSeries(wave_interpolated, meta)

        return new_wave

    @staticmethod
    def from_csv(path, granularity, field):
        df = pd.read_csv(path)

        fields = df['_field'].unique()
        assert len(fields) == 1, "more than one field type in table"
        tuple_arr = np.stack((pd.to_datetime(df['_time']), df['_value']), axis=1)
        result = np.fromiter(map(lambda x: re.sub("[^0-9|.]", "", x), tuple_arr[:, 1]), dtype=float)

        return result
