"""
Pricing Data Cache with TTL
==============================
In-memory cache for pricing API responses to reduce redundant calls.
Maintains zero-persistence compliance — cache lives only in session memory.

Features:
  - TTL-based expiration (configurable per cache type)
  - LRU eviction when cache exceeds max size
  - Cache hit/miss statistics
  - Manual invalidation
"""

import time
import hashlib
import json
from typing import Any, Dict, Optional, Tuple
from collections import OrderedDict


class PricingCache:
    """
    LRU cache with TTL for pricing data.
    Thread-safe for single-threaded Streamlit usage.
    """

    def __init__(self, max_size: int = 500, default_ttl: int = 1800):
        """
        Args:
            max_size: Maximum number of cached entries
            default_ttl: Default time-to-live in seconds (30 min)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict = OrderedDict()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "expirations": 0,
        }

    def _make_key(self, cache_type: str, params: Dict) -> str:
        """Create a deterministic cache key from parameters."""
        key_data = json.dumps({"type": cache_type, **params}, sort_keys=True)
        return hashlib.md5(key_data.encode()).hexdigest()

    def get(self, cache_type: str, params: Dict) -> Tuple[Optional[Any], bool]:
        """
        Get cached value.
        Returns (value, hit) where hit indicates cache hit.
        """
        key = self._make_key(cache_type, params)

        if key not in self._cache:
            self._stats["misses"] += 1
            return None, False

        entry = self._cache[key]

        # Check expiration
        if time.time() > entry["expires_at"]:
            del self._cache[key]
            self._stats["expirations"] += 1
            self._stats["misses"] += 1
            return None, False

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        self._stats["hits"] += 1
        return entry["value"], True

    def put(self, cache_type: str, params: Dict, value: Any,
            ttl: Optional[int] = None):
        """
        Cache a value with optional custom TTL.
        """
        key = self._make_key(cache_type, params)
        ttl = ttl or self.default_ttl

        # Evict if at capacity
        while len(self._cache) >= self.max_size:
            evicted_key = next(iter(self._cache))
            del self._cache[evicted_key]
            self._stats["evictions"] += 1

        self._cache[key] = {
            "value": value,
            "created_at": time.time(),
            "expires_at": time.time() + ttl,
            "cache_type": cache_type,
        }

    def invalidate(self, cache_type: Optional[str] = None):
        """Invalidate cache entries. If cache_type is None, clear all."""
        if cache_type is None:
            self._cache.clear()
        else:
            keys_to_remove = [
                k for k, v in self._cache.items()
                if v.get("cache_type") == cache_type
            ]
            for k in keys_to_remove:
                del self._cache[k]

    def get_stats(self) -> Dict:
        """Get cache statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / max(1, total)) * 100

        # Count non-expired entries
        now = time.time()
        active = sum(1 for v in self._cache.values() if v["expires_at"] > now)

        return {
            "size": len(self._cache),
            "active": active,
            "max_size": self.max_size,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "hit_rate_pct": round(hit_rate, 1),
            "evictions": self._stats["evictions"],
            "expirations": self._stats["expirations"],
        }

    def get_entries_by_type(self) -> Dict[str, int]:
        """Get count of cached entries by type."""
        counts = {}
        now = time.time()
        for v in self._cache.values():
            if v["expires_at"] > now:
                ct = v.get("cache_type", "unknown")
                counts[ct] = counts.get(ct, 0) + 1
        return counts


# Cache type constants and TTLs
CACHE_TYPES = {
    "azure_vm_pricing": {"ttl": 1800, "desc": "Azure VM pricing"},
    "azure_storage_pricing": {"ttl": 1800, "desc": "Azure storage pricing"},
    "aws_reference": {"ttl": 3600, "desc": "AWS reference catalog"},
    "currency_rates": {"ttl": 3600, "desc": "Currency exchange rates"},
    "instance_match": {"ttl": 900, "desc": "Instance matching results"},
}

# Singleton cache instance
pricing_cache = PricingCache(max_size=500, default_ttl=1800)


def cached_azure_vm_pricing(fetch_fn, region_code: str,
                            vcpu_needed: int, mem_needed: float):
    """Wrapper for Azure VM pricing with caching."""
    params = {"region": region_code, "vcpu": vcpu_needed, "mem": mem_needed}
    cached, hit = pricing_cache.get("azure_vm_pricing", params)
    if hit:
        return cached

    result = fetch_fn(region_code, vcpu_needed, mem_needed)
    if result:
        pricing_cache.put("azure_vm_pricing", params, result,
                         ttl=CACHE_TYPES["azure_vm_pricing"]["ttl"])
    return result


def cached_azure_storage_pricing(fetch_fn, region_code: str):
    """Wrapper for Azure storage pricing with caching."""
    params = {"region": region_code}
    cached, hit = pricing_cache.get("azure_storage_pricing", params)
    if hit:
        return cached

    result = fetch_fn(region_code)
    if result:
        pricing_cache.put("azure_storage_pricing", params, result,
                         ttl=CACHE_TYPES["azure_storage_pricing"]["ttl"])
    return result
