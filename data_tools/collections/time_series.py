import numpy as np
import datetime
import matplotlib.pyplot as plt
import math
import pandas as pd
import copy
import warnings
from pint.registry import Unit


from data_tools import unit_registry  # Important so that different TimeSeries don't experience registry errors


class TimeSeries(np.ndarray):
    """
    This class encapsulates time-series data with units, a temporal x–axis, and metadata.

    Data is homogenous and evenly-spaced, such that temporal period between subsequent elements is constant.
    """
    UnitRegistry = unit_registry

    # How far a given ``length`` or ``stop`` may disagree with the one derived from ``period``, in seconds, as
    # the larger of an absolute amount (datetimes only carry microseconds) and a fraction of the period
    _ABS_TOLERANCE = 1e-5
    _REL_TOLERANCE = 1e-3

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
                 units: Unit | str = None,
                 meta: dict = None):
        """
        :param input_array: The evenly-spaced data.
        :param datetime.datetime start_time: Timezone-aware time of the first element.
        :param datetime.datetime stop_time: Optional, timezone-aware time of the last element. Derived from
            ``start_time`` and ``period`` when they are given, so it only needs to be given in their place.
        :param float period: Time between elements in seconds. If not given, it is derived from ``length`` (or
            ``stop_time``) and the number of elements.
        :param float length: Optional, time between the first and last element in seconds. Like ``stop_time``,
            derived from ``period`` when it is given.
        :param str | Unit units: Units of the data, dimensionless if ``None``.
        :param dict meta: Metadata for the TimeSeries.
        :raises ValueError: If ``start_time`` or ``stop_time`` is naive.
        :warns UserWarning: If ``length`` or ``stop_time`` disagrees with ``period``, in which case the length and
            stop are derived from ``period``.
        """
        # Check if the start and stop are not naive
        if start_time is not None:
            if start_time.tzinfo is None:
                raise ValueError("The start time does not have an assigned timezone!")

        if stop_time is not None:
            if stop_time.tzinfo is None:
                raise ValueError("The end time does not have an assigned timezone!")

        num_elements = self._num_elements()
        stop_length = (stop_time - start_time).total_seconds() \
            if start_time is not None and stop_time is not None else None

        # Derive the period from whichever span was given
        if period is None and num_elements > 1:
            span = length if length is not None else stop_length
            if span is not None:
                period = span / (num_elements - 1)

        # Anything else given should agree with the period, which wins: the x–axis is evenly spaced by it
        if period is not None:
            derived_length = period * max(num_elements - 1, 0)
            tolerance = max(TimeSeries._ABS_TOLERANCE, TimeSeries._REL_TOLERANCE * abs(period))
            for name, given in (("length", length), ("stop_time", stop_length)):
                if given is not None and abs(given - derived_length) > tolerance:
                    warnings.warn(
                        f"The {name} implies a length of {given} s, but {num_elements} elements with a period of "
                        f"{period} s span {derived_length} s! Using {derived_length} s.",
                        stacklevel=2
                    )

        self._start: datetime.datetime = start_time
        # Only used when there is no period to derive them from
        self._stop: datetime.datetime = stop_time
        self._length: float = length if length is not None else stop_length

        # Setting units
        if units is None:
            self._units = self.ureg.dimensionless
        elif isinstance(units, str): # Eg. "meter/second**2" or "J"
            self._units = self.ureg.parse_units(units)
        elif isinstance(units, Unit):
            self._units = units

        if meta is None:
            self._meta = {}
        else:
            self._meta = meta

        self._period: float = period

    def _num_elements(self) -> int:
        return self.shape[0] if self.ndim > 0 else 1

    @property
    def ureg(self):
        return TimeSeries.UnitRegistry

    def __add__(self, other):
        if isinstance(other, TimeSeries):
            self_aligned, other_aligned = TimeSeries.align(self, other)

            # Check dimensionalilty
            if not self_aligned.units.dimensionality == other_aligned.units.dimensionality:
                raise ValueError(
                    f"Incompatible units: {self_aligned.units} and {other_aligned.units}"
                )

            # Convert other to self's units
            factor = (1 * other_aligned.units).to(self_aligned.units).magnitude # 1 * unit turns it into a quanity rather than pure unit
            converted_other = np.asarray(other_aligned) * factor

            raw_sum = np.ndarray.__add__(self_aligned, converted_other)

            result: TimeSeries = self_aligned.promote(raw_sum)
            result._units = self_aligned.units
            return result
        
        elif isinstance(other, self.ureg.Quantity):
             # Check dimensionalilty
            if not self.units.dimensionality == other.units.dimensionality:
                raise ValueError(
                    f"Incompatible units: {self.units} and {other.units}"
                )

            # Convert other to self's units
            factor = (1 * other.units).to(self.units).magnitude # 1 * unit turns it into a quality rather than pure unit
            converted_other = other.magnitude * factor

            raw_sum = np.ndarray.__add__(self, converted_other)

            result: TimeSeries = self.promote(raw_sum)
            result._units = self.units
            return result
        
        else:
            raw_sum = np.ndarray.__add__(self, other) # Assumption being that the added value is the same unit as the TimeSeries
            result = self.promote(raw_sum)
            result._units = self.units
            return result
    
    def __sub__(self, other):
        if isinstance(other, TimeSeries):
            # Align time series
            self_aligned, other_aligned = TimeSeries.align(self, other)

            # Check dimensionality
            if not self_aligned.units.dimensionality == other_aligned.units.dimensionality:
                raise ValueError(
                    f"Incompatible units: {self_aligned.units} and {other_aligned.units}"
                )

            # Convert other to self's units
            factor = (1 * other_aligned.units).to(self_aligned.units).magnitude #  1 * unit turns it into a quality rather than pure unit
            converted_other = np.asarray(other_aligned) * factor

            # Perform subtraction
            raw_sub = np.ndarray.__sub__(self_aligned, converted_other)

            result = self_aligned.promote(raw_sub)
            result._units = self_aligned.units
            return result
        
        elif isinstance(other, self.ureg.Quantity):
            
             # Check dimensionality
            if not self.units.dimensionality == other.units.dimensionality:
                raise ValueError(
                    f"Incompatible units: {self.units} and {other.units}"
                )

            # Convert other to self's units
            factor = (1 * other.units).to(self.units).magnitude # 1 * unit turns it into a quality rather than pure unit
            converted_other = other.magnitude * factor

            raw_sum = np.ndarray.__sub__(self, converted_other)

            result: TimeSeries = self.promote(raw_sum)
            result._units = self.units
            return result
        
        else:
            # Scalar subtraction, assuming other is in the same units
            raw_sub = np.ndarray.__sub__(self, other)
            result = self.promote(raw_sub)
            result._units = self.units
            return result 

    def __mul__(self, other):

        if isinstance(other, TimeSeries): # If TimeSeries
            self_aligned, other_aligned = TimeSeries.align(self, other)

            raw_product = np.ndarray.__mul__(self_aligned, other_aligned)

            result = self_aligned.promote(raw_product)

            # Compose units
            result._units = self_aligned.units * other_aligned.units

            return result
        
        elif isinstance(other, self.ureg.Quantity): # If Pint Quantity
            raw_product = np.ndarray.__mul__(self, other.magnitude)

            result = self.promote(raw_product)

            result._units = self.units * other.units

            return result

        else:
            raw_product = np.ndarray.__mul__(self, other)

            result = self.promote(raw_product)
            result._units = self.units
            return result

    def __truediv__(self, other):
        if isinstance(other, TimeSeries):
            self_aligned, other_aligned = TimeSeries.align(self, other)

            raw_product = np.ndarray.__truediv__(self_aligned, other_aligned)

            result = self_aligned.promote(raw_product)

            # Compose units
            result._units = self_aligned.units / other_aligned.units

            return result
        
        elif isinstance(other, self.ureg.Quantity):

            raw_product = np.ndarray.__truediv__(self, other.magnitude)

            result = self.promote(raw_product)

            # Compose units
            result._units = self.units/other.units

            return result

        else:
            raw_product = np.ndarray.__truediv__(self, other)

            result = self.promote(raw_product)
            result._units = self.units
            return result
        
    def __radd__(self, other):
        return self.__add__(other)

    def __rmul__(self, other):
        return self.__mul__(other)
    
    def __rsub__(self, other):
        # This might not be the wanted implementation, but its also really unintuitive to subtract a time series from an integer so I dont know what the desired output is
        raw_sub =  np.ndarray.__sub__(self, other) # other - self = -(self - other)
        result = -1 * self.promote(raw_sub)
        
        # Units for scalar - TimeSeries are typically -self.units
        result._units = self.units # Magnitude is negative, units remain same
            
        return result
    
    def __rtruediv__(self, other):
        # reverses the division: other / self
        # This logic only triggers when the numerator is not a TimeSeries, meaning in this case it is only ever a unitless other (float or integer). 
        # Currently there is no implementation of multiplying or dividing by pint quantities    

        raw_product = np.ndarray.__rtruediv__(self, other)
        result = self.promote(raw_product)
        result._units = 1 / self.units 

        return result
            
    @property
    def x_axis(self) -> np.ndarray:
        """
        This wave's x–axis in relative seconds, such that the first element is ``t=0``.
        """
        relative_x_axis = np.linspace(0.0, self.length, len(self))

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
        This wave's x–axis as timezone-aware datetimes.
        """
        tz = self.start.tzinfo
        return pd.to_datetime(self.unix_x_axis, unit='s', utc=True).tz_convert(tz).to_numpy()

    @property
    def length(self) -> float:
        """
        Total time between the first and last element of this wave's data
        """
        if self._period is None:
            return self._length

        return self._period * max(self._num_elements() - 1, 0)

    @property
    def period(self) -> float:
        """
        Get the period, in seconds, between data points of this TimeSeries.

        :return: period, in seconds.
        """
        return self._period

    @property
    def units(self) -> Unit:
        """
        The units of this wave's data
        """
        return self._units

    def override_units(self, new_unit: Unit | str):
        """ Overrides the units of a TimeSeries, directly changes one unit for another. Does not convert magnitudes! 
        If you wish to convert units, use .convert_to()

            :param str new_unit: The unit the entire series will be translated to
            :raises ValueError: Cannot convert TimeSeries without units
        """
        if new_unit is None:
            self._units = self.ureg.dimensionless
        elif isinstance(new_unit, str): # Eg. "meter/second**2" or "J"
            self._units = self.ureg.parse_units(new_unit)
        elif isinstance(new_unit, self.ureg.Unit):
            self._units = new_unit
        else:
            raise ValueError(
                f"Input should be a string or Unit object, not {type(new_unit)}!"
            )

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
        length = self.length
        if self._start is None or self._period is None or length is None:
            return self._stop

        return self._start + datetime.timedelta(seconds=length)

    def __getitem__(self, item):
        data_to_slice = self

        if isinstance(item, float):
            index = self.index_of(item)
            return super(TimeSeries, data_to_slice).__getitem__(index)

        elif isinstance(item, datetime.datetime):
            num_elements = len(data_to_slice)
            if num_elements == 0:
                raise IndexError("Cannot index an empty TimeSeries by datetime!")

            if item.tzinfo is None:
                raise ValueError("The index does not have an assigned timezone!")

            item_ts = item.timestamp()

            # Same values as unix_x_axis[0] and unix_x_axis[-1], without building the whole axis on every lookup
            start_timestamp: float = self.start.timestamp()
            stop_timestamp: float = start_timestamp + self.length if num_elements > 1 else start_timestamp

            if item_ts > stop_timestamp or item_ts < start_timestamp:
                tz = self.start.tzinfo
                raise IndexError(
                    f"Datetime {item} is out of bounds! "
                    f"Range: [{datetime.datetime.fromtimestamp(start_timestamp, tz)}, "
                    f"{datetime.datetime.fromtimestamp(stop_timestamp, tz)}]"
                )

            dt = stop_timestamp - start_timestamp

            if dt == 0:
                return data_to_slice[0]

            interpolation_index = (item_ts - start_timestamp) * (len(data_to_slice) - 1)/dt

            return data_to_slice.interpolate_indices(interpolation_index)

        result = super(TimeSeries, data_to_slice).__getitem__(item)

        # A forward slice is still evenly spaced: move its x–axis to the elements it kept
        if isinstance(item, slice) and isinstance(result, TimeSeries) and self.ndim == 1:
            kept = range(len(self))[item]
            if kept.step > 0 and len(kept) > 0 and self._start is not None and self._period is not None:
                result._start = self._start + datetime.timedelta(seconds=kept.start * self._period)
                result._period = self._period * kept.step

        return result

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

        meta = self.meta or {}

        # InfluxDB series name a measurement and field; Sunbeam series an event and signal
        name = meta.get("field", meta.get("signal"))
        group = meta.get("measurement", meta.get("event"))

        fig, ax = plt.subplots()

        ax.set_title(f"{group}: {name}" if group is not None else (name or ""))
        dimensionless = self.units is None or self.units == self.ureg.dimensionless
        ax.set_ylabel("Arbitrary Units" if dimensionless else str(self.units))
        ax.set_xlabel("Time")
        ax.plot(self.datetime_x_axis, np.asarray(self), label=name)

        if show:
            plt.show()

    def index_of(self, time: float) -> int:
        """
        Return the index of the data element that represents the time closest to ``time``.

        :param float time: time (in seconds) that will be evaluated against
        :raises: ValueError if ``time`` falls outside of x–axis
        """
        if not (0.0 <= time <= self.length):
            raise ValueError(f"Relative time {time} falls outside of x–axis!")

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
        as this TimeSeries (start_time, stop_time, period, length, units, meta)

        This method is particularly useful for interfacing
        with libraries such as SciPy and NumPy, which will return an ndarray even when
        given a TimeSeries.

        :param array: plain ndarray to be promoted
        :return: new, promoted TimeSeries with the same properties as this TimeSeries
        """
        # A copy, so that changing one TimeSeries' metadata doesn't change the other's
        meta: dict = copy.copy(self.meta)

        # With a period, the stop and length follow from it (and the length of ``array``)
        unspaced = self.period is None

        return TimeSeries(
            array,
            self.start,
            stop_time=self.stop if unspaced else None,
            period=self.period,
            length=self.length if unspaced else None,
            units=self.units,
            meta=meta
        )
    
    def interpolate_indices(self, i: float) -> float:
        """ Function which interpolates between the two nearest indices

        :param float i: floating index

        :return float: interpolated value
        """
        i1 = math.floor(i)
        i2 = math.ceil(i)

        inter = i - i1

        value1 = self[i1]
        value2 = self[i2]

        return value1*(1-inter) + value2*inter
    
    def slice(self, start_time: datetime.datetime, end_time: datetime.datetime):
        """ This function returns all values between two given points, useful for filtering out data for specific dates or times. 
        The returned series will not have the argument start_time and end_time, instead the returned series will align the start and end time to existing points

        :param datetime.datetime start_time: The start datetime to slice with
        :param datetime.datetime end_time: The end datetime to slice with

        :raises ValueError: Naive inputs (Inputs do not have assigned timezones)
        :raises ValueError: start_time is after stop_time
        :raises ValueError: stop_time is before TimeSeries start time
        :raises ValueError: start_time is after TimeSeries stop time

        :return TimeSeries: Returns a series with all values between start and stop time
        """

        if (start_time.tzinfo is None) or (end_time.tzinfo is None): # Throw error if start or stop time is naive
            raise ValueError("The start or end time does not have an assigned timezone!")

        if end_time < start_time: # Throw error if the end time is before stop time
            raise ValueError(f"Start time {start_time} is after stop time {end_time}!")
        
        if end_time < self.start:
            raise ValueError("Slice ends before TimeSeries starts!")
        
        if start_time > self.stop:
            raise ValueError("Slice starts after TimeSeries ends!")

        dt = self.stop - self.start

        # Values used for indexing
        relative_start = start_time - self.start
        relative_stop = end_time - self.start

        if relative_start < datetime.timedelta(0):
            relative_start = datetime.timedelta(0)

        if relative_stop > dt:
            relative_stop = dt

        # Finding indexes to slice with
        start_index = math.ceil((relative_start / self.period).total_seconds())
        stop_index = min(math.floor((relative_stop / self.period).total_seconds()), len(self) - 1)

        new_series = TimeSeries(
            np.array(self)[start_index:stop_index + 1],
            self.start + datetime.timedelta(seconds = start_index * self.period),
            period = self.period,
            units = self.units,
            meta = copy.copy(self.meta)
        )

        return new_series
    
    def shift(self, shift: float | datetime.timedelta):
        """A function which moves a TimeSeries backwards or forwards in time without changing any data inside it. Can have timedelta or a float as an input

        :param float | datetime.timedelta shift: The amount of seconds the series should be shifted
        :return TimeSeries: Shifted timeseries
        """        
        if not isinstance(shift, datetime.timedelta):
            shift = datetime.timedelta(seconds=shift)

        # A copy of the data, so that changing the shifted series doesn't change this one
        timeseries_copy = self.promote(np.array(self))
        timeseries_copy._start = self.start + shift
        if timeseries_copy._stop is not None:
            timeseries_copy._stop = timeseries_copy._stop + shift

        return timeseries_copy

    def convert_to(self, new_unit: Unit | str):
        """ Returns a new TimeSeries after being converted to a new unit, appropriately scales TimeSeries

            :param str new_unit: The unit the entire series will be translated to

            :raises ValueError: Cannot convert TimeSeries without units
            :raises ValueError: Unable to convert between units of different dimensionality

            :return: TimeSeries with converted units
        """

        new_unit_parsed = self.ureg.parse_units(new_unit)
        # Check dimensionality
        if self.units.dimensionality != new_unit_parsed.dimensionality:
            raise ValueError(
                f"Cannot convert {self.units} to {new_unit_parsed} (incompatible dimensions)"
            )

        factor = (1 * self.units).to(new_unit_parsed).magnitude # 1 * unit turns it into a quality rather than pure unit

        converted_values = np.asarray(self) * factor

        result = self.promote(converted_values)
        result._units = new_unit_parsed

        return result

    def convert_to_base_units(self):
        """
        Converts TimeSeries units to the unit registry system base units (SI Units by default)

        :return TimeSeries: Timeseries with converted units
        """
        # Find base units
        new_unit = (1 * self.units).to_base_units().units

        # Multiply by a factor
        factor = (1 * self.units).to(new_unit).magnitude # 1 * unit turns it into a quality rather than pure unit
        converted_values = np.asarray(self) * factor

        # Construct new TimeSeries
        result = self.promote(converted_values)

        result._units = new_unit

        return result

    @staticmethod
    def align(*args) -> list:
        """
        Re-interpolate TimeSeries onto a shared x–axis: the time range they all cover, with the finest of their
        periods (rounded down to divide the range evenly).

        :raises ValueError: If the TimeSeries don't all overlap in time.
        :return: The aligned TimeSeries, in the order given.
        """
        start_time = max(arg.start.timestamp() for arg in args)
        end_time = min(arg.stop.timestamp() for arg in args)
        period = min(arg.period for arg in args)

        new_length = end_time - start_time
        if new_length < 0:
            raise ValueError("Cannot align TimeSeries that don't overlap in time!")

        # As in generate_timeseries, spans within a thousandth of a period of a whole number of periods are that number
        num_points = math.ceil(new_length / period - 1e-3) + 1
        new_x_axis = np.linspace(start_time, end_time, num_points)
        new_period = new_length / (num_points - 1) if num_points > 1 else period

        new_args = []
        for array in args:
            # Interpolate from each series' own x–axis, so its samples keep their true times
            interpolated_values = np.interp(new_x_axis, array.unix_x_axis, np.asarray(array))

            new_args.append(
                TimeSeries(
                    interpolated_values,
                    datetime.datetime.fromtimestamp(start_time, array.start.tzinfo),
                    period=new_period,
                    units=array.units,
                    meta=copy.copy(array.meta)
                )
            )

        return new_args

    @staticmethod
    def merge(*args, fill_value: float = 0):
        """The merge function combines several TimeSeries into one contiguous series. Any spaces in time is filled by the 'fill_value'. 
        It assumes that the datapoints pull from the same source, as overlapping point are overridden.

        :param float fill_value: The value for filling between gaps of time. Defaults to 0.

        :raises ValueError: If no TimeSeries are input

        :return TimeSeries: The merged series
        """        
        
        if len(args) == 0:
            raise ValueError("At least one TimeSeries is required")

        # Series properties
        start_time = min(ts.start.timestamp() for ts in args)
        end_time = max(ts.stop.timestamp() for ts in args)
        period = min(ts.period for ts in args)  # highest resolution

        new_length = end_time - start_time
        num_points = math.ceil(new_length / period - 1e-3) + 1

        merged_values = np.full(num_points, fill_value, dtype=float)

        # Use metadata from the first series
        base = args[0]
        units = base.units
        meta = copy.deepcopy(base.meta)

        # Merge TimeSeries loop
        for ts in args:

            # Convert to common units and check dimensionality
            if ts.units != units:
                if ts.units.dimensionality == units.dimensionality:
                    ts = ts.convert_to(str(units))
                else:
                    raise ValueError("One of the TimeSeries is not in the same units of dimensionality")

            ts_times = ts.unix_x_axis
            ts_values = np.asarray(ts)

            # Map ts indices into the whole space
            indices = np.round((ts_times - start_time) / period).astype(int)

            # Clamp indices (safety)
            valid = (indices >= 0) & (indices < num_points)
            indices = indices[valid]
            ts_values = ts_values[valid]

            # Overwrite values in the merged series
            merged_values[indices] = ts_values

        # Create final series
        # Values were placed every ``period`` from the start, which fixes the stop (it may pass end_time by less
        # than a period)
        merged_series = TimeSeries(
            merged_values,
            start_time=datetime.datetime.fromtimestamp(start_time, base.start.tzinfo),
            period=period,
            units=units,
            meta=meta
        )

        return merged_series
    
    @staticmethod
    def from_query_dataframe(query_df: pd.DataFrame, period: float, field: str, units: Unit | str):
        """
        Create a TimeSeries from the DataFrame of an InfluxDB query for one field, re-interpolated onto an even grid
        of ``period`` seconds. ``query_df`` is not modified.

        :param pd.DataFrame query_df: Query result, with ``_time``, ``car``, ``_measurement`` and ``field`` columns.
        :param float period: Time between elements of the result, in seconds.
        :param str field: The column holding the data.
        :param str | Unit units: Units of the data.
        :return: Homogenized TimeSeries, in the timezone of ``_time`` (UTC if it has none).
        """
        times = pd.DatetimeIndex(pd.to_datetime(query_df['_time']))
        x_axis = np.array([t.timestamp() for t in times], dtype=float)

        meta: dict = {
            "car": query_df["car"].to_numpy()[0],
            "measurement": query_df["_measurement"].to_numpy()[0],
            "field": field
        }

        return TimeSeries.generate_timeseries(x_axis,
                                              query_df[field].to_numpy(),
                                              period,
                                              units,
                                              timezone=times.tz or datetime.timezone.utc,
                                              meta=meta)

    @staticmethod
    def from_samples(timestamps,
                     values,
                     period: float,
                     units: Unit | str = None,
                     meta: dict = None) -> "TimeSeries":
        """
        Create a TimeSeries from timestamped samples, re-interpolated onto an even grid of ``period`` seconds.
        Missing values (``None`` or NaN) are dropped first, so they are interpolated across rather than kept.

        :param timestamps: Sample times, ascending: UTC UNIX timestamps in seconds, or timezone-aware datetimes.
        :param values: The sample at each timestamp.
        :param float period: Time between elements of the result, in seconds.
        :param str | Unit units: Units of the data, dimensionless if ``None``.
        :param dict meta: Metadata for the TimeSeries.
        :raises ValueError: If there are no (non-missing) samples, ``timestamps`` and ``values`` differ in length,
            a datetime is naive, or ``period`` isn't positive.
        :return: Homogenized TimeSeries, with timezone-aware UTC start and stop times.
        """
        if len(timestamps) != len(values):
            raise ValueError(f"Got {len(timestamps)} timestamps but {len(values)} values!")

        def to_unix(t) -> float:
            if isinstance(t, datetime.datetime):
                if t.tzinfo is None:
                    raise ValueError(f"Timestamp {t} does not have an assigned timezone!")
                return t.timestamp()
            if isinstance(t, np.datetime64):  # Timezone-naive by design, and UTC by convention
                return float((t - np.datetime64(0, "s")) / np.timedelta64(1, "s"))
            return float(t)

        times = np.array([to_unix(t) for t in timestamps], dtype=float)
        data = np.array([np.nan if v is None else v for v in values], dtype=float)

        present = ~np.isnan(data)
        if not present.any():
            raise ValueError("Cannot create a TimeSeries without any samples!")

        return TimeSeries.generate_timeseries(times[present], data[present], period, units, meta=meta)

    @staticmethod
    def generate_timeseries(x_axis: list,
                            y_axis: list, 
                            period: float, 
                            units: Unit | str, 
                            timezone: datetime.timezone = datetime.timezone.utc, 
                            meta: dict = None):
        """
        Creates a TimeSeries from a non-homogeneous / not evenly spaces set of data with a specified period. Useful for converting weirder data into a neat TimeSeries.

        :param list x_axis: Data point times, as ascending UNIX timestamps in seconds
        :param list y_axis: Data points
        :param float period: Time between data points in seconds
        :param str | Unit units: Units of the TimeSeries
        :param datetime.timezone timezone: Timezone
        :param dict meta: Metadata for the TimeSeries

        :raises ValueError: If ``period`` isn't positive.
        :return: Homogenized TimeSeries

        """
        if not period > 0:
            raise ValueError(f"Period must be positive, not {period}!")

        if meta is None:
            meta = {}

        # Get the x-axis in relative seconds (first element is t=0)
        x_axis = np.asarray(x_axis, dtype=float)
        rel_x_axis = x_axis - x_axis[0]

        # Reshape the x-axis to have the right number of elements for needed period. Spans within a thousandth of a
        # period of a whole number of periods are that number: UNIX timestamps only carry ~0.2 us of precision, which
        # would otherwise add an extra element (0.2 s / 0.1 s -> 2.000002)
        temporal_length: float = rel_x_axis[-1]  # Total time of the query in seconds
        desired_num_elements: int = math.ceil(temporal_length / period - 1e-3)
        desired_x_axis = np.linspace(0, temporal_length, desired_num_elements + 1, endpoint=True)

        # Re-interpolate our data on x-axis
        wave = np.array(y_axis, dtype=float).reshape(-1)
        wave_interpolated = np.interp(desired_x_axis, rel_x_axis, wave)

        # A single data point spans no time, so its x-axis has no spacing to measure
        actual_granularity = float(np.mean(np.diff(desired_x_axis))) if desired_num_elements > 0 else period

        start_time = datetime.datetime.fromtimestamp(x_axis[0], tz=timezone)

        new_wave = TimeSeries(wave_interpolated,
                              start_time = start_time,
                              period = actual_granularity,
                              units = units,
                              meta = meta)

        return new_wave

    @staticmethod
    def from_csv(path, period: float, field: str = None, units: Unit | str = None) -> "TimeSeries":
        """
        Create a TimeSeries from a CSV exported from InfluxDB, with ``_time``, ``_field`` and ``_value`` columns,
        re-interpolated onto an even grid of ``period`` seconds.

        :param path: Path to the CSV.
        :param float period: Time between elements of the result, in seconds.
        :param str field: The field to read. Optional if the CSV only has one.
        :param str | Unit units: Units of the data, dimensionless if ``None``.
        :raises ValueError: If ``field`` isn't given and the CSV has several fields, or it has no rows for the field.
        :return: Homogenized TimeSeries.
        """
        df = pd.read_csv(path)

        if field is None:
            fields = df['_field'].unique()
            if len(fields) != 1:
                raise ValueError(f"The CSV has fields {list(fields)}: choose one with `field`!")
            field = fields[0]

        df = df[df['_field'] == field]
        if df.empty:
            raise ValueError(f"The CSV has no rows for field {field!r}!")

        times = pd.DatetimeIndex(pd.to_datetime(df['_time']))
        order = np.argsort(times.asi8, kind="stable")
        x_axis = np.array([t.timestamp() for t in times], dtype=float)[order]

        # Strip anything around the number (e.g. units), keeping its sign and exponent
        values = pd.to_numeric(
            df['_value'].astype(str).str.replace(r"[^0-9eE.+\-]", "", regex=True)
        ).to_numpy(dtype=float)[order]

        meta = {"field": field}
        if "_measurement" in df.columns:
            meta["measurement"] = df["_measurement"].iloc[0]
        if "car" in df.columns:
            meta["car"] = df["car"].iloc[0]

        return TimeSeries.generate_timeseries(x_axis, values, period, units,
                                              timezone=times.tz or datetime.timezone.utc, meta=meta)
