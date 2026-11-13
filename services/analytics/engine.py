"""
TwinOps Analytics Orchestration Engine
Integrates OEE computations, Isolation Forest anomaly scoring,
and Weibull/exponential RUL predictions.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import numpy as np

from ml.anomaly_model import IsolationForestAnomalyDetector
from ml.rul_model import RULPrediction, WeibullDegradationRULModel
from services.common.canonical import CanonicalTelemetryMessage

logger = logging.getLogger("twinops.analytics.engine")


@dataclass
class AssetAnalyticsState:
    asset_id: str
    anomaly_detector: IsolationForestAnomalyDetector
    rul_model: WeibullDegradationRULModel
    # 5-minute sliding window metrics history: { metric_name: [val1, val2, ...] }
    metric_window: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    timestamps_window: list[datetime] = field(default_factory=list)
    # Long-term degradation history for RUL: (time_hours, vibration_mm_s)
    rul_time_history: list[float] = field(default_factory=list)
    rul_vib_history: list[float] = field(default_factory=list)
    current_operating_hours: float = 0.0
    latest_anomaly_score: float = 0.05
    latest_contributions: dict[str, float] = field(default_factory=dict)
    is_anomaly_active: bool = False
    latest_rul: RULPrediction | None = None


class AnalyticsEngine:
    def __init__(self, window_size_samples: int = 300):
        self.window_size_samples = window_size_samples  # 5 min at 1Hz = 300 samples
        self.states: dict[str, AssetAnalyticsState] = {}
        self._lock = asyncio.Lock()

    def _get_or_create_state(self, asset_id: str) -> AssetAnalyticsState:
        if asset_id not in self.states:
            detector = IsolationForestAnomalyDetector()
            # Bootstrap detector with standard nominal operating windows
            nominal_synthetic = self._generate_synthetic_nominal_windows(asset_id)
            detector.fit_baseline(nominal_synthetic)

            rul_model = WeibullDegradationRULModel()

            self.states[asset_id] = AssetAnalyticsState(
                asset_id=asset_id,
                anomaly_detector=detector,
                rul_model=rul_model,
            )
        return self.states[asset_id]

    def _generate_synthetic_nominal_windows(self, asset_id: str) -> list[dict[str, list[float]]]:
        """Generate baseline nominal windows for model pre-fitting."""
        np_rng = np.random.default_rng(42)
        windows = []
        for _ in range(30):
            # Healthy pump/spindle baseline
            vib = np_rng.normal(loc=1.8, scale=0.15, size=60).tolist()
            temp = np_rng.normal(loc=45.0, scale=1.0, size=60).tolist()
            power = np_rng.normal(loc=12.0, scale=0.4, size=60).tolist()
            windows.append(
                {
                    "vibration_mm_s": vib,
                    "motor_temp_c": temp,
                    "spindle_temp_c": temp,
                    "power_kw": power,
                }
            )
        return windows

    async def ingest_telemetry(
        self, msg: CanonicalTelemetryMessage
    ) -> tuple[float, RULPrediction | None]:
        """
        Ingest telemetry point into 5-minute sliding window,
        update anomaly score and RUL estimate.
        """
        async with self._lock:
            state = self._get_or_create_state(msg.asset_id)
            now = msg.ts if msg.ts.tzinfo else msg.ts.replace(tzinfo=UTC)

            state.timestamps_window.append(now)
            for m_name, m_val in msg.metrics.items():
                state.metric_window[m_name].append(m_val.v)
                if len(state.metric_window[m_name]) > self.window_size_samples:
                    state.metric_window[m_name].pop(0)

            if len(state.timestamps_window) > self.window_size_samples:
                state.timestamps_window.pop(0)

            # Score window if sufficient samples (>= 5 samples)
            if len(state.timestamps_window) >= 5:
                score, contribs, is_persistent = state.anomaly_detector.score_window(
                    state.metric_window
                )
                state.latest_anomaly_score = score
                state.latest_contributions = contribs
                state.is_anomaly_active = is_persistent

            # Update RUL history if vibration is present
            vib_val = msg.metrics.get("vibration_mm_s") or msg.metrics.get("vibration_rms_mm_s")
            if vib_val:
                state.current_operating_hours += 0.01  # small tick
                state.rul_time_history.append(state.current_operating_hours)
                state.rul_vib_history.append(vib_val.v)
                if len(state.rul_time_history) > 500:
                    state.rul_time_history.pop(0)
                    state.rul_vib_history.pop(0)

                state.latest_rul = state.rul_model.estimate_rul(
                    asset_id=state.asset_id,
                    time_history_hours=state.rul_time_history,
                    vibration_history_mm_s=state.rul_vib_history,
                    current_operating_hours=state.current_operating_hours,
                )

            return state.latest_anomaly_score, state.latest_rul

    def get_asset_anomaly(self, asset_id: str) -> dict[str, Any]:
        """Get live anomaly score and top contributors for an asset."""
        state = self._get_or_create_state(asset_id)
        return {
            "asset_id": asset_id,
            "anomaly_score": state.latest_anomaly_score,
            "is_anomaly_active": state.is_anomaly_active,
            "contributing_signals": state.latest_contributions,
            "sample_count": len(state.timestamps_window),
        }

    def get_asset_rul(self, asset_id: str) -> RULPrediction:
        """Get current RUL prediction for an asset."""
        state = self._get_or_create_state(asset_id)
        if state.latest_rul:
            return state.latest_rul
        # Default fallback
        return state.rul_model.estimate_rul(
            asset_id=asset_id,
            time_history_hours=[0.0, 100.0],
            vibration_history_mm_s=[1.8, 1.85],
            current_operating_hours=100.0,
        )


# Global analytics engine instance
analytics_engine = AnalyticsEngine()
