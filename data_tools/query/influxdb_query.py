from data_tools.localization import InfluxDBLanguageLocalization, CanonicalName, TemporalLocalization
from influxdb_client import InfluxDBClient as _InfluxDBClient
from data_tools.collections.time_series import TimeSeries
from datetime import datetime, timezone
from data_tools.utils.times import ensure_utc
from data_tools.query.flux import FluxQuery
from pydantic import BaseModel, Field
from typing import Any, Iterable, Optional, Type
from dotenv import load_dotenv
import pandas as pd
import os


DEFAULT_INFLUXDB_URL = "http://influxdb.telemetry.ubcsolar.com"


class TimeSeriesTarget(BaseModel):
    """
    Encapsulates the data required to completely query a specific time series from InfluxDB.
    """
    name: str
    field: str
    measurement: str
    frequency: float = Field(gt=0)
    units: str
    car: str
    bucket: str
    description: str = Field(default_factory=str)
    meta: dict = Field(default_factory=dict)


class InfluxDBClient:
    """
    This class encapsulates a connection to an InfluxDB database.
    """

    def __init__(
            self,
            influxdb_org=None,
            influxdb_token=None,
            url=None,
            timeout=10,
            temporal_localization: Optional[Type[TemporalLocalization]] = None,
            language_localization: Optional[Type[InfluxDBLanguageLocalization]] = None,
            enable_gzip: bool = False
        ):
        """
        Create a connection to the InfluxDB database.

        :param influxdb_org: The name of the InfluxDB organization.
        :param influxdb_token: The API Token to the InfluxDB database.
        :param url: The URL to the InfluxDB database, default is "http://influxdb.telemetry.ubcsolar.com"
        :param timeout: The request timeout in seconds, default is 10 seconds. Applies to every request this client
            makes, so use separate clients where some requests need a longer timeout than others.
        :param temporal_localization: The type of temporal localization to use, default is TemporalLocalization.
        :param language_localization: The type of language localization to use, default is LanguageLocalization.
        :param enable_gzip: Compress requests and responses. Off by default: it costs more than it saves on the
            small, frequent responses of polling queries.
        """
        if influxdb_token is None or influxdb_org is None:
            load_dotenv()

            influxdb_token = os.getenv("INFLUX_TOKEN")
            influxdb_org = os.getenv("INFLUX_ORG")

        self._influx_org = influxdb_org
        url = DEFAULT_INFLUXDB_URL if url is None else url

        self._language_localization = language_localization if language_localization else InfluxDBLanguageLocalization
        self._temporal_localization = temporal_localization if temporal_localization else TemporalLocalization

        self._client = _InfluxDBClient(
            url=url, org=influxdb_org, token=influxdb_token, timeout=int(timeout * 1000), enable_gzip=enable_gzip
        )

    @staticmethod
    def _flux_time(dt: datetime) -> str:
        """
        Format a timezone-aware datetime as a Flux (RFC 3339, UTC) timestamp.

        :raises ValueError: If ``dt`` is naive.
        """
        if dt.tzinfo is None:
            raise ValueError("Timestamps must be timezone-aware!")
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    def ping(self) -> bool:
        """
        Check that the InfluxDB server is reachable.

        :return: ``True`` if the server responded, ``False`` otherwise.
        """
        return bool(self._client.ping())

    def bucket_exists(self, bucket: str) -> bool:
        """
        Check that a bucket exists and is visible to this client's token and organization.

        :param bucket: The name of the bucket.
        :raises influxdb_client.rest.ApiException: If the server rejected the request (e.g. a bad token).
        """
        return self._client.buckets_api().find_bucket_by_name(bucket) is not None

    def has_data(self, bucket: str, start: datetime, stop: datetime) -> bool:
        """
        Check whether a bucket holds any point at all in ``[start, stop)``. Only the first point found is read,
        so this is cheap even over a long range.

        Like ``query_time_series``, the range is temporally localized: give true times, not InfluxDB's.

        :param bucket: The bucket to look in.
        :param start: The (timezone-aware) start of the range.
        :param stop: The (timezone-aware) end of the range.
        """
        shift = self._temporal_localization.localize(start)
        query = FluxQuery() \
            .from_bucket(bucket) \
            .range(start=self._flux_time(start - shift), stop=self._flux_time(stop - shift)) \
            .limit(1)

        records = self._client.query_api().query_stream(query.compile_query(), org=self._influx_org)
        return next(iter(records), None) is not None

    def query_last_values(
            self,
            bucket: str,
            fields: Iterable[str],
            start: datetime,
            stop: datetime
    ) -> dict[str, tuple[datetime, Any] | None]:
        """
        Get the most recent point of each of ``fields`` in ``[start, stop)``, with a single query. Meant for
        polling live data, so results are streamed rather than built into tables or DataFrames.

        Like ``query_time_series``, times are temporally localized: the range is given, and the times are returned,
        as true times rather than InfluxDB's.

        :param bucket: The bucket to query.
        :param fields: The names of the fields, as stored in InfluxDB.
        :param start: The (timezone-aware) start of the range.
        :param stop: The (timezone-aware) end of the range.
        :return: Each field's ``(time, value)``, or ``None`` for a field with no point in the range.
        """
        fields = tuple(fields)
        out: dict[str, tuple[datetime, Any] | None] = {field: None for field in fields}
        if not fields:
            return out

        shift = self._temporal_localization.localize(start)
        query = FluxQuery() \
            .from_bucket(bucket) \
            .range(start=self._flux_time(start - shift), stop=self._flux_time(stop - shift)) \
            .filter_fields(fields) \
            .last() \
            .keep(["_field", "_value", "_time"])

        records = self._client.query_api().query_stream(query.compile_query(), org=self._influx_org)
        for record in records or ():
            if record is not None and record.get_field() in out:
                out[record.get_field()] = (record.get_time() + shift, record.get_value())

        return out

    def get_buckets(self) -> list[str]:
        """
        Obtain the available buckets.
        :return: list of available buckets
        """
        result = self._client.buckets_api().find_buckets()
        buckets = [bucket.name for bucket in result.buckets]
        return list(buckets)

    def get_measurements_in_bucket(self, bucket: str) -> list[str]:
        """
        Obtain a list of the possible measurements within a bucket.

        :param bucket: the bucket that will be queried. Must exist.
        :return: a list of available measurements in `bucket`.
        """
        query = f'''
                import "influxdata/influxdb/schema"
                schema.measurements(bucket: "{bucket}")
                '''

        result = self._client.query_api().query(org=self._influx_org, query=query)
        measurements = {record.get_value() for table in result for record in table.records}

        return list(measurements)

    def get_fields_in_measurement(self, bucket: str, measurement: str) -> list[str]:
        """
        Obtain the possible fields within a measurement and bucket.
        :param bucket: the bucket that will be queried. Must exist.
        :param measurement: the measurement that will be queried. Must exist.
        :return:
        """
        # NOTE: This will need to be updated in 2054 to query all data properly
        field_query = f'''from(bucket: "{bucket}")
                      |> range(start: -30y)
                      |> filter(fn: (r) => r["_measurement"] == "{measurement}")
                      |> group(columns: ["_field"])
                      |> distinct(column: "_field")'''

        field_result = self._client.query_api().query(org=self._influx_org, query=field_query, params={"timeout": 20})
        fields = {record.get_value() for table in field_result for record in table.records}

        return list(fields)

    def get_cars_in_measurement(self, bucket: str, measurement: str) -> list[str]:
        """
        Obtain the different cars within a measurement and bucket.
        :param bucket: the bucket that will be queried. Must exist.
        :param measurement: the measurement that will be queried. Must exist.
        :return:
        """
        # NOTE: This will need to be updated in 2054 to query all data properly
        field_query = f'''from(bucket: "{bucket}")
                      |> range(start: -30y)
                      |> distinct(column: "car")'''

        cars_result = self._client.query_api().query(org=self._influx_org, query=field_query)
        cars = {record.get_value() for table in cars_result for record in table.records}

        return list(cars)

    def query_dataframe(self, query: FluxQuery) -> pd.DataFrame:
        """
        Submit a Flux query, and return the result as a DataFrame.

        :param FluxQuery query: the query which will be submitted
        :return: the resulting data as a DataFrame
        """
        compiled_query = query.compile_query()
        compiled_query += ' |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value") '

        return self._client.query_api().query_data_frame(compiled_query)

    def query_series(self, start: datetime, stop: datetime, field: str, bucket: str = "CAN_log",
                     car: str = "Brightside", measurement: str = None):
        """
        Query the database for a specific field, over a certain time range.
        The data will be returned as a DataFrame.

        :param start: the start time of the query as an ISO 8601-compliant string, such as "2024-06-30T23:00:00Z".
        :param stop: the end time of the query as an ISO 8601-compliant string, such as "2024-06-30T23:00:00Z".
        :param field: the field which is to be queried.
        :param str bucket: the bucket which will be queried
        :param car: the car which data is being queried for, default is "Brightside".
        :return: a TimeSeries of the resulting time-series data
        """
        utc_start = ensure_utc(start)
        utc_end = ensure_utc(stop)

        # Make the query
        query = FluxQuery() \
            .from_bucket(bucket) \
            .range(start=utc_start.isoformat(), stop=utc_end.isoformat()) \
            .filter(field=field) \
            .car(car)

        if measurement:
            query = query.filter(measurement=measurement)
        query_df = self.query_dataframe(query)

        if isinstance(query_df, list):
            raise ValueError("Query returned multiple fields! Please refine your query.")

        if len(query_df) == 0:
            raise ValueError("Query is empty! Verify that the data is visible on InfluxDB for the queried bucket.")

        return query_df

    def query_time_series(self, start: datetime, stop: datetime, field: str | CanonicalName, bucket: str = "CAN_log",
                          car: str = "Brightside", granularity: float = 0.1, units: str = "",
                          measurement: str = None) -> TimeSeries:
        """
        Query the database for a specific field, over a certain time range.
        The data will be processed into a TimeSeries, which has homogenous and evenly-spaced (temporally) elements.
        Data will be re-interpolated to have temporal granularity of ``granularity``.

        :param start: the start time of the query as an ISO 8601-compliant string, such as "2024-06-30T23:00:00Z".
        :param stop: the end time of the query as an ISO 8601-compliant string, such as "2024-06-30T23:00:00Z".
        :param field: the field which is to be queried.
        :param str bucket: the bucket which will be queried
        :param car: the car which data is being queried for, default is "Brightside".
        :param granularity: the temporal granularity of the resulting TimeSeries in seconds, default is 0.1s.
        :param units: the units of the returned data, optional.
        :return: a TimeSeries of the resulting time-series data
        """
        if isinstance(field, CanonicalName):
            field_str, measurement, units, frequency = self._language_localization.localize(field, start.date())
            granularity = 1 / frequency
        else:
            field_str = field

        timezone_fix = self._temporal_localization.localize(start)
        start = start - timezone_fix
        stop = stop - timezone_fix

        query_df = self.query_series(start, stop, field_str, bucket, car, measurement)
        time_series = TimeSeries.from_query_dataframe(query_df, granularity, field_str, units)

        time_series._start = time_series._start + timezone_fix
        time_series._stop = time_series._stop + timezone_fix

        return time_series

    def close(self):
        self._client.close()


if __name__ == "__main__":
    start_time = datetime(2024, 6, 16, 10, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2024, 8, 16, 23, 0, 0, tzinfo=timezone.utc)

    client = InfluxDBClient()

    pack_voltage: TimeSeries = client.query_time_series(start_time, end_time, "TotalPackVoltage", units="V",
                                                        measurement="BMS")

    pack_voltage.plot()
