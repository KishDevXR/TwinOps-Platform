"""
TwinOps Isolation Forest Anomaly Detection Model (ANL-02)
Features:
- Unsupervised anomaly detection on 5-min statistical feature windows
- Normalized anomaly score [0.0, 1.0]
- Signal contribution attribution
- Multi-window persistence check (> 0.8 for 3 consecutive windows)
"""

from __future__ import annotations

import logging

import numpy as np
from sklearn.ensemble import IsolationForest

from ml.features import extract_multivariate_features

logger = logging.getLogger("twinops.ml.anomaly")


class IsolationForestAnomalyDetector:
    def __init__(
        self,
        contamination: float = 0.01,
        n_estimators: int = 100,
        random_state: int = 42,
    ):
        self.model = IsolationForest(
            contamination=contamination,
            n_estimators=n_estimators,
            random_state=random_state,
            n_jobs=-1,
        )
        self.is_fitted = False
        self.feature_names: list[str] = []
        self.baseline_mean: np.ndarray | None = None
        self.baseline_std: np.ndarray | None = None
        # Recent anomaly scores history for multi-window persistence
        self.recent_scores: list[float] = []

    def fit_baseline(
        self,
        nominal_windows: list[dict[str, list[float]]],
    ) -> None:
        """
        Fit detector on healthy baseline operational windows.
        """
        if not nominal_windows:
            raise ValueError("No baseline windows provided for training.")

        X_list = []
        for win in nominal_windows:
            vec, names = extract_multivariate_features(win)
            X_list.append(vec)
            if not self.feature_names:
                self.feature_names = names

        X = np.array(X_list)
        self.baseline_mean = np.mean(X, axis=0)
        self.baseline_std = np.std(X, axis=0) + 1e-6

        self.model.fit(X)
        self.is_fitted = True
        logger.info(
            "Trained Isolation Forest baseline on %d windows (%d features)",
            len(X_list),
            len(self.feature_names),
        )

    def score_window(
        self,
        window: dict[str, list[float]],
    ) -> tuple[float, dict[str, float], bool]:
        """
        Calculate anomaly score [0.0, 1.0] for a 5-min window,
        identify top contributing signals, and check 3-window persistence.
        Returns: (anomaly_score, contributing_signals, is_persistent_anomaly)
        """
        vec, names = extract_multivariate_features(window)
        if not self.is_fitted:
            # Fallback bootstrap if not pre-trained: use heuristic deviation from nominal
            return self._heuristic_score(vec, names)

        # Standardized z-score deviation against baseline
        assert self.baseline_mean is not None and self.baseline_std is not None
        z_scores = np.abs((vec - self.baseline_mean) / self.baseline_std)

        # Compute maximum z-score across key statistical moments (mean, std)
        z_stat_max = 0.0
        for name, z in zip(names, z_scores, strict=False):
            if "mean" in name or "std" in name:
                z_stat_max = max(z_stat_max, float(z))

        # IsolationForest decision_function: higher = normal, lower = anomalous
        decision = float(self.model.decision_function([vec])[0])

        # Convert z-score deviation into anomaly scale:
        # z <= 3.0: normal statistical variation (< 0.15)
        # 3.0 < z <= 6.0: elevated / warning (0.15 to 0.70)
        # z > 6.0: severe anomaly (> 0.80)
        if z_stat_max <= 3.0:
            z_score_norm = 0.15 * (z_stat_max / 3.0)
        elif z_stat_max <= 6.0:
            z_score_norm = 0.15 + 0.55 * ((z_stat_max - 3.0) / 3.0)
        else:
            z_score_norm = min(1.0, 0.70 + 0.30 * (1.0 - np.exp(-0.4 * (z_stat_max - 6.0))))

        # Calibrate decision score into anomaly score
        if decision >= 0.05:
            iforest_score = max(0.01, (0.15 - decision) / 0.15 * 0.15)
        elif decision > 0.0:
            iforest_score = 0.15 + (0.05 - decision) / 0.05 * 0.45
        else:
            iforest_score = min(1.0, 0.60 + abs(decision) * 3.0)

        # Combined anomaly score: blend isolation tree score with statistical departure
        norm_score = max(iforest_score, z_score_norm)

        # Track history for 3-window persistence rule
        self.recent_scores.append(norm_score)
        if len(self.recent_scores) > 10:
            self.recent_scores.pop(0)

        is_persistent = len(self.recent_scores) >= 3 and all(
            s > 0.8 for s in self.recent_scores[-3:]
        )

        # Calculate contributing signals (z-score deviation against baseline)
        contributions: dict[str, float] = {}
        if self.baseline_mean is not None and self.baseline_std is not None:
            z_scores = np.abs((vec - self.baseline_mean) / self.baseline_std)
            for name, z in zip(names, z_scores, strict=False):
                metric = name.split("_")[0]
                contributions[metric] = max(contributions.get(metric, 0.0), float(z))

        # Normalize contributions to percentages
        tot = sum(contributions.values()) or 1.0
        pct_contributions = {k: round((v / tot) * 100, 1) for k, v in contributions.items()}

        return round(norm_score, 3), pct_contributions, is_persistent

    def _heuristic_score(
        self, vec: np.ndarray, names: list[str]
    ) -> tuple[float, dict[str, float], bool]:
        """Bootstrap scoring when model is fitting on-the-fly."""
        # Check vibration and temp features
        score = 0.05
        contribs: dict[str, float] = {}
        for name, val in zip(names, vec, strict=False):
            if "vibration" in name:
                if "mean" in name and val > 4.5:
                    score = max(score, min(0.95, (val / 7.1)))
                if "kurtosis" in name and val > 3.0:
                    score = max(score, 0.85)
                contribs["vibration"] = contribs.get("vibration", 0.0) + val
            elif "temp" in name:
                if "mean" in name and val > 75.0:
                    score = max(score, min(0.95, (val / 95.0)))
                contribs["temperature"] = contribs.get("temperature", 0.0) + val

        self.recent_scores.append(score)
        is_persistent = len(self.recent_scores) >= 3 and all(
            s > 0.8 for s in self.recent_scores[-3:]
        )
        return round(score, 3), contribs, is_persistent
