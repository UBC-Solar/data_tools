import datetime
from data_tools.utils.times import parse_iso_datetime, ensure_utc
from typing import Union


type DateLike = Union[str, datetime.datetime]


class Event:
    def __init__(self, start: DateLike, stop: DateLike, name: str = None):
        """
        Create an Event from either ISO8601 strings or datetime.datetime objects.
        Any datetime.datetime objects or ISO8601 strings MUST contain timezone information.

        Optionally, name the event with `name`.

        :param start: the start time of this Event
        :param stop: the end time of this Event
        :param name: the name of this event, optional, defaulted to "Unnamed Event"
        """
        if isinstance(start, datetime.datetime):
            self._start = ensure_utc(start)
        elif isinstance(start, str):
            self._start: datetime = parse_iso_datetime(start)
        else:
            raise TypeError("start must be datetime or str!")

        if isinstance(stop, datetime.datetime):
            self._stop = ensure_utc(stop)
        elif isinstance(stop, str):
            self._stop: datetime = parse_iso_datetime(stop)
        else:
            raise TypeError("start must be datetime or str!")

        if not isinstance(name, str):
            raise TypeError("name must be str!")

        self._name = name if name is not None else "Unnamed Event"

    @property
    def start(self) -> datetime.datetime:
        """
        Obtain the end time of this Event as a datetime.datetime object.
        """
        return self._start

    @property
    def stop(self) -> datetime.datetime:
        """
        Obtain the end time of this Event as a datetime.datetime object.
        """
        return self._stop

    @property
    def start_as_iso_str(self) -> str:
        """
        Return the start time of this Event as an ISO8601 string, such as 2024-11-07T15:30:45.12Z
        """
        return self._start.isoformat().replace("+00:00", "Z")

    @property
    def stop_as_iso_str(self) -> str:
        """
        Return the stop time of this Event as an ISO8601 string, such as 2024-11-07T15:30:45.12Z
        """
        return self._stop.isoformat().replace("+00:00", "Z")

    @property
    def name(self) -> str:
        """
        The name of the event, if this event is named, or "Unnamed Event" if not.
        """
        return self._name

    @staticmethod
    def from_dict(data_dict: dict):
        """
        Obtain an event from a dictionary.
        Dictionary must contain a key "start" containing an ISO8601 string or datetime.datetime object,
        a key "stop" containing an ISO8601 string or datetime.datetime object, and optionally a name.

        datetime.datetime objects and ISO8601 strings MUST contain timezone information.

        :param data_dict: valid dictionary containing data
        :return: an Event with the
        """
        try:
            start_time = data_dict["start"]
            end_time = data_dict["stop"]
            name = data_dict["name"] if "name" in data_dict.keys() else None

            return Event(start_time, end_time, name)

        except KeyError as e:
            raise KeyError("Dictionary must contain ") from e

    def to_dict(self) -> dict:
        """
        Compile this Event to its dictionary representation.

        :return: the representation of this Event as a dictionary
        """
        return {
            "start": self.start_as_iso_str,
            "stop": self.stop_as_iso_str,
            "name": self.name
        }

