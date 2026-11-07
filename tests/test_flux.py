import pytest

from data_tools.query import FluxQuery

RANGE = ("2024-07-16T07:00:00Z", "2024-07-16T08:00:00Z")


def test_statements_compile_in_priority_order():
    query = FluxQuery() \
        .keep(["_field", "_value"]) \
        .last() \
        .filter_fields(["PackCurrent", "TotalPackVoltage"]) \
        .range(*RANGE) \
        .from_bucket("CAN_log")

    assert query.compile_query() == (
        'from(bucket: "CAN_log") '
        '|> range(start: 2024-07-16T07:00:00Z, stop: 2024-07-16T08:00:00Z) '
        '|> filter(fn:(r) => r._field == "PackCurrent" or r._field == "TotalPackVoltage") '
        '|> last() '
        '|> keep(columns: ["_field", "_value"]) '
    )


def test_limit():
    query = FluxQuery().from_bucket("CAN_log").range(*RANGE).limit(1)

    assert query.compile_query().endswith("|> limit(n: 1) ")


def test_single_field_filter_matches_filter():
    by_fields = FluxQuery().from_bucket("b").filter_fields(["PackCurrent"]).compile_query()
    by_filter = FluxQuery().from_bucket("b").filter(field="PackCurrent").compile_query()

    assert by_fields == by_filter


def test_invalid_arguments_are_rejected():
    with pytest.raises(AssertionError):
        FluxQuery().filter_fields([])

    with pytest.raises(AssertionError):
        FluxQuery().limit(0)
