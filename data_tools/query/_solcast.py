import os
from enum import Enum, StrEnum
from solcast import forecast, live
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime, UTC
import numpy as np
from numpy.typing import NDArray
from data_tools.utils import ensure_utc
from typing import Optional
from math import ceil


load_dotenv()


# Class to represent the temporal granularity of Solcast Radiation and Weather API
class SolcastPeriod(StrEnum):
    PT5M = "PT5M"
    PT10M = "PT10M"
    PT15M = "PT15M"
    PT20M = "PT20M"
    PT30M = "PT30M"
    PT60M = "PT60M"

    def as_frequency(self) -> int:
        match self:
            case SolcastPeriod.PT5M: return 12
            case SolcastPeriod.PT10M: return 6
            case SolcastPeriod.PT15M: return 4
            case SolcastPeriod.PT20M: return 3
            case SolcastPeriod.PT30M: return 2
            case SolcastPeriod.PT60M: return 1


class SolcastOutput(StrEnum):
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
    def __init__(self, api_key: str = None):
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
    def _parse_num_hours(start_time: datetime, end_time: datetime) -> tuple[int, int]:
        start_time_utc = ensure_utc(start_time)
        end_time_utc = ensure_utc(end_time)

        now: datetime.datetime = datetime.now(UTC)

        if not end_time_utc > start_time_utc:
            raise ValueError("End time must be after start time!")

        past_diff = now - start_time_utc
        num_past_seconds = past_diff.total_seconds()
        num_past_hours = SolcastClient._round_to_hour(num_past_seconds)

        if num_past_hours > 24 * 7:
            raise ValueError("Cannot query weather further than 7 days into the past!")

        future_diff = end_time_utc - now
        num_future_seconds = future_diff.total_seconds()
        num_future_hours = SolcastClient._round_to_hour(num_future_seconds)

        if num_past_hours > 24 * 14:
            raise ValueError("Cannot query weather further than 14 days into the future!")

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

            case _:
                raise RuntimeError(f"An unknown error has been encountered! Additional Exception Details: {exception}")

    def query(
            self,
            latitude: float,
            longitude: float,
            period: SolcastPeriod,
            output_parameters: list[SolcastOutput],
            tilt: float,
            azimuth: float,
            start_time: datetime,
            end_time: datetime,
            return_dataframe: bool = False
    ) -> tuple[NDArray, ...] | pd.DataFrame:
        num_past_hours, num_future_hours = SolcastClient._parse_num_hours(start_time, end_time)

        output_parameter_strings_forecast = list(map(lambda parameter: str(parameter), output_parameters))
        output_parameter_strings_live = filter(
            lambda parameter: parameter not in _FORECAST_ONLY,
            output_parameter_strings_forecast,
        )

        if num_past_hours > 0:
            live_data = live.radiation_and_weather(
                latitude=latitude,
                longitude=longitude,
                output_parameters=list(output_parameter_strings_live),
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
                output_parameters=list(output_parameter_strings_forecast),
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

        if forecast_df is not None and live_df is None:
            weather_df: pd.DataFrame = forecast_df

        if forecast_df is None and live_df is not None:
            weather_df: pd.DataFrame = live_df

        if forecast_df is not None and live_df is not None:
            # We will probably have data from both APIs for the current time,
            # and if that is the case, we want to discard the Forecast and preserve the Live
            # API since it is probably more accurate.
            if live_df.index[-1] == forecast_df.index[0]:
                forecast_df = forecast_df.iloc[1:]

            weather_df: pd.DataFrame = pd.concat([live_df, forecast_df])

        else:
            # The hope is that we don't get here since the response code should be 202 if
            # the query is empty, so it gets caught by `_handle_query_error`, but maybe not!
            raise ValueError("Weather forecast query is empty!")

        weather_df.sort_index(inplace=True)

        if return_dataframe:
            return weather_df

        time: NDArray = np.fromiter(map(lambda timestamp: timestamp.timestamp(), weather_df.index), dtype=float)
        data_arrays: list[NDArray] = [
            weather_df[str(output_parameter)].to_numpy() for output_parameter in output_parameters
        ]

        return time, *data_arrays
