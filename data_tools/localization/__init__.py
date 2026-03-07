import pathlib

from .versioned_table import VersionedTable
from .language_localization import LanguageLocalization, CanonicalName

LOCALIZATION_TABLE_PATH = pathlib.Path(__file__).parent / "language_localization.toml"
if not LOCALIZATION_TABLE_PATH.exists():
    raise FileNotFoundError(f"Localization file {LOCALIZATION_TABLE_PATH} not found! "
                            f"A localization file is required to use this module")
else:
    LanguageLocalization.load(LOCALIZATION_TABLE_PATH)


__all__ = [
    "VersionedTable",
    "LanguageLocalization",
    "CanonicalName",
    "LOCALIZATION_TABLE_PATH"
]