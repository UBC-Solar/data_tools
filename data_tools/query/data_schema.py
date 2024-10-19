from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, Float, UniqueConstraint, Engine

Base = declarative_base()

targets = ["TotalPackVoltage", "BatteryCurrent", "BatteryVoltage", "VehicleVelocity"]

_data_id_encodings = {
    "TotalPackVoltage": 0,
    "BatteryCurrent": 1,
    "BatteryVoltage": 2,
    "VehicleVelocity": 3,
    "PackCurrent": 4,
    "BatteryCurrentDirection": 5,
    "VoltageofLeast": 6
}


_data_units = {
    0: "V",
    1: "A",
    2: "V",
    3: "m/s",
    4: "A",
    5: "A.U.",
    6: "V"
}


def get_sensor_id(data_field: str) -> int:
    """
    Return the canonical data ID corresponding to the data titled ``data_field``.

    :param data_field: the data's name as a string
    :return: the data's canonical ID as an integer
    """
    return _data_id_encodings[data_field]


def get_data_units(data_id: int) -> str:
    """
    Return the units of the data corresponding to the canonical ID ``data_id``.

    :param int data_id: the data's canonical ID as an integer
    :return: the data's units as a string
    """
    return _data_units[data_id]


class CANLog(Base):
    """

    Encapsulates a single CAN log message within an SQL database.

    """
    __tablename__ = "sensor_data"

    id = Column(Integer, primary_key=True)          # The unique ID of this entry in the database
    timestamp = Column(Float, nullable=False)       # The timestamp as a UTC POSIX timestamp
    sensor_type = Column(Integer, nullable=False)   # The canonical data ID of this log
    value = Column(Float, nullable=False)           # The value of this measurement

    # Enforce that there should be no entries of the same data at the same time!
    __table_args__ = (
        UniqueConstraint('timestamp', 'sensor_type', name='unique_timestamp_sensor_type'),
    )


def init_schema(engine: Engine):
    """
    Initialize this schema in the database connected to by ``engine``.

    :param engine: connection to database that will be mutated with this schema
    """
    Base.metadata.create_all(engine)
