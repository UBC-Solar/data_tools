from enum import StrEnum
from collections.abc import Callable
from abc import ABC, abstractmethod
from typing import Union, List, Any
from functools import reduce


class FileType(StrEnum):
    """
    Discretize the valid types of data that a `File` is supported to contain.
    All `DataSource` implementations are expected to satisfy each supported file type.
    """
    TimeSeries = "TimeSeries"
    Scalar = "Scalar"


class File:
    """
    An atomic unit of data, described by data, a file type describing the data stored, and a canonical
    path denoting its location in some filesystem-like storage.
    """
    def __init__(self, data, file_type: FileType, origin: str, path: Union[str, List[str]], name: str) -> None:
        """
        Construct a File.

        :param Any data: the data stored by this File
        :param FileType file_type: the type of data stored by this File, must be a supported type.
        :param str origin: identifies the origin (code) of this data, usually the data pipeline version.
        :param Union[str, List[str]] path: any remaining path elements. Must include the stage that produced this data as the first or only element!
        :param str name: the name of this data
        """
        self.data: Any = data
        self.type: FileType = file_type
        self.origin: str = origin
        self.path: List[str] = path if isinstance(path, list) else [path]
        self.name: str = name

        assert len(self.path) > 0, "`path` must contain at least one element!"

    @property
    def canonical_path(self) -> str:
        """
        Obtain the canonical path of this `File`.
        """
        return f"{self.origin}/" + reduce(lambda x, y: x + "/" + y, self.path) + "/" + self.name

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


class FileLoader:
    """
    A callable object that wraps a lambda function to acquire a `File`, as well as the
    canonical path that will be queried for the `File` in question.
    """
    def __init__(self, loader: Callable[[], File], canonical_path: str) -> None:
        """
        Wrap a `loader` along with the `canonical_path` that it will be querying.

        :param loader: a zero-argument lambda that will return either a `File` or raise a `FileNotFoundError`.
        :param canonical_path: the path that the lambda will be querying.
        """
        self._loader = loader
        self._canonical_path = canonical_path

    def __call__(self) -> File:
        """
        Invoke this `FileLoader`, and obtain a File` or raise a `FileNotFoundError` if it cannot be found.

        :raises FileNotFoundError: If the `File` cannot be loaded
        :return: the `File` that was loaded
        """
        return self._loader()

    @property
    def canonical_path(self) -> str:
        return self._canonical_path


class DataSource(ABC):
    def __init__(self, *args, **kwargs) -> None:
        pass

    @abstractmethod
    def store(self, **kwargs) -> FileLoader:
        raise NotImplementedError

    @abstractmethod
    def get(self, canonical_path: str, **kwargs) -> File:
        raise NotImplementedError

