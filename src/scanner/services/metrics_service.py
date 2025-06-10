"""Metrics collection and monitoring service."""

import time
from collections import defaultdict
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ..config import get_config

config = get_config()


@dataclass
class RequestMetrics:
    """Metrics for individual requests."""
    timestamp: datetime
    endpoint: str
    method: str
    status_code: int
    processing_time_ms: float
    image_size_bytes: Optional[int] = None
    gemini_cost: Optional[float] = None
    tcg_matches: Optional[int] = None
    error_type: Optional[str] = None


@dataclass
class ServiceMetrics:
    """Aggregated service metrics."""
    # Request counts
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    
    # Response times
    avg_response_time_ms: float = 0.0
    min_response_time_ms: float = float('inf')
    max_response_time_ms: float = 0.0
    
    # API usage
    gemini_api_calls: int = 0
    tcg_api_calls: int = 0
    total_cost_usd: float = 0.0
    
    # Image processing
    images_processed: int = 0
    total_image_size_mb: float = 0.0
    heic_images: int = 0
    
    # Cache metrics
    cache_hits: int = 0
    cache_misses: int = 0
    
    # Error tracking
    errors_by_type: Dict[str, int] = field(default_factory=dict)
    
    # Time periods
    start_time: datetime = field(default_factory=datetime.now)
    last_request_time: Optional[datetime] = None


class MetricsService:
    """Service for collecting and aggregating application metrics."""
    
    def __init__(self):
        self.metrics = ServiceMetrics()
        self.recent_requests = []  # Last 100 requests for detailed metrics
        self.response_times = []  # Last 1000 response times for percentiles
        self._hourly_metrics = defaultdict(lambda: ServiceMetrics())
    
    def record_request(self, request_metrics: RequestMetrics):
        """Record metrics for a completed request."""
        if not config.enable_metrics:
            return
        
        # Update basic counters
        self.metrics.total_requests += 1
        self.metrics.last_request_time = request_metrics.timestamp
        
        # Track success/failure
        if 200 <= request_metrics.status_code < 400:
            self.metrics.successful_requests += 1
        else:
            self.metrics.failed_requests += 1
        
        # Update response time metrics
        self._update_response_times(request_metrics.processing_time_ms)
        
        # Track API usage
        if request_metrics.endpoint == "/api/v1/scan":
            self.metrics.gemini_api_calls += 1
            if request_metrics.tcg_matches is not None:
                self.metrics.tcg_api_calls += 1
        
        # Track costs
        if request_metrics.gemini_cost:
            self.metrics.total_cost_usd += request_metrics.gemini_cost
        
        # Track image processing
        if request_metrics.image_size_bytes:
            self.metrics.images_processed += 1
            self.metrics.total_image_size_mb += request_metrics.image_size_bytes / (1024 * 1024)
        
        # Track errors
        if request_metrics.error_type:
            self.metrics.errors_by_type[request_metrics.error_type] = (
                self.metrics.errors_by_type.get(request_metrics.error_type, 0) + 1
            )
        
        # Store recent requests (limit to last 100)
        self.recent_requests.append(request_metrics)
        if len(self.recent_requests) > 100:
            self.recent_requests.pop(0)
        
        # Update hourly metrics
        hour_key = request_metrics.timestamp.replace(minute=0, second=0, microsecond=0)
        hourly = self._hourly_metrics[hour_key]
        hourly.total_requests += 1
        if 200 <= request_metrics.status_code < 400:
            hourly.successful_requests += 1
        else:
            hourly.failed_requests += 1
        
        # Clean old hourly metrics (keep last 24 hours)
        cutoff = datetime.now() - timedelta(hours=24)
        self._hourly_metrics = {
            k: v for k, v in self._hourly_metrics.items() if k >= cutoff
        }
    
    def _update_response_times(self, processing_time_ms: float):
        """Update response time statistics."""
        # Update min/max
        self.metrics.min_response_time_ms = min(
            self.metrics.min_response_time_ms, processing_time_ms
        )
        self.metrics.max_response_time_ms = max(
            self.metrics.max_response_time_ms, processing_time_ms
        )
        
        # Store for percentile calculations (limit to last 1000)
        self.response_times.append(processing_time_ms)
        if len(self.response_times) > 1000:
            self.response_times.pop(0)
        
        # Update average
        if self.response_times:
            self.metrics.avg_response_time_ms = sum(self.response_times) / len(self.response_times)
    
    def record_cache_hit(self):
        """Record a cache hit."""
        if config.enable_metrics:
            self.metrics.cache_hits += 1
    
    def record_cache_miss(self):
        """Record a cache miss."""
        if config.enable_metrics:
            self.metrics.cache_misses += 1
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current aggregated metrics."""
        if not config.enable_metrics:
            return {"metrics_disabled": True}
        
        uptime = datetime.now() - self.metrics.start_time
        
        # Calculate percentiles
        percentiles = self._calculate_percentiles()
        
        # Calculate rates
        uptime_seconds = uptime.total_seconds()
        request_rate = self.metrics.total_requests / uptime_seconds if uptime_seconds > 0 else 0
        error_rate = (self.metrics.failed_requests / self.metrics.total_requests * 100 
                     if self.metrics.total_requests > 0 else 0)
        
        # Cache hit rate
        total_cache_requests = self.metrics.cache_hits + self.metrics.cache_misses
        cache_hit_rate = (self.metrics.cache_hits / total_cache_requests * 100 
                         if total_cache_requests > 0 else 0)
        
        return {
            "uptime_seconds": int(uptime_seconds),
            "uptime_human": str(uptime).split('.')[0],  # Remove microseconds
            
            # Request metrics
            "requests": {
                "total": self.metrics.total_requests,
                "successful": self.metrics.successful_requests,
                "failed": self.metrics.failed_requests,
                "rate_per_second": round(request_rate, 2),
                "error_rate_percent": round(error_rate, 2),
            },
            
            # Response time metrics
            "response_times_ms": {
                "average": round(self.metrics.avg_response_time_ms, 2),
                "minimum": round(self.metrics.min_response_time_ms, 2) if self.metrics.min_response_time_ms != float('inf') else None,
                "maximum": round(self.metrics.max_response_time_ms, 2),
                **percentiles,
            },
            
            # API usage
            "api_usage": {
                "gemini_calls": self.metrics.gemini_api_calls,
                "tcg_calls": self.metrics.tcg_api_calls,
                "total_cost_usd": round(self.metrics.total_cost_usd, 6),
                "avg_cost_per_request": round(
                    self.metrics.total_cost_usd / self.metrics.gemini_api_calls, 6
                ) if self.metrics.gemini_api_calls > 0 else 0,
            },
            
            # Image processing
            "image_processing": {
                "images_processed": self.metrics.images_processed,
                "total_size_mb": round(self.metrics.total_image_size_mb, 2),
                "avg_size_mb": round(
                    self.metrics.total_image_size_mb / self.metrics.images_processed, 2
                ) if self.metrics.images_processed > 0 else 0,
                "heic_images": self.metrics.heic_images,
            },
            
            # Cache metrics
            "cache": {
                "hits": self.metrics.cache_hits,
                "misses": self.metrics.cache_misses,
                "hit_rate_percent": round(cache_hit_rate, 2),
            },
            
            # Error breakdown
            "errors": dict(self.metrics.errors_by_type),
            
            # Timestamps
            "start_time": self.metrics.start_time.isoformat(),
            "last_request_time": self.metrics.last_request_time.isoformat() if self.metrics.last_request_time else None,
        }
    
    def _calculate_percentiles(self) -> Dict[str, float]:
        """Calculate response time percentiles."""
        if not self.response_times:
            return {}
        
        sorted_times = sorted(self.response_times)
        length = len(sorted_times)
        
        def percentile(p):
            index = int(length * p / 100)
            if index >= length:
                index = length - 1
            return round(sorted_times[index], 2)
        
        return {
            "p50": percentile(50),
            "p90": percentile(90),
            "p95": percentile(95),
            "p99": percentile(99),
        }
    
    def get_hourly_metrics(self) -> Dict[str, Any]:
        """Get hourly metrics for the last 24 hours."""
        if not config.enable_metrics:
            return {"metrics_disabled": True}
        
        hourly_data = []
        for hour, metrics in sorted(self._hourly_metrics.items()):
            hourly_data.append({
                "hour": hour.isoformat(),
                "total_requests": metrics.total_requests,
                "successful_requests": metrics.successful_requests,
                "failed_requests": metrics.failed_requests,
                "error_rate_percent": round(
                    metrics.failed_requests / metrics.total_requests * 100, 2
                ) if metrics.total_requests > 0 else 0,
            })
        
        return {
            "hours": hourly_data,
            "total_hours": len(hourly_data),
        }
    
    def get_recent_requests(self, limit: int = 10) -> Dict[str, Any]:
        """Get recent request details."""
        if not config.enable_metrics:
            return {"metrics_disabled": True}
        
        recent = self.recent_requests[-limit:] if limit > 0 else self.recent_requests
        
        return {
            "requests": [
                {
                    "timestamp": req.timestamp.isoformat(),
                    "endpoint": req.endpoint,
                    "method": req.method,
                    "status_code": req.status_code,
                    "processing_time_ms": round(req.processing_time_ms, 2),
                    "image_size_kb": round(req.image_size_bytes / 1024, 2) if req.image_size_bytes else None,
                    "cost_usd": req.gemini_cost,
                    "tcg_matches": req.tcg_matches,
                    "error_type": req.error_type,
                }
                for req in reversed(recent)  # Most recent first
            ],
            "total_recent": len(self.recent_requests),
        }
    
    def reset_metrics(self):
        """Reset all metrics (for testing or maintenance)."""
        self.metrics = ServiceMetrics()
        self.recent_requests.clear()
        self.response_times.clear()
        self._hourly_metrics.clear()


# Global metrics service instance
_metrics_service: Optional[MetricsService] = None


def get_metrics_service() -> MetricsService:
    """Get global metrics service instance."""
    global _metrics_service
    if _metrics_service is None:
        _metrics_service = MetricsService()
    return _metrics_service