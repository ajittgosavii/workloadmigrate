"""
Unit Tests for Pricing Engine
================================
Tests core pricing calculations, right-sizing logic,
and output generation for correctness.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pricing_engine import (
    compute_right_sized_cpu, compute_right_sized_memory, compute_right_sized_storage,
    determine_family, determine_storage_type, compute_licensing, compute_on_prem,
    determine_paas, determine_target_os, calculate_all_outputs,
    compute_azure_local, _region_mult,
)


class TestRightSizing:
    """Tests for right-sizing calculations."""

    def test_cpu_right_sizing_basic(self):
        """50% usage of 8 vCPU → 8*0.5*1.3=5.2 → nearest 8"""
        result = compute_right_sized_cpu(8, 50)
        assert result == 8

    def test_cpu_right_sizing_low_usage(self):
        """10% usage of 16 vCPU → 16*0.1*1.3=2.08 → nearest 4"""
        result = compute_right_sized_cpu(16, 10)
        assert result == 4

    def test_cpu_right_sizing_high_usage(self):
        """90% usage of 4 vCPU → 4*0.9*1.3=4.68 → nearest 8"""
        result = compute_right_sized_cpu(4, 90)
        assert result == 8

    def test_cpu_right_sizing_zero_usage(self):
        """0% usage should return original vCPU count."""
        result = compute_right_sized_cpu(8, 0)
        assert result == 8

    def test_cpu_right_sizing_minimum(self):
        """Very low values should not go below 1."""
        result = compute_right_sized_cpu(1, 5)
        assert result >= 1

    def test_memory_right_sizing_basic(self):
        """50% of 32GB → 32*0.5*1.3=20.8 → nearest 32"""
        result = compute_right_sized_memory(32, 50)
        assert result == 32.0

    def test_memory_right_sizing_low(self):
        """20% of 64GB → 64*0.2*1.3=16.64 → nearest 32"""
        result = compute_right_sized_memory(64, 20)
        assert result == 32.0

    def test_memory_right_sizing_zero_usage(self):
        """0% usage should return original."""
        result = compute_right_sized_memory(16, 0)
        assert result == 16.0

    def test_storage_right_sizing_basic(self):
        """60% of 500GB → 500*0.6*1.4=420 → 420"""
        result = compute_right_sized_storage(500, 60)
        assert result >= 420
        assert result <= 500

    def test_storage_right_sizing_minimum(self):
        """Result should never go below 20GB."""
        result = compute_right_sized_storage(10, 10)
        assert result >= 20

    def test_storage_right_sizing_zero_usage(self):
        """0% usage returns original."""
        result = compute_right_sized_storage(200, 0)
        assert result == 200


class TestWorkloadFamily:
    """Tests for workload family determination."""

    def test_database_from_db_field(self):
        result = determine_family("Application", "MySQL", 50, 16, 4)
        assert result == "database"

    def test_database_from_server_type(self):
        result = determine_family("Database Server", "None", 50, 16, 4)
        assert result == "database"

    def test_memory_optimized(self):
        """High memory-to-CPU ratio → memory family."""
        result = determine_family("Application", "None", 30, 128, 4)
        assert result == "memory"

    def test_compute_optimized(self):
        """High CPU usage → compute family."""
        result = determine_family("Web Server", "None", 85, 8, 4)
        assert result == "compute"

    def test_general_purpose(self):
        """Default case → general."""
        result = determine_family("Web Server", "None", 40, 16, 4)
        assert result == "general"


class TestStorageType:
    """Tests for storage type determination."""

    def test_aws_high_iops(self):
        result = determine_storage_type("AWS", 20000, 100)
        assert result == "io2"

    def test_aws_medium_iops(self):
        result = determine_storage_type("AWS", 5000, 100)
        assert result == "io1"

    def test_aws_default(self):
        result = determine_storage_type("AWS", 1000, 100)
        assert result == "gp3"

    def test_aws_large_volume(self):
        result = determine_storage_type("AWS", 500, 1000)
        assert result == "st1"

    def test_azure_high_iops(self):
        result = determine_storage_type("Azure", 15000, 100)
        assert result == "Ultra Disk"

    def test_azure_default(self):
        result = determine_storage_type("Azure", 1000, 100)
        assert result == "Standard SSD"


class TestLicensing:
    """Tests for OS licensing calculations."""

    def test_windows_licensing(self):
        result = compute_licensing("Windows Server 2022", 4)
        assert result == 22.0  # 5.50 * 4

    def test_rhel_licensing(self):
        result = compute_licensing("Red Hat Enterprise Linux 9", 4)
        assert result == 12.0  # 3.00 * 4

    def test_suse_licensing(self):
        result = compute_licensing("SUSE Linux Enterprise 15", 4)
        assert result == 10.0  # 2.50 * 4

    def test_ubuntu_free(self):
        result = compute_licensing("Ubuntu 22.04", 4)
        assert result == 0.0

    def test_amazon_linux_free(self):
        result = compute_licensing("Amazon Linux 2023", 8)
        assert result == 0.0


class TestOnPremCost:
    """Tests for on-premises TCO calculation."""

    def test_basic_on_prem(self):
        total, breakdown = compute_on_prem(4, 16, 200, "Ubuntu 22.04")
        assert total > 0
        assert breakdown["hw_compute"] == 520.0  # 4 * 130
        assert breakdown["hw_memory"] == 160.0    # 16 * 10
        assert breakdown["hw_storage"] == 16.0    # 200 * 0.08
        assert breakdown["facility"] == 1200.0
        assert breakdown["admin_labor"] == 1500.0
        assert breakdown["annual_licensing"] == 0.0  # Ubuntu is free

    def test_windows_on_prem(self):
        total, breakdown = compute_on_prem(4, 16, 200, "Windows Server 2022")
        assert breakdown["annual_licensing"] == 264.0  # 4 * 5.50 * 12
        assert total > compute_on_prem(4, 16, 200, "Ubuntu 22.04")[0]

    def test_power_calculation(self):
        _, breakdown = compute_on_prem(8, 32, 500, "Linux")
        expected_watts = 8 * 25  # 200W
        assert breakdown["server_watts"] == 200.0
        assert breakdown["pue"] == 1.55
        assert breakdown["electricity_rate"] == 0.12

    def test_breakdown_sources(self):
        """Verify all source citations are present."""
        _, breakdown = compute_on_prem(4, 16, 200, "Linux")
        sources = breakdown["sources"]
        assert "compute" in sources
        assert "memory" in sources
        assert "power" in sources
        assert "facility" in sources
        assert "labor" in sources


class TestAzureLocal:
    """Tests for Azure Local pricing."""

    def test_linux_scenario(self):
        result = compute_azure_local(4, 16, 200, "Ubuntu 22.04")
        assert result["host_fee_monthly"] == 40.0  # 4 * $10
        assert result["host_fee_annual"] == 480.0
        assert result["linux_total_annual"] > 0

    def test_windows_scenario(self):
        result = compute_azure_local(4, 16, 200, "Windows Server 2022")
        assert result["ws_sub_monthly"] == 93.2  # 4 * $23.30
        assert result["windows_total_annual"] > result["linux_total_annual"]

    def test_ahb_cheapest(self):
        """Azure Hybrid Benefit should always be cheapest."""
        result = compute_azure_local(8, 32, 500, "Windows Server 2022")
        assert result["ahb_total_annual"] < result["windows_total_annual"]
        assert result["ahb_total_annual"] < result["linux_total_annual"]


class TestCalculateAllOutputs:
    """Tests for the master calculation function."""

    def test_basic_aws_output(self):
        inputs = {
            "cloud_provider": "AWS", "cloud_region": "US East (N. Virginia)",
            "host_name": "test-server", "ip_address": "10.0.1.1",
            "platform": "Linux", "operating_system": "Ubuntu 22.04",
            "environment": "Production", "server_type": "Application Server",
            "os_eol_status": "No", "migration_type": "Rehost",
            "databases_caches": "None", "app_services": "",
            "instance_usage": "24x7", "vcpu_count": 4, "avg_cpu_usage": 50,
            "memory_gb": 16, "avg_memory_usage": 60, "total_storage_gb": 200,
            "storage_usage_pct": 60, "avg_network_throughput": 100,
            "total_network_throughput": 1000, "avg_disk_iops": 500,
        }
        result = calculate_all_outputs(inputs)

        # Verify all required output keys exist
        required_keys = [
            "right_sizing_cpu", "right_sizing_memory", "right_sizing_storage",
            "iaas_on_demand_price", "iaas_reserved_1yr_price", "iaas_reserved_3yr_price",
            "recomm_instance_type", "recomm_vcpu", "recomm_memory",
            "paas_service", "paas_instance_type",
            "on_prem_yearly_cost", "on_prem_breakdown",
            "azure_local", "cross_provider", "target_operating_system",
        ]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"

        # Verify cross-provider has both AWS and Azure
        assert "AWS" in result["cross_provider"]
        assert "Azure" in result["cross_provider"]

        # Verify pricing is positive
        assert result["iaas_on_demand_price"] > 0
        assert result["iaas_reserved_1yr_price"] > 0
        assert result["iaas_reserved_3yr_price"] > 0
        assert result["on_prem_yearly_cost"] > 0

        # Verify RI pricing is discounted
        assert result["iaas_reserved_1yr_price"] < result["iaas_on_demand_price"]
        assert result["iaas_reserved_3yr_price"] < result["iaas_reserved_1yr_price"]

    def test_azure_output(self):
        inputs = {
            "cloud_provider": "Azure", "cloud_region": "East US",
            "host_name": "az-test", "ip_address": "10.0.1.2",
            "platform": "Linux", "operating_system": "Ubuntu 22.04",
            "environment": "Production", "server_type": "Web Server",
            "os_eol_status": "No", "migration_type": "Rehost",
            "databases_caches": "None", "app_services": "Apache",
            "instance_usage": "24x7", "vcpu_count": 2, "avg_cpu_usage": 30,
            "memory_gb": 8, "avg_memory_usage": 40, "total_storage_gb": 100,
            "storage_usage_pct": 50, "avg_network_throughput": 50,
            "total_network_throughput": 500, "avg_disk_iops": 200,
        }
        result = calculate_all_outputs(inputs)
        assert result["_cloud_provider"] == "Azure"
        assert result["recomm_instance_type"] != ""

    def test_azure_local_output(self):
        inputs = {
            "cloud_provider": "Azure Local", "cloud_region": "East US",
            "host_name": "azl-test", "ip_address": "10.0.1.3",
            "platform": "Windows", "operating_system": "Windows Server 2022",
            "environment": "Production", "server_type": "Application Server",
            "os_eol_status": "No", "migration_type": "Rehost",
            "databases_caches": "SQL Server", "app_services": "",
            "instance_usage": "24x7", "vcpu_count": 8, "avg_cpu_usage": 65,
            "memory_gb": 32, "avg_memory_usage": 70, "total_storage_gb": 500,
            "storage_usage_pct": 75, "avg_network_throughput": 200,
            "total_network_throughput": 2000, "avg_disk_iops": 3000,
        }
        result = calculate_all_outputs(inputs)
        azl = result["azure_local"]
        assert azl["linux_total_annual"] > 0
        assert azl["windows_total_annual"] > 0
        assert azl["ahb_total_annual"] > 0

    def test_target_os_eol(self):
        """EOL OS should get upgraded recommendation."""
        result = determine_target_os("CentOS 7", "Yes - EOL")
        assert "2023" in result or "24.04" in result  # Modern OS recommended


class TestRegionMultipliers:
    """Tests for regional pricing multipliers."""

    def test_us_east_baseline(self):
        assert _region_mult("AWS", "US East (N. Virginia)") == 1.0
        assert _region_mult("Azure", "East US") == 1.0

    def test_ap_premium(self):
        mult = _region_mult("AWS", "Asia Pacific (Tokyo)")
        assert mult > 1.0

    def test_india_discount(self):
        mult = _region_mult("AWS", "Asia Pacific (Mumbai)")
        assert mult < 1.0


class TestPaaS:
    """Tests for PaaS service determination."""

    def test_postgres_aws(self):
        service, name = determine_paas("AWS", "PostgreSQL")
        assert "RDS" in service
        assert "PostgreSQL" in name

    def test_mysql_azure(self):
        service, name = determine_paas("Azure", "MySQL")
        assert "Azure" in service

    def test_redis_aws(self):
        service, name = determine_paas("AWS", "Redis")
        assert "ElastiCache" in service

    def test_mongo_azure(self):
        service, name = determine_paas("Azure", "MongoDB")
        assert "Cosmos" in service

    def test_default_aws(self):
        service, name = determine_paas("AWS", "None")
        assert service != ""  # Should have a default
