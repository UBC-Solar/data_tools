from data_tools.localization.localization import Localization
from datetime import datetime


class SpatialLocalization(Localization):
    def localize(self, query_datetime: datetime) -> tuple[list, str]:
        """
        Return the timedelta to add to InfluxDB query ranges to account for timezone reporting errors in InfluxDB.
        The same error should be subtracted from returned data ranges to amend them.
        """
        coords, name = self._localization_table.lookup("position", query_datetime.date())

        return coords, name
