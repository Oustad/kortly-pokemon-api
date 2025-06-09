"""Cost tracking utilities for Pokemon card scanner API usage."""

import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class CostTracker:
    """Track and estimate costs for API operations."""
    
    # Gemini API pricing (approximate, varies by region)
    # Source: https://ai.google.dev/pricing
    GEMINI_COSTS = {
        "input_tokens_per_1k": 0.00015,   # $0.00015 per 1k input tokens
        "output_tokens_per_1k": 0.0006,    # $0.0006 per 1k output tokens
        "image_processing": 0.0025,        # $0.0025 per image for multimodal
    }
    
    # Pokemon TCG API is free but has rate limits
    TCG_API_COSTS = {
        "search": 0.0,  # Free
        "get_card": 0.0,  # Free
    }
    
    def __init__(self):
        """Initialize cost tracker with session storage."""
        self.session_costs: List[Dict] = []
        self.session_start = datetime.now()
    
    def track_gemini_usage(
        self,
        prompt_tokens: int = 0,
        response_tokens: int = 0,
        includes_image: bool = False,
        operation: str = "identify_card"
    ) -> float:
        """
        Track Gemini API usage and calculate cost.
        
        Args:
            prompt_tokens: Number of input tokens
            response_tokens: Number of output tokens
            includes_image: Whether request included an image
            operation: Description of the operation
            
        Returns:
            Estimated cost in USD
        """
        cost = 0.0
        
        # Token costs
        if prompt_tokens > 0:
            cost += (prompt_tokens / 1000) * self.GEMINI_COSTS["input_tokens_per_1k"]
            
        if response_tokens > 0:
            cost += (response_tokens / 1000) * self.GEMINI_COSTS["output_tokens_per_1k"]
            
        # Image processing cost
        if includes_image:
            cost += self.GEMINI_COSTS["image_processing"]
        
        # Track the usage
        usage_record = {
            "timestamp": datetime.now().isoformat(),
            "service": "gemini",
            "operation": operation,
            "prompt_tokens": prompt_tokens,
            "response_tokens": response_tokens,
            "includes_image": includes_image,
            "cost_usd": cost,
        }
        
        self.session_costs.append(usage_record)
        logger.info(f"💰 Gemini API cost: ${cost:.6f} for {operation}")
        
        return cost
    
    def track_tcg_usage(self, operation: str = "search") -> float:
        """
        Track Pokemon TCG API usage (free but good to monitor).
        
        Args:
            operation: Type of TCG API operation
            
        Returns:
            Cost (always 0.0 for TCG API)
        """
        usage_record = {
            "timestamp": datetime.now().isoformat(),
            "service": "tcg_api",
            "operation": operation,
            "cost_usd": 0.0,
        }
        
        self.session_costs.append(usage_record)
        return 0.0
    
    def get_session_summary(self) -> Dict:
        """
        Get summary of costs for the current session.
        
        Returns:
            Dictionary with cost summary
        """
        total_cost = sum(record["cost_usd"] for record in self.session_costs)
        
        # Group by service
        service_costs = {}
        for record in self.session_costs:
            service = record["service"]
            if service not in service_costs:
                service_costs[service] = {
                    "count": 0,
                    "total_cost": 0.0,
                    "operations": {}
                }
            
            service_costs[service]["count"] += 1
            service_costs[service]["total_cost"] += record["cost_usd"]
            
            # Track operation counts
            op = record.get("operation", "unknown")
            if op not in service_costs[service]["operations"]:
                service_costs[service]["operations"][op] = 0
            service_costs[service]["operations"][op] += 1
        
        return {
            "session_start": self.session_start.isoformat(),
            "session_duration_minutes": (datetime.now() - self.session_start).seconds / 60,
            "total_requests": len(self.session_costs),
            "total_cost_usd": round(total_cost, 6),
            "estimated_monthly_cost": round(total_cost * 30 * 24 * 60 / ((datetime.now() - self.session_start).seconds / 60) if self.session_costs else 0, 2),
            "services": service_costs,
            "average_cost_per_request": round(total_cost / len(self.session_costs), 6) if self.session_costs else 0,
        }
    
    def reset_session(self):
        """Reset session tracking."""
        self.session_costs = []
        self.session_start = datetime.now()
        logger.info("Cost tracking session reset")
    
    def estimate_scan_cost(self, use_image: bool = True) -> Dict[str, float]:
        """
        Estimate cost for a single card scan operation.
        
        Args:
            use_image: Whether scanning includes image processing
            
        Returns:
            Dictionary with cost breakdown
        """
        # Typical token usage for Pokemon card identification
        avg_prompt_tokens = 150 if not use_image else 50  # Less tokens needed with image
        avg_response_tokens = 300  # Typical response length
        
        token_cost = (
            (avg_prompt_tokens / 1000) * self.GEMINI_COSTS["input_tokens_per_1k"] +
            (avg_response_tokens / 1000) * self.GEMINI_COSTS["output_tokens_per_1k"]
        )
        
        image_cost = self.GEMINI_COSTS["image_processing"] if use_image else 0.0
        
        return {
            "token_cost": round(token_cost, 6),
            "image_cost": round(image_cost, 6),
            "total_cost": round(token_cost + image_cost, 6),
            "cost_per_1000_scans": round((token_cost + image_cost) * 1000, 2),
        }