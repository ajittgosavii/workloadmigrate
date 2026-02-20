"""
Storage Tier Optimization Engine
==================================
Recommends optimal storage tiers (hot/warm/cool/archive) based on
access patterns, age, and cost optimization.

Sources:
  AWS S3:     aws.amazon.com/s3/pricing/
  AWS EBS:    aws.amazon.com/ebs/pricing/
  Azure Blob: azure.microsoft.com/en-us/pricing/details/storage/blobs/
  Azure Disk: azure.microsoft.com/en-us/pricing/details/managed-disks/
"""

from typing import Dict, List, Tuple
import math


# ─── Storage tier pricing (per GB/month) ─────────────────────────────────────
STORAGE_TIERS = {
    "AWS": {
        "hot": {
            "name": "gp3 / S3 Standard",
            "disk_per_gb": 0.08,
            "object_per_gb": 0.023,
            "iops_included": 3000,
            "throughput_included_mbps": 125,
            "min_gb": 1,
        },
        "warm": {
            "name": "st1 / S3 IA",
            "disk_per_gb": 0.045,
            "object_per_gb": 0.0125,
            "iops_included": 500,
            "throughput_included_mbps": 40,
            "min_gb": 125,
        },
        "cool": {
            "name": "sc1 / S3 Glacier IR",
            "disk_per_gb": 0.015,
            "object_per_gb": 0.004,
            "iops_included": 250,
            "throughput_included_mbps": 12,
            "min_gb": 125,
        },
        "archive": {
            "name": "S3 Glacier Deep Archive",
            "disk_per_gb": None,  # No EBS equivalent
            "object_per_gb": 0.00099,
            "retrieval_per_gb": 0.02,
            "retrieval_time": "12 hours",
        },
    },
    "Azure": {
        "hot": {
            "name": "Premium SSD / Hot Blob",
            "disk_per_gb": 0.132,
            "object_per_gb": 0.0184,
            "iops_included": 3500,
            "throughput_included_mbps": 150,
            "min_gb": 1,
        },
        "warm": {
            "name": "Standard SSD / Cool Blob",
            "disk_per_gb": 0.075,
            "object_per_gb": 0.01,
            "iops_included": 500,
            "throughput_included_mbps": 60,
            "min_gb": 1,
        },
        "cool": {
            "name": "Standard HDD / Cold Blob",
            "disk_per_gb": 0.04,
            "object_per_gb": 0.0036,
            "iops_included": 500,
            "throughput_included_mbps": 60,
            "min_gb": 1,
        },
        "archive": {
            "name": "Archive Blob",
            "disk_per_gb": None,
            "object_per_gb": 0.002,
            "retrieval_per_gb": 0.022,
            "retrieval_time": "Up to 15 hours",
        },
    },
}


def classify_storage_tiers(
    total_storage_gb: float,
    storage_usage_pct: float,
    avg_iops: float,
    server_type: str = "Application",
    databases: str = "None",
) -> Dict[str, float]:
    """
    Classify storage into tiers based on access patterns and server type.

    Returns estimated percentage distribution across tiers.
    """
    used_gb = total_storage_gb * (storage_usage_pct / 100.0)

    # Database servers keep most data hot
    if databases.lower() not in ("none", "") or "database" in server_type.lower():
        return {
            "hot": 0.70,
            "warm": 0.20,
            "cool": 0.08,
            "archive": 0.02,
        }

    # High IOPS = mostly hot
    if avg_iops > 5000:
        return {
            "hot": 0.80,
            "warm": 0.15,
            "cool": 0.04,
            "archive": 0.01,
        }

    # Web/API servers
    if server_type in ("Web Server", "API Gateway"):
        return {
            "hot": 0.40,
            "warm": 0.30,
            "cool": 0.20,
            "archive": 0.10,
        }

    # File servers have lots of old data
    if server_type == "File Server":
        return {
            "hot": 0.20,
            "warm": 0.25,
            "cool": 0.30,
            "archive": 0.25,
        }

    # CI/CD and monitoring — lots of logs
    if server_type in ("CI/CD", "Monitoring"):
        return {
            "hot": 0.25,
            "warm": 0.25,
            "cool": 0.30,
            "archive": 0.20,
        }

    # Default: application servers
    return {
        "hot": 0.50,
        "warm": 0.25,
        "cool": 0.15,
        "archive": 0.10,
    }


def calculate_tiered_storage_cost(
    cloud: str,
    total_storage_gb: float,
    storage_usage_pct: float,
    avg_iops: float,
    server_type: str = "Application",
    databases: str = "None",
    region_multiplier: float = 1.0,
) -> Dict:
    """
    Calculate optimized storage cost using tier distribution.
    Compares single-tier (all hot) vs optimized multi-tier approach.
    """
    used_gb = total_storage_gb * (storage_usage_pct / 100.0)
    tiers = STORAGE_TIERS.get(cloud, STORAGE_TIERS["AWS"])
    distribution = classify_storage_tiers(
        total_storage_gb, storage_usage_pct, avg_iops, server_type, databases
    )

    # Calculate optimized cost with tiering
    tier_details = []
    optimized_total = 0.0

    for tier_name, pct in distribution.items():
        tier_gb = used_gb * pct
        tier_info = tiers[tier_name]
        rate = tier_info.get("disk_per_gb") or tier_info.get("object_per_gb", 0)
        cost = tier_gb * rate * region_multiplier

        tier_details.append({
            "tier": tier_name,
            "name": tier_info["name"],
            "gb": round(tier_gb, 2),
            "pct": round(pct * 100, 1),
            "rate_per_gb": rate,
            "monthly_cost": round(cost, 2),
        })
        optimized_total += cost

    # Calculate single-tier cost (all on hot)
    hot_rate = tiers["hot"]["disk_per_gb"]
    single_tier_cost = used_gb * hot_rate * region_multiplier

    savings = single_tier_cost - optimized_total
    savings_pct = (savings / max(1, single_tier_cost)) * 100

    return {
        "used_storage_gb": round(used_gb, 2),
        "distribution": distribution,
        "tier_details": tier_details,
        "optimized_monthly": round(optimized_total, 2),
        "optimized_annual": round(optimized_total * 12, 2),
        "single_tier_monthly": round(single_tier_cost, 2),
        "single_tier_annual": round(single_tier_cost * 12, 2),
        "savings_monthly": round(savings, 2),
        "savings_annual": round(savings * 12, 2),
        "savings_pct": round(savings_pct, 1),
        "recommendation": (
            f"Tiered storage saves {savings_pct:.0f}% (${savings:.2f}/mo) "
            f"by moving {distribution.get('cool', 0)*100:.0f}% to cool "
            f"and {distribution.get('archive', 0)*100:.0f}% to archive tier"
        ),
    }
