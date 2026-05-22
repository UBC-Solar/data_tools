from .language_localization import LanguageLocalization as _LanguageLocalization, CanonicalName
from .temporal_localization import TemporalLocalization as _TemporalLocalization
from .spatial_localization import SpatialLocalization as _SpatialLocalization
from .versioned_table import VersionedTable
from .localization import Localization
import pathlib


INFLUXDB_LANGUAGE_LOCALIZATION_TABLE_PATH = pathlib.Path(__file__).parent / "influxdb_language_localization.toml"
if not INFLUXDB_LANGUAGE_LOCALIZATION_TABLE_PATH.exists():
    raise FileNotFoundError(f"Localization file {INFLUXDB_LANGUAGE_LOCALIZATION_TABLE_PATH} not found! "
                            f"A localization file is required to use this module")
else:
    InfluxDBLanguageLocalization = _LanguageLocalization(INFLUXDB_LANGUAGE_LOCALIZATION_TABLE_PATH)

SUNBEAMDB_LANGUAGE_LOCALIZATION_TABLE_PATH = pathlib.Path(__file__).parent / "sunbeamdb_language_localization.toml"
if not SUNBEAMDB_LANGUAGE_LOCALIZATION_TABLE_PATH.exists():
    raise FileNotFoundError(f"Localization file {SUNBEAMDB_LANGUAGE_LOCALIZATION_TABLE_PATH} not found! "
                            f"A localization file is required to use this module")
else:
    SunbeamDBLanguageLocalization = _LanguageLocalization(SUNBEAMDB_LANGUAGE_LOCALIZATION_TABLE_PATH)


TEMPORAL_LOCALIZATION_TABLE_PATH = pathlib.Path(__file__).parent / "temporal_localization.toml"
if not TEMPORAL_LOCALIZATION_TABLE_PATH.exists():
    raise FileNotFoundError(f"Localization file {TEMPORAL_LOCALIZATION_TABLE_PATH} not found! "
                            f"A localization file is required to use this module")
else:
    TemporalLocalization = _TemporalLocalization(TEMPORAL_LOCALIZATION_TABLE_PATH)


SPATIAL_LOCALIZATION_TABLE_PATH = pathlib.Path(__file__).parent / "spatial_localization.toml"
if not SPATIAL_LOCALIZATION_TABLE_PATH.exists():
    raise FileNotFoundError(f"Localization file {SPATIAL_LOCALIZATION_TABLE_PATH} not found! "
                            f"A localization file is required to use this module")
else:
    SpatialLocalization = _SpatialLocalization(SPATIAL_LOCALIZATION_TABLE_PATH)


__all__ = [
    "VersionedTable",
    "Localization",
    "InfluxDBLanguageLocalization",
    "SunbeamDBLanguageLocalization",
    "TemporalLocalization",
    "SpatialLocalization",
    "CanonicalName"
]