from enum import StrEnum
from typing import Any


class UnwrappedError(Exception):
    pass


class Result:
    """
    Algebraic datatype that can either represent a successful result of some operation,
    or a failure.

    A `Result` can be unwrapped to retrieve the result or raise the exception raised wrapped in a `UnwrappedError`.
    """
    class ResultType(StrEnum):
        Ok = "Ok"
        Err = "Err"

    def __init__(self, result: Any, result_type: ResultType):
        self._result = result
        self._result_type = result_type

    @staticmethod
    def Ok(result: Any):
        """
        Wrap a successful result in a `Result`.

        :param result: the successful result to be wrapped
        :return: a `Result` instance wrapping `result`.
        """
        return Result(result, Result.ResultType.Ok)

    @staticmethod
    def Err(error: Exception):
        """
        Wrap an error/failure/exception in a `Result`.

        :param error: the error to be wrapped
        :return: a `Result` instance wrapping `error`.
        """
        return Result(error, Result.ResultType.Err)

    def unwrap(self):
        """
        Unwrap this `Result` to reveal a successful result or an error.

        :raises UnwrappedError: if an error is unwrapped
        :return: the result, if it was successful
        """
        if self._result_type == self.ResultType.Ok:
            return self._result

        elif self._result_type == self.ResultType.Err:
            raise UnwrappedError from self._result

    def __bool__(self):
        return True if self._result_type == self.ResultType.Ok else False
