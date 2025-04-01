import datetime
from data_tools.utils.times import parse_iso_datetime, ensure_utc
from typing import Union, List


type DateLike = Union[str, datetime.datetime]


class Event:
    """
    Represents an event that took place between `start` and `stop` (accessible as datetime.datetime objects or
    as ISO 8601 formatted strings), with a `name` and optionally any additional `attributes` such as
    `attributes["realtime"]` or `attributes["test"]`.
    """
    def __init__(
            self,
            start: DateLike,
            stop: DateLike, name: str = None,
            attributes: dict = None,
            flags: List[str] = None
    ):
        """
        Create an Event from either ISO8601 strings or datetime.datetime objects.
        Any datetime.datetime objects or ISO8601 strings MUST contain timezone information.

        Optionally, name the event with `name`, and with additional `attributes`.

        :param start: The start time of this Event
        :param stop: The end time of this Event
        :param name: The name of this event, optional, defaulted to "Unnamed Event"
        :param flags: A list of strings that indicate flags that are present.
        :param dict attributes: A dictionary of any additional attributes and/or metadata for this Event
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

        if not isinstance(name, str) and name is not None:
            raise TypeError("name must be str!")
        else:
            self._name = name if name is not None else "Unnamed Event"

        if not isinstance(attributes, dict) and attributes is not None:
            raise TypeError("attributes must be dict!")
        else:
            self._attributes = attributes if attributes is not None else None

        if not isinstance(flags, list) and flags is not None:
            raise TypeError("flags must be list!")
        else:
            self._flags = flags if flags is not None else None

    @property
    def attributes(self) -> dict:
        """
        Obtain a dictionary of additional metadata or relevant attributes for this Event.
                """
        return self._attributes

    @property
    def start(self) -> datetime.datetime:
        """
        Obtain the end time of this Event as a datetime.datetime object.
        """
        return self._start

    @property
    def flags(self) -> List[str]:
        """
        Obtain the flags of this event as a list. May be empty.
        """
        return self._flags

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
        :return: an Event hydrated with the provided data
        """
        data = data_dict.copy()

        start_time = data["start"]
        del data["start"]

        end_time = data["stop"]
        del data["stop"]

        if "name" in data.keys():
            name = data["name"]
            del data["name"]

        else:
            name = None

        return Event(start_time, end_time, name, data)

    def to_dict(self) -> dict:
        """
        Compile this Event to its dictionary representation.

        :return: the representation of this Event as a dictionary
        """
        ret_dict = {
            "start": self.start_as_iso_str,
            "stop": self.stop_as_iso_str,
            "name": self.name
        }

        if self._attributes is not None:
            for key, value in self._attributes.items():
                ret_dict[key] = value

        return ret_dict
