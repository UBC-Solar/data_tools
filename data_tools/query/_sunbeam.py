import base64
from dotenv import load_dotenv
import os
import requests
from data_tools.schema import File, Result, CanonicalPath
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

        Uses the `SUNBEAM_URL` environment variable if ``api_url`` is not set, or by default "api.sunbeam.ubcsolar.com".
        """
        if api_url is None:
            api_url = os.getenv("SUNBEAM_URL") if "SUNBEAM_URL" in os.environ.keys() else "api.sunbeam.ubcsolar.com"

        self._base_url = api_url

    @property
    def cache(self):
        """
        Acquire an interface to the Sunbeam Cache API, descended from this client.
        """
        return SunbeamCache(self._base_url + "/cache")

    def distinct(self, key: str, filter: dict[str, str]) -> list[str]:
        """
        Obtain the distinct values of a given key, subject to a filter.

        For example, if you want to see the distinct events processed by a certain pipeline,
        you can set `key` to `"event"` and `filter` to `{"origin": "your_pipeline"}`.

        As another example, if you wanted to see the events processed by a certain pipeline where the "power" stage
        was processed, you can set `key` to `"event"` and `filter` to `{"origin": "your_pipeline", "source": "power"}`.

        :param key: name of the field for which we want to get the distinct values
        :param filter: a mapping which filters the query to have items match this filter's values by field
        :return: the values corresponding the `key` field of matching items
        """
        url_components: list[str] = [self._base_url, "files", "distinct"]
        url = "http://" + "/".join(url_components)
        data = {"key": key}
        data.update(filter)

        response = requests.post(url, data=data)

        if response.status_code == 200:
            return json.loads(response.text)

        # Otherwise, acquire and wrap the error
        else:
            # Try to extract the error and capture it
            response.raise_for_status()



    def get_file(self, origin: str = None, event: str = None, source: str = None, name: str = None, path: CanonicalPath = None) -> Result[File | Exception]:
        """
        Get a File from the Sunbeam API.

        You must provide either a ``CanonicalPath`` object directory by setting ``path``, OR provide ALL the
        individual path elements ``origin``, ``event``, ``source``, and ``name``.

        :return: a ``Result`` wrapping a ``File`` or an ``Exception``
        :raises AssertionError: if ``path`` was not provided and any of ``origin``, ``event``, ``source``, ``name`` are None.
        """
        # Start the url as api.sunbeam.ubcsolar.com/files
        url_components: list[str] = [self._base_url, "files"]

        # Prefer using ``path`` to build the URL
        if path is not None:
            url_components.extend(path.unwrap())

        else:
            # Make sure if we are using the individual path elements, all of them were provided
            if None in [origin, event, source, name]:
                raise AssertionError("All of ``origin``, ``event``, ``source``, and ``name`` cannot be none!")

            url_components.extend([origin, event, source, name])

        # Build the path, and set file_type=bin to request the binary data of the File we want
        url = "http://" + "/".join(url_components)
        params = {'file_type': "bin"}

        response = requests.get(url, params=params)

        # If we got the File successfully, wrap and return the deserialized File object
        if response.status_code == 200:
            serialized_data = response.content
            return Result.Ok(dill.loads(serialized_data))

        # Otherwise, acquire and wrap the error
        else:
            # Try to extract the error and capture it
            try:
                response.raise_for_status()

            except requests.exceptions.HTTPError as e:
                return Result.Err(e)

            # We didn't capture an error, but we still didn't get an OK error code, so wrap
            # the response message in a RuntimeError
            if isinstance(response.reason, bytes):
                reason = response.reason.decode("utf-8")
            else:
                reason = response.reason

            return Result.Err(RuntimeError(reason))
