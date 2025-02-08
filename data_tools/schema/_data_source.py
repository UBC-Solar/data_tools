from abc import ABC, abstractmethod
from data_tools.schema import Result, File, FileLoader, CanonicalPath


class DataSource(ABC):
    """
    Abstract base class for data sources.
    """
    def __init__(self, *args, **kwargs) -> None:
        pass

    @abstractmethod
    def store(self, file: File) -> FileLoader:
        raise NotImplementedError

    @abstractmethod
    def get(self, canonical_path: CanonicalPath, **kwargs) -> Result:
        raise NotImplementedError
