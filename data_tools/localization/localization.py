from data_tools.localization.versioned_table import VersionedTable
from abc import ABC, abstractmethod
import pathlib


class Localization(ABC):
    _instance: "Localization | None" = None

    def __init__(self, localization_table: pathlib.Path):
        self._localization_table = VersionedTable.from_toml_file(str(localization_table.absolute()))

    @abstractmethod
    def localize(self, *args, **kwargs): ...
