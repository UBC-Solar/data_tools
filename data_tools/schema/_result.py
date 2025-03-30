from enum import StrEnum
from typing import TypeVar


T = TypeVar("T")


class UnwrappedError(Exception):
    pass


class Result[T]:
    """
    Algebraic datatype that can either represent a successful result of some operation,
    or a failure.

    A `Result` can be unwrapped to retrieve the result or raise the exception raised wrapped in a `UnwrappedError`.
    """
    class ResultType(StrEnum):
        Ok = "Ok"
        Err = "Err"

    def __init__(self, result: T, result_type: ResultType):
        """
        Do not call this directly.
        Call `Result.Ok()` or `Result.Err()`.

        :param T result: Data or exception to be wrapped.
        :param ResultType result_type: Whether the result is data or an exception.
        :raises TypeError: If trying to wrap data as an `Exception` or an `Exception` as data
        """
        if result_type == Result.ResultType.Ok and isinstance(result, Exception):
            raise TypeError("Cannot wrap an Exception with Result.Ok()! Wrap it with Result.Err() instead.")

        if not isinstance(result, Exception) and result_type == Result.ResultType.Err:
            raise TypeError("Cannot wrap a non-Exception with Result.Err()! Wrap it with Result.Ok() instead.")

        self._result = result
        self._result_type = result_type

    @staticmethod
    def Ok(result: T):
        """
        Wrap a successful result in a `Result`.

        :param result: The successful result to be wrapped
        :return: A `Result` instance wrapping `result`.
        :raises TypeError: If `result` is an `Exception`.
        """
        return Result(result, Result.ResultType.Ok)

    @staticmethod
    def Err(error: Exception):
        """
        Wrap an error/failure/exception in a `Result`.

        :param error: The error to be wrapped
        :return: A `Result` instance wrapping `error`.
        :raises TypeError: If `error` is not an `Exception`.
        """
        return Result(error, Result.ResultType.Err)

    def unwrap(self) -> T | UnwrappedError:
        """
        Unwrap this `Result` to reveal a successful result or an error.

        :raises UnwrappedError: If an error is unwrapped
        :return: The result, if it was successful
        """
        if self._result_type == self.ResultType.Ok:
            return self._result

        # We must have self._result_type == Result.ResultType.Err
        raise UnwrappedError from self._result

    def __bool__(self):
        return True if self._result_type == self.ResultType.Ok else False
