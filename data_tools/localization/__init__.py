from .language_localization import LanguageLocalization, CanonicalName
from .temporal_localization import TemporalLocalization
from .versioned_table import VersionedTable
from .localization import Localization
import pathlib


LANGUAGE_LOCALIZATION_TABLE_PATH = pathlib.Path(__file__).parent / "language_localization.toml"
if not LANGUAGE_LOCALIZATION_TABLE_PATH.exists():
    raise FileNotFoundError(f"Localization file {LANGUAGE_LOCALIZATION_TABLE_PATH} not found! "
                            f"A localization file is required to use this module")
else:
    LanguageLocalization.load(LANGUAGE_LOCALIZATION_TABLE_PATH)


TEMPORAL_LOCALIZATION_TABLE_PATH = pathlib.Path(__file__).parent / "temporal_localization.toml"
if not TEMPORAL_LOCALIZATION_TABLE_PATH.exists():
    raise FileNotFoundError(f"Localization file {TEMPORAL_LOCALIZATION_TABLE_PATH} not found! "
                            f"A localization file is required to use this module")
else:
    TemporalLocalization.load(TEMPORAL_LOCALIZATION_TABLE_PATH)


__all__ = [
    "VersionedTable",
    "Localization",
    "LanguageLocalization",
    "CanonicalName"
]