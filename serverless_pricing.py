"""
Serverless & Container Pricing Engine
========================================
Calculates costs for serverless (Lambda/Functions) and container
(ECS/EKS/ACA) deployment options for refactor migration paths.

Sources:
  AWS Lambda:       aws.amazon.com/lambda/pricing/
  AWS ECS/Fargate:  aws.amazon.com/fargate/pricing/
  AWS EKS:          aws.amazon.com/eks/pricing/
  Azure Functions:  azure.microsoft.com/en-us/pricing/details/functions/
  Azure Container:  azure.microsoft.com/en-us/pricing/details/container-apps/
  Azure AKS:        azure.microsoft.com/en-us/pricing/details/kubernetes-service/
"""

from typing import Dict, List
import math


# ─── Serverless pricing ─────────────────────────────────────────────────────
LAMBDA_PRICING = {
    "request_per_million": 0.20,
    "duration_per_gb_sec": 0.0000166667,
    "free_requests_per_month": 1_000_000,
    "free_gb_seconds": 400_000,
    "provisioned_concurrency_per_gb_hr": 0.0000041667 * 3600,  # ~$0.015/GB-hr
}

AZURE_FUNCTIONS_PRICING = {
    "request_per_million": 0.20,
    "duration_per_gb_sec": 0.000016,
    "free_requests_per_month": 1_000_000,
    "free_gb_seconds": 400_000,
}

# ─── Container pricing (Fargate / Container Apps) ────────────────────────────
FARGATE_PRICING = {
    "vcpu_per_hour": 0.04048,
    "memory_per_gb_hour": 0.004445,
    "ephemeral_storage_per_gb_hour": 0.000111,
    "spot_discount": 0.70,  # 70% discount for Spot
}

AZURE_CONTAINER_APPS_PRICING = {
    "vcpu_per_second": 0.000024,
    "memory_per_gb_second": 0.000003,
    "free_requests_per_month": 2_000_000,
    "free_vcpu_seconds": 180_000,
    "free_memory_gb_seconds": 360_000,
}

# ─── Kubernetes pricing ─────────────────────────────────────────────────────
EKS_PRICING = {
    "cluster_per_hour": 0.10,  # EKS control plane
    "cluster_monthly": 73.0,
}

AKS_PRICING = {
    "cluster_per_hour": 0.00,  # Free tier
    "cluster_monthly": 0.00,   # AKS management is free
    "uptime_sla_monthly": 73.0,  # Optional paid SLA
}


def estimate_serverless_cost(
    cloud: str,
    vcpu_count: int,
    avg_cpu_usage: float,
    memory_gb: float,
    avg_memory_usage: float,
    server_type: str = "Application",
    instance_usage: str = "24x7",
    region_multiplier: float = 1.0,
) -> Dict:
    """
    Estimate serverless (Lambda/Functions) cost for this workload.

    Converts traditional server metrics to serverless estimates:
    - Request rate from CPU usage and server type
    - Execution duration from workload characteristics
    - Memory allocation from actual usage
    """
    # Estimate requests per month from server type and usage
    requests_per_second = {
        "Web Server": 50,
        "API Gateway": 100,
        "Application Server": 30,
        "Database Server": 0,  # Not suitable for serverless
        "Cache Server": 0,     # Not suitable
        "File Server": 5,
        "Mail Server": 10,
        "Load Balancer": 0,    # Not applicable
        "Monitoring": 5,
        "CI/CD": 2,
    }

    rps = requests_per_second.get(server_type, 20) * (avg_cpu_usage / 50.0)

    # Usage hours per month
    usage_hours = {
        "24x7": 730, "Business Hours": 260,
        "On-Demand": 365, "Scheduled": 400,
    }
    hours = usage_hours.get(instance_usage, 730)

    monthly_requests = rps * 3600 * hours
    avg_duration_ms = 200  # Average execution time

    # Memory per invocation
    mem_per_invocation = max(128, min(10240, memory_gb * (avg_memory_usage / 100.0) * 1024))
    mem_gb = mem_per_invocation / 1024

    gb_seconds = monthly_requests * (avg_duration_ms / 1000) * mem_gb

    if server_type in ("Database Server", "Cache Server", "Load Balancer"):
        return {
            "suitable": False,
            "reason": f"{server_type} is not suitable for serverless deployment",
            "monthly_cost": 0,
            "annual_cost": 0,
        }

    if cloud == "AWS":
        p = LAMBDA_PRICING
        billable_requests = max(0, monthly_requests - p["free_requests_per_month"])
        billable_gb_sec = max(0, gb_seconds - p["free_gb_seconds"])
        request_cost = (billable_requests / 1_000_000) * p["request_per_million"]
        compute_cost = billable_gb_sec * p["duration_per_gb_sec"]
        total = (request_cost + compute_cost) * region_multiplier
        service_name = "AWS Lambda"
    else:
        p = AZURE_FUNCTIONS_PRICING
        billable_requests = max(0, monthly_requests - p["free_requests_per_month"])
        billable_gb_sec = max(0, gb_seconds - p["free_gb_seconds"])
        request_cost = (billable_requests / 1_000_000) * p["request_per_million"]
        compute_cost = billable_gb_sec * p["duration_per_gb_sec"]
        total = (request_cost + compute_cost) * region_multiplier
        service_name = "Azure Functions"

    return {
        "suitable": True,
        "service": service_name,
        "estimated_requests_month": round(monthly_requests),
        "avg_duration_ms": avg_duration_ms,
        "memory_mb": round(mem_per_invocation),
        "gb_seconds": round(gb_seconds),
        "request_cost": round(request_cost, 2),
        "compute_cost": round(compute_cost, 2),
        "monthly_cost": round(total, 2),
        "annual_cost": round(total * 12, 2),
        "vs_note": "Serverless best for event-driven, variable workloads with <15 min execution time",
    }


def estimate_container_cost(
    cloud: str,
    vcpu_count: int,
    avg_cpu_usage: float,
    memory_gb: float,
    avg_memory_usage: float,
    instance_usage: str = "24x7",
    region_multiplier: float = 1.0,
    use_spot: bool = False,
) -> Dict:
    """
    Estimate container (Fargate/Container Apps) cost.

    Right-sizes containers based on actual utilization.
    """
    # Right-size for containers (tighter than VMs)
    needed_vcpu = max(0.25, vcpu_count * (avg_cpu_usage / 100.0) * 1.2)
    needed_mem = max(0.5, memory_gb * (avg_memory_usage / 100.0) * 1.2)

    # Fargate vCPU sizes: 0.25, 0.5, 1, 2, 4, 8, 16
    fargate_vcpu_sizes = [0.25, 0.5, 1, 2, 4, 8, 16]
    container_vcpu = next((s for s in fargate_vcpu_sizes if s >= needed_vcpu), 16)

    # Memory per vCPU: 2-8 GB ratio typical
    container_mem = max(needed_mem, container_vcpu * 2)

    # Usage hours
    usage_hours = {
        "24x7": 730, "Business Hours": 260,
        "On-Demand": 365, "Scheduled": 400,
    }
    hours = usage_hours.get(instance_usage, 730)

    if cloud == "AWS":
        p = FARGATE_PRICING
        vcpu_cost = container_vcpu * p["vcpu_per_hour"] * hours
        mem_cost = container_mem * p["memory_per_gb_hour"] * hours
        total = (vcpu_cost + mem_cost) * region_multiplier

        if use_spot:
            total *= (1 - p["spot_discount"])

        service_name = "AWS Fargate"
        extras = {
            "eks_management": EKS_PRICING["cluster_monthly"],
            "note": "Add EKS cluster fee ($73/mo) if using Kubernetes",
        }
    else:
        p = AZURE_CONTAINER_APPS_PRICING
        seconds = hours * 3600
        vcpu_cost = max(0, container_vcpu * seconds - p["free_vcpu_seconds"]) * p["vcpu_per_second"]
        mem_cost = max(0, container_mem * seconds - p["free_memory_gb_seconds"]) * p["memory_per_gb_second"]
        total = (vcpu_cost + mem_cost) * region_multiplier
        service_name = "Azure Container Apps"
        extras = {
            "aks_management": AKS_PRICING["cluster_monthly"],
            "note": "AKS management plane is free; add $73/mo for Uptime SLA",
        }

    return {
        "service": service_name,
        "container_vcpu": container_vcpu,
        "container_memory_gb": round(container_mem, 2),
        "usage_hours_month": hours,
        "use_spot": use_spot,
        "vcpu_cost": round(vcpu_cost, 2),
        "memory_cost": round(mem_cost, 2),
        "monthly_cost": round(total, 2),
        "annual_cost": round(total * 12, 2),
        "extras": extras,
    }


def calculate_all_modern_options(
    cloud: str,
    vcpu_count: int,
    avg_cpu_usage: float,
    memory_gb: float,
    avg_memory_usage: float,
    server_type: str = "Application",
    instance_usage: str = "24x7",
    region_multiplier: float = 1.0,
) -> Dict:
    """Calculate all modern deployment options (serverless + containers)."""
    serverless = estimate_serverless_cost(
        cloud, vcpu_count, avg_cpu_usage, memory_gb, avg_memory_usage,
        server_type, instance_usage, region_multiplier,
    )

    container = estimate_container_cost(
        cloud, vcpu_count, avg_cpu_usage, memory_gb, avg_memory_usage,
        instance_usage, region_multiplier,
    )

    container_spot = estimate_container_cost(
        cloud, vcpu_count, avg_cpu_usage, memory_gb, avg_memory_usage,
        instance_usage, region_multiplier, use_spot=True,
    )

    options = [
        {"name": "Container (On-Demand)", "monthly": container["monthly_cost"],
         "annual": container["annual_cost"], "details": container},
        {"name": "Container (Spot/Preemptible)", "monthly": container_spot["monthly_cost"],
         "annual": container_spot["annual_cost"], "details": container_spot},
    ]

    if serverless["suitable"]:
        options.insert(0, {
            "name": "Serverless", "monthly": serverless["monthly_cost"],
            "annual": serverless["annual_cost"], "details": serverless,
        })

    options.sort(key=lambda x: x["monthly"])
    best = options[0]

    return {
        "serverless": serverless,
        "container": container,
        "container_spot": container_spot,
        "all_options": options,
        "recommended": best["name"],
        "recommended_monthly": best["monthly"],
        "recommended_annual": best["annual"],
    }
