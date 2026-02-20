"""
Matilda Server Discovery
===========================
Discovers server inventory exclusively from Matilda.
Supports two methods:
  1. Matilda REST API  — query live inventory
  2. Matilda File Import — upload exported CSV/Excel/JSON

Zero persistence: all data stays in session memory only.
"""

import json
import io
from typing import Dict, List, Optional
from datetime import datetime


class DiscoveryResult:
    """Container for discovery results."""

    def __init__(self, source: str):
        self.source = source
        self.servers: List[Dict] = []
        self.errors: List[str] = []
        self.timestamp = datetime.now().isoformat()
        self.success = False
        self.message = ""

    def add_server(self, server: Dict):
        self.servers.append(server)

    def add_error(self, error: str):
        self.errors.append(error)

    @property
    def count(self) -> int:
        return len(self.servers)


# ═══════════════════════════════════════════════════════════════════════════════
# MATILDA REST API DISCOVERY
# ═══════════════════════════════════════════════════════════════════════════════

def discover_matilda_api(
    base_url: str,
    api_key: str,
    filters: Optional[Dict] = None,
    limit: int = 10000,
) -> DiscoveryResult:
    """
    Discover servers from Matilda via REST API.
    Queries the Matilda inventory endpoint for server data.
    """
    result = DiscoveryResult("Matilda API")

    try:
        import requests

        url = f"{base_url.rstrip('/')}/api/v1/servers"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        params = {"limit": limit}
        if filters:
            if filters.get("environment"):
                params["environment"] = filters["environment"]
            if filters.get("platform"):
                params["platform"] = filters["platform"]
            if filters.get("location"):
                params["location"] = filters["location"]

        resp = requests.get(url, headers=headers, params=params, timeout=60)

        if resp.status_code == 401:
            result.add_error("Authentication failed — check your API key")
            result.message = "Matilda API authentication failed"
            return result
        if resp.status_code != 200:
            result.add_error(f"Matilda API returned HTTP {resp.status_code}")
            result.message = f"API error: HTTP {resp.status_code}"
            return result

        data = resp.json()
        records = data.get("servers", data.get("results", data.get("data", [])))
        if isinstance(data, list):
            records = data

        for rec in records:
            server = _map_matilda_record(rec)
            result.add_server(server)

        result.success = True
        result.message = f"Discovered {result.count:,} servers from Matilda API"

    except ImportError:
        result.add_error("requests package not installed")
        result.message = "requests package not available"
    except requests.exceptions.Timeout:
        result.add_error("Matilda API request timed out after 60s")
        result.message = "Connection timeout — is Matilda reachable?"
    except requests.exceptions.ConnectionError:
        result.add_error("Could not connect to Matilda API")
        result.message = "Connection failed — check the URL"
    except Exception as e:
        result.add_error(str(e))
        result.message = f"Matilda API discovery failed: {str(e)[:100]}"

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# MATILDA FILE IMPORT (CSV / Excel / JSON)
# ═══════════════════════════════════════════════════════════════════════════════

# Column mappings: Matilda export field → our internal field
MATILDA_COLUMN_MAP = {
    # Matilda name variants → internal name
    "server_name": "Host Name",
    "hostname": "Host Name",
    "host_name": "Host Name",
    "name": "Host Name",
    "ip": "IP Address",
    "ip_address": "IP Address",
    "ipaddress": "IP Address",
    "os": "Operating System",
    "operating_system": "Operating System",
    "os_name": "Operating System",
    "platform": "Platform",
    "os_type": "Platform",
    "environment": "Environment",
    "env": "Environment",
    "server_type": "Server Type",
    "type": "Server Type",
    "role": "Server Type",
    "classification": "Server Type",
    "vcpu": "VCPUCount",
    "vcpu_count": "VCPUCount",
    "cpu_count": "VCPUCount",
    "cpus": "VCPUCount",
    "cores": "VCPUCount",
    "cpu_usage": "AvgCPUUsage (%tage)",
    "avg_cpu": "AvgCPUUsage (%tage)",
    "avg_cpu_usage": "AvgCPUUsage (%tage)",
    "cpu_utilization": "AvgCPUUsage (%tage)",
    "memory_gb": "Memory(GB)",
    "memory": "Memory(GB)",
    "ram": "Memory(GB)",
    "ram_gb": "Memory(GB)",
    "memory_usage": "Avg Memory (%tage)",
    "avg_memory": "Avg Memory (%tage)",
    "avg_memory_usage": "Avg Memory (%tage)",
    "memory_utilization": "Avg Memory (%tage)",
    "storage_gb": "Total Storage(GB)",
    "disk_space": "Total Storage(GB)",
    "total_storage": "Total Storage(GB)",
    "storage": "Total Storage(GB)",
    "disk_gb": "Total Storage(GB)",
    "storage_usage": "Storage Usage (%)",
    "storage_utilization": "Storage Usage (%)",
    "disk_usage": "Storage Usage (%)",
    "network_throughput": "Average Network Throughput (Mbps)",
    "avg_network": "Average Network Throughput (Mbps)",
    "network_mbps": "Average Network Throughput (Mbps)",
    "total_network": "Total Network Throughput (Mbps)",
    "iops": "Average Disk IOPS",
    "avg_iops": "Average Disk IOPS",
    "disk_iops": "Average Disk IOPS",
    "database": "Databases/Caches",
    "databases": "Databases/Caches",
    "db": "Databases/Caches",
    "app_services": "AppServices",
    "applications": "AppServices",
    "cloud_provider": "Cloud Provider",
    "target_cloud": "Cloud Provider",
    "cloud": "Cloud Provider",
    "region": "Cloud Region",
    "cloud_region": "Cloud Region",
    "location": "Cloud Region",
    "migration_type": "Migration Type",
    "migration_strategy": "Migration Type",
    "eol_status": "OS EOL Status",
    "os_eol": "OS EOL Status",
    "usage_pattern": "InstanceUsage",
    "instance_usage": "InstanceUsage",
}


def discover_matilda_file(file_data, filename: str) -> DiscoveryResult:
    """
    Import server inventory from a Matilda-exported file.
    Supports CSV, Excel (.xlsx/.xls), and JSON.
    Auto-maps Matilda column names to our internal format.
    """
    result = DiscoveryResult("Matilda File Import")

    try:
        import pandas as pd

        # Read file based on extension
        fname_lower = filename.lower()
        if fname_lower.endswith(".json"):
            return _import_matilda_json(file_data)
        elif fname_lower.endswith(".csv"):
            df = pd.read_csv(file_data)
        elif fname_lower.endswith((".xlsx", ".xls")):
            df = pd.read_excel(file_data)
        else:
            result.add_error(f"Unsupported file format: {filename}")
            result.message = "Please upload CSV, Excel, or JSON files"
            return result

        if df.empty:
            result.add_error("File contains no data")
            result.message = "Empty file uploaded"
            return result

        # Auto-map columns
        df = _auto_map_columns(df)

        # Convert each row to a server dict
        for _, row in df.iterrows():
            server = _row_to_server(row)
            result.add_server(server)

        result.success = True
        result.message = f"Imported {result.count:,} servers from Matilda export ({filename})"

    except Exception as e:
        result.add_error(str(e))
        result.message = f"File import failed: {str(e)[:100]}"

    return result


def _import_matilda_json(file_data) -> DiscoveryResult:
    """Import from Matilda JSON export."""
    result = DiscoveryResult("Matilda JSON Import")

    try:
        if hasattr(file_data, 'read'):
            raw = file_data.read()
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
        else:
            raw = file_data

        data = json.loads(raw)

        # Handle various JSON structures Matilda might export
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            records = data.get("servers", data.get("results",
                     data.get("data", data.get("inventory", []))))
        else:
            result.add_error("Unexpected JSON structure")
            result.message = "JSON must be an array or object with a servers key"
            return result

        for rec in records:
            server = _map_matilda_record(rec)
            result.add_server(server)

        result.success = True
        result.message = f"Imported {result.count:,} servers from Matilda JSON"

    except json.JSONDecodeError as e:
        result.add_error(f"Invalid JSON: {e}")
        result.message = "Failed to parse JSON file"
    except Exception as e:
        result.add_error(str(e))
        result.message = f"JSON import failed: {str(e)[:100]}"

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# COLUMN & RECORD MAPPING
# ═══════════════════════════════════════════════════════════════════════════════

def _auto_map_columns(df):
    """Auto-map Matilda export columns to our internal column names."""
    import pandas as pd

    rename_map = {}
    for col in df.columns:
        normalized = col.strip().lower().replace(" ", "_").replace("-", "_")
        if normalized in MATILDA_COLUMN_MAP:
            rename_map[col] = MATILDA_COLUMN_MAP[normalized]
        elif col in MATILDA_COLUMN_MAP.values():
            pass  # Already in our format
    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def _map_matilda_record(rec: Dict) -> Dict:
    """Map a single Matilda API/JSON record to our input format."""
    # Normalize keys to lowercase for flexible matching
    norm = {k.strip().lower().replace(" ", "_").replace("-", "_"): v for k, v in rec.items()}

    def get(keys, default=""):
        for k in keys:
            if k in norm and norm[k] is not None and str(norm[k]).strip():
                return norm[k]
        return default

    hostname = str(get(["server_name", "hostname", "host_name", "name"], "unknown"))
    os_name = str(get(["operating_system", "os", "os_name"], "Linux"))
    platform = str(get(["platform", "os_type"], _guess_platform(os_name)))
    env = str(get(["environment", "env"], "Production"))
    stype = str(get(["server_type", "type", "role", "classification"], "Application Server"))

    return {
        "Cloud Provider": str(get(["cloud_provider", "target_cloud", "cloud"], "AWS")),
        "Cloud Region": str(get(["cloud_region", "region", "location"], "US East (N. Virginia)")),
        "Host Name": hostname,
        "IP Address": str(get(["ip_address", "ip", "ipaddress"], "")),
        "Platform": platform,
        "Operating System": os_name,
        "Environment": _normalize_environment(env),
        "Server Type": _normalize_server_type(stype),
        "OS EOL Status": str(get(["os_eol", "eol_status", "os_eol_status"], "No")),
        "Migration Type": str(get(["migration_type", "migration_strategy"], "Rehost (Lift & Shift)")),
        "Databases/Caches": str(get(["databases", "database", "db", "databases_caches"], "None")),
        "AppServices": str(get(["app_services", "applications", "appservices"], "")),
        "InstanceUsage": str(get(["instance_usage", "usage_pattern"], "24x7")),
        "VCPUCount": _safe_int(get(["vcpu", "vcpu_count", "cpu_count", "cpus", "cores"], 4)),
        "AvgCPUUsage (%tage)": _safe_float(get(["cpu_usage", "avg_cpu", "avg_cpu_usage", "cpu_utilization"], 50)),
        "Memory(GB)": _safe_float(get(["memory_gb", "memory", "ram", "ram_gb"], 16)),
        "Avg Memory (%tage)": _safe_float(get(["memory_usage", "avg_memory", "avg_memory_usage", "memory_utilization"], 50)),
        "Total Storage(GB)": _safe_float(get(["storage_gb", "total_storage", "disk_space", "storage", "disk_gb"], 200)),
        "Storage Usage (%)": _safe_float(get(["storage_usage", "storage_utilization", "disk_usage"], 60)),
        "Average Network Throughput (Mbps)": _safe_float(get(["network_throughput", "avg_network", "network_mbps"], 100)),
        "Total Network Throughput (Mbps)": _safe_float(get(["total_network", "total_network_throughput"], 1000)),
        "Average Disk IOPS": _safe_float(get(["iops", "avg_iops", "disk_iops"], 500)),
        "_source": "matilda",
    }


def _row_to_server(row) -> Dict:
    """Convert a pandas DataFrame row (after column mapping) to our input format."""
    def g(key, default=""):
        val = row.get(key, default)
        if val is None or (isinstance(val, float) and str(val) == "nan"):
            return default
        return val

    hostname = str(g("Host Name", "unknown"))
    os_name = str(g("Operating System", "Linux"))
    platform = str(g("Platform", _guess_platform(os_name)))

    return {
        "Cloud Provider": str(g("Cloud Provider", "AWS")),
        "Cloud Region": str(g("Cloud Region", "US East (N. Virginia)")),
        "Host Name": hostname,
        "IP Address": str(g("IP Address", "")),
        "Platform": platform,
        "Operating System": os_name,
        "Environment": _normalize_environment(str(g("Environment", "Production"))),
        "Server Type": _normalize_server_type(str(g("Server Type", "Application Server"))),
        "OS EOL Status": str(g("OS EOL Status", "No")),
        "Migration Type": str(g("Migration Type", "Rehost (Lift & Shift)")),
        "Databases/Caches": str(g("Databases/Caches", "None")),
        "AppServices": str(g("AppServices", "")),
        "InstanceUsage": str(g("InstanceUsage", "24x7")),
        "VCPUCount": _safe_int(g("VCPUCount", 4)),
        "AvgCPUUsage (%tage)": _safe_float(g("AvgCPUUsage (%tage)", 50)),
        "Memory(GB)": _safe_float(g("Memory(GB)", 16)),
        "Avg Memory (%tage)": _safe_float(g("Avg Memory (%tage)", 50)),
        "Total Storage(GB)": _safe_float(g("Total Storage(GB)", 200)),
        "Storage Usage (%)": _safe_float(g("Storage Usage (%)", 60)),
        "Average Network Throughput (Mbps)": _safe_float(g("Average Network Throughput (Mbps)", 100)),
        "Total Network Throughput (Mbps)": _safe_float(g("Total Network Throughput (Mbps)", 1000)),
        "Average Disk IOPS": _safe_float(g("Average Disk IOPS", 500)),
        "_source": "matilda",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _guess_platform(os_name: str) -> str:
    ol = os_name.lower()
    if "windows" in ol:
        return "Windows"
    if "vmware" in ol or "esx" in ol:
        return "VMware"
    return "Linux"


def _normalize_environment(env: str) -> str:
    el = env.strip().lower()
    mapping = {
        "production": "Production", "prod": "Production", "prd": "Production",
        "development": "Development", "dev": "Development",
        "test": "Testing", "testing": "Testing", "tst": "Testing",
        "qa": "QA",
        "staging": "Staging", "stage": "Staging", "stg": "Staging",
        "dr": "DR", "disaster": "DR",
        "uat": "UAT",
    }
    for k, v in mapping.items():
        if k in el:
            return v
    return env.strip() if env.strip() else "Production"


def _normalize_server_type(stype: str) -> str:
    sl = stype.strip().lower()
    if "web" in sl:
        return "Web Server"
    if "database" in sl or "db " in sl or sl == "db":
        return "Database Server"
    if "mail" in sl or "email" in sl:
        return "Mail Server"
    if "file" in sl:
        return "File Server"
    if "app" in sl:
        return "Application Server"
    return stype.strip() if stype.strip() else "Application Server"


def _safe_int(val, default: int = 4) -> int:
    try:
        return max(1, int(float(str(val).replace(",", "").strip())))
    except (ValueError, TypeError):
        return default


def _safe_float(val, default: float = 0.0) -> float:
    try:
        v = float(str(val).replace(",", "").replace("%", "").strip())
        return v if v >= 0 else default
    except (ValueError, TypeError):
        return default
