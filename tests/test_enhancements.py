"""
Unit Tests for Enhancement Modules
=====================================
Tests network costs, DR/backup, storage optimizer,
scenario analysis, currency, serverless pricing,
retry logic, and caching.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from network_costs import calculate_egress_cost, calculate_network_costs, estimate_migration_transfer_cost
from dr_backup import calculate_backup_costs, calculate_dr_costs, calculate_total_dr_backup
from storage_optimizer import classify_storage_tiers, calculate_tiered_storage_cost
from scenario_engine import calculate_roi_breakeven, project_costs, generate_wave_plan
from currency_converter import convert, get_symbol, format_currency, get_multiplier
from serverless_pricing import estimate_serverless_cost, estimate_container_cost, calculate_all_modern_options
from retry_utils import CircuitBreaker, get_circuit_breaker_status
from pricing_cache import PricingCache


class TestNetworkCosts:
    def test_aws_egress_free_tier(self):
        result = calculate_egress_cost("AWS", 0.5)
        assert result["monthly_cost"] == 0.0

    def test_aws_egress_basic(self):
        result = calculate_egress_cost("AWS", 100)
        assert result["monthly_cost"] > 0
        assert result["annual_cost"] == result["monthly_cost"] * 12

    def test_network_costs_web_server(self):
        result = calculate_network_costs("AWS", 100, 1000, "Web Server")
        assert result["total_monthly"] > 0
        assert result["egress_ratio"] == 0.60

    def test_network_costs_database(self):
        result = calculate_network_costs("Azure", 50, 500, "Database Server")
        assert result["egress_ratio"] == 0.10  # DB has low egress

    def test_migration_transfer_small(self):
        result = estimate_migration_transfer_cost("AWS", 100, 60)
        assert result["data_to_transfer_gb"] == 60.0
        assert len(result["methods"]) > 0


class TestDRBackup:
    def test_backup_costs_basic(self):
        result = calculate_backup_costs("AWS", 500, 60, "Application Server")
        assert result["total_monthly"] > 0
        assert result["total_annual"] == result["total_monthly"] * 12

    def test_backup_costs_database(self):
        result = calculate_backup_costs("Azure", 500, 60, "Database Server",
                                        databases="PostgreSQL")
        assert result["db_backup_cost_monthly"] > 0

    def test_dr_costs_pilot_light(self):
        result = calculate_dr_costs("AWS", 200, 500, 60, "Production", "pilot_light")
        assert result["total_monthly"] > 0
        assert result["rto"] == "10-30 minutes"

    def test_dr_costs_dev_environment(self):
        result = calculate_dr_costs("Azure", 200, 500, 60, "Development", "pilot_light")
        assert result["total_monthly"] == 0  # No DR for dev

    def test_combined_dr_backup(self):
        result = calculate_total_dr_backup("AWS", 200, 500, 60)
        assert result["combined_monthly"] > 0
        assert "backup" in result
        assert "dr" in result


class TestStorageOptimizer:
    def test_classify_database(self):
        dist = classify_storage_tiers(500, 60, 5000, "Database Server", "MySQL")
        assert dist["hot"] >= 0.50  # DB keeps most data hot

    def test_classify_file_server(self):
        dist = classify_storage_tiers(2000, 80, 200, "File Server")
        assert dist["archive"] >= 0.20  # File servers have old data

    def test_tiered_storage_savings(self):
        result = calculate_tiered_storage_cost("AWS", 1000, 70, 500)
        assert result["savings_monthly"] >= 0
        assert result["optimized_monthly"] <= result["single_tier_monthly"]


class TestScenarioEngine:
    def test_roi_breakeven_positive(self):
        result = calculate_roi_breakeven(10000, 5000, "Rehost", "None")
        assert result["breakeven_achieved"]
        assert result["breakeven_months"] > 0
        assert result["three_year_savings"] > 0

    def test_roi_breakeven_negative(self):
        result = calculate_roi_breakeven(5000, 10000, "Rehost", "None")
        assert not result["breakeven_achieved"]

    def test_roi_complex_migration(self):
        result = calculate_roi_breakeven(10000, 5000, "Refactor", "Oracle")
        assert result["migration_cost"] > calculate_roi_breakeven(10000, 5000, "Rehost", "None")["migration_cost"]

    def test_cost_projection(self):
        breakdown = {"hw_total": 3000, "power_cooling": 500,
                     "facility": 1200, "admin_labor": 1500, "annual_licensing": 0}
        result = project_costs(10000, 6000, breakdown, years=5)
        assert len(result["on_prem"]) == 5
        assert len(result["cloud"]) == 5
        assert result["total_savings"] > 0

    def test_wave_plan(self):
        servers = [
            {"inputs": {"host_name": "dev-1", "environment": "Development",
                         "server_type": "Web Server", "migration_type": "Rehost",
                         "databases_caches": "None", "os_eol_status": "No"},
             "outputs": {"on_prem_yearly_cost": 5000,
                         "cross_provider": {"AWS": {"annual_3yr_ri": 3000},
                                           "Azure": {"annual_3yr_ri": 3200}}}},
            {"inputs": {"host_name": "db-1", "environment": "Production",
                         "server_type": "Database Server", "migration_type": "Rehost",
                         "databases_caches": "PostgreSQL", "os_eol_status": "No"},
             "outputs": {"on_prem_yearly_cost": 15000,
                         "cross_provider": {"AWS": {"annual_3yr_ri": 8000},
                                           "Azure": {"annual_3yr_ri": 8500}}}},
        ]
        result = generate_wave_plan(servers)
        assert result["total_servers"] == 2
        # Dev server should be Wave 1, DB server should be Wave 3
        assert len(result["waves"]["wave_1"]["servers"]) >= 1
        assert len(result["waves"]["wave_3"]["servers"]) >= 1


class TestCurrencyConverter:
    def test_usd_to_usd(self):
        assert convert(100.0, "USD", "USD") == 100.0

    def test_usd_to_eur(self):
        result = convert(100.0, "USD", "EUR")
        assert result < 100.0  # EUR is worth more than USD

    def test_usd_to_inr(self):
        result = convert(100.0, "USD", "INR")
        assert result > 100.0  # INR is less valuable

    def test_symbol(self):
        assert get_symbol("USD") == "$"
        assert get_symbol("EUR") == "\u20ac"
        assert get_symbol("GBP") == "\u00a3"

    def test_format_currency(self):
        result = format_currency(100.0, "USD")
        assert "$" in result

    def test_multiplier(self):
        assert get_multiplier("USD") == 1.0
        assert get_multiplier("CAD") > 1.0


class TestServerlessPricing:
    def test_lambda_cost(self):
        result = estimate_serverless_cost("AWS", 4, 50, 8, 60, "Web Server")
        assert result["suitable"]
        assert result["monthly_cost"] >= 0

    def test_database_not_suitable(self):
        result = estimate_serverless_cost("AWS", 4, 50, 16, 60, "Database Server")
        assert not result["suitable"]

    def test_container_cost(self):
        result = estimate_container_cost("AWS", 4, 50, 16, 60)
        assert result["monthly_cost"] > 0
        assert result["container_vcpu"] >= 0.25

    def test_spot_discount(self):
        regular = estimate_container_cost("AWS", 4, 50, 16, 60, use_spot=False)
        spot = estimate_container_cost("AWS", 4, 50, 16, 60, use_spot=True)
        assert spot["monthly_cost"] < regular["monthly_cost"]

    def test_all_modern_options(self):
        result = calculate_all_modern_options("Azure", 4, 50, 16, 60, "Application Server")
        assert "serverless" in result
        assert "container" in result
        assert result["recommended"] != ""


class TestCircuitBreaker:
    def test_initial_state(self):
        cb = CircuitBreaker(failure_threshold=3, reset_timeout=1)
        assert cb.can_execute()
        assert cb.state == CircuitBreaker.CLOSED

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=2, reset_timeout=60)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitBreaker.OPEN
        assert not cb.can_execute()

    def test_success_resets(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.state == CircuitBreaker.CLOSED

    def test_status_report(self):
        status = get_circuit_breaker_status()
        assert "azure_pricing" in status
        assert "aws_pricing" in status


class TestPricingCache:
    def test_cache_miss(self):
        cache = PricingCache(max_size=10, default_ttl=300)
        value, hit = cache.get("test", {"key": "value"})
        assert not hit
        assert value is None

    def test_cache_hit(self):
        cache = PricingCache(max_size=10, default_ttl=300)
        cache.put("test", {"key": "value"}, "cached_data")
        value, hit = cache.get("test", {"key": "value"})
        assert hit
        assert value == "cached_data"

    def test_cache_eviction(self):
        cache = PricingCache(max_size=2, default_ttl=300)
        cache.put("test", {"key": "1"}, "data1")
        cache.put("test", {"key": "2"}, "data2")
        cache.put("test", {"key": "3"}, "data3")
        assert cache.get_stats()["size"] <= 2

    def test_cache_invalidation(self):
        cache = PricingCache(max_size=10, default_ttl=300)
        cache.put("azure_vm", {"region": "eastus"}, "data")
        cache.invalidate("azure_vm")
        value, hit = cache.get("azure_vm", {"region": "eastus"})
        assert not hit

    def test_cache_stats(self):
        cache = PricingCache(max_size=10, default_ttl=300)
        cache.put("test", {"k": "1"}, "d1")
        cache.get("test", {"k": "1"})  # Hit
        cache.get("test", {"k": "2"})  # Miss
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate_pct"] == 50.0
