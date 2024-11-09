from enum import StrEnum
from collections.abc import Callable
from abc import ABC, abstractmethod


type FileLoader = Callable[[], File]


class FileType(StrEnum):
    TimeSeries = "TimeSeries"
    Scalar = "Scalar"


class File:
    def __init__(self, data, file_type: FileType, origin: str, stage: str, name: str) -> None:
        self.data = data
        self.type = file_type
        self.origin = origin
        self.stage = stage
        self.name = name

    def canonical_path(self) -> str:
        return f"{self.origin}/{self.stage}/{self.name}"


class DataSource(ABC):
    def __init__(self, *args, **kwargs) -> None:
        pass

    @abstractmethod
    def store(self, **kwargs) -> FileLoader:
        raise NotImplementedError

    @abstractmethod
    def get(self, canonical_path: str, **kwargs) -> File:
        raise NotImplementedError

