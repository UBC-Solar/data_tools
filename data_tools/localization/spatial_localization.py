from data_tools.localization.localization import Localization
from datetime import datetime


class SpatialLocalization(Localization):
    @classmethod
    def localize(cls, query_datetime: datetime) -> tuple[list, str]:
        """
        Return the timedelta to add to InfluxDB query ranges to account for timezone reporting errors in InfluxDB.
        The same error should be subtracted from returned data ranges to amend them.
        """
        inst = cls._get()
        coords, name = inst._localization_table.lookup("position", query_datetime.date())

        return coords, name
