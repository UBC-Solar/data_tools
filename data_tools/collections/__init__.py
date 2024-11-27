"""
===========================================
Collections (:mod:`data_tools.collections`)
===========================================

Time Series Data
===========
.. autosummary::
   :toctree: generated/

   TimeSeries    -- Enhanced `ndarray` with powerful data analysis features

Race Tools
===========
.. autosummary::
   :toctree: generated/

   FSGPDayLaps    -- Data parser and container for FSGP 2024 lap data

"""
from .time_series import TimeSeries
from .fsgp_2024_laps import FSGPDayLaps
from .lap_query import collect_lap_data


__all__ = [
    "TimeSeries",
    "FSGPDayLaps",
    "collect_lap_data"
]
