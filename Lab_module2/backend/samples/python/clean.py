"""Temperature conversion utilities."""

from collections.abc import Iterable


def celsius_to_fahrenheit(celsius: float) -> float:
    """Convert a temperature from Celsius to Fahrenheit."""
    return celsius * 9 / 5 + 32


def average_temperature(readings: Iterable[float]) -> float:
    """Return the mean of the readings; raise ValueError if there are none."""
    values = list(readings)
    if not values:
        raise ValueError("At least one reading is required.")
    return sum(values) / len(values)
