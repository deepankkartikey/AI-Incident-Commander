from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


# ============================================================================
# Data Models
# ============================================================================

class StreamEvent(BaseModel):
    """Represents an event from one of the streams"""
    timestamp: str
    channel: str  # "metrics", "slack", or "zoom"
    message: str


class IncidentState(BaseModel):
    """Current state of the incident"""
    metrics_events: List[StreamEvent] = Field(default_factory=list)
    slack_events: List[StreamEvent] = Field(default_factory=list)
    zoom_events: List[StreamEvent] = Field(default_factory=list)
    last_summary_time: Optional[float] = None
    incident_start_time: float = Field(default_factory=lambda: datetime.now().timestamp())
    slack_channel_id: Optional[str] = None  # Track the incident Slack channel ID

    @property
    def all_events(self) -> List[StreamEvent]:
        """Get all events sorted by timestamp"""
        all_events = self.metrics_events + self.slack_events + self.zoom_events
        return sorted(all_events, key=lambda e: e.timestamp)

    @property
    def recent_events(self, seconds: int = 60) -> List[StreamEvent]:
        """Get events from the last N seconds"""
        cutoff_time = datetime.now().timestamp() - seconds
        return [e for e in self.all_events if self._event_timestamp(e) > cutoff_time]

    def _event_timestamp(self, event: StreamEvent) -> float:
        """Convert event timestamp to unix timestamp"""
        # Assuming timestamp format is "HH:MM:SS"
        try:
            time_parts = event.timestamp.split(":")
            hours, minutes, seconds = int(time_parts[0]), int(time_parts[1]), int(time_parts[2])
            today = datetime.now()
            event_time = today.replace(hour=hours, minute=minutes, second=seconds, microsecond=0)
            return event_time.timestamp()
        except:
            return datetime.now().timestamp()


class ExecutiveSummary(BaseModel):
    """Executive summary for leadership"""
    timestamp: str
    incident_duration: str
    current_status: str
    customer_impact: str
    key_actions_taken: List[str]
    root_cause: Optional[str] = None
    eta_to_resolution: Optional[str] = None
    severity: str

