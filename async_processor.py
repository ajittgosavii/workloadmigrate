"""
Async/Parallel Processing Engine
===================================
Provides parallel processing for bulk server analysis
using Python's concurrent.futures for CPU-bound pricing calculations.

Features:
  - Thread pool for I/O-bound API calls (Azure pricing)
  - Batch processing with configurable chunk size
  - Progress callback for UI updates
  - Error isolation (one server failure doesn't affect others)
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Callable, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class BatchProcessor:
    """
    Parallel batch processor for server analysis.
    Uses ThreadPoolExecutor for concurrent API-bound pricing lookups.
    """

    def __init__(self, max_workers: int = 4, chunk_size: int = 10):
        """
        Args:
            max_workers: Maximum parallel threads
            chunk_size: Servers per processing chunk
        """
        self.max_workers = max_workers
        self.chunk_size = chunk_size

    def process_batch(
        self,
        servers: List[Dict],
        calculate_fn: Callable,
        progress_callback: Optional[Callable] = None,
        error_callback: Optional[Callable] = None,
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Process a batch of servers in parallel.

        Args:
            servers: List of server input dicts
            calculate_fn: Function to calculate outputs for one server
            progress_callback: Called with (completed, total, server_name, result)
            error_callback: Called with (server_name, error_message)

        Returns:
            Tuple of (successful_results, failed_results)
        """
        results = []
        errors = []
        total = len(servers)
        completed = 0

        # For small batches, run sequentially (thread overhead not worth it)
        if total <= 5:
            for inp in servers:
                try:
                    out = calculate_fn(inp)
                    result = {"inputs": inp, "outputs": out}
                    results.append(result)
                    completed += 1
                    if progress_callback:
                        progress_callback(completed, total, inp.get("host_name", ""), result)
                except Exception as e:
                    errors.append({"inputs": inp, "error": str(e)})
                    completed += 1
                    if error_callback:
                        error_callback(inp.get("host_name", ""), str(e))
            return results, errors

        # Process in parallel chunks
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_inp = {}
            for inp in servers:
                future = executor.submit(self._safe_calculate, calculate_fn, inp)
                future_to_inp[future] = inp

            # Collect results as they complete
            for future in as_completed(future_to_inp):
                inp = future_to_inp[future]
                completed += 1

                try:
                    out, error = future.result()
                    if error:
                        errors.append({"inputs": inp, "error": error})
                        if error_callback:
                            error_callback(inp.get("host_name", ""), error)
                    else:
                        result = {"inputs": inp, "outputs": out}
                        results.append(result)
                        if progress_callback:
                            progress_callback(completed, total,
                                            inp.get("host_name", ""), result)
                except Exception as e:
                    errors.append({"inputs": inp, "error": str(e)})
                    if error_callback:
                        error_callback(inp.get("host_name", ""), str(e))

        # Sort results by original order (futures complete out of order)
        host_order = {s.get("host_name", str(i)): i for i, s in enumerate(servers)}
        results.sort(key=lambda r: host_order.get(r["inputs"].get("host_name", ""), 0))

        return results, errors

    def _safe_calculate(self, calculate_fn: Callable, inp: Dict) -> Tuple[Optional[Dict], Optional[str]]:
        """Execute calculation with error isolation."""
        try:
            out = calculate_fn(inp)
            return out, None
        except Exception as e:
            logger.error(f"Error analyzing {inp.get('host_name', 'unknown')}: {e}")
            return None, str(e)

    def estimate_time(self, server_count: int, avg_time_per_server: float = 2.0) -> Dict:
        """
        Estimate processing time for a batch.

        Args:
            server_count: Number of servers to process
            avg_time_per_server: Average time per server (seconds)

        Returns:
            Dict with time estimates
        """
        sequential_time = server_count * avg_time_per_server
        parallel_time = (server_count / self.max_workers) * avg_time_per_server

        return {
            "server_count": server_count,
            "sequential_seconds": round(sequential_time, 1),
            "parallel_seconds": round(parallel_time, 1),
            "speedup": round(sequential_time / max(0.1, parallel_time), 1),
            "workers": self.max_workers,
            "estimated_display": _format_time(parallel_time),
        }


def _format_time(seconds: float) -> str:
    """Format seconds to human-readable string."""
    if seconds < 60:
        return f"~{seconds:.0f} seconds"
    minutes = seconds / 60
    if minutes < 60:
        return f"~{minutes:.0f} minutes"
    return f"~{minutes / 60:.1f} hours"


# Default processor
batch_processor = BatchProcessor(max_workers=4, chunk_size=10)
