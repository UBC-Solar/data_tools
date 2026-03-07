from data_tools.localization.versioned_table import VersionedTable
from abc import ABC, abstractmethod
from datetime import date
import pathlib


class Localization(ABC):
    _instance: "Localization | None" = None

    def __init__(self, localization_table: pathlib.Path):
        self._localization_table = VersionedTable.from_toml_file(str(localization_table.absolute()))

    @classmethod
    def load(cls, localization_table: pathlib.Path) -> "Localization":
        if cls._instance is None:
            cls._instance = cls(localization_table)
        return cls._instance

    @classmethod
    def _get(cls) -> "Localization":
        if cls._instance is None:
            raise RuntimeError(f"{cls.__name__} not loaded. Call {cls.__name__}.load(path) first.")
        return cls._instance

    @classmethod
    @abstractmethod
    def localize(cls, *args, **kwargs): ...
