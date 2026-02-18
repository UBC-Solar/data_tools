from data_tools.localization.versioned_table import VersionedTable
from enum import StrEnum
from datetime import date
import pathlib


class LanguageLocalization:
    _instance: "LanguageLocalization | None" = None

    def __init__(self, localization_table: pathlib.Path):
        self._localization_table = VersionedTable.from_toml_file(
            str(localization_table.absolute())
        )

    @classmethod
    def load(cls, localization_table: pathlib.Path) -> "LanguageLocalization":
        if cls._instance is None:
            cls._instance = cls(localization_table)
        return cls._instance

    @classmethod
    def _get(cls) -> "LanguageLocalization":
        if cls._instance is None:
            raise RuntimeError("LanguageLocalization not loaded. Call LanguageLocalization.load(path) first.")
        return cls._instance

    @classmethod
    def localize(cls, canonical_name: str, current_date: date | str) -> tuple[str, str, str]:
        """
        Return the (field, board, units)
        """
        inst = cls._get()
        name, board, units = inst._localization_table.lookup(canonical_name, current_date)
        return name, board, units


class CanonicalName(StrEnum):
    VehicleSpeed = "VehicleSpeed"
    BatteryVoltage = "BatteryVoltage"
