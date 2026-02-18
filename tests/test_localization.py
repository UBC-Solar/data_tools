from data_tools.localization import LOCALIZATION_TABLE_PATH
from data_tools.localization import VersionedTable
from data_tools.localization import CanonicalName
from datetime import date
import tomllib
import pytest


@pytest.fixture
def versioned_table():
    table_dict = {
        "2024-01-01": {
            "VehicleVelocity": ("VehicleVelocity", "km/h"),
            "BatteryVoltage": ("TotalPackVoltage", "V"),
            "ArrayString1Voltage": ("String1Voltage", "V"),
        },
        "2025-01-01": {
            "VehicleVelocity": ("MotorRotatingSpeed", "m/s"),
            "BatteryVoltage": ("TotalPackVoltage", "V"),
            "ArrayString1Voltage": ("MPPTAInput", "V"),
        },
        "2026-01-01": {
            "VehicleVelocity": ("MotorRotatingSpeed", "m/s"),
            "BatteryVoltage": ("TotalPackVoltage", "V"),
            "Latitude": ("GPS_Latitude", "degrees"),
        }
    }

    return VersionedTable.from_dict(table_dict)

def test_localization(versioned_table):
    assert versioned_table.lookup("VehicleVelocity", "2024-01-02") == ("VehicleVelocity", "km/h")
    assert versioned_table.lookup("VehicleVelocity", "2025-01-02") == ("MotorRotatingSpeed", "m/s")
    assert versioned_table.lookup("BatteryVoltage", "2025-01-02") == ("TotalPackVoltage", "V")
    assert versioned_table.lookup("ArrayString1Voltage", "2024-01-02") == ("String1Voltage", "V")
    assert versioned_table.lookup("Latitude", "2026-01-02") == ("GPS_Latitude", "degrees")

    # Check everything again with dates
    assert versioned_table.lookup("VehicleVelocity", date.fromisoformat("2024-01-02")) == ("VehicleVelocity", "km/h")
    assert versioned_table.lookup("VehicleVelocity", date.fromisoformat("2025-01-02")) == ("MotorRotatingSpeed", "m/s")
    assert versioned_table.lookup("BatteryVoltage", date.fromisoformat("2025-01-02")) == ("TotalPackVoltage", "V")
    assert versioned_table.lookup("ArrayString1Voltage", date.fromisoformat("2024-01-02")) == ("String1Voltage", "V")
    assert versioned_table.lookup("Latitude", date.fromisoformat("2026-01-02")) == ("GPS_Latitude", "degrees")


def test_invalid_localization(versioned_table):
    # Invalid Key
    with pytest.raises(UnboundLocalError):
        _ = versioned_table.lookup("MotorRotatingSpeed", "2024-01-02")

    # Invalid Date
    with pytest.raises(ValueError):
        _ = versioned_table.lookup("VehicleVelocity", "2024-67-42")

    # Name isn't available yet
    with pytest.raises(KeyError):
        _ = versioned_table.lookup("Latitude", "2024-01-02")

    # Name doesn't exist anymore
    with pytest.raises(KeyError):
        _ = versioned_table.lookup("ArrayString1Voltage", "2026-01-02")


def test_all_names():
    with open(LOCALIZATION_TABLE_PATH, "rb") as f:
        data = tomllib.load(f)

    for _, section_dict in data.items():
        for name in section_dict.keys():
            assert name in CanonicalName, (f"The name {name} is defined in the localization table but "
                                           f"was not found as a CanonicalName option. Please add it.")
