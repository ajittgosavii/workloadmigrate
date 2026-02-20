"""
Disaster Recovery & Backup Cost Calculator
=============================================
Estimates DR/backup infrastructure costs for cloud workloads.

Sources:
  AWS Backup:           aws.amazon.com/backup/pricing/
  Azure Backup:         azure.microsoft.com/en-us/pricing/details/backup/
  Azure Site Recovery:  azure.microsoft.com/en-us/pricing/details/site-recovery/
  AWS Elastic DR:       aws.amazon.com/disaster-recovery/pricing/
"""

from typing import Dict


# ─── Backup pricing ──────────────────────────────────────────────────────────
BACKUP_RATES = {
    "AWS": {
        "ebs_snapshot_per_gb": 0.05,        # per GB-month of stored snapshots
        "s3_standard_per_gb": 0.023,         # S3 Standard storage
        "s3_glacier_per_gb": 0.004,          # S3 Glacier Deep Archive
        "rds_backup_per_gb": 0.095,          # RDS automated backup beyond free
        "aws_backup_per_gb": 0.05,           # AWS Backup warm storage
        "aws_backup_cold_per_gb": 0.01,      # AWS Backup cold storage
    },
    "Azure": {
        "lrs_per_gb": 0.025,                 # Locally Redundant Storage
        "grs_per_gb": 0.05,                  # Geo-Redundant Storage
        "blob_cool_per_gb": 0.01,            # Cool tier
        "blob_archive_per_gb": 0.002,        # Archive tier
        "sql_backup_per_gb": 0.095,          # SQL Database backup
        "vm_backup_instance": 10.00,         # Per protected VM instance/month
    },
}

# ─── DR pricing ──────────────────────────────────────────────────────────────
DR_RATES = {
    "AWS": {
        "drs_per_instance_hr": 0.028,        # Elastic Disaster Recovery per source server
        "drs_monthly": 20.44,                # ~$0.028 × 730 hrs
        "pilot_light_compute_pct": 0.10,     # 10% of production compute for pilot light
        "warm_standby_compute_pct": 0.30,    # 30% of production compute for warm standby
    },
    "Azure": {
        "site_recovery_per_instance": 25.00,  # Azure Site Recovery per protected instance
        "pilot_light_compute_pct": 0.10,
        "warm_standby_compute_pct": 0.30,
    },
}

# ─── Backup retention policies ───────────────────────────────────────────────
DEFAULT_RETENTION = {
    "daily_days": 30,
    "weekly_weeks": 12,
    "monthly_months": 12,
    "yearly_years": 3,
    "change_rate_daily_pct": 5,  # Daily data change rate
}


def calculate_backup_costs(
    cloud: str,
    total_storage_gb: float,
    storage_usage_pct: float,
    server_type: str = "Application",
    environment: str = "Production",
    databases: str = "None",
    retention_days: int = 30,
    geo_redundant: bool = False,
) -> Dict:
    """
    Calculate monthly backup costs for a server.

    Methodology:
    - Full backup stored once + incremental daily changes
    - Change rate varies by server type (DB: 10%, App: 5%, Web: 3%)
    - Production gets geo-redundant by default; dev/test gets LRS
    """
    used_gb = total_storage_gb * (storage_usage_pct / 100.0)

    # Daily change rate by server type
    change_rates = {
        "Database Server": 0.10,
        "Application Server": 0.05,
        "Web Server": 0.03,
        "File Server": 0.08,
        "Mail Server": 0.07,
        "Cache Server": 0.15,
        "API Gateway": 0.02,
        "Load Balancer": 0.01,
        "Monitoring": 0.05,
        "CI/CD": 0.04,
    }
    daily_change = change_rates.get(server_type, 0.05)

    # Total backup storage needed:
    # Full backup + (retention_days × daily_change × used_storage)
    full_backup_gb = used_gb
    incremental_total_gb = used_gb * daily_change * retention_days
    total_backup_gb = full_backup_gb + incremental_total_gb

    # Is production? → geo-redundant
    is_prod = environment in ("Production", "DR")
    use_geo = geo_redundant or is_prod

    rates = BACKUP_RATES.get(cloud, BACKUP_RATES["AWS"])

    if cloud == "AWS":
        storage_rate = rates["ebs_snapshot_per_gb"]
        # Long-term in Glacier
        warm_gb = min(total_backup_gb, used_gb * 2)
        cold_gb = max(0, total_backup_gb - warm_gb)
        storage_cost = warm_gb * rates["aws_backup_per_gb"] + cold_gb * rates["aws_backup_cold_per_gb"]

        # DB-specific backup costs
        db_backup_cost = 0.0
        if databases.lower() not in ("none", ""):
            db_backup_cost = used_gb * 0.3 * rates["rds_backup_per_gb"]

        total_monthly = storage_cost + db_backup_cost
    else:
        # Azure
        instance_cost = rates["vm_backup_instance"]
        if use_geo:
            storage_rate = rates["grs_per_gb"]
        else:
            storage_rate = rates["lrs_per_gb"]

        storage_cost = total_backup_gb * storage_rate
        db_backup_cost = 0.0
        if databases.lower() not in ("none", ""):
            db_backup_cost = used_gb * 0.3 * rates["sql_backup_per_gb"]

        total_monthly = instance_cost + storage_cost + db_backup_cost

    return {
        "used_storage_gb": round(used_gb, 2),
        "daily_change_rate": daily_change,
        "total_backup_storage_gb": round(total_backup_gb, 2),
        "retention_days": retention_days,
        "geo_redundant": use_geo,
        "storage_cost_monthly": round(storage_cost, 2),
        "db_backup_cost_monthly": round(db_backup_cost, 2),
        "instance_cost_monthly": round(rates.get("vm_backup_instance", 0), 2) if cloud == "Azure" else 0,
        "total_monthly": round(total_monthly, 2),
        "total_annual": round(total_monthly * 12, 2),
    }


def calculate_dr_costs(
    cloud: str,
    monthly_compute_cost: float,
    total_storage_gb: float,
    storage_usage_pct: float,
    environment: str = "Production",
    dr_strategy: str = "pilot_light",
) -> Dict:
    """
    Calculate monthly DR costs based on strategy.

    Strategies:
    - backup_restore: Cheapest — just restore from backups (RTO: hours)
    - pilot_light: Core services running at minimal (RTO: 10-30 min)
    - warm_standby: Scaled-down but functional (RTO: minutes)
    - multi_site: Full active-active (RTO: near-zero)
    """
    rates = DR_RATES.get(cloud, DR_RATES["AWS"])

    strategies = {
        "backup_restore": {
            "label": "Backup & Restore",
            "rto": "4-24 hours",
            "rpo": "Last backup (1-24 hrs)",
            "compute_pct": 0.0,
            "storage_pct": 1.0,  # Need stored backups
        },
        "pilot_light": {
            "label": "Pilot Light",
            "rto": "10-30 minutes",
            "rpo": "Minutes (replication lag)",
            "compute_pct": rates["pilot_light_compute_pct"],
            "storage_pct": 1.0,
        },
        "warm_standby": {
            "label": "Warm Standby",
            "rto": "Minutes",
            "rpo": "Seconds",
            "compute_pct": rates["warm_standby_compute_pct"],
            "storage_pct": 1.0,
        },
        "multi_site": {
            "label": "Multi-Site Active/Active",
            "rto": "Near-zero",
            "rpo": "Near-zero",
            "compute_pct": 1.0,
            "storage_pct": 1.0,
        },
    }

    strategy = strategies.get(dr_strategy, strategies["pilot_light"])
    used_gb = total_storage_gb * (storage_usage_pct / 100.0)

    # Compute cost for DR region
    dr_compute = monthly_compute_cost * strategy["compute_pct"]

    # Storage replication cost
    if cloud == "AWS":
        dr_storage = used_gb * BACKUP_RATES["AWS"]["ebs_snapshot_per_gb"] * strategy["storage_pct"]
        dr_service = rates["drs_monthly"] if dr_strategy != "backup_restore" else 0
    else:
        dr_storage = used_gb * BACKUP_RATES["Azure"]["grs_per_gb"] * strategy["storage_pct"]
        dr_service = rates["site_recovery_per_instance"] if dr_strategy != "backup_restore" else 0

    total_monthly = dr_compute + dr_storage + dr_service

    # Only Production/DR environments need full DR
    if environment not in ("Production", "DR"):
        total_monthly *= 0.0  # No DR for dev/test
        strategy_note = f"DR not recommended for {environment} — cost set to $0"
    else:
        strategy_note = ""

    return {
        "strategy": dr_strategy,
        "strategy_label": strategy["label"],
        "rto": strategy["rto"],
        "rpo": strategy["rpo"],
        "dr_compute_monthly": round(dr_compute, 2),
        "dr_storage_monthly": round(dr_storage, 2),
        "dr_service_monthly": round(dr_service, 2),
        "total_monthly": round(total_monthly, 2),
        "total_annual": round(total_monthly * 12, 2),
        "note": strategy_note,
    }


def calculate_total_dr_backup(
    cloud: str,
    monthly_compute_cost: float,
    total_storage_gb: float,
    storage_usage_pct: float,
    server_type: str = "Application",
    environment: str = "Production",
    databases: str = "None",
    dr_strategy: str = "pilot_light",
    retention_days: int = 30,
) -> Dict:
    """Combined DR + Backup cost calculation."""
    backup = calculate_backup_costs(
        cloud, total_storage_gb, storage_usage_pct,
        server_type, environment, databases, retention_days,
    )
    dr = calculate_dr_costs(
        cloud, monthly_compute_cost, total_storage_gb,
        storage_usage_pct, environment, dr_strategy,
    )

    total_monthly = backup["total_monthly"] + dr["total_monthly"]

    return {
        "backup": backup,
        "dr": dr,
        "combined_monthly": round(total_monthly, 2),
        "combined_annual": round(total_monthly * 12, 2),
    }
