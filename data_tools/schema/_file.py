from enum import StrEnum
from typing import Union, List, Any
from functools import reduce
from pydantic import BaseModel
import pathlib


type StringCollection = Union[str, List[str]]


class FileType(StrEnum):
    """
    Discretize the valid types of data that a `File` is supported to contain.
    All `DataSource` implementations can be expected to satisfy each supported file type for all applicable methods.
    """
    TimeSeries = "TimeSeries"
    Scalar = "Scalar"
    Empty = "Empty"


class CanonicalPath:
    def __init__(self, origin: str, source: str, path: StringCollection, name: str):
        """
        Construct a canonical path representing a path to a file in any abstract data source

        :param str origin: identifies the origin (code) of this data, usually the data pipeline version.
        :param str source: the producer of the data pointed to by this canonical path, usually a pipeline stage
        :param Union[str, List[str]] path: any remaining path elements from the producer to the file pointed to
        :param str name: the name of this data
        """
        self._origin = origin
        self._source = source
        self._path = path if isinstance(path, list) else [path]
        self._name = name

    def to_string(self) -> str:
        """
        Obtain the string representation of this canonical path

        :return: str
        """
        return "/".join([self._origin] + self._path + [self._source, self._name])

    def to_path(self) -> pathlib.Path:
        return reduce(lambda x, y: x / pathlib.Path(y), self.unwrap())

    @property
    def origin(self) -> str:
        return self._origin

    @property
    def source(self) -> str:
        return self._source

    @property
    def path(self) -> StringCollection:
        return self._path

    @property
    def name(self) -> str:
        return self._name

    def __str__(self):
        return self.to_string()

    def __repr__(self):
        return self.to_string()

    def unwrap(self) -> List[str]:
        """
        Decompose this CanonicalPath into its subatomic elements
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

        :param canonical_path: the path to be decomposed
        :return: a List[str] of path elements
        """
        return canonical_path.split("/")


class File(BaseModel):
    """
    An atomic unit of data, described by data, a file type describing the data stored, and a canonical
    path denoting its location in some filesystem-like storage.
    """
    data: Any                       # The data contained by this file
    file_type: FileType             # The type of data contained by this file
    canonical_path: CanonicalPath   # The path to this file within the data source where it is stored

    class Config:
        arbitrary_types_allowed = True
