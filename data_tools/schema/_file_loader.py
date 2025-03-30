from typing import Callable
from data_tools.schema import Result, CanonicalPath, File


class FileLoader:
    """
    A callable object that wraps a lambda function to acquire a `File`, as well as the
    canonical path that will be queried for the `File` in question.
    """
    def __init__(self, loader: Callable[[CanonicalPath], Result[File]], canonical_path: CanonicalPath) -> None:
        """
        Wrap a `loader` along with the `canonical_path` that it will be querying.

        :param loader: A single argument lambda expecting a canonical path that will return
            either a `File` wrapped in a `Result` or raise a `FileNotFoundError`.
        :param canonical_path: The path that the lambda will be querying.
        """
        self._loader: Callable[[CanonicalPath], Result[File]] = loader
        self._canonical_path: CanonicalPath = canonical_path

    def __call__(self) -> Result[File]:
        """
        Invoke this `FileLoader`, and obtain a `Result` containing a File` or an `FileNotFoundError` if it cannot be found.

        :raises FileNotFoundError: If the `File` cannot be loaded.
        :return: The `File` that was loaded
        """
        return self._loader(self._canonical_path)

    @property
    def canonical_path(self) -> CanonicalPath:
        return self._canonical_path
