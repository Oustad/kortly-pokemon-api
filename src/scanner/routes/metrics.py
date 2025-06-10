"""Metrics and monitoring endpoints."""

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request

from ..config import get_config
from ..services.metrics_service import get_metrics_service

logger = logging.getLogger(__name__)
config = get_config()

router = APIRouter(prefix="/api/v1", tags=["metrics"])


@router.get("/metrics")
async def get_metrics() -> Dict[str, Any]:
    """
    Get current application metrics.
    
    Returns aggregated metrics including request counts, response times,
    API usage, costs, and error rates.
    """
    if not config.enable_metrics:
        raise HTTPException(
            status_code=404,
            detail="Metrics collection is disabled"
        )
    
    metrics_service = get_metrics_service()
    return metrics_service.get_current_metrics()


@router.get("/metrics/hourly")
async def get_hourly_metrics() -> Dict[str, Any]:
    """
    Get hourly metrics for the last 24 hours.
    
    Returns hourly breakdown of request counts and error rates.
    """
    if not config.enable_metrics:
        raise HTTPException(
            status_code=404,
            detail="Metrics collection is disabled"
        )
    
    metrics_service = get_metrics_service()
    return metrics_service.get_hourly_metrics()


@router.get("/metrics/recent")
async def get_recent_requests(limit: int = 10) -> Dict[str, Any]:
    """
    Get recent request details.
    
    Args:
        limit: Number of recent requests to return (max 100)
        
    Returns detailed information about recent requests.
    """
    if not config.enable_metrics:
        raise HTTPException(
            status_code=404,
            detail="Metrics collection is disabled"
        )
    
    if limit > 100:
        limit = 100
    
    metrics_service = get_metrics_service()
    return metrics_service.get_recent_requests(limit)


@router.post("/metrics/reset")
async def reset_metrics(request: Request) -> Dict[str, str]:
    """
    Reset all metrics.
    
    Only available in development/debug mode.
    """
    if not config.debug and config.environment == "production":
        raise HTTPException(
            status_code=404,
            detail="Endpoint not available in production mode"
        )
    
    if not config.enable_metrics:
        raise HTTPException(
            status_code=404,
            detail="Metrics collection is disabled"
        )
    
    metrics_service = get_metrics_service()
    metrics_service.reset_metrics()
    
    logger.info("Metrics reset by admin request")
    
    return {"status": "metrics_reset", "message": "All metrics have been reset"}


@router.get("/metrics/prometheus")
async def get_prometheus_metrics() -> str:
    """
    Get metrics in Prometheus format.
    
    Returns metrics formatted for Prometheus scraping.
    """
    if not config.enable_metrics:
        raise HTTPException(
            status_code=404,
            detail="Metrics collection is disabled"
        )
    
    metrics_service = get_metrics_service()
    current_metrics = metrics_service.get_current_metrics()
    
    # Convert to Prometheus format
    prometheus_lines = [
        "# HELP pokemon_scanner_requests_total Total number of requests",
        "# TYPE pokemon_scanner_requests_total counter",
        f"pokemon_scanner_requests_total {current_metrics['requests']['total']}",
        "",
        "# HELP pokemon_scanner_requests_successful_total Total number of successful requests",
        "# TYPE pokemon_scanner_requests_successful_total counter", 
        f"pokemon_scanner_requests_successful_total {current_metrics['requests']['successful']}",
        "",
        "# HELP pokemon_scanner_requests_failed_total Total number of failed requests",
        "# TYPE pokemon_scanner_requests_failed_total counter",
        f"pokemon_scanner_requests_failed_total {current_metrics['requests']['failed']}",
        "",
        "# HELP pokemon_scanner_response_time_ms_avg Average response time in milliseconds",
        "# TYPE pokemon_scanner_response_time_ms_avg gauge",
        f"pokemon_scanner_response_time_ms_avg {current_metrics['response_times_ms']['average']}",
        "",
        "# HELP pokemon_scanner_gemini_api_calls_total Total Gemini API calls",
        "# TYPE pokemon_scanner_gemini_api_calls_total counter",
        f"pokemon_scanner_gemini_api_calls_total {current_metrics['api_usage']['gemini_calls']}",
        "",
        "# HELP pokemon_scanner_tcg_api_calls_total Total TCG API calls", 
        "# TYPE pokemon_scanner_tcg_api_calls_total counter",
        f"pokemon_scanner_tcg_api_calls_total {current_metrics['api_usage']['tcg_calls']}",
        "",
        "# HELP pokemon_scanner_total_cost_usd Total cost in USD",
        "# TYPE pokemon_scanner_total_cost_usd counter",
        f"pokemon_scanner_total_cost_usd {current_metrics['api_usage']['total_cost_usd']}",
        "",
        "# HELP pokemon_scanner_images_processed_total Total images processed",
        "# TYPE pokemon_scanner_images_processed_total counter",
        f"pokemon_scanner_images_processed_total {current_metrics['image_processing']['images_processed']}",
        "",
        "# HELP pokemon_scanner_cache_hits_total Total cache hits",
        "# TYPE pokemon_scanner_cache_hits_total counter",
        f"pokemon_scanner_cache_hits_total {current_metrics['cache']['hits']}",
        "",
        "# HELP pokemon_scanner_cache_misses_total Total cache misses",
        "# TYPE pokemon_scanner_cache_misses_total counter",
        f"pokemon_scanner_cache_misses_total {current_metrics['cache']['misses']}",
        "",
        "# HELP pokemon_scanner_uptime_seconds Service uptime in seconds",
        "# TYPE pokemon_scanner_uptime_seconds gauge",
        f"pokemon_scanner_uptime_seconds {current_metrics['uptime_seconds']}",
    ]
    
    # Add response time percentiles
    if 'p50' in current_metrics['response_times_ms']:
        prometheus_lines.extend([
            "",
            "# HELP pokemon_scanner_response_time_ms_p50 50th percentile response time",
            "# TYPE pokemon_scanner_response_time_ms_p50 gauge",
            f"pokemon_scanner_response_time_ms_p50 {current_metrics['response_times_ms']['p50']}",
            "",
            "# HELP pokemon_scanner_response_time_ms_p90 90th percentile response time",
            "# TYPE pokemon_scanner_response_time_ms_p90 gauge", 
            f"pokemon_scanner_response_time_ms_p90 {current_metrics['response_times_ms']['p90']}",
            "",
            "# HELP pokemon_scanner_response_time_ms_p95 95th percentile response time",
            "# TYPE pokemon_scanner_response_time_ms_p95 gauge",
            f"pokemon_scanner_response_time_ms_p95 {current_metrics['response_times_ms']['p95']}",
            "",
            "# HELP pokemon_scanner_response_time_ms_p99 99th percentile response time", 
            "# TYPE pokemon_scanner_response_time_ms_p99 gauge",
            f"pokemon_scanner_response_time_ms_p99 {current_metrics['response_times_ms']['p99']}",
        ])
    
    # Add error counts by type
    for error_type, count in current_metrics['errors'].items():
        prometheus_lines.extend([
            "",
            f"# HELP pokemon_scanner_errors_{error_type.lower()}_total Total {error_type} errors",
            f"# TYPE pokemon_scanner_errors_{error_type.lower()}_total counter",
            f"pokemon_scanner_errors_{error_type.lower()}_total {count}",
        ])
    
    return "\n".join(prometheus_lines)