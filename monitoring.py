"""
Monitoring & Alerting Module
===============================
Provides application-level monitoring, performance metrics,
and alerting for API failures and performance degradation.

Tracks:
  - API response times and error rates
  - Analysis throughput (servers/second)
  - Export generation times
  - Memory usage estimates
  - User session metrics
"""

import time
import logging
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    In-memory metrics collector for application monitoring.
    Stores metrics in session state for zero-persistence compliance.
    """

    def __init__(self):
        self._metrics: Dict[str, List] = defaultdict(list)
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = {}
        self._alerts: List[Dict] = []
        self._start_time = time.time()

    def record_timing(self, metric_name: str, duration_ms: float,
                      tags: Optional[Dict] = None):
        """Record a timing metric (e.g., API response time)."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "value": duration_ms,
            "tags": tags or {},
        }
        self._metrics[metric_name].append(entry)

        # Keep last 1000 entries per metric
        if len(self._metrics[metric_name]) > 1000:
            self._metrics[metric_name] = self._metrics[metric_name][-1000:]

        # Check thresholds
        self._check_timing_alert(metric_name, duration_ms)

    def increment_counter(self, counter_name: str, amount: int = 1):
        """Increment a counter (e.g., total analyses, errors)."""
        self._counters[counter_name] += amount

    def set_gauge(self, gauge_name: str, value: float):
        """Set a gauge value (e.g., active sessions, queue depth)."""
        self._gauges[gauge_name] = value

    def time_operation(self, metric_name: str, tags: Optional[Dict] = None):
        """Context manager to time an operation."""
        return _TimingContext(self, metric_name, tags)

    def get_stats(self, metric_name: str) -> Dict:
        """Get statistics for a timing metric."""
        values = [e["value"] for e in self._metrics.get(metric_name, [])]
        if not values:
            return {"count": 0, "avg": 0, "min": 0, "max": 0, "p95": 0, "p99": 0}

        values.sort()
        n = len(values)
        return {
            "count": n,
            "avg": round(sum(values) / n, 2),
            "min": round(min(values), 2),
            "max": round(max(values), 2),
            "p95": round(values[int(n * 0.95)] if n > 1 else values[0], 2),
            "p99": round(values[int(n * 0.99)] if n > 1 else values[0], 2),
            "last": round(values[-1], 2),
        }

    def get_counter(self, name: str) -> int:
        return self._counters.get(name, 0)

    def get_gauge(self, name: str) -> float:
        return self._gauges.get(name, 0.0)

    def get_dashboard(self) -> Dict:
        """Get comprehensive monitoring dashboard data."""
        uptime = time.time() - self._start_time

        return {
            "uptime_seconds": round(uptime, 0),
            "uptime_display": _format_duration(uptime),
            "api_metrics": {
                "azure_pricing": self.get_stats("api.azure_pricing"),
                "aws_pricing": self.get_stats("api.aws_pricing"),
                "anthropic_ai": self.get_stats("api.anthropic"),
                "currency_api": self.get_stats("api.currency"),
            },
            "analysis_metrics": {
                "single_server": self.get_stats("analysis.single"),
                "batch_server": self.get_stats("analysis.batch_per_server"),
                "total_analyzed": self.get_counter("analysis.total_servers"),
                "total_batches": self.get_counter("analysis.total_batches"),
            },
            "export_metrics": {
                "csv_exports": self.get_counter("export.csv"),
                "excel_exports": self.get_counter("export.excel"),
                "pdf_exports": self.get_counter("export.pdf"),
                "csv_timing": self.get_stats("export.csv_timing"),
                "excel_timing": self.get_stats("export.excel_timing"),
            },
            "error_metrics": {
                "api_errors": self.get_counter("errors.api"),
                "validation_errors": self.get_counter("errors.validation"),
                "export_errors": self.get_counter("errors.export"),
                "total_errors": sum(
                    self.get_counter(f"errors.{k}")
                    for k in ("api", "validation", "export", "general")
                ),
            },
            "alerts": self._alerts[-20:],  # Last 20 alerts
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
        }

    def add_alert(self, severity: str, message: str,
                  source: str = "system"):
        """Add a monitoring alert."""
        alert = {
            "timestamp": datetime.now().isoformat(),
            "severity": severity,  # info, warning, error, critical
            "message": message,
            "source": source,
            "acknowledged": False,
        }
        self._alerts.append(alert)

        # Keep last 100 alerts
        if len(self._alerts) > 100:
            self._alerts = self._alerts[-100:]

        # Log to Python logger
        log_levels = {"info": logging.INFO, "warning": logging.WARNING,
                      "error": logging.ERROR, "critical": logging.CRITICAL}
        logger.log(log_levels.get(severity, logging.INFO),
                   f"[ALERT:{severity.upper()}] {source}: {message}")

    def get_health_status(self) -> Dict:
        """Get overall health status."""
        api_errors = self.get_counter("errors.api")
        total_ops = self.get_counter("analysis.total_servers") + 1

        error_rate = api_errors / max(1, total_ops)

        if error_rate > 0.5:
            status = "unhealthy"
            color = "red"
        elif error_rate > 0.1:
            status = "degraded"
            color = "yellow"
        else:
            status = "healthy"
            color = "green"

        return {
            "status": status,
            "color": color,
            "error_rate": round(error_rate * 100, 1),
            "uptime": _format_duration(time.time() - self._start_time),
            "total_operations": total_ops,
            "active_alerts": sum(1 for a in self._alerts if not a.get("acknowledged")),
        }

    def _check_timing_alert(self, metric_name: str, duration_ms: float):
        """Check if timing exceeds thresholds and create alerts."""
        thresholds = {
            "api.azure_pricing": 10000,    # 10s
            "api.aws_pricing": 10000,
            "api.anthropic": 30000,         # 30s
            "analysis.single": 15000,       # 15s
            "export.excel_timing": 60000,   # 60s
        }

        threshold = thresholds.get(metric_name)
        if threshold and duration_ms > threshold:
            self.add_alert(
                severity="warning",
                message=f"{metric_name} took {duration_ms:.0f}ms (threshold: {threshold}ms)",
                source="performance",
            )


class _TimingContext:
    """Context manager for timing operations."""

    def __init__(self, collector: MetricsCollector, metric_name: str,
                 tags: Optional[Dict] = None):
        self.collector = collector
        self.metric_name = metric_name
        self.tags = tags
        self.start = 0

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start) * 1000
        self.collector.record_timing(self.metric_name, duration_ms, self.tags)
        if exc_type:
            self.collector.increment_counter("errors.general")
        return False  # Don't suppress exceptions


def _format_duration(seconds: float) -> str:
    """Format seconds into human-readable duration."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds / 60:.0f}m"
    hours = seconds / 3600
    if hours < 24:
        return f"{hours:.1f}h"
    return f"{hours / 24:.1f}d"


# Singleton instance for the application
metrics = MetricsCollector()
