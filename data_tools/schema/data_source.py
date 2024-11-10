from enum import StrEnum
from collections.abc import Callable
from abc import ABC, abstractmethod


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
    def __init__(self, data, file_type: FileType, origin: str, stage: str, name: str) -> None:
        self.data = data
        self.type = file_type
        self.origin = origin
        self.stage = stage
        self.name = name

    def canonical_path(self) -> str:
        """
        Obtain the canonical path of this `File`.
        """
        return f"{self.origin}/{self.stage}/{self.name}"


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

