"""
Unit Tests for Input Validation
==================================
Tests validation logic for all input parameters,
edge cases, and bulk data validation.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validation import (
    validate_hostname, validate_ip_address, validate_numeric_range,
    validate_enum, validate_server_inputs, validate_bulk_dataframe,
    VALID_CLOUD_PROVIDERS, VALID_PLATFORMS,
)


class TestHostnameValidation:
    def test_valid_hostname(self):
        ok, msg = validate_hostname("web-prod-01")
        assert ok

    def test_valid_fqdn(self):
        ok, msg = validate_hostname("server.example.com")
        assert ok

    def test_empty_hostname(self):
        """Empty hostname is optional."""
        ok, msg = validate_hostname("")
        assert ok

    def test_invalid_hostname_special_chars(self):
        ok, msg = validate_hostname("server@invalid!")
        assert not ok

    def test_hostname_too_long(self):
        ok, msg = validate_hostname("a" * 300)
        assert not ok


class TestIPValidation:
    def test_valid_ip(self):
        ok, msg = validate_ip_address("10.0.1.100")
        assert ok

    def test_valid_ip_zeros(self):
        ok, msg = validate_ip_address("0.0.0.0")
        assert ok

    def test_valid_ip_max(self):
        ok, msg = validate_ip_address("255.255.255.255")
        assert ok

    def test_empty_ip(self):
        """Empty IP is optional."""
        ok, msg = validate_ip_address("")
        assert ok

    def test_invalid_ip_format(self):
        ok, msg = validate_ip_address("not.an.ip.address")
        assert not ok

    def test_invalid_ip_range(self):
        ok, msg = validate_ip_address("256.1.1.1")
        assert not ok

    def test_invalid_ip_short(self):
        ok, msg = validate_ip_address("10.0.1")
        assert not ok


class TestNumericValidation:
    def test_valid_number(self):
        ok, msg, val = validate_numeric_range(50, "CPU", 0, 100, True)
        assert ok
        assert val == 50.0

    def test_below_min(self):
        ok, msg, val = validate_numeric_range(-5, "vCPU", 1, 128)
        assert not ok

    def test_above_max(self):
        ok, msg, val = validate_numeric_range(200, "CPU %", 0, 100)
        assert not ok

    def test_non_numeric(self):
        ok, msg, val = validate_numeric_range("abc", "CPU", 0, 100)
        assert not ok

    def test_zero_when_allowed(self):
        ok, msg, val = validate_numeric_range(0, "IOPS", 0, 500000, True)
        assert ok

    def test_zero_when_not_allowed(self):
        ok, msg, val = validate_numeric_range(0, "vCPU", 1, 128, False)
        assert not ok


class TestEnumValidation:
    def test_valid_provider(self):
        ok, msg, val = validate_enum("AWS", "Cloud Provider", VALID_CLOUD_PROVIDERS)
        assert ok
        assert val == "AWS"

    def test_case_insensitive(self):
        ok, msg, val = validate_enum("aws", "Cloud Provider", VALID_CLOUD_PROVIDERS)
        assert ok
        assert val == "AWS"

    def test_invalid_enum(self):
        ok, msg, val = validate_enum("GCP", "Cloud Provider", VALID_CLOUD_PROVIDERS)
        assert not ok

    def test_empty_enum(self):
        ok, msg, val = validate_enum("", "Cloud Provider", VALID_CLOUD_PROVIDERS)
        assert not ok


class TestServerInputValidation:
    def test_valid_inputs(self):
        inputs = {
            "cloud_provider": "AWS",
            "host_name": "web-01",
            "ip_address": "10.0.1.1",
            "platform": "Linux",
            "environment": "Production",
            "server_type": "Web Server",
            "os_eol_status": "No",
            "migration_type": "Rehost",
            "instance_usage": "24x7",
            "vcpu_count": 4,
            "avg_cpu_usage": 50,
            "memory_gb": 16,
            "avg_memory_usage": 60,
            "total_storage_gb": 200,
            "storage_usage_pct": 65,
            "avg_network_throughput": 100,
            "total_network_throughput": 1000,
            "avg_disk_iops": 500,
        }
        result = validate_server_inputs(inputs)
        assert result.is_valid

    def test_invalid_ip(self):
        inputs = {
            "cloud_provider": "AWS",
            "ip_address": "999.999.999.999",
            "vcpu_count": 4, "avg_cpu_usage": 50,
            "memory_gb": 16, "avg_memory_usage": 50,
            "total_storage_gb": 100, "storage_usage_pct": 50,
        }
        result = validate_server_inputs(inputs)
        assert not result.is_valid

    def test_negative_vcpu(self):
        inputs = {
            "cloud_provider": "AWS",
            "vcpu_count": -4, "avg_cpu_usage": 50,
            "memory_gb": 16, "avg_memory_usage": 50,
            "total_storage_gb": 100, "storage_usage_pct": 50,
        }
        result = validate_server_inputs(inputs)
        assert not result.is_valid

    def test_warning_low_cpu(self):
        """Very low CPU should produce a warning."""
        inputs = {
            "cloud_provider": "AWS",
            "vcpu_count": 16, "avg_cpu_usage": 2,
            "memory_gb": 64, "avg_memory_usage": 50,
            "total_storage_gb": 200, "storage_usage_pct": 50,
        }
        result = validate_server_inputs(inputs)
        assert len(result.warnings) > 0

    def test_warning_high_storage(self):
        inputs = {
            "cloud_provider": "Azure",
            "vcpu_count": 4, "avg_cpu_usage": 50,
            "memory_gb": 16, "avg_memory_usage": 50,
            "total_storage_gb": 500, "storage_usage_pct": 95,
        }
        result = validate_server_inputs(inputs)
        assert any("Storage" in w for w in result.warnings)


class TestBulkValidation:
    def test_valid_dataframe(self):
        import pandas as pd
        df = pd.DataFrame({
            "Cloud Provider": ["AWS", "Azure"],
            "Cloud Region": ["US East (N. Virginia)", "East US"],
            "Host Name": ["server1", "server2"],
            "VCPUCount": [4, 8],
            "Memory(GB)": [16, 32],
            "Total Storage(GB)": [200, 500],
        })
        result = validate_bulk_dataframe(df)
        assert result.is_valid

    def test_missing_columns(self):
        import pandas as pd
        df = pd.DataFrame({"Cloud Provider": ["AWS"], "Host Name": ["s1"]})
        result = validate_bulk_dataframe(df)
        assert not result.is_valid

    def test_duplicate_hostnames(self):
        import pandas as pd
        df = pd.DataFrame({
            "Cloud Provider": ["AWS", "AWS"],
            "Cloud Region": ["US East (N. Virginia)"] * 2,
            "Host Name": ["server1", "server1"],  # Duplicate
            "VCPUCount": [4, 8],
            "Memory(GB)": [16, 32],
            "Total Storage(GB)": [200, 500],
        })
        result = validate_bulk_dataframe(df)
        assert any("Duplicate" in w for w in result.warnings)

    def test_empty_dataframe(self):
        import pandas as pd
        df = pd.DataFrame(columns=["Cloud Provider", "Host Name", "VCPUCount",
                                    "Memory(GB)", "Total Storage(GB)", "Cloud Region"])
        result = validate_bulk_dataframe(df)
        assert not result.is_valid
