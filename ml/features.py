"""
TwinOps Feature Engineering for Machine Learning
Extracts statistical features over sliding time windows (mean, std, slope, kurtosis).
"""

from __future__ import annotations

import numpy as np
from scipy import stats


def extract_window_features(series: list[float] | np.ndarray) -> dict[str, float]:
    """
    Extract 4 statistical features from a time-series window (5-min telemetry window):
    - mean: central tendency / shift
    - std: variance / vibration energy
    - slope: rate-of-change trend
    - kurtosis: peakedness / impulse sharpness (bearing spalls, impacts)
    """
    arr = np.asarray(series, dtype=float)
    if len(arr) == 0:
        return {"mean": 0.0, "std": 0.0, "slope": 0.0, "kurtosis": 0.0}

    mean_val = float(np.mean(arr))
    std_val = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0

    # Linear slope
    if len(arr) > 1:
        x = np.arange(len(arr), dtype=float)
        # polyfit degree 1: [slope, intercept]
        slope_val = float(np.polyfit(x, arr, 1)[0])
    else:
        slope_val = 0.0

    # Fisher kurtosis (normal distribution = 0.0)
    if len(arr) >= 4 and std_val > 1e-9:
        kurt_val = float(stats.kurtosis(arr, fisher=True))
    else:
        kurt_val = 0.0

    return {
        "mean": mean_val,
        "std": std_val,
        "slope": slope_val,
        "kurtosis": kurt_val,
    }


def extract_multivariate_features(
    metrics_history: dict[str, list[float]],
) -> tuple[np.ndarray, list[str]]:
    """
    Extract concatenated feature vector across multiple metrics with feature names.
    """
    feature_values: list[float] = []
    feature_names: list[str] = []

    for metric_name, values in sorted(metrics_history.items()):
        feats = extract_window_features(values)
        for stat_name, val in sorted(feats.items()):
            feature_names.append(f"{metric_name}_{stat_name}")
            feature_values.append(val)

    return np.array(feature_values, dtype=float), feature_names
