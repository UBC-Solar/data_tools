from datetime import datetime, timezone
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session
from data_tools.query.data_schema import init_schema, CANLog, get_sensor_id, get_data_units
from data_tools.collections.time_series import TimeSeries
import matplotlib.pyplot as plt
import numpy as np
from typing import List, Type, Union
import os
from dotenv import load_dotenv

load_dotenv()

POSTGRESQL_USERNAME = os.getenv("POSTGRESQL_USERNAME")
POSTGRESQL_PASSWORD = os.getenv("POSTGRESQL_PASSWORD")
POSTGRESQL_DATABASE = os.getenv("POSTGRESQL_DATABASE")
POSTGRESQL_ADDRESS  = os.getenv("POSTGRESQL_ADDRESS")


def _get_db_url(db_name: str, ip_address: str, username: str, password: str) -> str:
    """
    Get the URL to a Postgres database.

    :param str db_name: the name of the database being connected to
    :param str ip_address: the IP Address of the machine running the PostgreSQL instance being connected to
    :param str username: the username of the user that is connecting
    :param str password: the password of the user that is connecting
    :return: the URL formatted as a string
    """
    assert isinstance(db_name, Union[str, None]), "db_name must be a string!"
    assert isinstance(username, Union[str, None]), "username must be a string!"
    assert isinstance(ip_address, Union[str, None]), "ip_address must be a string!"
    assert isinstance(password, Union[str, None]), "password must be a string!"

    return f"postgresql://{username}:{password}@{ip_address}:5432/{db_name}"


class PostgresClient:
    """

    Connect to a PostgresSQL database and concisely make queries for time-series data.

    """
    def __init__(self, db_name: str, ip_address: str = None, username: str = None, password: str = None):
        assert isinstance(db_name, Union[str, None]), "db_name must be a string!"
        assert isinstance(username, Union[str, None]), "username must be a string!"
        assert isinstance(ip_address, Union[str, None]), "ip_address must be a string!"
        assert isinstance(password, Union[str, None]), "password must be a string!"

        if username is None:
            username = POSTGRESQL_USERNAME
        if ip_address is None:
            ip_address = POSTGRESQL_ADDRESS
        if password is None:
            password = POSTGRESQL_PASSWORD

        url = _get_db_url(db_name, ip_address, username, password)
        self._engine: Engine = create_engine(url)

        self._session_builder = sessionmaker(bind=self._engine)
        self._session: Session = self._session_builder()

    def query(self, field: str, start_time: datetime, end_time: datetime, granularity: float = 1.0,) -> TimeSeries:
        """
        Query the database for time-series data matching ``field``, between ``start_time`` and ``end_time``.

        Undefined behaviour when timestamps provided are not in UTC!

        :param str field: name of the field that will be queried
        :param datetime.datetime start_time: the UTC datetime of the beginning of the data to be queried
        :param datetime.datetime end_time: the UTC datetime of the end of the data to be queried
        :param float granularity: the desired temporal granularity of the returned data
        :return: successfully queried data formatted as a TimeSeries
        :raises ValueError: if no data could be queried
        """
        unix_start_time = start_time.timestamp()
        unix_end_time = end_time.timestamp()

        queried_data: List[Type[CANLog]] = self._session.query(CANLog)\
            .filter(CANLog.sensor_type == get_sensor_id(field),
                    CANLog.timestamp >= unix_start_time,
                    CANLog.timestamp <= unix_end_time)\
            .order_by(CANLog.timestamp).all()

        if len(queried_data) == 0:
            raise ValueError("Query returned no data!")

        timestamps = np.fromiter([datum.timestamp for datum in queried_data], dtype=float)
        values = np.fromiter([datum.value for datum in queried_data], dtype=float)

        # The start and end times of the returned data may not be the same as what was requested,
        # and we need the actual values to store the metadata properly
        actual_start_time = datetime.fromtimestamp(timestamps[0], tz=timezone.utc)
        actual_end_time = datetime.fromtimestamp(timestamps[-1], tz=timezone.utc)

        # Subtract off the first timestamp so every timestamp is delta-time from the first.
        timestamps -= timestamps[0]

        plt.plot(timestamps, values)
        plt.show()

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

    def write(self, session: Session, instance: Union[object, List[object]]) -> Union[None, Exception]:
        """
        Write some data ``instance`` to this database using ``session``.

        :param session: the Session that will be used to write to the database
        :param instance: the data that will be uploaded, can be a single object or an iterable of objects.
        :return: None if the data was uploaded successfully, or the Exception that was raised otherwise
        """
        try:
            # Upload data as a batch if it's a list
            if isinstance(data, List):
                session.add_all(instance)
            else:
                session.add(instance)

            session.commit()

        except Exception as e:
            session.rollback()
            return e

        
if __name__ == "__main__":
    field = "VehicleVelocity"
    client = PostgresClient(POSTGRESQL_DATABASE, POSTGRESQL_ADDRESS, POSTGRESQL_USERNAME, POSTGRESQL_PASSWORD)

    start_time = datetime(2024, 7, 16, 15, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2024, 7, 16, 22, 0, 0, tzinfo=timezone.utc)

    data: TimeSeries = client.query(field, start_time, end_time)

    data.plot()
