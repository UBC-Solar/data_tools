from data_tools.localization.versioned_table import VersionedTable
from enum import StrEnum
from datetime import date
import pathlib


class LanguageLocalization:
    _instance: "LanguageLocalization | None" = None

    def __init__(self, localization_table: pathlib.Path):
        self._localization_table = VersionedTable.from_toml_file(str(localization_table.absolute()))

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
    PackVoltage = "PackVoltage"
    PackCurrent = "PackCurrent"
    MotorCurrent = "MotorCurrent"
    AcceleratorPosition = "AcceleratorPosition"
    VoltageOfLeast = "VoltageOfLeast"
    VoltageOfHighest = "VoltageOfHighest"
    BrakePressed = "BrakePressed"

    MPPTOutputVoltageA = "MPPTOutputVoltageA"
    MPPTOutputVoltageB = "MPPTOutputVoltageB"
    MPPTOutputVoltageC = "MPPTOutputVoltageC"
    MPPTOutputCurrentA = "MPPTOutputCurrentA"
    MPPTOutputCurrentB = "MPPTOutputCurrentB"
    MPPTOutputCurrentC = "MPPTOutputCurrentC"

    MPPTInputVoltageA = "MPPTInputVoltageA"
    MPPTInputVoltageB = "MPPTInputVoltageB"
    MPPTInputVoltageC = "MPPTInputVoltageC"
    MPPTInputCurrentA = "MPPTInputCurrentA"
    MPPTInputCurrentB = "MPPTInputCurrentB"
    MPPTInputCurrentC = "MPPTInputCurrentC"

    GPSLatitude = "GPSLatitude"
    GPSLongitude = "GPSLongitude"

    Acceleration_X = "Acceleration_X"
    Acceleration_Y = "Acceleration_Y"
    Acceleration_Z = "Acceleration_Z"
