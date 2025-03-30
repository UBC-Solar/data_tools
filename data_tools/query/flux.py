"""
ORM-like query-building tools for Flux, InfluxDB's custom querying language.

See InfluxDB's documentation for more details: https://docs.influxdata.com/influxdb/v2/query-data/flux/
"""
from typing import Callable, List
from dateutil import parser


# Function signature required for a parameterized Flux statement formatter
FluxFormatter = Callable[[List[str]], str]


class FluxStatement:
    """
    Represent and construct a single Flux statement. such as
    ``"filter(fn:(r) => r._field == "TotalPackVoltage")``.

    A FluxStatement is the atomic unit that can be composed into a FluxQuery, which is capable of querying our
    InfluxDB database.
    """
    def __init__(self, statement: str, priority: int):
        assert isinstance(statement, str), f"Statement must be of type `str`, not {type(statement)}!"
        assert (isinstance(priority, int) and priority >= 0), "Priority must be a non-negative integer!"

        self._statement: str = statement
        self._priority: int = priority

    @property
    def priority(self) -> int:
        """
        The priority of this statement, which determines its position in a Flux query. Lower number indicates
        higher priority.
        """
        return self._priority

    @property
    def statement(self) -> str:
        """
        The canonical string representation of this Flux query.
        """
        return self._statement


class ParameterizedFluxStatement:
    """
    Represent and encapsulate a parameterized Flux statement.

    An instance of this class can be instantiated statically as a part
    of a module to provide built-in support for standard Flux statements.
    """
    def __init__(self, formatter: FluxFormatter, priority: int):
        """
        Instantiate a ParameterizedFluxStatement.

        :param FluxFormatter formatter: must be a ``Callable`` that takes in a ``List[str]``, the parameters to the Flux query, and returns a ``str``, which is the Flux query injected with parameters.
        :param int priority: must be a non-negative integer that indicates the priority of the Flux statement encapsulated by this class.
        """
        assert isinstance(formatter, Callable), "formatter must have signature `Callable[[List[str]], str]`!"
        assert (isinstance(priority, int) and priority >= 0), "Priority must be a non-negative integer!"

        self._formatter: FluxFormatter = formatter
        self._priority: int = priority

    def get(self, parameters: List[str]) -> FluxStatement:
        """
        Inject the ``parameters`` into this ``ParameterizedFluxStatement`` to produce a concrete ``FluxStatement``.

        :param List[str] parameters: the parameters to be injected, must match the number of paramaters expected by the formatter used to construct this ``ParameterizedFluxStatement``.
        :return: the concrete ``FluxStatement``
        """
        return FluxStatement(self._formatter(parameters), self.priority)

    @property
    def priority(self) -> int:
        """
        Obtain the priority that concrete ``FluxStatement``s produced by this ``ParameterizedFluxStatement`` will inherit.
        """
        return self._priority


class FluxQuery:
    """
    Represent a Flux query: a collection of ``FluxStatement`` chained together to form a complete query
    to our InfluxDB database.

    Supports method chaining for fluent construction of queries.
    """
    _from_bucket_formatter: FluxFormatter = lambda args: f'from(bucket: "{args[0]}") '
    _from_bucket_statement = ParameterizedFluxStatement(formatter=_from_bucket_formatter, priority=0)

    _unbound_range_formatter: FluxFormatter = lambda args: f'range(start: {args[0]}) '
    _unbound_range_statement = ParameterizedFluxStatement(formatter=_unbound_range_formatter, priority=1)

    _bound_range_formatter: FluxFormatter = lambda args: f'range(start: {args[0]}, stop: {args[1]}) '
    _bound_range_statement = ParameterizedFluxStatement(formatter=_bound_range_formatter, priority=1)

    _filter_measurement_formatter: FluxFormatter = lambda args: f'filter(fn:(r) => r._measurement == "{args[0]}") '
    _filter_measurement_statement = ParameterizedFluxStatement(formatter=_filter_measurement_formatter, priority=2)

    _filter_field_formatter: FluxFormatter = lambda args: f'filter(fn:(r) => r._field == "{args[0]}") '
    _filter_field_statement = ParameterizedFluxStatement(formatter=_filter_field_formatter, priority=3)

    _car_formatter: FluxFormatter = lambda args: f'filter(fn:(r) => r.car == "{args[0]}") '
    _car_statement = ParameterizedFluxStatement(formatter=_car_formatter, priority=3)

    def __init__(self):
        """
        Instantiate an empty Flux query.
        :return: this FluxQuery with the new statement inserted
        """
        self._statements: List[FluxStatement] = []

    def from_bucket(self, bucket: str):
        """
        Specify the bucket that will be queried from.

        :param str bucket: bucket name
        :return: this FluxQuery with the new statement inserted
        """
        assert isinstance(bucket, str), f"Bucket must be a `str`, not {type(bucket)}!"

        new_statement = FluxQuery._from_bucket_statement.get([bucket])
        self._statements.append(new_statement)

        return self

    def range(self, start: str, stop: str = None):
        """
        Specify the time range of the time-series data to query.

        :param start: start time of the time range as an ISO 8601 compliant string.
        :param stop: stop time of the time range as an ISO 8601 compliant string, optional.
        :return: this FluxQuery with the new statement inserted
        """
        # Verify that `start` and `stop` are valid ISO 8601 dates.
        try:
            parser.parse(start)
            if stop is not None:
                parser.parse(stop)
        except parser.ParserError:
            raise ValueError("Invalid dates provided to range! Must be of ISO 8601 format.")

        if stop is not None:
            new_statement = FluxQuery._bound_range_statement.get([start, stop])
            self._statements.append(new_statement)

        else:
            new_statement = FluxQuery._unbound_range_statement.get([start])
            self._statements.append(new_statement)

        return self

    def filter(self, measurement: str = None, field: str = None):
        """
        Apply a filter to the query. Any or both of ``measurement`` and ``field`` may be specified and both filters will
        be applied. No effect if neither is.

        :param str measurement: measurement to filter for, such as "BMS"
        :param str field: field to filter for, such as "PackCurrent".
        :return: this FluxQuery with the new statement inserted
        """
        if measurement is not None:
            new_statement = FluxQuery._filter_measurement_statement.get([measurement])
            self._statements.append(new_statement)

        if field is not None:
            new_statement = FluxQuery._filter_field_statement.get([field])
            self._statements.append(new_statement)

        return self

    def car(self, car: str):
        """
        Filter for data from a specific car.

        :param car: car name, such as "Brightside".
        :return: this FluxQuery with the new statement inserted
        """
        assert isinstance(car, str), f"Car must be a `str`, not {type(car)}!"

        new_statement = FluxQuery._car_statement.get([car])
        self._statements.append(new_statement)

        return self

    def inject_raw(self, statement: FluxStatement):
        """
        Inject a FluxStatement into this query. This may be necessary if the
        Flux statement is not available with the existing built-in Flux statements.

        :param statement:
        :return: this FluxQuery with the new statement inserted
        """
        self._statements.append(statement)

        return self

    def compile_query(self) -> str:
        """
        Compile this object into a Flux query, as a string.

        :return: the canonical string representation of this Flux query, with statements ordered according to priority.
        """
        sorted_statements = sorted(self._statements, key=lambda statement: statement.priority)

        compiled_statement = sorted_statements.pop(0).statement
        for flux_statement in sorted_statements:
            compiled_statement += f"|> {flux_statement.statement}"

        return compiled_statement
