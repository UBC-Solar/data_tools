import base64
from datetime import datetime, timezone
from urllib.parse import quote
from dotenv import load_dotenv
import numpy as np
import os
import requests
from data_tools.collections import TimeSeries
import dill
import json


load_dotenv()


class SunbeamCache:
    def __init__(self, api_url: str = None):
        """
        Create a client to connect to the Sunbeam Cache API.

        Uses ``api_url`` if set, or by default "api.sunbeam.ubcsolar.com/cache".
        """
        self._base_url = api_url or "api.sunbeam.ubcsolar.com/cache"

    def _build_url(self, *components):
        """
        Construct the full URL for the given endpoint components.
        """
        return "http://" + "/".join([self._base_url] + list(components))

    @staticmethod
    def _handle_error(response):
        """Handle HTTP errors consistently."""
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            reason = response.reason
            if isinstance(reason, bytes):
                reason = reason.decode("utf-8")
            raise RuntimeError(reason)

    def __getitem__(self, item):
        url = self._build_url("get")
        response = requests.get(url, params={"key": item})

        # If we found the cached item, return it
        if response.status_code == 200:
            encoded_data = response.content
            serialized_data = base64.b64decode(encoded_data)

            return dill.loads(serialized_data)

        # Otherwise if the item wasn't found
        elif response.status_code == 406:
            raise KeyError(response.text)

        # Or if we encountered some other error
        else:
            SunbeamCache._handle_error(response)

    def __setitem__(self, key, value):
        url = self._build_url("set")
        serialized_data = dill.dumps(value, protocol=dill.HIGHEST_PROTOCOL)
        encoded_data = base64.b64encode(serialized_data).decode("utf-8")
        response = requests.get(url, params={"key": key, "value": encoded_data})

        # Handle the error if the set failed
        if response.status_code != 201:
            SunbeamCache._handle_error(response)

    def __contains__(self, item):
        url = self._build_url("exists")
        response = requests.get(url, params={"key": item})

        # Decode the response to a bool, as Flask encodes `True` into `"True"` when emitting the response
        if response.status_code == 200:
            return response.text.strip().lower() == "true"

        else:
            SunbeamCache._handle_error(response)

    def __delitem__(self, key):
        url = self._build_url("delete")
        response = requests.get(url, params={"key": key})

        if response.status_code != 200:
            SunbeamCache._handle_error(response)

    def keys(self):
        url = self._build_url("keys")
        response = requests.get(url)

        if response.status_code != 200:
            SunbeamCache._handle_error(response)

        else:
            return json.loads(response.content)


class SunbeamClient:
    """

    Encapsulate a client connection to the Sunbeam API, UBC Solar's custom data pipeline.

    """
    def __init__(self, api_url: str = None):
        """
        Create a client to connect to the Sunbeam API.

        Uses the ``SUNBEAM_URL`` environment variable if ``api_url`` is not set, or by default
        "http://localhost:8000". A URL without a scheme is assumed to be ``http://``.
        """
        if api_url is None:
            api_url = os.getenv("SUNBEAM_URL", "http://localhost:8000")

        if "://" not in api_url:
            api_url = "http://" + api_url

        self._base_url = api_url.rstrip("/")

    def _get(self, path: str, params: dict = None, timeout: float = 5):
        """
        GET a path of the API and decode its JSON.

        :raises KeyError: If the API reports that the event or signal doesn't exist.
        :raises RuntimeError: For any other error response, with the API's reason.
        :raises requests.exceptions.RequestException: If the request itself failed, e.g. timed out.
        """
        response = requests.get(f"{self._base_url}{path}", params=params, timeout=timeout)

        if response.status_code == 200:
            return response.json()

        try:
            detail = response.json().get("detail", response.reason)
        except ValueError:
            detail = response.reason

        if response.status_code == 404:
            raise KeyError(detail)
        raise RuntimeError(f"{response.status_code}: {detail}")

    def list_events(self, timeout: float = 5) -> list[str]:
        """
        Obtain the names of the events Sunbeam knows about.

        :param timeout: The amount of time to wait for a request to return.
        """
        return [event["name"] for event in self._get("/events", timeout=timeout)]

    def list_signals(self, event: str, timeout: float = 5) -> list[str]:
        """
        Obtain the names of the signals Sunbeam has for an event.

        :param event: The name of the event.
        :param timeout: The amount of time to wait for a request to return.
        :raises KeyError: If there is no such event.
        """
        return [signal["name"] for signal in self._get(f"/events/{quote(event, safe='')}/signals", timeout=timeout)]

    def get_time_series(self, event: str, signal: str, timeout: float = 30) -> TimeSeries:
        """
        Get all the data Sunbeam has for one signal of an event.

        The ``TimeSeries`` has the signal's units, and a period of ``1 / frequency`` when Sunbeam knows the
        signal's frequency (otherwise the typical spacing of its samples). Its ``meta`` holds ``event``,
        ``signal``, ``source`` (``"raw"`` or ``"derived"``), ``description``, and ``frequency``.

        :param event: The name of the event.
        :param signal: The name of the signal.
        :param timeout: The amount of time to wait for each request (long signals take several) to return.
        :raises KeyError: If there is no such event, or the event has no such signal.
        :raises ValueError: If the signal has no data.
        :raises requests.exceptions.Timeout: If a request times out.
        """
        path = f"/events/{quote(event, safe='')}/signals/{quote(signal, safe='')}/data"

        # The API returns at most a page of the MOST RECENT samples before ``end``; walk backwards until a page
        # isn't truncated. Timestamps are epoch milliseconds, ascending.
        pages: list[dict] = []
        params: dict = {}
        while True:
            page = self._get(path, params=params, timeout=timeout)
            pages.append(page)
            if not page["truncated"] or not page["timestamps"]:
                break
            earliest = datetime.fromtimestamp(page["timestamps"][0] / 1000, tz=timezone.utc)
            params = {"end": earliest.isoformat()}

        timestamps: list[int] = []
        values: list = []
        # Newest page first, each older one prepended
        for page in pages:
            # A sample that rounded up to the newer page's first millisecond comes back in both pages
            keep = len(page["timestamps"])
            while timestamps and keep and page["timestamps"][keep - 1] >= timestamps[0]:
                keep -= 1
            timestamps = page["timestamps"][:keep] + timestamps
            values = page["values"][:keep] + values

        if not any(value is not None for value in values):
            raise ValueError(f"Sunbeam has no data for {signal!r} in {event!r}!")

        latest = pages[0]
        frequency = latest["frequency"]
        seconds = np.array(timestamps, dtype=float) / 1000

        if frequency:
            period = 1 / frequency
        elif len(seconds) > 1:
            period = float(np.median(np.diff(seconds)))
        else:
            period = 1.0

        return TimeSeries.from_samples(
            seconds,
            values,
            period=period,
            units=latest["unit"] or None,
            meta={
                "event": event,
                "signal": signal,
                "source": latest["source"],
                "description": latest["description"],
                "frequency": frequency,
            },
        )

    def is_alive(self, timeout: float = 0.5):
        """
        Verify if the Sunbeam API is available.

        :param timeout: The time to wait for a response.
        :return: `True` if the Sunbeam API is available, and `False` otherwise.
        """
        try:
            response = requests.get(f"{self._base_url}/health", timeout=timeout)

        except requests.exceptions.RequestException:  # Base class for exceptions from `requests`
            return False

        # Check the status code.
        # If the health check responds with an error code, something odd is going on.
        return response.status_code == 200
