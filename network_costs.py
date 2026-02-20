"""
Network & Egress Cost Calculator
==================================
Calculates cloud network egress costs, VPN/ExpressRoute/Direct Connect,
and data transfer costs that are often overlooked in migration planning.

Sources:
  AWS:   aws.amazon.com/ec2/pricing/on-demand/#Data_Transfer
  Azure: azure.microsoft.com/en-us/pricing/details/bandwidth/
"""

from typing import Dict


# ─── Egress pricing tiers (per GB/month) ─────────────────────────────────────
AWS_EGRESS_TIERS = [
    (1, 0.00),          # First 1 GB free
    (10 * 1024, 0.09),  # Up to 10 TB: $0.09/GB
    (40 * 1024, 0.085), # 10-50 TB: $0.085/GB
    (100 * 1024, 0.07), # 50-150 TB: $0.07/GB
    (float('inf'), 0.05),  # 150+ TB: $0.05/GB
]

AZURE_EGRESS_TIERS = [
    (5, 0.00),              # First 5 GB free
    (10 * 1024, 0.087),     # 5 GB - 10 TB
    (40 * 1024, 0.083),     # 10-50 TB
    (100 * 1024, 0.07),     # 50-150 TB
    (float('inf'), 0.05),   # 150+ TB
]

# ─── VPN / Private connectivity monthly costs ────────────────────────────────
VPN_COSTS = {
    "AWS": {
        "site_to_site_vpn": 36.50,       # per VPN connection/month
        "direct_connect_1gbps": 220.00,   # per port/month (1 Gbps)
        "direct_connect_10gbps": 1650.00, # per port/month (10 Gbps)
        "transit_gateway": 36.00,         # per attachment/month
        "nat_gateway_per_gb": 0.045,      # per GB processed
    },
    "Azure": {
        "vpn_gateway_basic": 26.00,       # VpnGw1
        "vpn_gateway_standard": 183.96,   # VpnGw2
        "expressroute_1gbps": 218.00,     # Standard - Metered
        "expressroute_10gbps": 3500.00,   # Standard - Unlimited
        "vnet_peering_per_gb": 0.01,      # per GB transferred
    },
}

# ─── Intra-region and inter-region transfer ──────────────────────────────────
INTER_REGION_COSTS = {
    "AWS": 0.02,    # per GB (between AWS regions)
    "Azure": 0.02,  # per GB (between Azure regions)
}

INTRA_REGION_COSTS = {
    "AWS": 0.01,    # per GB (between AZs in same region)
    "Azure": 0.00,  # Free within same VNet
}

# ─── Load balancer costs ─────────────────────────────────────────────────────
LOAD_BALANCER_COSTS = {
    "AWS": {
        "alb_hourly": 0.0225,       # Application LB per hour
        "alb_lcu": 0.008,           # per LCU-hour
        "nlb_hourly": 0.0225,       # Network LB per hour
        "nlb_lcu": 0.006,           # per NLCU-hour
    },
    "Azure": {
        "standard_hourly": 0.025,   # Standard LB per hour
        "rules_per_month": 10.00,   # per rule per month (first 5 free)
        "data_per_gb": 0.005,       # per GB processed
    },
}


def calculate_egress_cost(cloud: str, monthly_gb: float) -> Dict:
    """
    Calculate monthly egress cost based on tiered pricing.
    Returns breakdown with cost per tier and total.
    """
    tiers = AWS_EGRESS_TIERS if cloud == "AWS" else AZURE_EGRESS_TIERS
    remaining = monthly_gb
    total_cost = 0.0
    tier_breakdown = []
    prev_limit = 0

    for limit, rate in tiers:
        tier_size = min(remaining, limit - prev_limit)
        if tier_size <= 0:
            break
        cost = tier_size * rate
        total_cost += cost
        tier_breakdown.append({
            "range": f"{prev_limit:.0f}-{limit:.0f} GB" if limit < float('inf') else f"{prev_limit:.0f}+ GB",
            "gb": round(tier_size, 2),
            "rate": rate,
            "cost": round(cost, 2),
        })
        remaining -= tier_size
        prev_limit = limit

    return {
        "monthly_egress_gb": monthly_gb,
        "monthly_cost": round(total_cost, 2),
        "annual_cost": round(total_cost * 12, 2),
        "tiers": tier_breakdown,
    }


def calculate_network_costs(
    cloud: str,
    avg_throughput_mbps: float,
    total_throughput_mbps: float,
    server_type: str = "Application",
    needs_vpn: bool = True,
    needs_load_balancer: bool = False,
    inter_region_gb: float = 0,
) -> Dict:
    """
    Calculate comprehensive monthly network costs for a server.

    Estimates egress from throughput:
      Monthly egress (GB) ≈ avg_throughput_Mbps × 3600 × hours/month × egress_ratio / 8 / 1024
      egress_ratio: portion of traffic that leaves the cloud (varies by server type)
    """
    # Estimate monthly data volume from throughput
    hours_per_month = 730
    seconds_per_month = hours_per_month * 3600

    # Egress ratio by server type (what % of traffic leaves the cloud)
    egress_ratios = {
        "Web Server": 0.60,
        "Application Server": 0.30,
        "Database Server": 0.10,
        "Cache Server": 0.05,
        "File Server": 0.40,
        "Mail Server": 0.50,
        "API Gateway": 0.55,
        "Load Balancer": 0.50,
        "Monitoring": 0.15,
        "CI/CD": 0.20,
    }
    egress_ratio = egress_ratios.get(server_type, 0.30)

    # Convert Mbps to GB/month (avg throughput × seconds / 8 bits / 1024 MB)
    total_monthly_gb = (avg_throughput_mbps * seconds_per_month) / 8 / 1024
    egress_monthly_gb = total_monthly_gb * egress_ratio

    # Egress cost
    egress = calculate_egress_cost(cloud, egress_monthly_gb)

    # VPN cost
    vpn_cost = 0.0
    vpn_type = "None"
    if needs_vpn:
        if cloud == "AWS":
            vpn_cost = VPN_COSTS["AWS"]["site_to_site_vpn"]
            vpn_type = "Site-to-Site VPN"
        else:
            vpn_cost = VPN_COSTS["Azure"]["vpn_gateway_basic"]
            vpn_type = "VPN Gateway (Basic)"

    # Load balancer cost
    lb_cost = 0.0
    lb_type = "None"
    if needs_load_balancer or server_type in ("Web Server", "API Gateway", "Load Balancer"):
        if cloud == "AWS":
            lb_cost = LOAD_BALANCER_COSTS["AWS"]["alb_hourly"] * hours_per_month
            lb_type = "Application LB"
        else:
            lb_cost = LOAD_BALANCER_COSTS["Azure"]["standard_hourly"] * hours_per_month
            lb_type = "Standard LB"

    # Inter-region transfer
    inter_region_cost = inter_region_gb * INTER_REGION_COSTS.get(cloud, 0.02)

    # NAT Gateway (AWS only, for private subnet internet access)
    nat_cost = 0.0
    if cloud == "AWS":
        nat_cost = egress_monthly_gb * VPN_COSTS["AWS"]["nat_gateway_per_gb"]

    total_monthly = egress["monthly_cost"] + vpn_cost + lb_cost + inter_region_cost + nat_cost

    return {
        "egress": egress,
        "vpn": {"type": vpn_type, "monthly_cost": round(vpn_cost, 2)},
        "load_balancer": {"type": lb_type, "monthly_cost": round(lb_cost, 2)},
        "inter_region": {"gb": inter_region_gb, "monthly_cost": round(inter_region_cost, 2)},
        "nat_gateway": {"monthly_cost": round(nat_cost, 2)} if cloud == "AWS" else None,
        "total_monthly": round(total_monthly, 2),
        "total_annual": round(total_monthly * 12, 2),
        "estimated_egress_gb_month": round(egress_monthly_gb, 2),
        "egress_ratio": egress_ratio,
        "server_type": server_type,
    }


def estimate_migration_transfer_cost(cloud: str, total_storage_gb: float,
                                     storage_usage_pct: float) -> Dict:
    """
    Estimate one-time data transfer cost for migration.
    Ingress is free for both AWS and Azure.
    """
    used_storage = total_storage_gb * (storage_usage_pct / 100.0)

    # AWS Transfer Acceleration: $0.04-$0.08/GB
    # Azure Data Box: $0 for under 100 TB (only device fee)
    transfer_methods = []
    if used_storage < 100:
        transfer_methods.append({
            "method": "Internet Transfer",
            "cost": 0.0,  # Ingress is free
            "estimated_hours": round(used_storage / 100, 1),  # ~100 GB/hr on fast connection
            "note": "Ingress to cloud is free",
        })
    elif used_storage < 10000:
        if cloud == "AWS":
            transfer_methods.append({
                "method": "AWS DataSync",
                "cost": round(used_storage * 0.0125, 2),  # $0.0125/GB
                "estimated_hours": round(used_storage / 500, 1),
                "note": "Automated, encrypted transfer",
            })
        else:
            transfer_methods.append({
                "method": "Azure Data Box Disk",
                "cost": round(used_storage * 0.02, 2),
                "estimated_hours": round(24 + used_storage / 1000 * 2, 1),
                "note": "Ship disks to Azure DC (including transit time)",
            })
    else:
        if cloud == "AWS":
            transfer_methods.append({
                "method": "AWS Snowball Edge",
                "cost": 300.0,  # per device per 10 days
                "estimated_hours": round(48 + used_storage / 5000 * 24, 1),
                "note": "Physical device for large transfers",
            })
        else:
            transfer_methods.append({
                "method": "Azure Data Box",
                "cost": 0.0,  # Device fee only, no per-GB charge under 500TB
                "estimated_hours": round(48 + used_storage / 5000 * 24, 1),
                "note": "Physical device, no per-GB charge",
            })

    return {
        "data_to_transfer_gb": round(used_storage, 2),
        "methods": transfer_methods,
        "recommended": transfer_methods[0],
    }
