"""
TwinOps Notification & Escalation Service (ALM-03 / TC-ALM-06)
Handles dispatch of alert notifications (Email, SMS, Teams/Webhook)
and manages escalation timers for unacknowledged critical alarms.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

logger = logging.getLogger("twinops.alarm.notification")


@dataclass
class NotificationMessage:
    id: str
    alarm_id: int
    asset_id: str
    severity: str
    message: str
    channel: str  # email, sms, webhook
    recipient: str
    sent_at: datetime
    is_escalation: bool = False


@dataclass
class EscalationRecord:
    alarm_id: int
    asset_id: str
    severity: str
    message: str
    raised_at: datetime
    escalate_after_s: float
    escalated: bool = False


class NotificationService:
    def __init__(self, escalation_default_delay_s: float = 900.0):  # 15 minutes default
        self.escalation_default_delay_s = escalation_default_delay_s
        self.sent_notifications: list[NotificationMessage] = []
        self.pending_escalations: dict[int, EscalationRecord] = {}
        self._lock = asyncio.Lock()

    async def notify_alarm_raised(
        self,
        alarm_id: int,
        asset_id: str,
        severity: str,
        message: str,
        channels: list[str] | None = None,
        escalate_after_s: float | None = None,
        raised_at: datetime | None = None,
    ) -> list[NotificationMessage]:
        """Dispatch notification for newly raised alarm and schedule escalation if critical."""
        if channels is None:
            if severity == "critical":
                channels = ["email", "sms", "webhook"]
            elif severity == "high":
                channels = ["email", "webhook"]
            else:
                channels = ["webhook"]

        now = raised_at or datetime.now(UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        dispatched: list[NotificationMessage] = []

        async with self._lock:
            for ch in channels:
                msg = NotificationMessage(
                    id=f"NOTIF-{len(self.sent_notifications) + 1}",
                    alarm_id=alarm_id,
                    asset_id=asset_id,
                    severity=severity,
                    message=message,
                    channel=ch,
                    recipient=f"maintenance-{ch}@plant.twinops.io",
                    sent_at=now,
                    is_escalation=False,
                )
                self.sent_notifications.append(msg)
                dispatched.append(msg)
                logger.info(
                    "Sent %s notification for alarm %d (%s: %s)",
                    ch.upper(),
                    alarm_id,
                    severity,
                    message,
                )

            # Schedule escalation if critical
            if severity == "critical":
                delay = (
                    escalate_after_s
                    if escalate_after_s is not None
                    else self.escalation_default_delay_s
                )
                self.pending_escalations[alarm_id] = EscalationRecord(
                    alarm_id=alarm_id,
                    asset_id=asset_id,
                    severity=severity,
                    message=message,
                    raised_at=now,
                    escalate_after_s=delay,
                    escalated=False,
                )

        return dispatched

    async def acknowledge_alarm(self, alarm_id: int) -> bool:
        """Cancel escalation when operator acknowledges the alarm."""
        async with self._lock:
            if alarm_id in self.pending_escalations:
                del self.pending_escalations[alarm_id]
                logger.info("Cancelled escalation timer for acknowledged alarm %d", alarm_id)
                return True
        return False

    async def check_escalations(
        self, current_time: datetime | None = None
    ) -> list[NotificationMessage]:
        """Check all pending escalations and dispatch supervisor alert if timer expired."""
        now = current_time or datetime.now(UTC)
        escalated_msgs: list[NotificationMessage] = []

        async with self._lock:
            for alarm_id, rec in list(self.pending_escalations.items()):
                if not rec.escalated:
                    elapsed = (now - rec.raised_at).total_seconds()
                    if elapsed >= rec.escalate_after_s:
                        # Escalate to plant management
                        rec.escalated = True
                        for ch in ["email", "sms"]:
                            esc_msg = NotificationMessage(
                                id=f"ESC-{len(self.sent_notifications) + 1}",
                                alarm_id=rec.alarm_id,
                                asset_id=rec.asset_id,
                                severity="critical",
                                message=f"[ESCALATED] Unacknowledged critical alarm on {rec.asset_id}: {rec.message}",
                                channel=ch,
                                recipient=f"supervisor-{ch}@plant.twinops.io",
                                sent_at=now,
                                is_escalation=True,
                            )
                            self.sent_notifications.append(esc_msg)
                            escalated_msgs.append(esc_msg)
                        logger.warning(
                            "Alarm %d escalated to plant supervisor after %.1f seconds unacknowledged",
                            alarm_id,
                            elapsed,
                        )

        return escalated_msgs


# Global notification service instance
notification_service = NotificationService()
