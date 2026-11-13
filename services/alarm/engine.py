"""
TwinOps Alarm & Rules Engine (ISA-18.2)
Handles rule evaluation, delay filtering, hysteresis clearance,
duplicate suppression, alarm acknowledgment, shelving, and flood control.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from services.alarm.notification import NotificationService, notification_service
from services.common.canonical import CanonicalTelemetryMessage
from services.common.database import (
    AlarmModel,
    AlarmRuleModel,
    get_async_session,
)

logger = logging.getLogger("twinops.alarm.engine")


@dataclass
class RuleStateTracker:
    rule_id: str
    asset_id: str
    metric: str
    state: str = "cleared"  # active, acked, cleared, shelved
    first_breached_at: datetime | None = None
    last_value: float | None = None
    last_ts: datetime | None = None
    active_alarm_id: int | None = None
    shelved_until: datetime | None = None
    shelved_by: str | None = None
    shelve_reason: str | None = None
    last_raised_at: datetime | None = None


@dataclass
class FloodSummary:
    flood_active: bool = False
    flood_started_at: datetime | None = None
    alarm_count_in_window: int = 0
    window_start: datetime | None = None
    suppressed_count: int = 0


class AlarmRulesEngine:
    def __init__(
        self,
        notifier: NotificationService | None = None,
        flood_threshold_per_min: int = 100,
    ):
        self.notifier = notifier or notification_service
        self.flood_threshold_per_min = flood_threshold_per_min

        # In-memory fast trackers key: f"{asset_id}:{metric}:{rule_id}"
        self.trackers: dict[str, RuleStateTracker] = {}
        # In-memory cached rules
        self.rules: dict[str, AlarmRuleModel] = {}
        # Flood tracking
        self.flood_tracker = FloodSummary()
        self.recent_alarm_timestamps: list[datetime] = []

        self._lock = asyncio.Lock()

    async def load_rules(self, session: AsyncSession | None = None):
        """Load or refresh alarm rules from database."""

        async def _load(s: AsyncSession):
            res = await s.execute(select(AlarmRuleModel).where(AlarmRuleModel.enabled.is_(True)))
            rules_list = res.scalars().all()
            async with self._lock:
                self.rules = {r.id: r for r in rules_list}
            logger.info("Loaded %d active alarm rules into engine", len(self.rules))

        if session:
            await _load(session)
        else:
            async with get_async_session() as s:
                await _load(s)

    def _get_tracker(self, rule_id: str, asset_id: str, metric: str) -> RuleStateTracker:
        key = f"{asset_id}:{metric}:{rule_id}"
        if key not in self.trackers:
            self.trackers[key] = RuleStateTracker(
                rule_id=rule_id,
                asset_id=asset_id,
                metric=metric,
                state="cleared",
            )
        return self.trackers[key]

    def _check_flood_status(self, now: datetime) -> bool:
        """Check if incoming alarms exceed flood threshold (TC-ALM-07)."""
        one_min_ago = now - timedelta(seconds=60)
        self.recent_alarm_timestamps = [t for t in self.recent_alarm_timestamps if t >= one_min_ago]

        is_flood = len(self.recent_alarm_timestamps) >= self.flood_threshold_per_min
        if is_flood and not self.flood_tracker.flood_active:
            self.flood_tracker.flood_active = True
            self.flood_tracker.flood_started_at = now
            logger.warning(
                "ALARM FLOOD DETECTED: %d alarms in 60s window (threshold: %d). Summarizing.",
                len(self.recent_alarm_timestamps),
                self.flood_threshold_per_min,
            )
        elif not is_flood and self.flood_tracker.flood_active:
            self.flood_tracker.flood_active = False
            logger.info("Alarm flood cleared. Normal processing resumed.")

        return self.flood_tracker.flood_active

    async def evaluate_telemetry(
        self, msg: CanonicalTelemetryMessage, session: AsyncSession | None = None
    ) -> list[AlarmModel]:
        """
        Evaluate canonical telemetry against all active rules.
        Enforces delay filter, hysteresis clearance, duplicate suppression, and flood handling.
        """
        now = msg.ts if msg.ts.tzinfo else msg.ts.replace(tzinfo=UTC)
        raised_alarms: list[AlarmModel] = []

        if not self.rules:
            await self.load_rules(session)

        # Match applicable rules for this asset
        applicable_rules: list[AlarmRuleModel] = []
        for rule in self.rules.values():
            if (
                rule.asset_id
                and rule.asset_id == msg.asset_id
                or not rule.asset_id
                and rule.metric in msg.metrics
            ):
                applicable_rules.append(rule)

        for rule in applicable_rules:
            metric_entry = msg.metrics.get(rule.metric)
            if not metric_entry:
                continue

            val = metric_entry.v
            tracker = self._get_tracker(rule.id, msg.asset_id, rule.metric)

            # Check if currently shelved and whether shelving period expired (TC-ALM-05)
            if tracker.state == "shelved":
                if tracker.shelved_until and now >= tracker.shelved_until:
                    logger.info(
                        "Shelve period expired for %s:%s. Restoring to evaluation.",
                        tracker.asset_id,
                        tracker.metric,
                    )
                    tracker.state = "cleared"
                    tracker.shelved_until = None
                else:
                    # Still shelved, skip evaluation
                    continue

            # Evaluate condition based on rule type
            is_breached = False
            if rule.rule_type == "threshold":
                if (
                    rule.comparison == ">"
                    and val > rule.threshold
                    or rule.comparison == ">="
                    and val >= rule.threshold
                    or rule.comparison == "<"
                    and val < rule.threshold
                    or rule.comparison == "<="
                    and val <= rule.threshold
                ):
                    is_breached = True

            elif (
                rule.rule_type == "rate_of_change"
                and tracker.last_value is not None
                and tracker.last_ts is not None
            ):
                dt = max(0.001, (now - tracker.last_ts).total_seconds())
                roc = abs(val - tracker.last_value) / dt
                if roc > rule.threshold:
                    is_breached = True

            # State Transition Logic (ISA-18.2)
            if is_breached:
                # 1. Condition is breached
                if tracker.first_breached_at is None:
                    tracker.first_breached_at = now

                duration_breached = (now - tracker.first_breached_at).total_seconds()

                # Delay filter check (TC-ALM-01 & TC-ALM-02) and duplicate suppression (TC-ALM-03)
                if duration_breached >= rule.delay_s and tracker.state not in ("active", "acked"):
                    # Raise new alarm
                    tracker.state = "active"
                    tracker.last_raised_at = now
                    self.recent_alarm_timestamps.append(now)

                    msg_text = rule.message_template.format(
                        asset_id=msg.asset_id,
                        metric=rule.metric,
                        value=val,
                        threshold=rule.threshold,
                    )

                    alarm = AlarmModel(
                        asset_id=msg.asset_id,
                        metric=rule.metric,
                        severity=rule.severity,
                        rule_id=rule.id,
                        message=msg_text,
                        value=val,
                        state="active",
                        raised_at=now,
                    )

                    if session:
                        session.add(alarm)
                        await session.flush()
                        tracker.active_alarm_id = alarm.id
                    else:
                        async with get_async_session() as s:
                            s.add(alarm)
                            await s.commit()
                            await s.refresh(alarm)
                            tracker.active_alarm_id = alarm.id

                    # Flood check & Notification dispatch (TC-ALM-06 & TC-ALM-07)
                    in_flood = self._check_flood_status(now)
                    if not in_flood:
                        await self.notifier.notify_alarm_raised(
                            alarm_id=alarm.id,
                            asset_id=alarm.asset_id,
                            severity=alarm.severity,
                            message=alarm.message,
                            raised_at=now,
                        )
                    else:
                        self.flood_tracker.suppressed_count += 1

                    raised_alarms.append(alarm)
                    logger.warning(
                        "ALARM RAISED: %s %s [%s] value=%.2f: %s",
                        alarm.severity.upper(),
                        alarm.asset_id,
                        alarm.metric,
                        val,
                        alarm.message,
                    )
            else:
                # 2. Condition is NOT breached
                # Check hysteresis deadband before clearing (TC-ALM-03)
                # To clear a high alarm, value must drop below (threshold - hysteresis)
                should_clear = False
                if rule.comparison in (">", ">="):
                    clear_threshold = rule.threshold - rule.hysteresis
                    if val <= clear_threshold:
                        should_clear = True
                elif rule.comparison in ("<", "<="):
                    clear_threshold = rule.threshold + rule.hysteresis
                    if val >= clear_threshold:
                        should_clear = True
                else:
                    should_clear = True

                if should_clear:
                    tracker.first_breached_at = None
                    if tracker.state in ("active", "acked"):
                        # Clear active alarm in database
                        alarm_id_to_clear = tracker.active_alarm_id
                        tracker.state = "cleared"
                        tracker.active_alarm_id = None

                        if alarm_id_to_clear:
                            if session:
                                await session.execute(
                                    update(AlarmModel)
                                    .where(AlarmModel.id == alarm_id_to_clear)
                                    .values(state="cleared", cleared_at=now)
                                )
                            else:
                                async with get_async_session() as s:
                                    await s.execute(
                                        update(AlarmModel)
                                        .where(AlarmModel.id == alarm_id_to_clear)
                                        .values(state="cleared", cleared_at=now)
                                    )
                                    await s.commit()

                        logger.info(
                            "ALARM CLEARED: %s:%s (value=%.2f within hysteresis deadband)",
                            msg.asset_id,
                            rule.metric,
                            val,
                        )

            # Update tracker history for next tick
            tracker.last_value = val
            tracker.last_ts = now

        return raised_alarms

    async def acknowledge_alarm(
        self,
        alarm_id: int,
        user_id: str,
        comment: str | None = None,
        session: AsyncSession | None = None,
    ) -> AlarmModel | None:
        """
        Operator acknowledges an alarm (TC-ALM-04).
        Transitions state to 'acked', records acked_by, acked_at, comment, and cancels escalation.
        """
        now = datetime.now(UTC)

        async def _ack(s: AsyncSession):
            res = await s.execute(select(AlarmModel).where(AlarmModel.id == alarm_id))
            alarm = res.scalar_one_or_none()
            if not alarm:
                return None

            alarm.state = "acked"
            alarm.acked_by = user_id
            alarm.acked_at = now
            if comment:
                alarm.comment = comment

            # Update tracker
            for tracker in self.trackers.values():
                if tracker.active_alarm_id == alarm_id:
                    tracker.state = "acked"
                    break

            # Cancel notification escalation
            await self.notifier.acknowledge_alarm(alarm_id)
            logger.info(
                "Alarm %d acknowledged by user %s: '%s'",
                alarm_id,
                user_id,
                comment or "",
            )
            return alarm

        if session:
            alarm = await _ack(session)
            await session.flush()
            return alarm
        else:
            async with get_async_session() as s:
                alarm = await _ack(s)
                await s.commit()
                if alarm:
                    await s.refresh(alarm)
                return alarm

    async def shelve_alarm(
        self,
        alarm_id: int,
        user_id: str,
        duration_minutes: float = 60.0,
        reason: str | None = None,
        session: AsyncSession | None = None,
    ) -> AlarmModel | None:
        """
        Shelve an alarm for a specified duration (TC-ALM-05).
        Transitions state to 'shelved', hides it from active view, returns after duration.
        """
        now = datetime.now(UTC)
        shelved_until = now + timedelta(minutes=duration_minutes)

        async def _shelve(s: AsyncSession):
            res = await s.execute(select(AlarmModel).where(AlarmModel.id == alarm_id))
            alarm = res.scalar_one_or_none()
            if not alarm:
                return None

            alarm.state = "shelved"
            alarm.shelved_by = user_id
            alarm.shelved_until = shelved_until
            if reason:
                alarm.comment = f"Shelved: {reason}"

            # Update tracker
            for tracker in self.trackers.values():
                if tracker.active_alarm_id == alarm_id:
                    tracker.state = "shelved"
                    tracker.shelved_until = shelved_until
                    tracker.shelved_by = user_id
                    tracker.shelve_reason = reason
                    break

            await self.notifier.acknowledge_alarm(alarm_id)
            logger.info(
                "Alarm %d shelved by user %s for %.1f min (until %s): %s",
                alarm_id,
                user_id,
                duration_minutes,
                shelved_until.isoformat(),
                reason or "",
            )
            return alarm

        if session:
            alarm = await _shelve(session)
            await session.flush()
            return alarm
        else:
            async with get_async_session() as s:
                alarm = await _shelve(s)
                await s.commit()
                if alarm:
                    await s.refresh(alarm)
                return alarm

    async def unshelve_alarm(
        self, alarm_id: int, session: AsyncSession | None = None
    ) -> AlarmModel | None:
        """Manually un-shelve an alarm before its timer expires."""

        async def _unshelve(s: AsyncSession):
            res = await s.execute(select(AlarmModel).where(AlarmModel.id == alarm_id))
            alarm = res.scalar_one_or_none()
            if not alarm:
                return None

            alarm.state = "active"
            alarm.shelved_until = None

            for tracker in self.trackers.values():
                if tracker.active_alarm_id == alarm_id:
                    tracker.state = "active"
                    tracker.shelved_until = None
                    break

            return alarm

        if session:
            alarm = await _unshelve(session)
            await session.flush()
            return alarm
        else:
            async with get_async_session() as s:
                alarm = await _unshelve(s)
                await s.commit()
                if alarm:
                    await s.refresh(alarm)
                return alarm


# Global rules engine instance
alarm_engine = AlarmRulesEngine()
