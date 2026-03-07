from data_tools.localization.versioned_table import VersionedTable
from data_tools.localization.localization import Localization
from enum import StrEnum
from datetime import date


class LanguageLocalization(Localization):
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
    MinimumModuleVoltage = "MinimumModuleVoltage"
    MaximumModuleVoltage = "MaximumModuleVoltage"
    BrakePressed = "BrakePressed"
    MotorCurrentDirection = "MotorCurrentDirection"

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
