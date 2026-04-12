"""Metrics collection and reporting for SFE."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import threading


@dataclass
class Timer:
    """Simple timer for measuring durations."""
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    
    def stop(self) -> float:
        """Stop the timer and return elapsed time in seconds."""
        self.end_time = time.time()
        return self.elapsed()
    
    def elapsed(self) -> float:
        """Get elapsed time in seconds."""
        end = self.end_time or time.time()
        return end - self.start_time
    
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        return self.elapsed() * 1000


@dataclass
class Counter:
    """Thread-safe counter."""
    value: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def increment(self, amount: int = 1) -> None:
        """Increment the counter."""
        with self._lock:
            self.value += amount
    
    def decrement(self, amount: int = 1) -> None:
        """Decrement the counter."""
        with self._lock:
            self.value -= amount
    
    def get(self) -> int:
        """Get current value."""
        with self._lock:
            return self.value
    
    def reset(self) -> None:
        """Reset counter to zero."""
        with self._lock:
            self.value = 0


@dataclass
class Gauge:
    """Thread-safe gauge for metrics that can go up and down."""
    value: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def set(self, value: float) -> None:
        """Set the gauge value."""
        with self._lock:
            self.value = value
    
    def increment(self, amount: float = 1.0) -> None:
        """Increment the gauge."""
        with self._lock:
            self.value += amount
    
    def decrement(self, amount: float = 1.0) -> None:
        """Decrement the gauge."""
        with self._lock:
            self.value -= amount
    
    def get(self) -> float:
        """Get current value."""
        with self._lock:
            return self.value


@dataclass
class Histogram:
    """Histogram for measuring value distributions."""
    values: List[float] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def observe(self, value: float) -> None:
        """Add a value to the histogram."""
        with self._lock:
            self.values.append(value)
    
    def get_percentile(self, percentile: float) -> float:
        """
        Get value at given percentile.
        
        Args:
            percentile: Value between 0.0 and 1.0
            
        Returns:
            Value at the given percentile
        """
        if not self.values:
            return 0.0
        
        with self._lock:
            sorted_values = sorted(self.values)
            index = int(percentile * len(sorted_values))
            index = max(0, min(index, len(sorted_values) - 1))
            return sorted_values[index]
    
    def get_mean(self) -> float:
        """Get mean value."""
        if not self.values:
            return 0.0
        
        with self._lock:
            return sum(self.values) / len(self.values)
    
    def get_count(self) -> int:
        """Get number of observations."""
        with self._lock:
            return len(self.values)
    
    def clear(self) -> None:
        """Clear all values."""
        with self._lock:
            self.values.clear()


class MetricsCollector:
    """Central metrics collector for SFE."""
    
    def __init__(self):
        # Counters
        self.total_requests = Counter()
        self.cache_hits = Counter()
        self.cache_misses = Counter()
        self.reuse_count = Counter()
        self.adapt_count = Counter()
        self.recompute_count = Counter()
        self.errors = Counter()
        self.total_cost_saved = Counter()  # Track total cost saved in dollars
        
        # Histograms for latency
        self.latency_histogram = Histogram()
        self.retrieval_latency = Histogram()
        self.validation_latency = Histogram()
        self.execution_latency = Histogram()
        
        # Gauges for current state
        self.active_fragments = Gauge()
        self.memory_usage_mb = Gauge()
        
        # Timers for specific operations
        self._timers: Dict[str, Timer] = {}
        self._timer_lock = threading.Lock()
    
    def start_timer(self, name: str) -> None:
        """Start a named timer."""
        with self._timer_lock:
            self._timers[name] = Timer()
    
    def stop_timer(self, name: str) -> float:
        """
        Stop a named timer and return elapsed time in seconds.
        
        Returns:
            Elapsed time in seconds, or 0 if timer not found
        """
        with self._timer_lock:
            timer = self._timers.pop(name, None)
            if timer is None:
                return 0.0
            return timer.stop()
    
    def record_request(self, decision: str, latency_ms: float) -> None:
        """Record a completed request."""
        self.total_requests.increment()
        self.latency_histogram.observe(latency_ms)
        
        if decision == "REUSE":
            self.reuse_count.increment()
            self.cache_hits.increment()
        elif decision == "ADAPT":
            self.adapt_count.increment()
            self.cache_hits.increment()  # Adapt still counts as hit
        elif decision == "RECOMPUTE":
            self.recompute_count.increment()
            self.cache_misses.increment()
    
    def record_error(self) -> None:
        """Record an error occurrence."""
        self.errors.increment()
    
    def update_fragment_count(self, count: int) -> None:
        """Update the active fragment count."""
        self.active_fragments.set(count)
    
    def update_memory_usage(self, mb: float) -> None:
        """Update memory usage gauge."""
        self.memory_usage_mb.set(mb)
    
    def get_metrics(self) -> dict[str, any]:
        """Get all current metrics."""
        total = self.total_requests.get()
        hits = self.cache_hits.get()
        miss = self.cache_misses.get()
        
        hit_rate = hits / max(hits + miss, 1)
        
        return {
            # Counters
            "total_requests": total,
            "cache_hits": hits,
            "cache_misses": miss,
            "reuse_count": self.reuse_count.get(),
            "adapt_count": self.adapt_count.get(),
            "recompute_count": self.recompute_count.get(),
            "error_count": self.errors.get(),
            
            # Rates
            "hit_rate": hit_rate,
            "miss_rate": 1.0 - hit_rate,
            "reuse_rate": self.reuse_count.get() / max(total, 1),
            "adapt_rate": self.adapt_count.get() / max(total, 1),
            "recompute_rate": self.recompute_count.get() / max(total, 1),
            "total_cost_saved": self.total_cost_saved.get(),
            
            # Latency (milliseconds)
            "latency_p50_ms": self.latency_histogram.get_percentile(0.5),
            "latency_p95_ms": self.latency_histogram.get_percentile(0.95),
            "latency_p99_ms": self.latency_histogram.get_percentile(0.99),
            "latency_mean_ms": self.latency_histogram.get_mean(),
            "latency_count": self.latency_histogram.get_count(),
            
            # Sub-operation latency
            "retrieval_latency_p50_ms": self.retrieval_latency.get_percentile(0.5),
            "validation_latency_p50_ms": self.validation_latency.get_percentile(0.5),
            "execution_latency_p50_ms": self.execution_latency.get_percentile(0.5),
            
            # Gauges
            "active_fragments": self.active_fragments.get(),
            "memory_usage_mb": self.memory_usage_mb.get(),
        }


# Global metrics collector instance
metrics_collector = MetricsCollector()