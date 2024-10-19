from datetime import datetime, timezone


def _ensure_utc(dt: datetime) -> datetime:
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
