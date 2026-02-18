from dataclasses import dataclass
from bisect import bisect_right
from typing import Optional
from datetime import date
import tomllib



@dataclass(frozen=True)
class Interval:
    start: date
    end: Optional[date]  # None => Ongoing
    value: tuple


@dataclass(frozen=True)
class VersionedTable:
    _intervals: dict[str, list[Interval]]

    @staticmethod
    def from_dict(raw: dict[str, dict[str, tuple]]) -> "VersionedTable":
        sections: list[tuple[date, dict[str, tuple]]] = []
        for k, v in raw.items():
            try:
                iso_date = date.fromisoformat(k)
            except ValueError as e:
                raise ValueError(f"{k} is not a valid date") from e

            sections.append((iso_date, v))

        sections.sort(key=lambda x: x[0])

        intervals: dict[str, list[Interval]] = {}
        active: dict[str, tuple[date, tuple[str]]] = {}

        # We'll march through each section and maintain a dictionary of every
        # name–data pair that we encounter and track the interval that
        # each pairing was "active" for.

        for i, (eff_date, mapping) in enumerate(sections):
            # Close intervals for names that disappeared to track
            # that they are no longer active.
            to_remove = []
            for name, (start, value) in active.items():
                if name not in mapping:
                    intervals.setdefault(name, []).append(
                        Interval(start, eff_date, value)
                    )
                    to_remove.append(name)

            for name in to_remove:
                del active[name]

            # Add/update names
            for name, value in mapping.items():
                if name in active:
                    old_start, old_value = active[name]

                    # If the name–data pair has changed, close the existing
                    # interval and start a new one for the new pair.
                    if old_value != value:
                        intervals.setdefault(name, []).append(
                            Interval(old_start, eff_date, old_value)
                        )
                        active[name] = (eff_date, value)
                else:
                    active[name] = (eff_date, value)

        # Close all remaining intervals (with `None` as a sentinel to mark them as current).
        for name, (start, value) in active.items():
            intervals.setdefault(name, []).append(Interval(start, None, value))

        return VersionedTable(intervals)

    def lookup(self, name: str, on: date | str) -> tuple:
        if isinstance(on, str):
            try:
                on = date.fromisoformat(on)
            except ValueError as e:
                raise ValueError(f"{on} is not a valid date") from e

        ivals = self._intervals.get(name)
        if not ivals:
            raise UnboundLocalError(f"Unknown name '{name}'")

        # The interval to which `on` belongs to will be the interval
        # with the start date closest (in the past) to `on`.
        starts = [iv.start for iv in ivals]
        i = bisect_right(starts, on) - 1

        # i < 0 means that there is no interval with a start date
        # before `on` with `name` as a defined name.
        if i < 0:
            earliest = ivals[0].start.isoformat()
            raise KeyError(
                f"No mapping for '{name}' on {on.isoformat()} (earliest is {earliest})"
            )

        iv = ivals[i]

        # `None` corresponds to "ongoing". Check that `name` didn't expire.
        if iv.end is not None and on >= iv.end:
            raise KeyError(
                f"'{name}' was deprecated after {iv.end.isoformat()}"
            )

        return iv.value

    @staticmethod
    def from_toml_file(path: str) -> "VersionedTable":
        with open(path, "rb") as f:
            raw = tomllib.load(f)

        return VersionedTable.from_dict(raw)


# --- Example usage ---
if __name__ == "__main__":

    lut = VersionedTable.from_toml_file("signals.toml")

    print(lut.lookup("VehicleVelocity", date(2024, 6, 1)))  # ["VehicleVelocity", "m/s"]
    print(lut.lookup("BatteryVoltage", date(2025, 6, 1)))   # ["TotalPackVoltage", "V"]
