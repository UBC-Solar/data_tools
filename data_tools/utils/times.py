from datetime import datetime, timezone


def ensure_utc(dt: datetime) -> datetime:
    """
    Ensure that a datetime, ``dt`` is localized to UTC.

    :param dt: the datetime that will be validated
    :raises ValueError: if ``dt`` is not localized to ANY timezone.
    :return:
    """
    # Check if ``dt`` is naive (not localized to a timezone), in that case we cannot safely proceed.
    if dt.tzinfo is None:
        raise ValueError("Datetime object must be timezone-aware.")

    # Otherwise, we can re-localize the ``dt`` to UTC if it isn't already
    if dt.tzinfo != timezone.utc:
        dt = dt.astimezone(timezone.utc)

    return dt


def parse_iso_datetime(iso_string: str) -> datetime:
    """
    Convert an ISO 8601 string to a timezone-aware datetime object.

    :param str iso_string: ISO 8601 formatted datetime string (e.g. "2024-01-01T15:30:00Z" or "2024-01-01T15:30:00+00:00")

    :returns: timezone-aware datetime object
    :rtype: datetime
    :raises ValueError: If the ISO string is invalid or timezone name is not recognized
    """
    try:
        # Handle both 'Z' and '+00:00' UTC formats
        if iso_string.endswith('Z'):
            dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        else:
            dt = datetime.fromisoformat(iso_string)

        dt_utc = ensure_utc(dt)

        return dt_utc

    except Exception as e:
        raise ValueError(f"Failed to parse ISO datetime string: {str(e)}") from e


def iso_string_from_datetime(dt: datetime) -> str:
    """

    Return the stop time of this Event as an ISO8601 string, such as 2024-11-07T15:30:45.12Z

    :param dt: datetime object to be converted
    :return: the datetime as an ISO8601 string
    """
    return dt.isoformat().replace("+00:00", "Z")
