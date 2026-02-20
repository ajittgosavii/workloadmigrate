"""
Audit Logging Module
======================
Tracks user actions for compliance and governance.
Stores audit entries in session state (zero-persistence).
Optional export to external systems.

Events tracked:
  - Login/logout
  - Server analysis (manual & batch)
  - Data exports (CSV/Excel/PDF)
  - AI analysis requests
  - Configuration changes
  - Auto-discovery runs
"""

from datetime import datetime
from typing import Dict, List, Optional
import json
import io


class AuditEvent:
    """Single audit event entry."""

    def __init__(
        self,
        action: str,
        user: str = "anonymous",
        role: str = "unknown",
        details: Optional[Dict] = None,
        category: str = "general",
        severity: str = "info",
    ):
        self.timestamp = datetime.now().isoformat()
        self.action = action
        self.user = user
        self.role = role
        self.details = details or {}
        self.category = category
        self.severity = severity  # info, warning, error, critical

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "action": self.action,
            "user": self.user,
            "role": self.role,
            "category": self.category,
            "severity": self.severity,
            "details": self.details,
        }


class AuditLogger:
    """
    In-memory audit logger using Streamlit session state.
    Compliant with zero-persistence architecture — logs exist only in session.
    """

    # Event categories
    AUTH = "authentication"
    ANALYSIS = "analysis"
    EXPORT = "export"
    AI = "ai_analysis"
    CONFIG = "configuration"
    DISCOVERY = "discovery"
    ADMIN = "administration"

    def __init__(self, session_state=None, max_entries: int = 10000):
        self._session_state = session_state
        self.max_entries = max_entries
        self._key = "_audit_log"

    def _get_log(self) -> List[Dict]:
        """Get audit log from session state."""
        if self._session_state is not None:
            return self._session_state.get(self._key, [])
        return []

    def _set_log(self, entries: List[Dict]):
        """Set audit log in session state."""
        if self._session_state is not None:
            self._session_state[self._key] = entries

    def log(self, action: str, user: str = "anonymous", role: str = "unknown",
            details: Optional[Dict] = None, category: str = "general",
            severity: str = "info"):
        """Log an audit event."""
        event = AuditEvent(action, user, role, details, category, severity)
        entries = self._get_log()
        entries.append(event.to_dict())

        # Trim if exceeds max
        if len(entries) > self.max_entries:
            entries = entries[-self.max_entries:]

        self._set_log(entries)

    def log_login(self, username: str, success: bool, role: str = "unknown"):
        self.log(
            action="LOGIN_SUCCESS" if success else "LOGIN_FAILED",
            user=username, role=role,
            category=self.AUTH,
            severity="info" if success else "warning",
            details={"success": success},
        )

    def log_logout(self, username: str, role: str = "unknown"):
        self.log(
            action="LOGOUT", user=username, role=role,
            category=self.AUTH,
        )

    def log_analysis(self, username: str, role: str, server_count: int,
                     cloud_provider: str = "", analysis_type: str = "manual"):
        self.log(
            action="SERVER_ANALYSIS", user=username, role=role,
            category=self.ANALYSIS,
            details={
                "server_count": server_count,
                "cloud_provider": cloud_provider,
                "analysis_type": analysis_type,
            },
        )

    def log_export(self, username: str, role: str, format: str,
                   row_count: int):
        self.log(
            action="DATA_EXPORT", user=username, role=role,
            category=self.EXPORT,
            details={"format": format, "row_count": row_count},
        )

    def log_ai_request(self, username: str, role: str,
                       analysis_type: str = "single"):
        self.log(
            action="AI_ANALYSIS_REQUEST", user=username, role=role,
            category=self.AI,
            details={"analysis_type": analysis_type},
        )

    def log_discovery(self, username: str, role: str,
                      source: str, server_count: int):
        self.log(
            action="AUTO_DISCOVERY", user=username, role=role,
            category=self.DISCOVERY,
            details={"source": source, "servers_discovered": server_count},
        )

    def get_entries(self, category: Optional[str] = None,
                    user: Optional[str] = None,
                    limit: int = 100) -> List[Dict]:
        """Get filtered audit entries."""
        entries = self._get_log()

        if category:
            entries = [e for e in entries if e.get("category") == category]
        if user:
            entries = [e for e in entries if e.get("user") == user]

        return entries[-limit:]

    def get_summary(self) -> Dict:
        """Get audit log summary statistics."""
        entries = self._get_log()
        if not entries:
            return {"total_events": 0}

        categories = {}
        users = {}
        severities = {}

        for e in entries:
            cat = e.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1
            user = e.get("user", "anonymous")
            users[user] = users.get(user, 0) + 1
            sev = e.get("severity", "info")
            severities[sev] = severities.get(sev, 0) + 1

        return {
            "total_events": len(entries),
            "by_category": categories,
            "by_user": users,
            "by_severity": severities,
            "first_event": entries[0].get("timestamp", ""),
            "last_event": entries[-1].get("timestamp", ""),
        }

    def export_csv(self) -> str:
        """Export audit log as CSV string."""
        import csv
        entries = self._get_log()
        if not entries:
            return ""

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            "timestamp", "action", "user", "role", "category", "severity", "details"
        ])
        writer.writeheader()
        for e in entries:
            row = dict(e)
            row["details"] = json.dumps(row.get("details", {}))
            writer.writerow(row)

        return output.getvalue()

    def export_json(self) -> str:
        """Export audit log as JSON string."""
        return json.dumps(self._get_log(), indent=2)
