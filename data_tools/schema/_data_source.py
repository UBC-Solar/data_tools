from abc import ABC, abstractmethod
from data_tools.schema import Result, File, FileLoader


class DataSource(ABC):
    def __init__(self, *args, **kwargs) -> None:
        pass

    @abstractmethod
    def store(self, file: File) -> FileLoader:
        raise NotImplementedError

    @abstractmethod
    def get(self, canonical_path: str, **kwargs) -> Result:
        raise NotImplementedError
