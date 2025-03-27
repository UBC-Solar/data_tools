from data_tools.query.flux import FluxQuery
from data_tools.utils.times import ensure_utc
from data_tools.collections.time_series import TimeSeries
from pydantic import BaseModel, Field
from influxdb_client import InfluxDBClient
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
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


class DBClient:
    """
    This class encapsulates a connection to an InfluxDB database.
    """

    def __init__(self, influxdb_org=None, influxdb_token=None, url=None):
        """
        Create a connection to the InfluxDB database.

        :param influxdb_org: The name of the InfluxDB organization.
        :param influxdb_token: The API Token to the InfluxDB database.
        :param url: The URL to the InfluxDB database, default is "http://influxdb.telemetry.ubcsolar.com"
        """
        if influxdb_token is None or influxdb_org is None:
            load_dotenv()

            influxdb_token = os.getenv("INFLUX_TOKEN")
            influxdb_org = os.getenv("INFLUX_ORG")

        self._influx_org = influxdb_org
        url = DEFAULT_INFLUXDB_URL if url is None else url

        self._client = InfluxDBClient(url=url, org=influxdb_org, token=influxdb_token)

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
        field_query = f'''from(bucket: "{bucket}")
                      |> range(start: -30d)
                      |> filter(fn: (r) => r["_measurement"] == "{measurement}")
                      |> group(columns: ["_field"])
                      |> distinct(column: "_field")'''

        field_result = self._client.query_api().query(org=self._influx_org, query=field_query)
        fields = {record.get_value() for table in field_result for record in table.records}

        return list(fields)

    def get_cars_in_measurement(self, bucket: str, measurement: str) -> list[str]:
        """
        Obtain the different cars within a measurement and bucket.
        :param bucket: the bucket that will be queried. Must exist.
        :param measurement: the measurement that will be queried. Must exist.
        :return:
        """
        field_query = f'''from(bucket: "{bucket}")
                      |> range(start: -30d)
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
        # InfluxDB has an issue where PST timestamps were interpreted as UTC. So, we need to mutate
        # the timestamps to represent a time -7 hours to compensate for the UTC offset of +7.

        utc_start = ensure_utc(start) - timedelta(hours=7)
        utc_end = ensure_utc(stop) - timedelta(hours=7)

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

    def query_time_series(self, start: datetime, stop: datetime, field: str, bucket: str = "CAN_log",
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
        query_df = self.query_series(start, stop, field, bucket, car, measurement)

        return TimeSeries.from_query_dataframe(query_df, granularity, field, units)


if __name__ == "__main__":
    start_time = datetime(2024, 6, 16, 10, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2024, 8, 16, 23, 0, 0, tzinfo=timezone.utc)

    client = DBClient()

    pack_voltage: TimeSeries = client.query_time_series(start_time, end_time, "TotalPackVoltage", units="V",
                                                        measurement="BMS")

    pack_voltage.plot()
