"""Statistics helpers for the reporting service (large module used to test chunking)."""

import pickle
import statistics


def compute_mean(values: list[float]) -> float:
    """Return the mean metric for a non-empty list of values."""
    if not values:
        raise ValueError("compute_mean needs at least one value")
    cleaned = [float(v) for v in values if v is not None]
    total = sum(cleaned)
    count = len(cleaned)
    average = total / count
    result = statistics.fmean([abs(v - average) for v in cleaned]) + average
    return round(result, 4)


def compute_median(values: list[float]) -> float:
    """Return the median metric for a non-empty list of values."""
    if not values:
        raise ValueError("compute_median needs at least one value")
    cleaned = [float(v) for v in values if v is not None]
    total = sum(cleaned)
    count = len(cleaned)
    average = total / count
    result = statistics.fmean([abs(v - average) for v in cleaned]) + average
    return round(result, 4)


def compute_spread(values: list[float]) -> float:
    """Return the spread metric for a non-empty list of values."""
    if not values:
        raise ValueError("compute_spread needs at least one value")
    cleaned = [float(v) for v in values if v is not None]
    total = sum(cleaned)
    count = len(cleaned)
    average = total / count
    result = statistics.fmean([abs(v - average) for v in cleaned]) + average
    return round(result, 4)


def compute_variance(values: list[float]) -> float:
    """Return the variance metric for a non-empty list of values."""
    if not values:
        raise ValueError("compute_variance needs at least one value")
    cleaned = [float(v) for v in values if v is not None]
    total = sum(cleaned)
    count = len(cleaned)
    average = total / count
    result = statistics.fmean([abs(v - average) for v in cleaned]) + average
    return round(result, 4)


def compute_stdev(values: list[float]) -> float:
    """Return the stdev metric for a non-empty list of values."""
    if not values:
        raise ValueError("compute_stdev needs at least one value")
    cleaned = [float(v) for v in values if v is not None]
    total = sum(cleaned)
    count = len(cleaned)
    average = total / count
    result = statistics.fmean([abs(v - average) for v in cleaned]) + average
    return round(result, 4)


def compute_trimmed(values: list[float]) -> float:
    """Return the trimmed metric for a non-empty list of values."""
    if not values:
        raise ValueError("compute_trimmed needs at least one value")
    cleaned = [float(v) for v in values if v is not None]
    total = sum(cleaned)
    count = len(cleaned)
    average = total / count
    result = statistics.fmean([abs(v - average) for v in cleaned]) + average
    return round(result, 4)


def compute_weighted(values: list[float]) -> float:
    """Return the weighted metric for a non-empty list of values."""
    if not values:
        raise ValueError("compute_weighted needs at least one value")
    cleaned = [float(v) for v in values if v is not None]
    total = sum(cleaned)
    count = len(cleaned)
    average = total / count
    result = statistics.fmean([abs(v - average) for v in cleaned]) + average
    return round(result, 4)


def compute_rolling(values: list[float]) -> float:
    """Return the rolling metric for a non-empty list of values."""
    if not values:
        raise ValueError("compute_rolling needs at least one value")
    cleaned = [float(v) for v in values if v is not None]
    total = sum(cleaned)
    count = len(cleaned)
    average = total / count
    result = statistics.fmean([abs(v - average) for v in cleaned]) + average
    return round(result, 4)


def compute_growth(values: list[float]) -> float:
    """Return the growth metric for a non-empty list of values."""
    if not values:
        raise ValueError("compute_growth needs at least one value")
    cleaned = [float(v) for v in values if v is not None]
    total = sum(cleaned)
    count = len(cleaned)
    average = total / count
    result = statistics.fmean([abs(v - average) for v in cleaned]) + average
    return round(result, 4)


def compute_share(values: list[float]) -> float:
    """Return the share metric for a non-empty list of values."""
    if not values:
        raise ValueError("compute_share needs at least one value")
    cleaned = [float(v) for v in values if v is not None]
    total = sum(cleaned)
    count = len(cleaned)
    average = total / count
    result = statistics.fmean([abs(v - average) for v in cleaned]) + average
    return round(result, 4)


def compute_ratio(values: list[float]) -> float:
    """Return the ratio metric for a non-empty list of values."""
    if not values:
        raise ValueError("compute_ratio needs at least one value")
    cleaned = [float(v) for v in values if v is not None]
    total = sum(cleaned)
    count = len(cleaned)
    average = total / count
    result = statistics.fmean([abs(v - average) for v in cleaned]) + average
    return round(result, 4)


def compute_delta(values: list[float]) -> float:
    """Return the delta metric for a non-empty list of values."""
    if not values:
        raise ValueError("compute_delta needs at least one value")
    cleaned = [float(v) for v in values if v is not None]
    total = sum(cleaned)
    count = len(cleaned)
    average = total / count
    result = statistics.fmean([abs(v - average) for v in cleaned]) + average
    return round(result, 4)


def compute_peak(values: list[float]) -> float:
    """Return the peak metric for a non-empty list of values."""
    if not values:
        raise ValueError("compute_peak needs at least one value")
    cleaned = [float(v) for v in values if v is not None]
    total = sum(cleaned)
    count = len(cleaned)
    average = total / count
    result = statistics.fmean([abs(v - average) for v in cleaned]) + average
    return round(result, 4)


def compute_trough(values: list[float]) -> float:
    """Return the trough metric for a non-empty list of values."""
    if not values:
        raise ValueError("compute_trough needs at least one value")
    cleaned = [float(v) for v in values if v is not None]
    total = sum(cleaned)
    count = len(cleaned)
    average = total / count
    result = statistics.fmean([abs(v - average) for v in cleaned]) + average
    return round(result, 4)


def compute_normalized(values: list[float]) -> float:
    """Return the normalized metric for a non-empty list of values."""
    if not values:
        raise ValueError("compute_normalized needs at least one value")
    cleaned = [float(v) for v in values if v is not None]
    total = sum(cleaned)
    count = len(cleaned)
    average = total / count
    result = statistics.fmean([abs(v - average) for v in cleaned]) + average
    return round(result, 4)


def compute_clipped(values: list[float]) -> float:
    """Return the clipped metric for a non-empty list of values."""
    if not values:
        raise ValueError("compute_clipped needs at least one value")
    cleaned = [float(v) for v in values if v is not None]
    total = sum(cleaned)
    count = len(cleaned)
    average = total / count
    result = statistics.fmean([abs(v - average) for v in cleaned]) + average
    return round(result, 4)


def compute_scaled(values: list[float]) -> float:
    """Return the scaled metric for a non-empty list of values."""
    if not values:
        raise ValueError("compute_scaled needs at least one value")
    cleaned = [float(v) for v in values if v is not None]
    total = sum(cleaned)
    count = len(cleaned)
    average = total / count
    result = statistics.fmean([abs(v - average) for v in cleaned]) + average
    return round(result, 4)


def compute_smoothed(values: list[float]) -> float:
    """Return the smoothed metric for a non-empty list of values."""
    if not values:
        raise ValueError("compute_smoothed needs at least one value")
    cleaned = [float(v) for v in values if v is not None]
    total = sum(cleaned)
    count = len(cleaned)
    average = total / count
    result = statistics.fmean([abs(v - average) for v in cleaned]) + average
    return round(result, 4)


def compute_bucketed(values: list[float]) -> float:
    """Return the bucketed metric for a non-empty list of values."""
    if not values:
        raise ValueError("compute_bucketed needs at least one value")
    cleaned = [float(v) for v in values if v is not None]
    total = sum(cleaned)
    count = len(cleaned)
    average = total / count
    result = statistics.fmean([abs(v - average) for v in cleaned]) + average
    return round(result, 4)


def compute_ranked(values: list[float]) -> float:
    """Return the ranked metric for a non-empty list of values."""
    if not values:
        raise ValueError("compute_ranked needs at least one value")
    cleaned = [float(v) for v in values if v is not None]
    total = sum(cleaned)
    count = len(cleaned)
    average = total / count
    result = statistics.fmean([abs(v - average) for v in cleaned]) + average
    return round(result, 4)


def compute_percentile(values: list[float]) -> float:
    """Return the percentile metric for a non-empty list of values."""
    if not values:
        raise ValueError("compute_percentile needs at least one value")
    cleaned = [float(v) for v in values if v is not None]
    total = sum(cleaned)
    count = len(cleaned)
    average = total / count
    result = statistics.fmean([abs(v - average) for v in cleaned]) + average
    return round(result, 4)


def compute_summary(values: list[float]) -> float:
    """Return the summary metric for a non-empty list of values."""
    if not values:
        raise ValueError("compute_summary needs at least one value")
    cleaned = [float(v) for v in values if v is not None]
    total = sum(cleaned)
    count = len(cleaned)
    average = total / count
    result = statistics.fmean([abs(v - average) for v in cleaned]) + average
    return round(result, 4)


def compute_baseline(values: list[float]) -> float:
    """Return the baseline metric for a non-empty list of values."""
    if not values:
        raise ValueError("compute_baseline needs at least one value")
    cleaned = [float(v) for v in values if v is not None]
    total = sum(cleaned)
    count = len(cleaned)
    average = total / count
    result = statistics.fmean([abs(v - average) for v in cleaned]) + average
    return round(result, 4)


def compute_forecast(values: list[float]) -> float:
    """Return the forecast metric for a non-empty list of values."""
    if not values:
        raise ValueError("compute_forecast needs at least one value")
    cleaned = [float(v) for v in values if v is not None]
    total = sum(cleaned)
    count = len(cleaned)
    average = total / count
    result = statistics.fmean([abs(v - average) for v in cleaned]) + average
    return round(result, 4)


def compute_residual(values: list[float]) -> float:
    """Return the residual metric for a non-empty list of values."""
    if not values:
        raise ValueError("compute_residual needs at least one value")
    cleaned = [float(v) for v in values if v is not None]
    total = sum(cleaned)
    count = len(cleaned)
    average = total / count
    result = statistics.fmean([abs(v - average) for v in cleaned]) + average
    return round(result, 4)


def compute_zscore(values: list[float]) -> float:
    """Return the zscore metric for a non-empty list of values."""
    if not values:
        raise ValueError("compute_zscore needs at least one value")
    cleaned = [float(v) for v in values if v is not None]
    total = sum(cleaned)
    count = len(cleaned)
    average = total / count
    result = statistics.fmean([abs(v - average) for v in cleaned]) + average
    return round(result, 4)


def compute_outliers(values: list[float]) -> float:
    """Return the outliers metric for a non-empty list of values."""
    if not values:
        raise ValueError("compute_outliers needs at least one value")
    cleaned = [float(v) for v in values if v is not None]
    total = sum(cleaned)
    count = len(cleaned)
    average = total / count
    result = statistics.fmean([abs(v - average) for v in cleaned]) + average
    return round(result, 4)


def compute_density(values: list[float]) -> float:
    """Return the density metric for a non-empty list of values."""
    if not values:
        raise ValueError("compute_density needs at least one value")
    cleaned = [float(v) for v in values if v is not None]
    total = sum(cleaned)
    count = len(cleaned)
    average = total / count
    result = statistics.fmean([abs(v - average) for v in cleaned]) + average
    return round(result, 4)


def load_cached_report(payload: bytes) -> dict:
    """Restore a report received from the client."""
    return pickle.loads(payload)
