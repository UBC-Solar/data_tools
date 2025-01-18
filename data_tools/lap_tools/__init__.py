"""
===========================================
Collections (:mod:`data_tools.lap_tools`)
===========================================

Race Data Tools
===========
.. autosummary::
   :toctree: generated/

   FSGPDayLaps    -- Data parser and container for FSGP 2024 lap data

.. autosummary::
   :toctree: generated/

   collect_lap_data    -- Collects data over each lap using FSGP 2024 timestamps

"""


from .fsgp_2024_laps import FSGPDayLaps
from .lap_query import collect_lap_data


__all__ = [
    "FSGPDayLaps",
    "collect_lap_data"
]
