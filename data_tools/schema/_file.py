from enum import StrEnum
from typing import List, Any
from functools import reduce
from pydantic import BaseModel, Field, ConfigDict
import pathlib


class FileType(StrEnum):
    """
    Discretize the valid types of data that a `File` is supported to contain.
    All `DataSource` implementations can be expected to satisfy each supported file type for all applicable methods.
    """
    TimeSeries = "TimeSeries"
    NDArray = "NDArray"
    Scalar = "Scalar"
    Empty = "Empty"
    Any = "Any"


class CanonicalPath:
    def __init__(self, origin: str, source: str, event: str, name: str):
        """
        Construct a canonical path representing a path to a file in any abstract data source.

        :param str origin: Identifies the origin (code) of this data, usually the data pipeline version.
        :param str source: The producer of the data pointed to by this canonical path, usually a pipeline stage
        :param str event: The event that this data belongs to
        :param str name: The name of this data
        """
        self._origin: str = origin
        self._source: str = source
        self._event: str = event
        self._name: str = name

    def to_string(self) -> str:
        """
        Obtain the string representation of this canonical path
        """
        return "/".join([self._origin, self._event, self._source, self._name])

    def to_path(self) -> pathlib.Path:
        return reduce(lambda x, y: x / pathlib.Path(y), self.unwrap())

    @property
    def origin(self) -> str:
        return self._origin

    @property
    def source(self) -> str:
        return self._source

    @property
    def event(self) -> str:
        return self._event

    @property
    def name(self) -> str:
        return self._name

    def __str__(self):
        return self.to_string()

    def __repr__(self):
        return self.to_string()

    def unwrap(self) -> List[str]:
        """
        Decompose this `CanonicalPath` into its constituent elements. Equivalent to `os.path.split`.
        """
        return self.to_string().split("/")

    @staticmethod
    def unwrap_canonical_path(canonical_path: str) -> List[str]:
        """
        Unwrap a canonical path into its elements.

        For example, `"pipeline_2024_11_01/ingest/TotalPackVoltage"` would be
        unwrapped to `["pipeline_2024_11_01", "ingest", "TotalPackVoltage"]`.

        The first element should always be a reference to the origin (code) that produced this data.
        The second element should always refer to the stage (processing step) that produced this data.
        The last element should always be the name of this data.

        :param canonical_path: The path to be decomposed
        :return: A List[str] of path elements
        """
        return canonical_path.split("/")


class File(BaseModel):
    """
    An atomic unit of data, described by data, a file type describing the data stored, and a canonical
    path denoting its location in some filesystem-like storage.
    """
    data: Any                                       # The data contained by this file
    file_type: FileType                             # The type of data contained by this file
    canonical_path: CanonicalPath                   # The path to this file within the data source where it is stored
    metadata: dict = Field(default_factory=dict)    # Any additional metadata that this file should hold
    description: str = Field(default_factory=str)   # A description of what this file is

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)
