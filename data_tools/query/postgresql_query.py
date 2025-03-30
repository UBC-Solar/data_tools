from data_tools.query.data_schema import init_schema, CANLog, get_sensor_id, get_data_units
from data_tools.collections.time_series import TimeSeries
from sqlalchemy.orm import sessionmaker, Session
from data_tools.utils.times import ensure_utc
from sqlalchemy import create_engine, Engine
from datetime import datetime, timezone
from typing import List, Type, Union
import matplotlib.pyplot as plt
from dotenv import load_dotenv
import numpy as np
import logging
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Set the logger to the lowest level (DEBUG)

# Create a handler for terminal output
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)  # Show INFO and ERROR on the terminal
logger.addHandler(console_handler)

load_dotenv()

_POSTGRESQL_USERNAME = os.getenv("POSTGRESQL_USERNAME")
_POSTGRESQL_PASSWORD = os.getenv("POSTGRESQL_PASSWORD")
_POSTGRESQL_DATABASE = os.getenv("POSTGRESQL_DATABASE")
_POSTGRESQL_ADDRESS = os.getenv("POSTGRESQL_ADDRESS")

if _POSTGRESQL_USERNAME is None:
    logger.error("Could not find a POSTGRESQL_USERNAME in .env!")

if _POSTGRESQL_PASSWORD is None:
    logger.error("Could not find a POSTGRESQL_PASSWORD in .env!")

if _POSTGRESQL_DATABASE is None:
    logger.error("Could not find a POSTGRESQL_DATABASE in .env!")

if _POSTGRESQL_ADDRESS is None:
    logger.error("Could not find a POSTGRESQL_ADDRESS in .env!")


def _get_db_url(db_name: str, ip_address: str, username: str, password: str) -> str:
    """
    Get the URL to a Postgres database.

    :param str db_name: the name of the database being connected to
    :param str ip_address: the IP Address of the machine running the PostgreSQL instance being connected to
    :param str username: the username of the user that is connecting
    :param str password: the password of the user that is connecting
    :return: the URL formatted as a string
    """
    assert isinstance(db_name, str), f"db_name must be a string, not {type(db_name)}!"
    assert isinstance(username, str), f"username must be a string, not {type(username)}!"
    assert isinstance(ip_address, str), f"ip_address must be a string, not {type(ip_address)}!"
    assert isinstance(password, str), f"password must be a string, not {type(password)}!"

    return f"postgresql://{username}:{password}@{ip_address}:5432/{db_name}"


class PostgresClient:
    """

    Connect to a PostgresSQL database and concisely make queries for time-series data.

    """
    def __init__(self, db_name: str = None, ip_address: str = None, username: str = None, password: str = None, timeout: float = 10):
        if username is None:
            username = _POSTGRESQL_USERNAME
        if db_name is None:
            db_name = _POSTGRESQL_DATABASE
        if ip_address is None:
            ip_address = _POSTGRESQL_ADDRESS
        if password is None:
            password = _POSTGRESQL_PASSWORD

        url = _get_db_url(db_name, ip_address, username, password)
        self._engine: Engine = create_engine(url, connect_args={'connect_timeout': timeout})

        self._session_builder = sessionmaker(bind=self._engine)
        self._session: Session = self._session_builder()

    def query(self, field: str, start_time: datetime, end_time: datetime, granularity: float = 1.0) -> TimeSeries:
        """
        Query the database for time-series data matching ``field``, between ``start_time`` and ``end_time``.

        Undefined behaviour when timestamps provided are not in UTC!

        PLEASE NOTE: If your data does not have a frequency of 1.0Hz, then you will be
        decimating or up-sampling your data. Set ``granularity`` to control the temporal
        granularity (time between measurements) of your data!

        :param str field: name of the field that will be queried
        :param datetime.datetime start_time: the UTC datetime of the beginning of the data to be queried
        :param datetime.datetime end_time: the UTC datetime of the end of the data to be queried
        :param float granularity: the desired temporal granularity (time between measurements) of the returned data
        :return: successfully queried data formatted as a TimeSeries
        :raises IndexError: if no data could be queried
        :raises RuntimeError: if the query failed for any reason
        :raises ValueError: if timestamps cannot be localized to UTC
        """
        # Validate that the times provided are localized to UTC
        utc_start_time = ensure_utc(start_time)
        utc_end_time = ensure_utc(end_time)

        unix_start_time = utc_start_time.timestamp()
        unix_end_time = utc_end_time.timestamp()

        try:
            queried_data: List[Type[CANLog]] = self._session.query(CANLog)\
                .filter(CANLog.sensor_type == get_sensor_id(field),
                        CANLog.timestamp >= unix_start_time,
                        CANLog.timestamp <= unix_end_time)\
                .order_by(CANLog.timestamp).all()

        # Catch any error from querying and wrap it in a RuntimeError
        except Exception as e:
            raise RuntimeError("Error whilst querying data!") from e

        if len(queried_data) == 0:
            raise IndexError("Query returned no data!")

        timestamps = np.fromiter([datum.timestamp for datum in queried_data], dtype=float)
        values = np.fromiter([datum.value for datum in queried_data], dtype=float)

        # The start and end times of the returned data may not be the same as what was requested,
        # and we need the actual values to store the metadata properly
        actual_start_time = datetime.fromtimestamp(timestamps[0], tz=timezone.utc)
        actual_end_time = datetime.fromtimestamp(timestamps[-1], tz=timezone.utc)

        # Subtract off the first timestamp so every timestamp is delta-time from the first.
        timestamps -= timestamps[0]

        # Reform the x-axis as a homogenous array
        x_axis = np.arange(timestamps[0], timestamps[-1], granularity)

        # Interpolate the data array onto this new x-axis
        wave = np.interp(x_axis, timestamps, values)

        time_series_dict = {
            "start": actual_start_time,
            "stop": actual_end_time,
            "car": "N/A",
            "measurement": "N/A",
            "field": field,
            "granularity": granularity,
            "length": len(x_axis),
            "units": get_data_units(get_sensor_id(field)),
        }

        return TimeSeries(wave, time_series_dict)

    def init_schema(self):
        """
        Initialize the Postgres database schema. This only needs to be called ONCE PER DATABASE.

        Has no effect if called on an already initialized database.
        """
        init_schema(self._engine)

    def get_session(self) -> Session:
        """
        Obtain a new Session to make queries to this database.
        :return: a new Session bound to this connection
        """
        return self._session_builder()

    def write(self, instance: Union[object, List[object]], session: Session = None) -> None:
        """
        Write some data ``instance`` to this database using ``session``.

        :param instance: the data that will be uploaded, can be a single object or an iterable of objects.
        :param session: optionally specify the Session that will be used to write to the database
        :raises RuntimeError: if the database write fails
        """
        # Use the default session if none was specified
        if session is None:
            session = self._session

        try:
            # Upload data as a batch if it's a list
            if isinstance(instance, List):
                session.add_all(instance)
            else:
                session.add(instance)

            session.commit()

        except Exception as e:
            # If the database write failed, ensure to roll back the commit
            session.rollback()
            raise RuntimeError("Failed to write to PostgreSQL!") from e

        
if __name__ == "__main__":
    field = "TotalPackVoltage"
    client = PostgresClient()

    start_time = datetime(2024, 6, 16, 10, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2024, 8, 21, 23, 0, 0, tzinfo=timezone.utc)

    data: TimeSeries = client.query(field, start_time, end_time, granularity=0.1)

    x_axis = data.datetime_x_axis
    plt.plot(x_axis, data)
    plt.show()
