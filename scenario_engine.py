"""
Scenario Analysis & Financial Projection Engine
=================================================
Provides what-if analysis, side-by-side scenario comparison,
ROI break-even calculations, and 3-5 year cost projections.
"""

import math
from typing import Dict, List, Optional
from copy import deepcopy


# ─── Cloud price trend assumptions ───────────────────────────────────────────
PRICE_TRENDS = {
    "cloud_annual_decrease": -0.05,     # Cloud prices decrease ~5%/yr historically
    "on_prem_hw_increase": 0.03,        # Hardware refresh costs increase ~3%/yr
    "on_prem_power_increase": 0.04,     # Electricity costs increase ~4%/yr
    "on_prem_labor_increase": 0.05,     # Labor costs increase ~5%/yr
    "on_prem_licensing_increase": 0.03, # License costs increase ~3%/yr
}

# ─── Migration cost benchmarks ───────────────────────────────────────────────
MIGRATION_COST_FACTORS = {
    "Rehost": {"per_server": 500, "complexity_mult": 1.0, "duration_days": 3},
    "Rehost (Lift & Shift)": {"per_server": 500, "complexity_mult": 1.0, "duration_days": 3},
    "Replatform": {"per_server": 1500, "complexity_mult": 1.5, "duration_days": 7},
    "Refactor": {"per_server": 5000, "complexity_mult": 3.0, "duration_days": 30},
    "Repurchase": {"per_server": 2000, "complexity_mult": 2.0, "duration_days": 14},
    "Retire": {"per_server": 100, "complexity_mult": 0.2, "duration_days": 1},
    "Retain": {"per_server": 0, "complexity_mult": 0.0, "duration_days": 0},
}

DATABASE_COMPLEXITY = {
    "None": 1.0,
    "MySQL": 1.5, "PostgreSQL": 1.5, "MariaDB": 1.5,
    "SQL Server": 2.0, "Oracle": 3.0,
    "MongoDB": 1.8, "Redis": 1.2, "Memcached": 1.1,
    "DynamoDB": 1.3, "Cassandra": 2.0,
}


def run_sensitivity_analysis(
    base_inputs: Dict,
    base_outputs: Dict,
    calculate_fn,
    variables: Optional[List[str]] = None,
    variation_pcts: Optional[List[float]] = None,
) -> Dict:
    """
    Run what-if sensitivity analysis by varying input parameters.

    Args:
        base_inputs: Original server inputs
        base_outputs: Original calculation outputs
        calculate_fn: Function to recalculate (calculate_all_outputs)
        variables: Which inputs to vary (default: CPU, memory, storage)
        variation_pcts: Percentage variations to test (default: -30%, -15%, +15%, +30%)

    Returns:
        Dict with sensitivity results for each variable
    """
    if variables is None:
        variables = ["vcpu_count", "avg_cpu_usage", "memory_gb", "avg_memory_usage",
                      "total_storage_gb", "avg_disk_iops"]

    if variation_pcts is None:
        variation_pcts = [-30, -15, 15, 30]

    results = {}

    for var in variables:
        if var not in base_inputs:
            continue

        base_val = float(base_inputs[var])
        var_results = []

        for pct in variation_pcts:
            new_val = base_val * (1 + pct / 100.0)

            # Clamp to valid ranges
            if var in ("avg_cpu_usage", "avg_memory_usage", "storage_usage_pct"):
                new_val = max(0, min(100, new_val))
            elif var in ("vcpu_count",):
                new_val = max(1, min(128, round(new_val)))
            elif var in ("memory_gb",):
                new_val = max(1, min(1024, new_val))
            elif var in ("total_storage_gb",):
                new_val = max(10, min(65536, new_val))
            elif var in ("avg_disk_iops",):
                new_val = max(0, min(500000, new_val))

            modified_inputs = deepcopy(base_inputs)
            modified_inputs[var] = new_val

            try:
                new_outputs = calculate_fn(modified_inputs)
                aws_ann = new_outputs["cross_provider"]["AWS"]["annual_3yr_ri"]
                az_ann = new_outputs["cross_provider"]["Azure"]["annual_3yr_ri"]
                on_prem = new_outputs["on_prem_yearly_cost"]

                var_results.append({
                    "variation_pct": pct,
                    "original_value": base_val,
                    "new_value": round(new_val, 2),
                    "aws_annual": aws_ann,
                    "azure_annual": az_ann,
                    "on_prem_annual": on_prem,
                    "right_cpu": new_outputs["right_sizing_cpu"],
                    "right_mem": new_outputs["right_sizing_memory"],
                    "right_stor": new_outputs["right_sizing_storage"],
                    "instance_type": new_outputs["recomm_instance_type"],
                })
            except Exception:
                continue

        # Include base case
        aws_base = base_outputs["cross_provider"]["AWS"]["annual_3yr_ri"]
        az_base = base_outputs["cross_provider"]["Azure"]["annual_3yr_ri"]
        op_base = base_outputs["on_prem_yearly_cost"]

        results[var] = {
            "variable": var,
            "base_value": base_val,
            "base_aws": aws_base,
            "base_azure": az_base,
            "base_on_prem": op_base,
            "scenarios": var_results,
        }

    return results


def compare_scenarios(scenarios: List[Dict]) -> Dict:
    """
    Compare multiple migration scenarios side-by-side.

    Each scenario dict should have:
        - name: Scenario label
        - inputs: Server inputs
        - outputs: Calculated outputs
    """
    if not scenarios:
        return {"error": "No scenarios to compare"}

    comparison = []
    for s in scenarios:
        out = s["outputs"]
        inp = s["inputs"]
        aws = out["cross_provider"]["AWS"]["annual_3yr_ri"]
        azure = out["cross_provider"]["Azure"]["annual_3yr_ri"]
        azl = out.get("azure_local", {}).get("recommended_annual", 0)
        on_prem = out["on_prem_yearly_cost"]
        best_cloud = min(aws, azure)
        savings = on_prem - best_cloud

        comparison.append({
            "name": s.get("name", "Unnamed"),
            "cloud_provider": inp.get("cloud_provider", ""),
            "instance_type": out["recomm_instance_type"],
            "right_cpu": out["right_sizing_cpu"],
            "right_mem": out["right_sizing_memory"],
            "right_stor": out["right_sizing_storage"],
            "aws_annual": aws,
            "azure_annual": azure,
            "azure_local_annual": azl,
            "on_prem_annual": on_prem,
            "best_cloud_annual": best_cloud,
            "savings": savings,
            "savings_pct": round((savings / max(1, on_prem)) * 100, 1),
            "best_provider": "AWS" if aws <= azure else "Azure",
        })

    # Find best scenario
    best = min(comparison, key=lambda x: x["best_cloud_annual"])

    return {
        "scenarios": comparison,
        "best_scenario": best["name"],
        "best_annual_cost": best["best_cloud_annual"],
        "best_savings": best["savings"],
    }


def calculate_roi_breakeven(
    on_prem_annual: float,
    cloud_annual: float,
    migration_type: str = "Rehost",
    databases: str = "None",
    server_count: int = 1,
) -> Dict:
    """
    Calculate ROI and break-even timeline for migration.

    Returns months to break even and cumulative savings projection.
    """
    mig_factors = MIGRATION_COST_FACTORS.get(migration_type,
                                              MIGRATION_COST_FACTORS["Rehost"])
    db_mult = DATABASE_COMPLEXITY.get(databases, 1.0)

    # One-time migration cost
    migration_cost = mig_factors["per_server"] * mig_factors["complexity_mult"] * db_mult * server_count

    # Monthly savings
    monthly_savings = (on_prem_annual - cloud_annual) / 12

    if monthly_savings <= 0:
        return {
            "migration_cost": round(migration_cost, 2),
            "monthly_savings": round(monthly_savings, 2),
            "breakeven_months": None,
            "breakeven_achieved": False,
            "note": "Cloud is more expensive than on-prem — no ROI break-even",
            "year_projections": [],
        }

    # Break-even month
    breakeven_months = math.ceil(migration_cost / monthly_savings)

    # Month-by-month projection (up to 36 months)
    projections = []
    cumulative = -migration_cost  # Start negative (migration investment)

    for month in range(1, 37):
        cumulative += monthly_savings
        projections.append({
            "month": month,
            "cumulative_savings": round(cumulative, 2),
            "is_positive": cumulative > 0,
        })

    # Year summaries
    year_projections = []
    for year in range(1, 4):
        yr_savings = monthly_savings * 12
        yr_cumulative = -migration_cost + (yr_savings * year)
        year_projections.append({
            "year": year,
            "annual_savings": round(yr_savings, 2),
            "cumulative_savings": round(yr_cumulative, 2),
            "roi_pct": round((yr_cumulative / max(1, migration_cost)) * 100, 1),
        })

    return {
        "migration_cost": round(migration_cost, 2),
        "migration_duration_days": mig_factors["duration_days"],
        "monthly_savings": round(monthly_savings, 2),
        "annual_savings": round(monthly_savings * 12, 2),
        "breakeven_months": breakeven_months,
        "breakeven_achieved": True,
        "month_projections": projections,
        "year_projections": year_projections,
        "three_year_savings": round(-migration_cost + monthly_savings * 36, 2),
        "three_year_roi_pct": round(((-migration_cost + monthly_savings * 36) / max(1, migration_cost)) * 100, 1),
    }


def project_costs(
    on_prem_annual: float,
    cloud_annual: float,
    on_prem_breakdown: Dict,
    years: int = 5,
    migration_cost: float = 0,
    custom_trends: Optional[Dict] = None,
) -> Dict:
    """
    Project costs over N years with trend adjustments.

    On-prem costs increase (hardware refresh, power, labor inflation).
    Cloud costs generally decrease (economies of scale, competition).
    """
    trends = custom_trends or PRICE_TRENDS

    on_prem_projections = []
    cloud_projections = []
    cumulative_on_prem = 0
    cumulative_cloud = migration_cost  # Include migration cost in Year 0

    for year in range(1, years + 1):
        # On-prem cost increases
        hw_mult = (1 + trends["on_prem_hw_increase"]) ** year
        power_mult = (1 + trends["on_prem_power_increase"]) ** year
        labor_mult = (1 + trends["on_prem_labor_increase"]) ** year
        lic_mult = (1 + trends["on_prem_licensing_increase"]) ** year

        hw = on_prem_breakdown.get("hw_total", on_prem_annual * 0.30) * hw_mult
        power = on_prem_breakdown.get("power_cooling", on_prem_annual * 0.15) * power_mult
        facility = on_prem_breakdown.get("facility", 1200) * labor_mult
        labor = on_prem_breakdown.get("admin_labor", 1500) * labor_mult
        licensing = on_prem_breakdown.get("annual_licensing", 0) * lic_mult

        yr_on_prem = hw + power + facility + labor + licensing
        cumulative_on_prem += yr_on_prem

        # Cloud cost decreases
        cloud_mult = (1 + trends["cloud_annual_decrease"]) ** year
        yr_cloud = cloud_annual * cloud_mult
        cumulative_cloud += yr_cloud

        cumulative_savings = cumulative_on_prem - cumulative_cloud

        on_prem_projections.append({
            "year": year,
            "annual_cost": round(yr_on_prem, 2),
            "cumulative": round(cumulative_on_prem, 2),
            "hw": round(hw, 2),
            "power": round(power, 2),
            "labor": round(labor + facility, 2),
            "licensing": round(licensing, 2),
        })

        cloud_projections.append({
            "year": year,
            "annual_cost": round(yr_cloud, 2),
            "cumulative": round(cumulative_cloud, 2),
            "price_multiplier": round(cloud_mult, 4),
        })

    return {
        "projection_years": years,
        "migration_cost": round(migration_cost, 2),
        "on_prem": on_prem_projections,
        "cloud": cloud_projections,
        "total_on_prem": round(cumulative_on_prem, 2),
        "total_cloud": round(cumulative_cloud, 2),
        "total_savings": round(cumulative_on_prem - cumulative_cloud, 2),
        "total_savings_pct": round(
            ((cumulative_on_prem - cumulative_cloud) / max(1, cumulative_on_prem)) * 100, 1
        ),
        "trends": trends,
    }


def generate_wave_plan(servers: List[Dict]) -> Dict:
    """
    Generate a migration wave plan based on server characteristics.

    Wave prioritization:
    - Wave 1 (Quick Wins): Dev/test, small, no DB, Rehost
    - Wave 2 (Core): Production app servers, medium complexity
    - Wave 3 (Complex): Database servers, stateful workloads
    - Wave 4 (Optimization): Refactor candidates, PaaS migration
    """
    waves = {
        "wave_1": {"name": "Quick Wins", "timeline": "Month 1-2", "servers": [], "criteria": "Dev/Test, non-DB, Rehost"},
        "wave_2": {"name": "Core Migration", "timeline": "Month 3-6", "servers": [], "criteria": "Production apps, medium complexity"},
        "wave_3": {"name": "Complex Workloads", "timeline": "Month 6-12", "servers": [], "criteria": "Database servers, stateful, EOL OS"},
        "wave_4": {"name": "Optimization", "timeline": "Month 12-18", "servers": [], "criteria": "Refactor/PaaS candidates, fine-tuning"},
    }

    for s in servers:
        inp = s.get("inputs", s)
        out = s.get("outputs", {})
        hostname = inp.get("host_name", "Unknown")
        env = inp.get("environment", "Production")
        stype = inp.get("server_type", "Application")
        mig_type = inp.get("migration_type", "Rehost")
        dbs = inp.get("databases_caches", "None")
        eol = inp.get("os_eol_status", "No")

        server_info = {
            "host_name": hostname,
            "environment": env,
            "server_type": stype,
            "migration_type": mig_type,
            "databases": dbs,
            "on_prem_cost": out.get("on_prem_yearly_cost", 0),
            "cloud_cost": min(
                out.get("cross_provider", {}).get("AWS", {}).get("annual_3yr_ri", 0),
                out.get("cross_provider", {}).get("Azure", {}).get("annual_3yr_ri", 0),
            ) if out else 0,
        }

        # Wave assignment logic
        if mig_type in ("Retire", "Retain"):
            waves["wave_1"]["servers"].append(server_info)
        elif env in ("Development", "Testing", "QA") and dbs in ("None", ""):
            waves["wave_1"]["servers"].append(server_info)
        elif mig_type in ("Refactor", "Repurchase"):
            waves["wave_4"]["servers"].append(server_info)
        elif dbs not in ("None", "") or "database" in stype.lower():
            waves["wave_3"]["servers"].append(server_info)
        elif "Yes" in str(eol):
            waves["wave_3"]["servers"].append(server_info)
        elif env in ("Staging",) or stype in ("Web Server", "API Gateway"):
            waves["wave_2"]["servers"].append(server_info)
        else:
            waves["wave_2"]["servers"].append(server_info)

    # Calculate wave summaries
    total_servers = len(servers)
    for wave_key, wave in waves.items():
        wave["count"] = len(wave["servers"])
        wave["pct"] = round((wave["count"] / max(1, total_servers)) * 100, 1)
        wave["total_on_prem"] = round(sum(s["on_prem_cost"] for s in wave["servers"]), 2)
        wave["total_cloud"] = round(sum(s["cloud_cost"] for s in wave["servers"]), 2)
        wave["total_savings"] = round(wave["total_on_prem"] - wave["total_cloud"], 2)

    return {
        "total_servers": total_servers,
        "waves": waves,
        "estimated_total_duration_months": 18,
    }
