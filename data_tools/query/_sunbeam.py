from dotenv import load_dotenv
import os
import requests
from data_tools.schema import File, Result, CanonicalPath
import dill


load_dotenv()


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
