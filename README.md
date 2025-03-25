# UBC Solar Data Tools

<!-- marker-index-start -->

[![Documentation Status](https://readthedocs.org/projects/ubc-solar-data-tools/badge/?version=latest)](https://ubc-solar-data-tools.readthedocs.io/en/latest/?badge=latest)

A collection of data querying, analysis, and structuring tools.

## Requirements

Versions for dependencies (except Python) indicated are recommended

* Git [^1]
* Python >=3.9 [^2]
* Poetry >=1.8.3 [^3]

### System Requirements

To use the `data_tools.query` module, you'll need access to the appropriate endpoints. UBC Solar members can ask their Lead to join the UBC Solar VPN which will allow them to access the pre-configured (default) endpoints. 

Otherwise, you'll need to configure relevant URLs (ex. set the InfluxDB URL when creating a `DBClient` to the appropriate endpoint).

## Installation

First, clone this repository.

```bash
git clone https://github.com/UBC-Solar/data_tools.git
```
Then, create and activate a virtual environment.
This project uses Poetry for dependency management. Next, use Poetry to install dependencies, with `--no-root` so that the `data_tools` package does not itself get installed into your virtual environment. This can be omitted if you're sure you know what you are doing. 

```bash
poetry install --no-root
```

Optionally, you can install dependencies for building the documentation and running tests.
```bash
poetry install --no-root --with docs --with test
```

## Getting Started
An example of querying data from Sunbeam (along with the involved data types)
```python
from data_tools.query import SunbeamClient
from data_tools.schema import CanonicalPath, Result, UnwrappedError
from data_tools.collections import TimeSeries

# CanonicalPath represents a path in the Sunbeam filesystem
motor_power_path = CanonicalPath(   
    origin="production",              # Use the production pipeline
    event="FSGP_2024_Day_1",          # Get from Day 1
    source="power",                   # Power Stage contains power calculations
    name="MotorPower"                 # Get MotorPower from the Power Stage
)
motor_power_day_one_result: Result = SunbeamClient().get_file(path=motor_power_path)

# The Result type can contain an error or the data, so unwrap it to reveal the data (if the query worked!)
# MotorPower is a TimeSeries
try:
    motor_power_day_one: TimeSeries = motor_power_day_one_result.unwrap()

# If `unwrap` is to reveal an error, it will raise an `UnwrappedError`.
except UnwrappedError as e:
    print("Query failed!")
    raise e

```

Example of querying data from InfluxDB and plotting it as a `TimeSeries`.

> When the `InfluxClient` class is imported, `data_tools` will attempt to locate a `.env` file in order to acquire an InfluxDB API token. If you do not have a `.env` or it is missing an API token, you will not be able to query data. UBC Solar members can acquire an API token by speaking to their Team Lead.

```python
from data_tools.collections.time_series import TimeSeries
from data_tools.query.influxdb_query import DBClient

client = DBClient()

# ISO 8601-compliant times corresponding to pre-competition testing
start = "2024-07-07T02:23:57Z" 
stop = "2024-07-07T02:34:15Z"

# We can, in one line, make a query to InfluxDB and parse 
# the data into a powerful format: the `TimeSeries` class.
voltage_data: TimeSeries = client.query_time_series(
    start=start,
    stop=stop,
    field="TotalPackVoltage",
    units="V"
)

# Plot the data
voltage_data.plot()
```

Example of using the `FluxQuery` module to make a Flux query that selects and aggregates some data.
We will use the `FluxStatement` class to construct a custom Flux statement, as the `aggregateWindow` statement is not yet included by this API.

```python
from data_tools.query.flux import FluxQuery, FluxStatement
from data_tools.query.influxdb_query import DBClient
from data_tools.collections.time_series import TimeSeries
import pandas as pd

client = DBClient()

# ISO 8601-compliant times corresponding to pre-competition testing
start = "2024-07-07T02:23:57Z" 
stop = "2024-07-07T02:34:15Z"

# The priority argument defines "where" in the Flux query the statement will get placed. Higher priority -> later
aggregate_flux_statement = FluxStatement('aggregateWindow(every: 10m, fn: mean, createEmpty: false)', priority=5)

query = FluxQuery()\
        .range(start=start, stop=stop)\
        .filter(field="VehicleVelocity")\
        .inject_raw(aggregate_flux_statement)

# We can inspect the Flux query
print(query.compile_query())

# Make the query, getting the data as a DataFrame
query_dataframe: pd.DataFrame = client.query_dataframe(query)

# Now, convert the data into a TimeSeries
measurement_period: float = 1.0 / 5  # VehicleVelocity is a 5Hz measurement, so period is 1.0 / 5Hz.
vehicle_velocity = TimeSeries.from_query_dataframe(query_dataframe, measurement_period, 
                                                   field="VehicleVelocity", 
                                                   units="m/s")

# Plot the data
vehicle_velocity.plot()
```

## Appendix

[^1]: use `git --version` to verify version

[^2]: use `python3 --version` to verify version

[^3]: use `poetry --version` to verify version

<!-- marker-index-end -->
