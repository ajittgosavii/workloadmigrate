"""
Historical Run Comparison
============================
Enables comparison between analysis runs to track
how costs change over time. Uses session state for
zero-persistence compliance — history exists only during session.

Features:
  - Save analysis snapshots with labels
  - Compare two snapshots side-by-side
  - Track cost deltas over time
  - Export comparison reports
"""

from datetime import datetime
from typing import Dict, List, Optional
import json
import io


class RunHistory:
    """
    Manages analysis run history within a session.
    Zero-persistence: all data in session state only.
    """

    def __init__(self, session_state=None, max_snapshots: int = 20):
        self._session_state = session_state
        self.max_snapshots = max_snapshots
        self._key = "_run_history"

    def _get_history(self) -> List[Dict]:
        if self._session_state is not None:
            return self._session_state.get(self._key, [])
        return []

    def _set_history(self, entries: List[Dict]):
        if self._session_state is not None:
            self._session_state[self._key] = entries

    def save_snapshot(self, label: str, results: List[Dict],
                      metadata: Optional[Dict] = None) -> str:
        """
        Save an analysis snapshot.
        Returns snapshot ID.
        """
        history = self._get_history()

        # Compute summary
        n = len(results)
        t_op = sum(r["outputs"]["on_prem_yearly_cost"] for r in results)
        t_aws = sum(r["outputs"]["cross_provider"]["AWS"]["annual_3yr_ri"] for r in results)
        t_az = sum(r["outputs"]["cross_provider"]["Azure"]["annual_3yr_ri"] for r in results)
        t_azl = sum(r["outputs"].get("azure_local", {}).get("recommended_annual", 0) for r in results)

        snapshot_id = f"snap_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(history)}"

        snapshot = {
            "id": snapshot_id,
            "label": label,
            "timestamp": datetime.now().isoformat(),
            "server_count": n,
            "summary": {
                "on_prem_annual": round(t_op, 2),
                "aws_annual": round(t_aws, 2),
                "azure_annual": round(t_az, 2),
                "azure_local_annual": round(t_azl, 2),
                "best_cloud": round(min(t_aws, t_az), 2),
                "savings": round(t_op - min(t_aws, t_az), 2),
                "savings_pct": round((t_op - min(t_aws, t_az)) / max(1, t_op) * 100, 1),
            },
            "per_server": [
                {
                    "host_name": r["inputs"].get("host_name", ""),
                    "cloud_provider": r["inputs"].get("cloud_provider", ""),
                    "instance_type": r["outputs"]["recomm_instance_type"],
                    "right_cpu": r["outputs"]["right_sizing_cpu"],
                    "right_mem": r["outputs"]["right_sizing_memory"],
                    "aws_annual": r["outputs"]["cross_provider"]["AWS"]["annual_3yr_ri"],
                    "azure_annual": r["outputs"]["cross_provider"]["Azure"]["annual_3yr_ri"],
                    "on_prem_annual": r["outputs"]["on_prem_yearly_cost"],
                }
                for r in results
            ],
            "metadata": metadata or {},
        }

        history.append(snapshot)

        # Trim old snapshots
        if len(history) > self.max_snapshots:
            history = history[-self.max_snapshots:]

        self._set_history(history)
        return snapshot_id

    def get_snapshots(self) -> List[Dict]:
        """Get list of saved snapshots (summary only, not per-server data)."""
        history = self._get_history()
        return [
            {
                "id": s["id"],
                "label": s["label"],
                "timestamp": s["timestamp"],
                "server_count": s["server_count"],
                "summary": s["summary"],
            }
            for s in history
        ]

    def get_snapshot(self, snapshot_id: str) -> Optional[Dict]:
        """Get a specific snapshot by ID."""
        history = self._get_history()
        for s in history:
            if s["id"] == snapshot_id:
                return s
        return None

    def compare_snapshots(self, id_a: str, id_b: str) -> Optional[Dict]:
        """
        Compare two snapshots side-by-side.
        Returns delta analysis.
        """
        snap_a = self.get_snapshot(id_a)
        snap_b = self.get_snapshot(id_b)

        if not snap_a or not snap_b:
            return None

        sum_a = snap_a["summary"]
        sum_b = snap_b["summary"]

        def delta(key):
            a_val = sum_a.get(key, 0)
            b_val = sum_b.get(key, 0)
            diff = b_val - a_val
            pct = (diff / max(1, abs(a_val))) * 100
            return {"a": a_val, "b": b_val, "delta": round(diff, 2), "delta_pct": round(pct, 1)}

        # Per-server comparison
        hosts_a = {s["host_name"]: s for s in snap_a.get("per_server", [])}
        hosts_b = {s["host_name"]: s for s in snap_b.get("per_server", [])}
        all_hosts = set(hosts_a.keys()) | set(hosts_b.keys())

        server_deltas = []
        for host in sorted(all_hosts):
            sa = hosts_a.get(host, {})
            sb = hosts_b.get(host, {})
            server_deltas.append({
                "host_name": host,
                "in_a": host in hosts_a,
                "in_b": host in hosts_b,
                "instance_a": sa.get("instance_type", "N/A"),
                "instance_b": sb.get("instance_type", "N/A"),
                "aws_delta": round(sb.get("aws_annual", 0) - sa.get("aws_annual", 0), 2),
                "azure_delta": round(sb.get("azure_annual", 0) - sa.get("azure_annual", 0), 2),
                "on_prem_delta": round(sb.get("on_prem_annual", 0) - sa.get("on_prem_annual", 0), 2),
            })

        return {
            "snapshot_a": {"id": id_a, "label": snap_a["label"],
                           "timestamp": snap_a["timestamp"]},
            "snapshot_b": {"id": id_b, "label": snap_b["label"],
                           "timestamp": snap_b["timestamp"]},
            "totals": {
                "on_prem": delta("on_prem_annual"),
                "aws": delta("aws_annual"),
                "azure": delta("azure_annual"),
                "azure_local": delta("azure_local_annual"),
                "savings": delta("savings"),
            },
            "server_count": {
                "a": snap_a["server_count"],
                "b": snap_b["server_count"],
                "added": sum(1 for s in server_deltas if s["in_b"] and not s["in_a"]),
                "removed": sum(1 for s in server_deltas if s["in_a"] and not s["in_b"]),
                "changed": sum(1 for s in server_deltas
                               if s["in_a"] and s["in_b"] and s["instance_a"] != s["instance_b"]),
            },
            "servers": server_deltas,
        }

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot by ID."""
        history = self._get_history()
        new_history = [s for s in history if s["id"] != snapshot_id]
        if len(new_history) < len(history):
            self._set_history(new_history)
            return True
        return False

    def export_comparison_csv(self, comparison: Dict) -> str:
        """Export comparison as CSV."""
        output = io.StringIO()
        output.write("Host,In A,In B,Instance A,Instance B,AWS Delta,Azure Delta,On-Prem Delta\n")
        for s in comparison.get("servers", []):
            output.write(
                f"{s['host_name']},{s['in_a']},{s['in_b']},"
                f"{s['instance_a']},{s['instance_b']},"
                f"{s['aws_delta']},{s['azure_delta']},{s['on_prem_delta']}\n"
            )
        return output.getvalue()
