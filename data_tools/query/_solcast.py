from enum import StrEnum
from typing import Optional
from solcast import forecast, live
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime, UTC, timedelta
import numpy as np
from numpy.typing import NDArray
from data_tools.utils import ensure_utc
from math import ceil
import os


load_dotenv()


class SolcastPeriod(StrEnum):
    """
    Represents the temporal granularity of Solcast Radiation and Weather API
    """
    PT5M = "PT5M"
    PT10M = "PT10M"
    PT15M = "PT15M"
    PT20M = "PT20M"
    PT30M = "PT30M"
    PT60M = "PT60M"

    def as_frequency(self) -> int:
        """
        Return the forecast frequency in hour^(-1) units. 
        """
        match self:
            case SolcastPeriod.PT5M:
                return 12
            case SolcastPeriod.PT10M:
                return 6
            case SolcastPeriod.PT15M:
                return 4
            case SolcastPeriod.PT20M:
                return 3
            case SolcastPeriod.PT30M:
                return 2
            case SolcastPeriod.PT60M:
                return 1

    def to_timedelta(self) -> timedelta:
        """
        Return a `timedelta` object representing the amount of time that
        will be covered by a forecast using this period.
        """
        match self:
            case SolcastPeriod.PT5M:
                return timedelta(minutes=5)
            case SolcastPeriod.PT10M:
                return timedelta(minutes=10)
            case SolcastPeriod.PT15M:
                return timedelta(minutes=15)
            case SolcastPeriod.PT20M:
                return timedelta(minutes=20)
            case SolcastPeriod.PT30M:
                return timedelta(minutes=30)
            case SolcastPeriod.PT60M:
                return timedelta(minutes=60)


class SolcastOutput(StrEnum):
    """
    Discretize the possible outputs that the Solcast Radiation and Weather API may provide
    """
    air_temperature = "air_temp"
    albedo = "albedo"
    azimuth = "azimuth"
    cape = "cape"
    clearsky_dhi = "clearsky_dhi"
    clearsky_dni = "clearsky_dni"
    clearsky_ghi = "clearsky_ghi"
    clearsky_gti = "clearsky_gti"
    cloud_opacity = "cloud_opacity"
    cloud_opacity10 = "cloud_opacity10"
    cloud_opacity90 = "cloud_opacity90"
    dewpoint_temp = "dewpoint_temp"
    dhi = "dhi"
    dhi10 = "dhi10"
    dhi90 = "dhi90"
    dni = "dni"
    dni10 = "dni10"
    dni90 = "dni90"
    ghi = "ghi"
    ghi10 = "ghi10"
    ghi90 = "ghi90"
    gti = "gti"
    gti10 = "gti10"
    gti90 = "gti90"
    precipitable_water = "precipitable_water"
    precipitation_rate = "precipitation_rate"
    relative_humidity = "relative_humidity"
    surface_pressure = "surface_pressure"
    snow_depth = "snow_depth"
    snow_soiling_rooftop = "snow_soiling_rooftop"
    snow_soiling_ground = "snow_soiling_ground"
    snow_water_equivalent = "snow_water_equivalent"
    snowfall_rate = "snowfall_rate"
    wind_direction_100m = "wind_direction_100m"
    wind_direction_10m = "wind_direction_10m"
    wind_gust = "wind_gust"
    wind_speed_100m = "wind_speed_100m"
    wind_speed_10m = "wind_speed_10m"
    zenith = "zenith"


_FORECAST_ONLY = ["dhi10", "dhi90", "dni10", "dni90", "ghi10", "ghi90", "gti10", "gti90"]


class SolcastClient:
    """
    Represents high-level access to the Solcast Radiation and Weather API
    """
    def __init__(self, api_key: str = None):
        """
        Instantiate a client for access to the Solcast API.

        Requires an API key to the Solcast Toolkit.
        `SolcastClient` will try to use environment variable `SOLCAST_API_KEY` if not provided as an argument.

        :param str api_key: A string containing a valid Solcast API key.
        """
        self._api_key = api_key if api_key else os.getenv("SOLCAST_API_KEY")

    @staticmethod
    def _round_to_hour(seconds: int | float) -> int:
        """
        Rounds a time duration (in seconds) to the nearest hour, with custom logic:

        If the total seconds are less than 60, returns 0. Otherwise, it calculates the exact number of hours
        as a float. If the fractional part of the hour is less than 60 seconds (1 minute), it rounds
        down. If the fractional part is 60 seconds or more, it rounds up.
        """
        if seconds < 60:
            return 0

        num_hours_fp: float = seconds / 3600        # Number of hours, exact
        num_hours_int: int = int(seconds // 3600)   # Number of hours, rounded down

        # Difference in length of time between exact and rounded, in seconds
        truncation = (num_hours_fp - num_hours_int) * 3600

        # If the hour is within a minute to the previous hour, round down. Otherwise, round up.
        if truncation < 60:
            return num_hours_int
        else:
            return ceil(num_hours_fp)

    @staticmethod
    def _parse_num_hours(
            start_time_utc: datetime,
            end_time_utc: datetime,
            now: Optional[datetime] = None
    ) -> tuple[int, int]:
        """
        Given `start_time_utc` and `end_time_UTC`, which must be UTC-localized datetimes, determine how many hours
         `start_time_utc` is in the past from the current time, and determine how many hours in the future
        `end_time_UTC` is from the current time.

        :param datetime start_time_utc: UTC-localized start time
        :param datetime end_time_utc: UTC-localized end time
        :param datetime now: UTC-localized current time
        :return: The number of hours in the past and the number of hours in the future, as a 2-tuple in that order
        """
        if now is None:
            now: datetime = datetime.now(UTC)

        if not end_time_utc > start_time_utc:
            raise ValueError("End time must be after start time!")

        past_diff = now - start_time_utc
        num_past_seconds = past_diff.total_seconds()
        num_past_hours = SolcastClient._round_to_hour(num_past_seconds)

        future_diff = end_time_utc - now
        num_future_seconds = future_diff.total_seconds()
        num_future_hours = SolcastClient._round_to_hour(num_future_seconds)

        return num_past_hours, num_future_hours

    @staticmethod
    def _handle_query_error(code: int, exception: str) -> None:
        match code:
            case 202:
                raise ValueError(f"Weather forecast query is empty! Additional Exception Details: {exception}")

            case 400:
                raise TypeError(f"Query contained invalid parameters! Additional Exception Details: {exception}")

            case 401:
                raise ConnectionRefusedError(f"Solcast API key is invalid! Additional Exception Details: {exception}")

            case 402 | 429:
                raise ConnectionRefusedError(f"API request usage limits have been "
                                             f"exceeded! Additional Exception Details: {exception}")

            case 500:
                raise RuntimeError(f"The Solcast server has encountered an error. Additional "
                                   f"Exception Details: {exception}")

            case _:
                raise RuntimeError(f"An unknown error has been encountered! Additional Exception Details: {exception}")

    def query(
            self,
            latitude: float,
            longitude: float,
            period: SolcastPeriod,
            output_parameters: list[SolcastOutput],
            tilt: float,
            start_time: datetime | timedelta,
            end_time: datetime | timedelta,
            azimuth: float = 0,
            return_dataframe: bool = False,
            return_datetime: bool = False,
    ) -> tuple[NDArray, ...] | pd.DataFrame:
        """
        Make a query to the Solcast Radiation and Weather API for a specific coordinate and time range

        Solcast query time ranges are expanded to fit hour boundaries, so a query between 6:13AM and 8:27AM will be
        actually result in a query with forecasts for 6:00AM to 9:00AM.
        Additionally, if the weather averaging period is less than an hour, for example five minutes, the elements
        will go like 6:00AM, 6:05AM, 6:10AM, and such, instead of incrementing from 6:13AM.

        The query will return a tuple of one-dimensional `ndarray`s where each `ndarray` has length `N` where `N` is
        the number of weather averaging periods contained within the hours encompassed by `start_time`
        and `end_time`.

        For example, if a query is between 6:13AM and 10:45AM with a weather averaging period of 10 minutes, there will
        be (5 hours) * (6 forecasts per hour) = 30 elements, as the query will be between 6:00AM and 11:00AM.

        The first `ndarray` contains POSIX timestamps where the “i”th element describes the end of the forecast
        window described by the “i”th element of each of the data `ndarray`s.

        All `ndarray`s after the first are data, and are returned in the order that they were requested in
        `output_parameters`.
        Each datapoint of a data `ndarray` describes that data type for the forecast window.

        For example,

        >>> time, ghi = SolcastClient().query(output_parameters=[SolcastOutput.ghi], period=SolcastPeriod.PT10M, ...)

        And then if time[5] = 9:10AM, then ghi[5] represents the GHI between 9:00AM and 9:10AM.

        Probabilistic data like ghi10 and dti90 are only available for the future and present.
        If you request these
        outputs, any times in the past will be NaN such that `np.isnan()` is `True` for those times.

        If `return_dataframe` is `True`, a Pandas DataFrame will be returned containing the query.
        If `return_datetime` is `True`, the time x-axis will contain datetime objects localized to UTC instead of
        POSIX timestamps.

        :param latitude: The latitude of the queried coordinate.
        :param longitude: The longitude of the queried coordinate.
        :param period: The weather forecast averaging period.
        :param output_parameters: A list of the output parameters that should be queried
        :param tilt: The tilt angle 0–90 in degrees of the solar collector from the horizontal
            where 90 is vertical.
        :param start_time: The time at which weather forecasts should begin.
            It must be in the past and no greater than 7 days in the past.
            It must be timezone-aware.
            Use `None` to denote the current time to ensure expected behaviour.
        :param end_time: The time at which weather forecasts should end.
            It must be in the future and no greater than 14 days in the future.
            It must be after `start_time`.
            It must be timezone-aware.
            Use `None` to denote the current time to ensure expected behaviour.
        :param return_dataframe: Return a Pandas DataFrame instead of tuple of `ndarray`s.
        :param bool return_datetime: Return datetime objects instead of UNIX timestamps in the time x-axis.
        :param azimuth: The azimuth (-180–180, compass direction) in degrees, in which the arrays are
            tilted where 0 is true north.
            Default is 0.
        """
        current_time = datetime.now(UTC)

        if start_time is None:
            start_time = current_time
        if end_time is None:
            end_time = current_time

        if isinstance(start_time, timedelta):
            start_time = current_time + start_time
        if isinstance(end_time, timedelta):
            end_time = current_time + end_time

        start_time_utc = ensure_utc(start_time)
        end_time_utc = ensure_utc(end_time)

        if not 0 <= tilt <= 90:
            raise ValueError("Tilt must be between 0 and 90 degrees!")

        if not end_time_utc > start_time_utc:
            raise ValueError("End time must be after start time!")

        num_past_hours, num_future_hours = SolcastClient._parse_num_hours(start_time_utc, end_time_utc, current_time)

        if num_past_hours > 24 * 7:
            raise ValueError("Cannot query weather further than 7 days into the past!")

        if num_future_hours > 24 * 14:
            raise ValueError("Cannot query weather further than 14 days into the future!")

        output_parameter_strings_forecast = [str(parameter) for parameter in output_parameters]
        output_parameter_strings_live = [
            parameter for parameter in output_parameter_strings_forecast if parameter not in _FORECAST_ONLY
        ]

        if num_past_hours > 0:
            live_data = live.radiation_and_weather(
                latitude=latitude,
                longitude=longitude,
                output_parameters=output_parameter_strings_live,
                hours=num_past_hours,
                tilt=tilt,
                azimuth=azimuth,
                period=str(period),
                api_key=self._api_key
            )

            if live_data.code != 200:
                SolcastClient._handle_query_error(live_data.code, live_data.exception)

            live_df = live_data.to_pandas()
            live_df.sort_index(inplace=True)

        else:
            live_df = None

        if num_future_hours > 0:
            forecast_data = forecast.radiation_and_weather(
                latitude=latitude,
                longitude=longitude,
                output_parameters=output_parameter_strings_forecast,
                hours=num_future_hours,
                tilt=tilt,
                azimuth=azimuth,
                period=str(period),
                api_key=self._api_key
            )

            if forecast_data.code != 200:
                SolcastClient._handle_query_error(forecast_data.code, forecast_data.exception)

            forecast_df = forecast_data.to_pandas()
            forecast_df.sort_index(inplace=True)

        else:
            forecast_df = None

        # We need to build a unified `weather_df` dataset.
        # If we only have `live_df`, use that.
        # If we only have `forecast_df`, then we just use that.
        # Otherwise, we need to combine them.

        if forecast_df is not None and live_df is None:
            weather_df: pd.DataFrame = forecast_df

        elif forecast_df is None and live_df is not None:
            weather_df: pd.DataFrame = live_df

        elif forecast_df is not None and live_df is not None:
            # We will probably have data from both APIs for the current time,
            # and if that is the case, we want to discard the Live and preserve the Forecast
            # API since we may want probabilistic data for the present.
            if live_df.index[-1] == forecast_df.index[0]:
                live_df = live_df.iloc[1:]

            weather_df: pd.DataFrame = pd.concat([live_df, forecast_df])

        else:
            # The hope is that we don't get here since the response code should be 202 if
            # the query is empty, so it gets caught by `_handle_query_error`, but maybe not!
            raise ValueError("Weather forecast query is empty!")

        weather_df.sort_index(inplace=True)

        index = weather_df.index                      # The index values are the END of the forecast period
        index_begin = index - period.to_timedelta()   # Now, we have the BEGINNING of the period

        # Disregard rows that are before the start time or after the end time
        weather_df = weather_df[(index >= start_time) & (index_begin <= end_time)]

        if return_dataframe:
            return weather_df

        # If we want to return datetimes, parse pandas.Timestamp to datetime, otherwise parse into POSIX timestamp
        def time_parser(timestamp: pd.Timestamp) -> float | datetime:
            return timestamp.timestamp() if not return_datetime else timestamp.to_pydatetime()

        time_axis: NDArray = np.fromiter(map(time_parser, weather_df.index), dtype=float)
        data_arrays: list[NDArray] = [
            weather_df[str(output_parameter)].to_numpy() for output_parameter in output_parameters
        ]

        return time_axis, *data_arrays
