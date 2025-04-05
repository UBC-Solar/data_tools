from data_tools.schema import Result, UnwrappedError
import pytest


def test_result_ok():
    data = {
        "some_data": 10,
        "some_more_data": 11
    }

    result_ok = Result.Ok(data)

    # Truth value should be `True` since the `Result` is of type `Ok`
    assert result_ok

    assert result_ok.unwrap() == data


def test_result_err():
    result_err = Result.Err(RuntimeError("Oh no!"))

    # Truth value should be `False` since the `Result` is of type `Err`
    assert not result_err

    # Ensure that an Unwrapped Error is raised
    with pytest.raises(UnwrappedError):
        result_err.unwrap()


def test_result_wrap_failure():
    error = RuntimeError("Oh no!")
    data = {
        "some_data": 10,
        "some_more_data": 11
    }

    # Trying to wrap an error as data should raise `TypeError`
    with pytest.raises(TypeError):
        Result.Ok(error)

    # Trying to wrap data as an error should raise `TypeError`
    with pytest.raises(TypeError):
        Result.Err(data)
