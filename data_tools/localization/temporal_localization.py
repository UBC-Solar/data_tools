from data_tools.localization.localization import Localization
from datetime import datetime, timedelta


class TemporalLocalization(Localization):
    def localize(self, query_datetime: datetime) -> timedelta:
        """
        Return the timedelta to subtract from InfluxDB query ranges to account for timezone reporting errors in InfluxDB.
        The same error should be added to returned data ranges to amend them.
        """
        shift_str: str = str(self._localization_table.lookup("shift", query_datetime.date())) # Will be a one-tuple

        return timedelta(hours=int(shift_str))
