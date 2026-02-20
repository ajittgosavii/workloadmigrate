"""
Input Validation & Sanitization Engine
========================================
Comprehensive validation for all 22 input parameters.
Handles edge cases, type checking, range validation,
and provides user-friendly error messages.
"""

import re
from typing import Dict, List, Tuple, Optional

# ─── Valid option sets ────────────────────────────────────────────────────────
VALID_CLOUD_PROVIDERS = {"AWS", "Azure", "Azure Local"}
VALID_PLATFORMS = {"Linux", "Windows", "VMware", "Hyper-V", "Physical"}
VALID_ENVIRONMENTS = {"Production", "Staging", "Development", "Testing", "DR", "QA"}
VALID_SERVER_TYPES = {
    "Web Server", "Application Server", "Database Server", "Cache Server",
    "File Server", "Mail Server", "API Gateway", "Load Balancer", "Monitoring", "CI/CD",
}
VALID_EOL_STATUSES = {"No", "Yes - EOL", "Yes - Extended Support"}
VALID_MIGRATION_TYPES = {
    "Rehost", "Rehost (Lift & Shift)", "Replatform", "Refactor",
    "Repurchase", "Retire", "Retain",
}
VALID_DATABASES = {
    "None", "MySQL", "PostgreSQL", "Oracle", "SQL Server", "MongoDB",
    "Redis", "Memcached", "MariaDB", "DynamoDB", "Cassandra",
}
VALID_INSTANCE_USAGE = {"24x7", "Business Hours", "On-Demand", "Scheduled"}
VALID_OS_LIST = {
    "Ubuntu 22.04", "Ubuntu 20.04", "Ubuntu 24.04 LTS", "Amazon Linux 2",
    "Amazon Linux 2023", "Red Hat Enterprise Linux 8", "Red Hat Enterprise Linux 9",
    "CentOS 7", "CentOS 8", "SUSE Linux Enterprise 15",
    "Windows Server 2022", "Windows Server 2019", "Windows Server 2016",
    "Debian 11", "Debian 12", "Linux",
}

# ─── Regex patterns ──────────────────────────────────────────────────────────
IP_V4_PATTERN = re.compile(
    r'^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)$'
)
HOSTNAME_PATTERN = re.compile(
    r'^[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?'
    r'(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
)
# Allow private IPs (10.x, 172.16-31.x, 192.168.x)
PRIVATE_IP_PATTERN = re.compile(
    r'^(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|'
    r'172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|'
    r'192\.168\.\d{1,3}\.\d{1,3})$'
)


class ValidationResult:
    """Container for validation results with errors and warnings."""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.sanitized: Dict = {}

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, field: str, message: str):
        self.errors.append(f"**{field}**: {message}")

    def add_warning(self, field: str, message: str):
        self.warnings.append(f"**{field}**: {message}")


def validate_hostname(hostname: str) -> Tuple[bool, str]:
    """Validate hostname format."""
    if not hostname or not hostname.strip():
        return True, ""  # Optional field
    hostname = hostname.strip()
    if len(hostname) > 253:
        return False, "Hostname too long (max 253 characters)"
    if not HOSTNAME_PATTERN.match(hostname):
        return False, "Invalid hostname format (use alphanumeric, hyphens, dots)"
    return True, ""


def validate_ip_address(ip: str) -> Tuple[bool, str]:
    """Validate IPv4 address format."""
    if not ip or not ip.strip():
        return True, ""  # Optional field
    ip = ip.strip()
    if not IP_V4_PATTERN.match(ip):
        return False, "Invalid IPv4 format (expected: x.x.x.x where x is 0-255)"
    return True, ""


def validate_numeric_range(value, field_name: str, min_val: float, max_val: float,
                           allow_zero: bool = False) -> Tuple[bool, str, float]:
    """Validate numeric value is within range."""
    try:
        val = float(value)
    except (TypeError, ValueError):
        return False, f"Must be a number (got: {value})", 0.0

    if not allow_zero and val <= 0:
        return False, f"Must be greater than 0 (got: {val})", val

    if val < min_val:
        return False, f"Must be >= {min_val} (got: {val})", val
    if val > max_val:
        return False, f"Must be <= {max_val} (got: {val})", val

    return True, "", val


def validate_enum(value: str, field_name: str, valid_set: set,
                  case_sensitive: bool = False) -> Tuple[bool, str, str]:
    """Validate value is in allowed set."""
    if not value or not str(value).strip():
        return False, f"Required field — choose from: {', '.join(sorted(valid_set))}", ""

    val = str(value).strip()
    if not case_sensitive:
        match = next((v for v in valid_set if v.lower() == val.lower()), None)
    else:
        match = val if val in valid_set else None

    if match is None:
        return False, f"Invalid value '{val}' — choose from: {', '.join(sorted(valid_set))}", val

    return True, "", match


def validate_server_inputs(inputs: Dict) -> ValidationResult:
    """
    Comprehensive validation of all 22 server input parameters.
    Returns ValidationResult with errors, warnings, and sanitized data.
    """
    result = ValidationResult()
    sanitized = dict(inputs)

    # ── Cloud Provider ──
    ok, msg, val = validate_enum(inputs.get("cloud_provider", ""), "Cloud Provider", VALID_CLOUD_PROVIDERS)
    if not ok:
        result.add_error("Cloud Provider", msg)
    else:
        sanitized["cloud_provider"] = val

    # ── Hostname ──
    ok, msg = validate_hostname(inputs.get("host_name", ""))
    if not ok:
        result.add_error("Host Name", msg)

    # ── IP Address ──
    ok, msg = validate_ip_address(inputs.get("ip_address", ""))
    if not ok:
        result.add_error("IP Address", msg)

    # ── Platform ──
    ok, msg, val = validate_enum(inputs.get("platform", ""), "Platform", VALID_PLATFORMS)
    if not ok:
        result.add_warning("Platform", msg + " (defaulting to Linux)")
        sanitized["platform"] = "Linux"
    else:
        sanitized["platform"] = val

    # ── Environment ──
    ok, msg, val = validate_enum(inputs.get("environment", ""), "Environment", VALID_ENVIRONMENTS)
    if not ok:
        result.add_warning("Environment", msg + " (defaulting to Production)")
        sanitized["environment"] = "Production"
    else:
        sanitized["environment"] = val

    # ── Server Type ──
    ok, msg, val = validate_enum(inputs.get("server_type", ""), "Server Type", VALID_SERVER_TYPES)
    if not ok:
        result.add_warning("Server Type", msg + " (defaulting to Application Server)")
        sanitized["server_type"] = "Application Server"
    else:
        sanitized["server_type"] = val

    # ── OS EOL Status ──
    ok, msg, val = validate_enum(inputs.get("os_eol_status", ""), "OS EOL Status", VALID_EOL_STATUSES)
    if not ok:
        sanitized["os_eol_status"] = "No"
    else:
        sanitized["os_eol_status"] = val
        if val != "No":
            result.add_warning("OS EOL Status", f"OS is {val} — migration urgency elevated")

    # ── Migration Type ──
    ok, msg, val = validate_enum(inputs.get("migration_type", ""), "Migration Type", VALID_MIGRATION_TYPES)
    if not ok:
        sanitized["migration_type"] = "Rehost"
    else:
        sanitized["migration_type"] = val

    # ── Instance Usage ──
    ok, msg, val = validate_enum(inputs.get("instance_usage", ""), "Instance Usage", VALID_INSTANCE_USAGE)
    if not ok:
        sanitized["instance_usage"] = "24x7"
    else:
        sanitized["instance_usage"] = val

    # ── Numeric fields ──
    numeric_fields = [
        ("vcpu_count", "vCPU Count", 1, 128, False),
        ("avg_cpu_usage", "Avg CPU Usage (%)", 0, 100, True),
        ("memory_gb", "Memory (GB)", 1, 1024, False),
        ("avg_memory_usage", "Avg Memory Usage (%)", 0, 100, True),
        ("total_storage_gb", "Total Storage (GB)", 10, 65536, False),
        ("storage_usage_pct", "Storage Usage (%)", 0, 100, True),
        ("avg_network_throughput", "Avg Network Throughput (Mbps)", 0, 100000, True),
        ("total_network_throughput", "Total Network Throughput (Mbps)", 0, 100000, True),
        ("avg_disk_iops", "Avg Disk IOPS", 0, 500000, True),
    ]

    for field, name, min_v, max_v, allow_z in numeric_fields:
        ok, msg, val = validate_numeric_range(inputs.get(field, 0), name, min_v, max_v, allow_z)
        if not ok:
            result.add_error(name, msg)
        else:
            sanitized[field] = val

    # ── Cross-field validations ──
    vcpu = sanitized.get("vcpu_count", 0)
    mem = sanitized.get("memory_gb", 0)
    cpu_pct = sanitized.get("avg_cpu_usage", 0)
    mem_pct = sanitized.get("avg_memory_usage", 0)
    stor = sanitized.get("total_storage_gb", 0)
    stor_pct = sanitized.get("storage_usage_pct", 0)
    avg_net = sanitized.get("avg_network_throughput", 0)
    total_net = sanitized.get("total_network_throughput", 0)

    if vcpu > 0 and mem > 0 and (mem / vcpu) > 32:
        result.add_warning("Memory/CPU Ratio",
                           f"Very high memory-to-CPU ratio ({mem/vcpu:.0f} GB/vCPU) — "
                           f"verify this is correct for memory-optimized workloads")

    if cpu_pct < 5 and vcpu >= 4:
        result.add_warning("CPU Utilization",
                           f"Very low CPU usage ({cpu_pct}%) with {vcpu} vCPUs — "
                           f"significant right-sizing opportunity")

    if mem_pct < 5 and mem >= 8:
        result.add_warning("Memory Utilization",
                           f"Very low memory usage ({mem_pct}%) with {mem} GB — "
                           f"consider smaller instance")

    if stor_pct > 90:
        result.add_warning("Storage Usage",
                           f"Storage is {stor_pct}% full — migration may need extra headroom")

    if avg_net > 0 and total_net > 0 and avg_net > total_net:
        result.add_warning("Network Throughput",
                           "Average throughput exceeds total — verify values")

    result.sanitized = sanitized
    return result


def validate_bulk_dataframe(df, required_columns: List[str] = None) -> ValidationResult:
    """
    Validate a bulk-imported DataFrame.
    Checks for missing columns, empty values, data types, and row-level issues.
    """
    result = ValidationResult()

    if required_columns is None:
        required_columns = [
            "Cloud Provider", "Cloud Region", "Host Name", "VCPUCount",
            "Memory(GB)", "Total Storage(GB)",
        ]

    # Check missing columns
    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        result.add_error("Missing Columns", f"Required columns not found: {', '.join(missing)}")
        return result

    # Check for empty dataset
    if len(df) == 0:
        result.add_error("Empty Dataset", "Uploaded file contains no data rows")
        return result

    # Check for duplicate hostnames
    if "Host Name" in df.columns:
        dupes = df["Host Name"].dropna()
        dupe_names = dupes[dupes.duplicated()].unique().tolist()
        if dupe_names:
            result.add_warning("Duplicate Hostnames",
                               f"Found {len(dupe_names)} duplicate hostname(s): "
                               f"{', '.join(str(d) for d in dupe_names[:5])}"
                               f"{'...' if len(dupe_names) > 5 else ''}")

    # Check numeric columns for non-numeric values
    numeric_cols = {
        "VCPUCount": (1, 128),
        "AvgCPUUsage (%tage)": (0, 100),
        "Memory(GB)": (1, 1024),
        "Avg Memory (%tage)": (0, 100),
        "Total Storage(GB)": (10, 65536),
        "Storage Usage (%)": (0, 100),
        "Average Network Throughput (Mbps)": (0, 100000),
        "Total Network Throughput (Mbps)": (0, 100000),
        "Average Disk IOPS": (0, 500000),
    }

    for col, (min_v, max_v) in numeric_cols.items():
        if col in df.columns:
            non_numeric = df[col].apply(lambda x: not _is_numeric(x)).sum()
            if non_numeric > 0:
                result.add_error(col, f"{non_numeric} row(s) have non-numeric values")

            numeric_vals = df[col].apply(lambda x: _safe_float(x))
            out_of_range = ((numeric_vals < min_v) | (numeric_vals > max_v)).sum()
            if out_of_range > 0:
                result.add_warning(col, f"{out_of_range} row(s) outside expected range [{min_v}-{max_v}]")

    # Validate Cloud Provider values
    if "Cloud Provider" in df.columns:
        invalid_providers = df["Cloud Provider"].apply(
            lambda x: str(x).strip() not in VALID_CLOUD_PROVIDERS if x else True
        ).sum()
        if invalid_providers > 0:
            result.add_warning("Cloud Provider",
                               f"{invalid_providers} row(s) have invalid cloud provider values")

    # Check for rows with all-zero metrics
    metric_cols = ["VCPUCount", "Memory(GB)", "Total Storage(GB)"]
    existing_metrics = [c for c in metric_cols if c in df.columns]
    if existing_metrics:
        numeric_df = df[existing_metrics].apply(lambda col: col.apply(lambda x: _safe_float(x)))
        zero_rows = (numeric_df == 0).all(axis=1).sum()
        if zero_rows > 0:
            result.add_warning("Zero Metrics",
                               f"{zero_rows} row(s) have all-zero resource metrics — likely invalid data")

    return result


def _is_numeric(val) -> bool:
    """Check if a value can be converted to float."""
    try:
        float(val)
        return True
    except (TypeError, ValueError):
        return False


def _safe_float(val, default=0.0) -> float:
    """Safely convert to float."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return default
