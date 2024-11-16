from enum import StrEnum
from typing import Union, List, Any
from functools import reduce


type StringCollection = Union[str, List[str]]


class FileType(StrEnum):
    """
    Discretize the valid types of data that a `File` is supported to contain.
    All `DataSource` implementations can be expected to satisfy each supported file type for all applicable methods.
    """
    TimeSeries = "TimeSeries"
    Scalar = "Scalar"


class File:
    """
    An atomic unit of data, described by data, a file type describing the data stored, and a canonical
    path denoting its location in some filesystem-like storage.
    """
    def __init__(self, data, file_type: FileType, origin: str, path: StringCollection, name: str) -> None:
        """
        Construct a File.

        :param Any data: the data stored by this File
        :param FileType file_type: the type of data stored by this File, must be a supported type.
        :param str origin: identifies the origin (code) of this data, usually the data pipeline version.
        :param str name: the name of this data
        :param Union[str, List[str]] path: any remaining path elements. Must include the stage that produced this data as the first or only element!
        """
        self.data: Any = data
        self.type: FileType = file_type
        self.origin: str = origin
        self.path: List[str] = path if isinstance(path, list) else [path]
        self.name: str = name

        assert len(self.path) > 0, "`path` must contain at least one element!"

    @staticmethod
    def make_canonical_path(origin: str, path: StringCollection, name: str) -> str:
        """
        Create a canonical path from subatomic elements.

        :param str origin: should always be a reference to the origin (code) that produced this data.
        :param name: should always be the name of this data
        :param StringCollection path: any remaining path elements. Must include the stage that produced this data as the first or only element!
        :return: the canonical path created from the provided elements
        """
        return f"{origin}/" + reduce(lambda x, y: x + "/" + y, path) + "/" + name

    @property
    def canonical_path(self) -> str:
        """
        Obtain the canonical path of this `File`.
        """
        return File.make_canonical_path(self.origin, self.path, self.name)

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
