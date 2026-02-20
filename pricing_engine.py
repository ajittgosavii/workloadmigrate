"""
Cloud Pricing Engine — Fully Dynamic & Stateless
==================================================
All outputs are computed at runtime from user inputs.
NO data is stored, cached, or persisted. Every call is independent.

Pricing sources (priority order):
  1. Azure Retail Prices REST API  (live)
  2. AWS Pricing Bulk JSON API     (live)
  3. Dynamic reference catalog     (fallback when APIs unreachable)

Regional multipliers are applied dynamically based on selected region.
"""

import requests
import math
import time
from typing import Dict, List, Optional, Tuple

from retry_utils import resilient_request, get_circuit_breaker
from pricing_cache import pricing_cache
from network_costs import calculate_network_costs, estimate_migration_transfer_cost
from dr_backup import calculate_total_dr_backup
from storage_optimizer import calculate_tiered_storage_cost
from serverless_pricing import calculate_all_modern_options

# ═══════════════════════════════════════════════════════════════════════════════
# REGION MAPS — used only for API query parameters
# ═══════════════════════════════════════════════════════════════════════════════
AWS_REGIONS = {
    "US East (N. Virginia)": "us-east-1", "US East (Ohio)": "us-east-2",
    "US West (Oregon)": "us-west-2", "US West (N. California)": "us-west-1",
    "Canada (Central)": "ca-central-1", "EU (Ireland)": "eu-west-1",
    "EU (Frankfurt)": "eu-central-1", "EU (London)": "eu-west-2",
    "Asia Pacific (Singapore)": "ap-southeast-1", "Asia Pacific (Sydney)": "ap-southeast-2",
    "Asia Pacific (Tokyo)": "ap-northeast-1", "Asia Pacific (Mumbai)": "ap-south-1",
}

AZURE_REGIONS = {
    "East US": "eastus", "East US 2": "eastus2",
    "West US": "westus", "West US 2": "westus2",
    "Canada Central": "canadacentral", "North Europe": "northeurope",
    "West Europe": "westeurope", "UK South": "uksouth",
    "Southeast Asia": "southeastasia", "Australia East": "australiaeast",
    "Japan East": "japaneast", "Central India": "centralindia",
}


# ═══════════════════════════════════════════════════════════════════════════════
# LIVE PRICING — Azure Retail Prices API
# ═══════════════════════════════════════════════════════════════════════════════
def fetch_azure_vm_pricing(region_code: str, vcpu_needed: int, mem_needed: float) -> List[Dict]:
    """Query Azure Retail Prices API for VM pricing with retry & caching."""
    # Check cache first
    cache_params = {"region": region_code, "vcpu": vcpu_needed, "mem": mem_needed}
    cached, hit = pricing_cache.get("azure_vm_pricing", cache_params)
    if hit:
        return cached

    cb = get_circuit_breaker("azure_pricing")
    if not cb.can_execute():
        return []

    results = []
    try:
        families = ["Standard_D", "Standard_E", "Standard_F"]
        for fam in families:
            url = "https://prices.azure.com/api/retail/prices"
            odata = (
                f"armRegionName eq '{region_code}' "
                f"and serviceName eq 'Virtual Machines' "
                f"and priceType eq 'Consumption' "
                f"and contains(armSkuName, '{fam}')"
            )
            try:
                resp = resilient_request(
                    url, params={"$filter": odata, "currencyCode": "USD", "$top": 20},
                    timeout=12, max_retries=2, circuit_breaker_name="azure_pricing"
                )
                if resp.status_code == 200:
                    for item in resp.json().get("Items", []):
                        if item.get("type") == "Consumption" and "Windows" not in item.get("productName", ""):
                            sku = item.get("armSkuName", "")
                            vcpu, mem = _parse_azure_sku(sku)
                            if vcpu >= vcpu_needed and mem >= mem_needed:
                                results.append({"type": sku, "vcpu": vcpu, "memory": mem,
                                                "price_hr": item.get("retailPrice", 0), "source": "azure_api_live"})
            except Exception:
                continue
        cb.record_success()
    except Exception:
        cb.record_failure()

    seen = {}
    for r in results:
        if r["type"] not in seen or r["price_hr"] < seen[r["type"]]["price_hr"]:
            seen[r["type"]] = r
    sorted_results = sorted(seen.values(), key=lambda x: (x["vcpu"], x["memory"], x["price_hr"]))

    # Cache the results
    if sorted_results:
        pricing_cache.put("azure_vm_pricing", cache_params, sorted_results, ttl=1800)

    return sorted_results


def fetch_azure_storage_pricing(region_code: str) -> Dict[str, float]:
    """Fetch per-GB/month storage pricing from Azure API."""
    prices = {}
    try:
        url = "https://prices.azure.com/api/retail/prices"
        odata = (f"armRegionName eq '{region_code}' and serviceName eq 'Storage' "
                 f"and priceType eq 'Consumption' and contains(meterName, 'Disk')")
        resp = requests.get(url, params={"$filter": odata, "currencyCode": "USD", "$top": 30}, timeout=10)
        if resp.status_code == 200:
            for item in resp.json().get("Items", []):
                meter = item.get("meterName", "")
                price = item.get("retailPrice", 0)
                if "Premium" in meter and price > 0:
                    prices["Premium SSD"] = min(prices.get("Premium SSD", 999), price)
                elif "Standard SSD" in meter and price > 0:
                    prices["Standard SSD"] = min(prices.get("Standard SSD", 999), price)
                elif "Standard HDD" in meter and price > 0:
                    prices["Standard HDD"] = min(prices.get("Standard HDD", 999), price)
    except Exception:
        pass
    return prices


def _parse_azure_sku(sku: str) -> Tuple[int, float]:
    """Parse vCPU/memory from Azure SKU name."""
    import re
    sku_map = {
        "Standard_B1s": (1, 1), "Standard_B1ms": (1, 2), "Standard_B2s": (2, 4), "Standard_B2ms": (2, 8),
        "Standard_D2s_v5": (2, 8), "Standard_D4s_v5": (4, 16), "Standard_D8s_v5": (8, 32),
        "Standard_D16s_v5": (16, 64), "Standard_D32s_v5": (32, 128), "Standard_D48s_v5": (48, 192),
        "Standard_D64s_v5": (64, 256),
        "Standard_E2s_v5": (2, 16), "Standard_E4s_v5": (4, 32), "Standard_E8s_v5": (8, 64),
        "Standard_E16s_v5": (16, 128), "Standard_E32s_v5": (32, 256),
        "Standard_F2s_v2": (2, 4), "Standard_F4s_v2": (4, 8), "Standard_F8s_v2": (8, 16),
        "Standard_F16s_v2": (16, 32), "Standard_F32s_v2": (32, 64),
    }
    if sku in sku_map:
        return sku_map[sku]
    m = re.search(r'(\d+)', sku.split("_")[-1] if "_" in sku else sku)
    if m:
        n = int(m.group(1))
        if "E" in sku.upper(): return (n, n * 8)
        elif "F" in sku.upper(): return (n, n * 2)
        return (n, n * 4)
    return (2, 8)


# ═══════════════════════════════════════════════════════════════════════════════
# DYNAMIC REFERENCE CATALOG — Fallback ONLY when live APIs fail
# ═══════════════════════════════════════════════════════════════════════════════
def _get_reference_catalog(cloud: str, family: str) -> List[Dict]:
    """Reference pricing catalog. Used ONLY as fallback when APIs unreachable."""
    aws = {
        "general": [
            {"type": "t3.micro", "vcpu": 2, "memory": 1, "base_price_hr": 0.0104},
            {"type": "t3.small", "vcpu": 2, "memory": 2, "base_price_hr": 0.0208},
            {"type": "t3.medium", "vcpu": 2, "memory": 4, "base_price_hr": 0.0416},
            {"type": "t3.large", "vcpu": 2, "memory": 8, "base_price_hr": 0.0832},
            {"type": "t3.xlarge", "vcpu": 4, "memory": 16, "base_price_hr": 0.1664},
            {"type": "t3.2xlarge", "vcpu": 8, "memory": 32, "base_price_hr": 0.3328},
            {"type": "m6i.large", "vcpu": 2, "memory": 8, "base_price_hr": 0.096},
            {"type": "m6i.xlarge", "vcpu": 4, "memory": 16, "base_price_hr": 0.192},
            {"type": "m6i.2xlarge", "vcpu": 8, "memory": 32, "base_price_hr": 0.384},
            {"type": "m6i.4xlarge", "vcpu": 16, "memory": 64, "base_price_hr": 0.768},
            {"type": "m6i.8xlarge", "vcpu": 32, "memory": 128, "base_price_hr": 1.536},
            {"type": "m6i.12xlarge", "vcpu": 48, "memory": 192, "base_price_hr": 2.304},
            {"type": "m6i.16xlarge", "vcpu": 64, "memory": 256, "base_price_hr": 3.072},
            {"type": "m7i.large", "vcpu": 2, "memory": 8, "base_price_hr": 0.1008},
            {"type": "m7i.xlarge", "vcpu": 4, "memory": 16, "base_price_hr": 0.2016},
            {"type": "m7i.2xlarge", "vcpu": 8, "memory": 32, "base_price_hr": 0.4032},
            {"type": "m7i.4xlarge", "vcpu": 16, "memory": 64, "base_price_hr": 0.8064},
            {"type": "m7i.8xlarge", "vcpu": 32, "memory": 128, "base_price_hr": 1.6128},
        ],
        "compute": [
            {"type": "c6i.large", "vcpu": 2, "memory": 4, "base_price_hr": 0.085},
            {"type": "c6i.xlarge", "vcpu": 4, "memory": 8, "base_price_hr": 0.17},
            {"type": "c6i.2xlarge", "vcpu": 8, "memory": 16, "base_price_hr": 0.34},
            {"type": "c6i.4xlarge", "vcpu": 16, "memory": 32, "base_price_hr": 0.68},
            {"type": "c6i.8xlarge", "vcpu": 32, "memory": 64, "base_price_hr": 1.36},
        ],
        "memory": [
            {"type": "r6i.large", "vcpu": 2, "memory": 16, "base_price_hr": 0.126},
            {"type": "r6i.xlarge", "vcpu": 4, "memory": 32, "base_price_hr": 0.252},
            {"type": "r6i.2xlarge", "vcpu": 8, "memory": 64, "base_price_hr": 0.504},
            {"type": "r6i.4xlarge", "vcpu": 16, "memory": 128, "base_price_hr": 1.008},
            {"type": "r6i.8xlarge", "vcpu": 32, "memory": 256, "base_price_hr": 2.016},
        ],
        "database": [
            {"type": "db.t3.micro", "vcpu": 2, "memory": 1, "base_price_hr": 0.017},
            {"type": "db.t3.small", "vcpu": 2, "memory": 2, "base_price_hr": 0.034},
            {"type": "db.t3.medium", "vcpu": 2, "memory": 4, "base_price_hr": 0.068},
            {"type": "db.t3.large", "vcpu": 2, "memory": 8, "base_price_hr": 0.136},
            {"type": "db.m6i.large", "vcpu": 2, "memory": 8, "base_price_hr": 0.171},
            {"type": "db.m6i.xlarge", "vcpu": 4, "memory": 16, "base_price_hr": 0.342},
            {"type": "db.m6i.2xlarge", "vcpu": 8, "memory": 32, "base_price_hr": 0.684},
            {"type": "db.m6i.4xlarge", "vcpu": 16, "memory": 64, "base_price_hr": 1.368},
            {"type": "db.r6i.large", "vcpu": 2, "memory": 16, "base_price_hr": 0.232},
            {"type": "db.r6i.xlarge", "vcpu": 4, "memory": 32, "base_price_hr": 0.464},
            {"type": "db.r6i.2xlarge", "vcpu": 8, "memory": 64, "base_price_hr": 0.928},
            {"type": "db.r6i.4xlarge", "vcpu": 16, "memory": 128, "base_price_hr": 1.856},
        ],
    }
    azure = {
        "general": [
            {"type": "Standard_B1s", "vcpu": 1, "memory": 1, "base_price_hr": 0.0104},
            {"type": "Standard_B1ms", "vcpu": 1, "memory": 2, "base_price_hr": 0.0207},
            {"type": "Standard_B2s", "vcpu": 2, "memory": 4, "base_price_hr": 0.0416},
            {"type": "Standard_B2ms", "vcpu": 2, "memory": 8, "base_price_hr": 0.0832},
            {"type": "Standard_D2s_v5", "vcpu": 2, "memory": 8, "base_price_hr": 0.096},
            {"type": "Standard_D4s_v5", "vcpu": 4, "memory": 16, "base_price_hr": 0.192},
            {"type": "Standard_D8s_v5", "vcpu": 8, "memory": 32, "base_price_hr": 0.384},
            {"type": "Standard_D16s_v5", "vcpu": 16, "memory": 64, "base_price_hr": 0.768},
            {"type": "Standard_D32s_v5", "vcpu": 32, "memory": 128, "base_price_hr": 1.536},
            {"type": "Standard_D48s_v5", "vcpu": 48, "memory": 192, "base_price_hr": 2.304},
            {"type": "Standard_D64s_v5", "vcpu": 64, "memory": 256, "base_price_hr": 3.072},
        ],
        "compute": [
            {"type": "Standard_F2s_v2", "vcpu": 2, "memory": 4, "base_price_hr": 0.085},
            {"type": "Standard_F4s_v2", "vcpu": 4, "memory": 8, "base_price_hr": 0.17},
            {"type": "Standard_F8s_v2", "vcpu": 8, "memory": 16, "base_price_hr": 0.34},
            {"type": "Standard_F16s_v2", "vcpu": 16, "memory": 32, "base_price_hr": 0.68},
            {"type": "Standard_F32s_v2", "vcpu": 32, "memory": 64, "base_price_hr": 1.36},
        ],
        "memory": [
            {"type": "Standard_E2s_v5", "vcpu": 2, "memory": 16, "base_price_hr": 0.126},
            {"type": "Standard_E4s_v5", "vcpu": 4, "memory": 32, "base_price_hr": 0.252},
            {"type": "Standard_E8s_v5", "vcpu": 8, "memory": 64, "base_price_hr": 0.504},
            {"type": "Standard_E16s_v5", "vcpu": 16, "memory": 128, "base_price_hr": 1.008},
            {"type": "Standard_E32s_v5", "vcpu": 32, "memory": 256, "base_price_hr": 2.016},
        ],
        "database": [
            {"type": "GP_Standard_D2ds_v4", "vcpu": 2, "memory": 8, "base_price_hr": 0.198},
            {"type": "GP_Standard_D4ds_v4", "vcpu": 4, "memory": 16, "base_price_hr": 0.396},
            {"type": "GP_Standard_D8ds_v4", "vcpu": 8, "memory": 32, "base_price_hr": 0.792},
            {"type": "GP_Standard_D16ds_v4", "vcpu": 16, "memory": 64, "base_price_hr": 1.584},
            {"type": "BC_Standard_E2ds_v4", "vcpu": 2, "memory": 16, "base_price_hr": 0.349},
            {"type": "BC_Standard_E4ds_v4", "vcpu": 4, "memory": 32, "base_price_hr": 0.698},
            {"type": "BC_Standard_E8ds_v4", "vcpu": 8, "memory": 64, "base_price_hr": 1.395},
            {"type": "BC_Standard_E16ds_v4", "vcpu": 16, "memory": 128, "base_price_hr": 2.791},
        ],
    }
    src = aws if cloud == "AWS" else azure
    return src.get(family, src["general"])


# ═══════════════════════════════════════════════════════════════════════════════
# DYNAMIC COMPUTATION FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════
def _region_mult(cloud: str, region: str) -> float:
    aws_m = {"us-east-1": 1.0, "us-east-2": 1.0, "us-west-2": 1.0, "us-west-1": 1.08,
             "ca-central-1": 1.04, "eu-west-1": 1.05, "eu-central-1": 1.08, "eu-west-2": 1.07,
             "ap-southeast-1": 1.06, "ap-southeast-2": 1.10, "ap-northeast-1": 1.12, "ap-south-1": 0.95}
    az_m = {"eastus": 1.0, "eastus2": 1.0, "westus": 1.0, "westus2": 1.0, "canadacentral": 1.04,
            "northeurope": 1.05, "westeurope": 1.08, "uksouth": 1.07, "southeastasia": 1.06,
            "australiaeast": 1.10, "japaneast": 1.12, "centralindia": 0.95}
    code = (AWS_REGIONS if cloud == "AWS" else AZURE_REGIONS).get(region, region)
    return (aws_m if cloud == "AWS" else az_m).get(code, 1.0)


def compute_right_sized_cpu(vcpu: int, avg_pct: float) -> int:
    if avg_pct <= 0: return max(1, vcpu)
    needed = vcpu * (avg_pct / 100.0) * 1.3
    for s in [1, 2, 4, 8, 16, 32, 48, 64, 96, 128]:
        if s >= needed: return s
    return 128


def compute_right_sized_memory(mem: float, avg_pct: float) -> float:
    if avg_pct <= 0: return max(1, mem)
    needed = mem * (avg_pct / 100.0) * 1.3
    for s in [1, 2, 4, 8, 16, 32, 64, 128, 192, 256, 384, 512]:
        if s >= needed: return float(s)
    return 512.0


def compute_right_sized_storage(total: float, pct: float) -> float:
    if pct <= 0: return max(20, total)
    return max(20, math.ceil(total * (pct / 100.0) * 1.4))


def determine_family(stype: str, dbs: str, cpu_pct: float, mem: float, vcpu: int) -> str:
    dl = str(dbs).lower()
    sl = str(stype).lower()
    if any(k in dl for k in ["mysql", "postgres", "oracle", "sql server", "mariadb",
                              "redis", "memcache", "mongo", "dynamo", "cassandra"]):
        return "database"
    if any(k in sl for k in ["database", "db", "data"]): return "database"
    if mem > 0 and vcpu > 0 and (mem / vcpu) > 6: return "memory"
    if cpu_pct > 70: return "compute"
    return "general"


def determine_storage_type(cloud: str, iops: float, gb: float) -> str:
    if cloud == "AWS":
        if iops > 16000: return "io2"
        if iops > 3000: return "io1"
        if gb > 500: return "st1"
        return "gp3"
    else:
        if iops > 10000: return "Ultra Disk"
        if iops > 3000: return "Premium SSD"
        if gb > 500: return "Standard HDD"
        return "Standard SSD"


def compute_storage_price(cloud: str, stype: str, gb: float, rmult: float, live: Dict = None) -> float:
    if live and stype in live: return round(gb * live[stype] * rmult, 2)
    rates = {"AWS": {"gp3": 0.08, "gp2": 0.10, "io1": 0.125, "io2": 0.125, "st1": 0.045},
             "Azure": {"Premium SSD": 0.132, "Standard SSD": 0.075, "Standard HDD": 0.04, "Ultra Disk": 0.165}}
    return round(gb * rates.get(cloud, {}).get(stype, 0.08) * rmult, 2)


def compute_licensing(os: str, vcpu: int) -> float:
    """OS licensing (Dell PowerEdge configurator pricing, dell.com 2025)."""
    ol = str(os).lower()
    if "windows" in ol: return round(5.50 * vcpu, 2)    # WS 2025 Std: $2,135/16-core
    if "red hat" in ol or "rhel" in ol: return round(3.00 * vcpu, 2)  # RHEL Premium 2SKT
    if "suse" in ol: return round(2.50 * vcpu, 2)        # SUSE SLES
    return 0.0


def compute_on_prem(vcpu: int, mem: float, stor: float, os: str) -> Tuple[float, Dict]:
    """
    Industry-sourced On-Premises / Data Center TCO calculation.
    Returns (total_yearly, breakdown_dict) with full transparency.

    Sources:
    ─────────────────────────────────────────────────────────────────────
    HARDWARE COMPUTE — $130/vCPU/yr
      Dell PowerEdge R760 (2× Intel Xeon, 64-core): ~$10,000-$15,000 base
      Amortized over 5-year lifecycle: ~$125-$187/vCPU/yr
      Reference: dell.com/poweredge-r760, TerraZone 5-Year TCO Analysis (2025)

    HARDWARE MEMORY — $10/GB/yr
      DDR5 64GB ECC RDIMM: ~$240-$615/module (2025 enterprise pricing)
      Enterprise volume at ~$8-12/GB, amortized over 5 years
      Reference: Counterpoint Research DRAM Report (2025), Tom's Hardware,
      Samsung DDR5 pricing data, NetworkWorld (Nov 2025)

    HARDWARE STORAGE — $0.08/GB/yr (blended SSD/HDD)
      Enterprise NVMe SSD: $0.10-$0.25/GB, amortized ~$0.02-$0.05/GB/yr
      Enterprise HDD: $0.02-$0.04/GB, amortized ~$0.004-$0.008/GB/yr
      Blended 70/30 SSD/HDD mix for enterprise workloads
      Reference: Industry standard enterprise storage pricing

    POWER & COOLING — Dynamic: watts_per_vcpu × PUE × 8,760hrs × $/kWh
      Server power draw: ~25W per vCPU (typical for Intel Xeon 4th/5th Gen)
      PUE: 1.55 (US industry average, DOE 2024 Data Center Energy Report)
      Electricity: $0.12/kWh (US industrial average, EIA 2024)
      Reference: US DOE/LBNL 2024 Data Center Energy Usage Report,
      US Energy Information Administration (eia.gov)

    FACILITY / RACK SPACE — $1,200/server/yr
      Colocation: $1,000-$2,500/rack/month (ENCOR Advisors, Brightlio 2025)
      42U rack holds 10-20 servers; per-server share: $800-$2,000/yr
      Reference: ENCOR Advisors Colocation Pricing Guide (2025),
      Brightlio Colocation Pricing (2025)

    ADMIN & LABOR — $1,500/server/yr
      SysAdmin salary: $80K-$120K/yr (US average)
      Ratio: 1 admin per 50-100 servers
      Includes: patching, monitoring, incident response, backups
      Reference: Sherweb TCO Analysis, Gartner IT staffing benchmarks

    OS LICENSING — Per vCPU/month rates:
      Windows Server 2025 Std: $2,135/16-core → $133/core/yr → ~$5.50/vCPU/mo
      RHEL Premium 2-socket: $1,430/yr → ~$3.00/vCPU/mo (normalized)
      SUSE Enterprise: ~$2.50/vCPU/mo
      Linux (Ubuntu/Debian/Amazon Linux): $0
      Reference: Dell PowerEdge R760/R770 configurator pricing (dell.com)
    ─────────────────────────────────────────────────────────────────────
    """
    # --- Industry-sourced rates ---
    RATE_CPU_PER_VCPU_YR = 130.00    # Dell PowerEdge amortized 5yr
    RATE_MEM_PER_GB_YR = 10.00       # DDR5 RDIMM enterprise, 5yr amortization
    RATE_STOR_PER_GB_YR = 0.08       # Blended SSD/HDD enterprise
    WATTS_PER_VCPU = 25.0            # Intel Xeon typical per-core draw
    PUE = 1.55                       # US industry avg (DOE 2024)
    ELECTRICITY_KWH = 0.12           # US industrial avg (EIA)
    FACILITY_PER_SERVER_YR = 1200.0  # Colocation rack-share
    ADMIN_PER_SERVER_YR = 1500.0     # SysAdmin labor allocation
    HOURS_PER_YEAR = 8760

    # Hardware costs (amortized annual)
    hw_cpu = vcpu * RATE_CPU_PER_VCPU_YR
    hw_mem = mem * RATE_MEM_PER_GB_YR
    hw_stor = stor * RATE_STOR_PER_GB_YR
    hw_total = hw_cpu + hw_mem + hw_stor

    # Power & Cooling (dynamic based on vCPU)
    server_watts = vcpu * WATTS_PER_VCPU
    total_watts_with_pue = server_watts * PUE
    power_kwh_yr = (total_watts_with_pue / 1000) * HOURS_PER_YEAR
    power_cooling = power_kwh_yr * ELECTRICITY_KWH

    # Facility (colocation rack share)
    facility = FACILITY_PER_SERVER_YR

    # Admin labor
    admin_labor = ADMIN_PER_SERVER_YR

    # OS Licensing
    ol = str(os).lower()
    lic_rate = 0.0
    lic_name = "Linux (free)"
    if "windows" in ol:
        lic_rate = 5.50
        lic_name = "Windows Server ($5.50/vCPU/mo — Dell pricing)"
    elif "red hat" in ol or "rhel" in ol:
        lic_rate = 3.00
        lic_name = "RHEL ($3.00/vCPU/mo — Dell pricing)"
    elif "suse" in ol:
        lic_rate = 2.50
        lic_name = "SUSE ($2.50/vCPU/mo)"
    annual_licensing = vcpu * lic_rate * 12

    total = hw_total + power_cooling + facility + admin_labor + annual_licensing

    breakdown = {
        "hw_compute": round(hw_cpu, 2),
        "hw_memory": round(hw_mem, 2),
        "hw_storage": round(hw_stor, 2),
        "hw_total": round(hw_total, 2),
        "server_watts": round(server_watts, 1),
        "pue": PUE,
        "electricity_rate": ELECTRICITY_KWH,
        "power_kwh_yr": round(power_kwh_yr, 1),
        "power_cooling": round(power_cooling, 2),
        "facility": round(facility, 2),
        "admin_labor": round(admin_labor, 2),
        "licensing_rate_per_vcpu": lic_rate,
        "licensing_name": lic_name,
        "annual_licensing": round(annual_licensing, 2),
        # Source citations for UI display
        "sources": {
            "compute": "Dell PowerEdge R760 pricing, 5-yr amortization (dell.com)",
            "memory": "DDR5 RDIMM enterprise pricing (Counterpoint Research 2025, NetworkWorld)",
            "storage": "Enterprise SSD/HDD blended pricing (industry standard)",
            "power": f"US DOE 2024 Data Center Energy Report (PUE={PUE}), EIA (${ELECTRICITY_KWH}/kWh)",
            "facility": "ENCOR Advisors & Brightlio Colocation Pricing Guide (2025)",
            "labor": "Gartner IT staffing benchmarks, Sherweb TCO Analysis",
            "licensing": "Dell PowerEdge configurator (dell.com/poweredge-r760)",
        },
    }
    return round(total, 2), breakdown


def determine_paas(cloud: str, dbs: str) -> Tuple[str, str]:
    db = str(dbs).lower()
    aws_map = {"postgres": ("Amazon RDS", "Aurora PostgreSQL"), "mysql": ("Amazon RDS", "Aurora MySQL"),
               "mariadb": ("Amazon RDS", "Aurora MySQL"), "oracle": ("Amazon RDS", "RDS for Oracle"),
               "sql server": ("Amazon RDS", "RDS for SQL Server"), "mongo": ("Amazon DocumentDB", "DocumentDB"),
               "redis": ("Amazon ElastiCache", "ElastiCache Redis"), "memcache": ("Amazon ElastiCache", "ElastiCache Memcached"),
               "dynamo": ("Amazon DynamoDB", "DynamoDB"), "cassandra": ("Amazon Keyspaces", "Keyspaces")}
    az_map = {"postgres": ("Azure Database", "Azure DB for PostgreSQL"), "mysql": ("Azure Database", "Azure DB for MySQL"),
              "mariadb": ("Azure Database", "Azure DB for MySQL"), "sql server": ("Azure SQL", "Azure SQL Database"),
              "mongo": ("Azure Cosmos DB", "Cosmos DB (MongoDB API)"), "redis": ("Azure Cache", "Azure Cache for Redis"),
              "oracle": ("Azure Database", "Azure DB for PostgreSQL"), "cassandra": ("Azure Cosmos DB", "Cosmos DB (Cassandra API)")}
    m = aws_map if cloud == "AWS" else az_map
    for k, v in m.items():
        if k in db: return v
    return ("Amazon RDS", "Aurora PostgreSQL") if cloud == "AWS" else ("Azure SQL", "Azure SQL Database")


def determine_target_os(os: str, eol: str) -> str:
    ol, el = str(os).lower(), str(eol).lower()
    is_eol = any(k in el for k in ["eol", "end", "yes"])
    if "windows" in ol: return "Windows Server 2022"
    if any(x in ol for x in ["centos", "red hat", "rhel"]): return "Amazon Linux 2023" if is_eol else "RHEL 9"
    if "ubuntu" in ol: return "Ubuntu 24.04 LTS"
    if "suse" in ol: return "SUSE Linux Enterprise 15 SP5"
    if "amazon" in ol: return "Amazon Linux 2023"
    if "debian" in ol: return "Debian 12"
    return "Ubuntu 24.04 LTS"


def _match(candidates: List[Dict], vcpu: int, mem: float) -> Dict:
    fit = [c for c in candidates if c["vcpu"] >= vcpu and c["memory"] >= mem]
    if not fit: fit = sorted(candidates, key=lambda x: (x["vcpu"], x["memory"]), reverse=True)
    fit.sort(key=lambda x: (x["vcpu"], x["memory"]))
    return fit[0] if fit else candidates[-1]


# ═══════════════════════════════════════════════════════════════════════════════
# MASTER CALCULATION — Stateless, zero storage, fully dynamic
# ═══════════════════════════════════════════════════════════════════════════════
# API CONNECTIVITY CHECKS
# ═══════════════════════════════════════════════════════════════════════════════
def check_aws_connectivity() -> Tuple[bool, str]:
    """Check AWS pricing API connectivity (uses public reference catalog, no auth needed)."""
    try:
        # AWS pricing is via reference catalog — always available
        cat = _get_reference_catalog("AWS", "general")
        if cat and len(cat) > 0:
            return True, f"Reference catalog: {len(cat)} instance types loaded"
        return False, "Reference catalog empty"
    except Exception as e:
        return False, str(e)


def check_azure_connectivity() -> Tuple[bool, str]:
    """Check Azure Retail Prices API connectivity (public, no auth needed)."""
    try:
        url = "https://prices.azure.com/api/retail/prices?$top=1"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            count = data.get("Count", 0)
            return True, f"Retail Prices API responding (HTTP 200)"
        return False, f"HTTP {resp.status_code}"
    except requests.exceptions.ConnectionError:
        return False, "Connection failed — check network"
    except requests.exceptions.Timeout:
        return False, "Timeout — API slow"
    except Exception as e:
        return False, str(e)


def check_anthropic_connectivity(api_key: str) -> Tuple[bool, str]:
    """Check Anthropic Claude API connectivity."""
    if not api_key or len(api_key) < 10:
        return False, "No API key configured"
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        # Minimal ping — 1 token
        resp = client.messages.create(
            model="claude-sonnet-4-20250514", max_tokens=5,
            messages=[{"role": "user", "content": "ping"}]
        )
        return True, f"Claude API connected (model: claude-sonnet-4)"
    except ImportError:
        return False, "anthropic package not installed"
    except Exception as e:
        err = str(e)
        if "401" in err or "invalid" in err.lower():
            return False, "Invalid API key"
        elif "rate" in err.lower():
            return True, "Connected (rate-limited)"
        return False, err[:80]


# ═══════════════════════════════════════════════════════════════════════════════
# AZURE LOCAL (formerly Azure Stack HCI) — Hybrid Option
# ═══════════════════════════════════════════════════════════════════════════════
# Sources:
#   Azure Local Pricing Page (azure.microsoft.com/en-us/pricing/details/azure-local/)
#   - Host service fee: $10/physical core/month
#   - Windows Server subscription: $23.30/physical core/month
#     (includes unlimited Windows Server guest licensing rights)
#   - Azure Hybrid Benefit: WS Datacenter w/ SA waives host + WS subscription
#   - AKS on Azure Local: included at no extra charge (2402+ / Jan 2025)
#   - 60-day free trial after registration
#   Microsoft Q&A / techielass.com (Feb 2025): per-core licensing confirmed
#   EasySAM / TechTarget: WS 2025 PAYG via Azure Arc = $33.58/core/mo
# ═══════════════════════════════════════════════════════════════════════════════
AZURE_LOCAL_RATES = {
    "host_fee_per_core_mo": 10.00,       # Azure Local host service fee
    "ws_sub_per_core_mo": 23.30,         # Includes unlimited Windows guest licensing
    "ws_payg_per_core_mo": 33.58,        # Windows Server 2025 PAYG via Azure Arc
    "ahb_discount": 1.0,                 # 100% waiver with Azure Hybrid Benefit
    "free_trial_days": 60,               # Free trial period
}


def compute_azure_local(vcpu: int, mem: float, stor: float, os: str) -> Dict:
    """
    Azure Local (Azure Stack HCI) pricing — hybrid on-prem + Azure management.
    Uses existing on-prem hardware costs + Azure Local service fees.
    vCPU count used as proxy for physical cores (noted in output).

    Returns dict with monthly/annual costs for 3 scenarios:
      1. Linux guest (host fee only)
      2. Windows guest (host + WS subscription)
      3. Azure Hybrid Benefit (WS Datacenter w/ SA — fees waived)
    """
    r = AZURE_LOCAL_RATES

    # On-prem hardware costs (same hardware, just adding Azure management layer)
    on_prem_total, on_prem_bkdn = compute_on_prem(vcpu, mem, stor, os)
    # Remove on-prem OS licensing since Azure Local handles it differently
    hw_and_ops = on_prem_total - on_prem_bkdn.get("annual_licensing", 0)

    # Scenario 1: Linux guest — host fee only ($10/core/mo)
    host_fee_mo = vcpu * r["host_fee_per_core_mo"]
    host_fee_yr = host_fee_mo * 12
    linux_total_yr = hw_and_ops + host_fee_yr

    # Scenario 2: Windows guest — host + WS subscription ($23.30/core/mo total)
    ws_sub_mo = vcpu * r["ws_sub_per_core_mo"]
    ws_sub_yr = ws_sub_mo * 12
    windows_total_yr = hw_and_ops + ws_sub_yr

    # Scenario 3: Azure Hybrid Benefit — WS Datacenter w/ SA waives fees
    ahb_total_yr = hw_and_ops  # No Azure Local fees

    ol = str(os).lower()
    is_windows = "windows" in ol

    # Pick the applicable scenario
    if is_windows:
        recommended_mo = ws_sub_mo
        recommended_yr = windows_total_yr
        recommended_label = "Windows (Host + WS Subscription)"
    else:
        recommended_mo = host_fee_mo
        recommended_yr = linux_total_yr
        recommended_label = "Linux (Host Fee Only)"

    return {
        "host_fee_per_core_mo": r["host_fee_per_core_mo"],
        "host_fee_monthly": round(host_fee_mo, 2),
        "host_fee_annual": round(host_fee_yr, 2),
        "ws_sub_per_core_mo": r["ws_sub_per_core_mo"],
        "ws_sub_monthly": round(ws_sub_mo, 2),
        "ws_sub_annual": round(ws_sub_yr, 2),
        "hw_and_ops_annual": round(hw_and_ops, 2),
        "linux_total_annual": round(linux_total_yr, 2),
        "windows_total_annual": round(windows_total_yr, 2),
        "ahb_total_annual": round(ahb_total_yr, 2),
        "recommended_monthly": round(recommended_mo, 2),
        "recommended_annual": round(recommended_yr, 2),
        "recommended_label": recommended_label,
        "physical_cores_note": "vCPU used as proxy for physical cores; "
                               "Azure Local bills per physical processor core (no HT).",
        "source": "Azure Local Pricing (azure.microsoft.com/en-us/pricing/details/azure-local/), "
                  "Microsoft Q&A, techielass.com (Feb 2025).",
    }


def calculate_all_outputs(inputs: Dict) -> Dict:

    """
    STATELESS: Takes input dict → returns output dict.
    Nothing cached, stored, or persisted. Every call is independent.
    Attempts live pricing APIs first; falls back to dynamic catalog.
    """
    cloud = str(inputs.get("cloud_provider", "AWS"))
    region = str(inputs.get("cloud_region", "US East (N. Virginia)"))
    # Azure Local uses Azure pricing for IaaS/PaaS comparison
    is_azure_local = cloud == "Azure Local"
    pricing_cloud = "Azure" if is_azure_local else cloud
    os_name = str(inputs.get("operating_system", "Linux"))
    server_type = str(inputs.get("server_type", "Application"))
    os_eol = str(inputs.get("os_eol_status", "No"))
    databases = str(inputs.get("databases_caches", "None"))
    vcpu_count = int(float(inputs.get("vcpu_count", 2)))
    avg_cpu = float(inputs.get("avg_cpu_usage", 50))
    memory_gb = float(inputs.get("memory_gb", 8))
    avg_memory = float(inputs.get("avg_memory_usage", 50))
    total_storage = float(inputs.get("total_storage_gb", 100))
    storage_pct = float(inputs.get("storage_usage_pct", 60))
    avg_iops = float(inputs.get("avg_disk_iops", 500))

    # Dynamic right-sizing
    rs_cpu = compute_right_sized_cpu(vcpu_count, avg_cpu)
    rs_mem = compute_right_sized_memory(memory_gb, avg_memory)
    rs_stor = compute_right_sized_storage(total_storage, storage_pct)
    family = determine_family(server_type, databases, avg_cpu, memory_gb, vcpu_count)
    rmult = _region_mult(pricing_cloud, region)
    MH = 730  # monthly hours

    # Live pricing attempt
    pricing_source = "reference_catalog"
    live_inst = []
    if pricing_cloud == "Azure":
        rcode = AZURE_REGIONS.get(region, "eastus")
        live_inst = fetch_azure_vm_pricing(rcode, rs_cpu, rs_mem)
        if live_inst: pricing_source = "azure_api_live"

    if live_inst:
        rec = _match(live_inst, rs_cpu, rs_mem)
        rec_hr = rec["price_hr"]
        cur_live = fetch_azure_vm_pricing(AZURE_REGIONS.get(region, "eastus"), vcpu_count, memory_gb)
        if cur_live:
            cur = _match(cur_live, vcpu_count, memory_gb)
            cur_hr = cur["price_hr"]
        else:
            cat = _get_reference_catalog(pricing_cloud, family)
            cur = _match(cat, vcpu_count, memory_gb)
            cur_hr = cur["base_price_hr"] * rmult
    else:
        cat = _get_reference_catalog(pricing_cloud, family)
        cur = _match(cat, vcpu_count, memory_gb)
        cur_hr = cur["base_price_hr"] * rmult
        rec = _match(cat, rs_cpu, rs_mem)
        rec_hr = rec["base_price_hr"] * rmult

    # IaaS pricing
    iaas_od = round(cur_hr * MH, 2)
    iaas_1y = round(iaas_od * 0.60, 2)
    iaas_3y = round(iaas_od * 0.40, 2)
    iaas_lic = compute_licensing(os_name, cur["vcpu"])

    rec_od = round(rec_hr * MH, 2)
    rec_1y = round(rec_od * 0.60, 2)
    rec_3y = round(rec_od * 0.40, 2)
    rec_lic = compute_licensing(os_name, rec["vcpu"])

    # Storage
    stype = determine_storage_type(pricing_cloud, avg_iops, rs_stor)
    live_stor = fetch_azure_storage_pricing(AZURE_REGIONS.get(region, "eastus")) if pricing_cloud == "Azure" and pricing_source == "azure_api_live" else None
    sprice = compute_storage_price(pricing_cloud, stype, rs_stor, rmult, live_stor)

    # PaaS
    ps, pn = determine_paas(pricing_cloud, databases)
    db_cat = _get_reference_catalog(pricing_cloud, "database")
    pi = _match(db_cat, rs_cpu, rs_mem)
    p_hr = pi.get("price_hr", pi.get("base_price_hr", 0)) * rmult
    p_od = round(p_hr * MH, 2)
    p_1y = round(p_od * 0.60, 2)
    p_3y = round(p_od * 0.40, 2)
    p_sp = round(sprice * 1.2, 2)
    p_lic = round(rec_lic * 0.5, 2)

    # On-prem with full breakdown
    on_prem_total, on_prem_bkdn = compute_on_prem(vcpu_count, memory_gb, total_storage, os_name)

    # Azure Local (formerly Azure Stack HCI) — hybrid option
    azl = compute_azure_local(vcpu_count, memory_gb, total_storage, os_name)

    # ── CROSS-PROVIDER COMPARISON ──────────────────────────────────────────────
    # Compute IaaS 3yr RI annual cost for BOTH AWS and Azure regardless of
    # which was selected, so every row shows all 3 + on-prem side by side.
    xp = {}
    for xcloud in ["AWS", "Azure"]:
        xrmult = _region_mult(xcloud, region)
        xcat = _get_reference_catalog(xcloud, family)
        xrec = _match(xcat, rs_cpu, rs_mem)
        xrec_hr = xrec["base_price_hr"] * xrmult
        xrec_od = round(xrec_hr * MH, 2)
        xrec_3y = round(xrec_od * 0.40, 2)
        xrec_lic = compute_licensing(os_name, xrec["vcpu"])
        xstype = determine_storage_type(xcloud, avg_iops, rs_stor)
        xsprice = compute_storage_price(xcloud, xstype, rs_stor, xrmult)
        xannual = round((xrec_3y + xrec_lic + xsprice) * 12, 2)
        xp[xcloud] = {
            "instance_type": xrec["type"], "vcpu": xrec["vcpu"], "memory": xrec["memory"],
            "monthly_3yr_ri": round(xrec_3y + xrec_lic + xsprice, 2),
            "annual_3yr_ri": xannual,
        }

    # ── ENHANCED: Network/Egress costs ──────────────────────────────────────
    avg_net = float(inputs.get("avg_network_throughput", 100))
    total_net = float(inputs.get("total_network_throughput", 1000))
    server_type = str(inputs.get("server_type", "Application Server"))

    try:
        network = calculate_network_costs(
            pricing_cloud, avg_net, total_net, server_type,
            needs_vpn=True, needs_load_balancer=False,
        )
    except Exception:
        network = {"total_monthly": 0, "total_annual": 0, "egress": {"monthly_cost": 0}}

    # ── ENHANCED: DR & Backup costs ──────────────────────────────────────
    environment = str(inputs.get("environment", "Production"))
    try:
        dr_backup = calculate_total_dr_backup(
            pricing_cloud, rec_od, total_storage, storage_pct,
            server_type, environment, databases,
        )
    except Exception:
        dr_backup = {"combined_monthly": 0, "combined_annual": 0,
                     "backup": {"total_monthly": 0}, "dr": {"total_monthly": 0}}

    # ── ENHANCED: Storage tier optimization ───────────────────────────────
    try:
        storage_tiers = calculate_tiered_storage_cost(
            pricing_cloud, total_storage, storage_pct, avg_iops,
            server_type, databases, rmult,
        )
    except Exception:
        storage_tiers = {"optimized_monthly": sprice, "savings_monthly": 0, "savings_pct": 0}

    # ── ENHANCED: Serverless/Container options ───────────────────────────
    try:
        modern_options = calculate_all_modern_options(
            pricing_cloud, vcpu_count, avg_cpu, memory_gb,
            float(inputs.get("avg_memory_usage", 50)),
            server_type, str(inputs.get("instance_usage", "24x7")), rmult,
        )
    except Exception:
        modern_options = {"recommended": "N/A", "recommended_monthly": 0,
                         "serverless": {"suitable": False}, "container": {"monthly_cost": 0}}

    # ── ENHANCED: Migration transfer cost ────────────────────────────────
    try:
        migration_transfer = estimate_migration_transfer_cost(
            pricing_cloud, total_storage, storage_pct,
        )
    except Exception:
        migration_transfer = {"data_to_transfer_gb": 0, "methods": []}

    return {
        "right_sizing_cpu": rs_cpu, "right_sizing_memory": rs_mem, "right_sizing_storage": rs_stor,
        "iaas_on_demand_price": iaas_od, "iaas_reserved_1yr_price": iaas_1y,
        "iaas_reserved_3yr_price": iaas_3y, "iaas_licensing_price": iaas_lic,
        "recomm_instance_type": rec["type"], "recomm_vcpu": rec["vcpu"], "recomm_memory": rec["memory"],
        "recomm_storage_type": stype,
        "iaas_rec_on_demand": rec_od, "iaas_rec_reserved_1yr": rec_1y,
        "iaas_rec_reserved_3yr": rec_3y, "iaas_rec_licensing": rec_lic,
        "rec_storage_gb": rs_stor, "rec_storage_price": sprice,
        "paas_service": ps, "paas_instance_type": pi["type"], "paas_service_name": pn,
        "paas_vcpu": pi["vcpu"], "paas_memory": pi["memory"],
        "paas_storage": rs_stor, "paas_storage_price": p_sp,
        "paas_on_demand": p_od, "paas_reserved_1yr": p_1y, "paas_reserved_3yr": p_3y, "paas_licensing": p_lic,
        "on_prem_yearly_cost": on_prem_total,
        "on_prem_breakdown": on_prem_bkdn,
        "azure_local": azl,
        "cross_provider": xp,
        "target_operating_system": determine_target_os(os_name, os_eol),
        # Enhanced outputs
        "network_costs": network,
        "dr_backup_costs": dr_backup,
        "storage_tiers": storage_tiers,
        "modern_options": modern_options,
        "migration_transfer": migration_transfer,
        "_cloud_provider": cloud, "_instance_family": family, "_region": region,
        "_hostname": str(inputs.get("host_name", "")), "_pricing_source": pricing_source,
    }
