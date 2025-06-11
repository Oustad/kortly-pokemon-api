"""Statistics analyzer for accuracy testing results."""

import statistics
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from collections import defaultdict, Counter


@dataclass
class TestMetrics:
    """Container for test metrics."""
    total_images: int
    successful_scans: int
    failed_scans: int
    success_rate: float
    avg_processing_time: float
    total_cost: float
    avg_cost_per_scan: float
    quality_distribution: Dict[str, int]
    processing_tier_distribution: Dict[str, int]
    error_types: Dict[str, int]
    timing_percentiles: Dict[str, float]
    # New card type metrics
    card_type_distribution: Dict[str, int]
    true_negatives: int
    false_negatives: int
    valid_attempts: int
    adjusted_success_rate: float


class StatsAnalyzer:
    """Analyze testing results and generate statistics."""
    
    def __init__(self):
        self.results = []
        
    def add_result(self, result: Dict[str, Any], filename: str):
        """Add a test result for analysis."""
        # Extract card type information (with safe defaults)
        card_identification = result.get("card_identification") or {}
        card_type_info = card_identification.get("card_type_info") or {}
        card_type = card_type_info.get("card_type", "unknown")
        is_pokemon_card = card_type_info.get("is_pokemon_card", False)
        card_side = card_type_info.get("card_side", "unknown")
        
        processed_result = {
            "filename": filename,
            "success": result.get("success", False),
            "processing_time": (result.get("_test_metadata") or {}).get("request_time_ms", 0),
            "status_code": (result.get("_test_metadata") or {}).get("status_code", 0),
            "error": result.get("error"),
            "cost": (result.get("cost_info") or {}).get("total_cost", 0),
            "quality_score": (result.get("processing") or {}).get("quality_score"),
            "processing_tier": (result.get("processing") or {}).get("processing_tier"),
            "model_used": (result.get("processing") or {}).get("model_used"),
            "tcg_matches": len(result.get("tcg_matches") or []),
            "best_match": result.get("best_match") is not None,
            "language_detected": card_identification.get("language_info", {}).get("detected_language"),
            "translation_occurred": card_identification.get("language_info", {}).get("is_translation", False),
            # New card type fields
            "card_type": card_type,
            "is_pokemon_card": is_pokemon_card,
            "card_side": card_side,
            "is_true_negative": card_type in ["pokemon_back", "non_pokemon"],
            "is_valid_attempt": card_type == "pokemon_front",
        }
        self.results.append(processed_result)
    
    def calculate_metrics(self) -> TestMetrics:
        """Calculate comprehensive test metrics."""
        if not self.results:
            return TestMetrics(
                total_images=0, successful_scans=0, failed_scans=0,
                success_rate=0.0, avg_processing_time=0.0,
                total_cost=0.0, avg_cost_per_scan=0.0,
                quality_distribution={}, processing_tier_distribution={},
                error_types={}, timing_percentiles={},
                card_type_distribution={}, true_negatives=0,
                false_negatives=0, valid_attempts=0, adjusted_success_rate=0.0
            )
        
        total_images = len(self.results)
        successful_scans = sum(1 for r in self.results if r["success"])
        failed_scans = total_images - successful_scans
        success_rate = (successful_scans / total_images) * 100
        
        # Processing times (only successful scans)
        processing_times = [r["processing_time"] for r in self.results if r["success"]]
        avg_processing_time = statistics.mean(processing_times) if processing_times else 0
        
        # Cost analysis
        total_cost = sum(r["cost"] for r in self.results)
        avg_cost_per_scan = total_cost / total_images if total_images > 0 else 0
        
        # Quality distribution
        quality_scores = [r["quality_score"] for r in self.results if r["quality_score"] is not None]
        quality_distribution = self._categorize_quality_scores(quality_scores)
        
        # Processing tier distribution
        tier_counts = Counter(r["processing_tier"] for r in self.results if r["processing_tier"])
        processing_tier_distribution = dict(tier_counts)
        
        # Error analysis
        error_types = self._analyze_errors()
        
        # Timing percentiles
        timing_percentiles = self._calculate_timing_percentiles(processing_times)
        
        # Card type analysis
        card_type_counts = Counter(r["card_type"] for r in self.results)
        card_type_distribution = dict(card_type_counts)
        
        # True negatives (card backs and non-Pokemon cards that were correctly identified)
        true_negatives = sum(1 for r in self.results if r["is_true_negative"] and r["success"])
        
        # Valid attempts (Pokemon front cards)
        valid_attempts = sum(1 for r in self.results if r["is_valid_attempt"])
        
        # False negatives (Pokemon front cards that failed)
        false_negatives = sum(1 for r in self.results if r["is_valid_attempt"] and not r["success"])
        
        # Adjusted success rate (only counting valid attempts)
        if valid_attempts > 0:
            successful_valid_attempts = sum(1 for r in self.results if r["is_valid_attempt"] and r["success"])
            adjusted_success_rate = (successful_valid_attempts / valid_attempts) * 100
        else:
            adjusted_success_rate = 0.0
        
        return TestMetrics(
            total_images=total_images,
            successful_scans=successful_scans,
            failed_scans=failed_scans,
            success_rate=success_rate,
            avg_processing_time=avg_processing_time,
            total_cost=total_cost,
            avg_cost_per_scan=avg_cost_per_scan,
            quality_distribution=quality_distribution,
            processing_tier_distribution=processing_tier_distribution,
            error_types=error_types,
            timing_percentiles=timing_percentiles,
            card_type_distribution=card_type_distribution,
            true_negatives=true_negatives,
            false_negatives=false_negatives,
            valid_attempts=valid_attempts,
            adjusted_success_rate=adjusted_success_rate
        )
    
    def _categorize_quality_scores(self, scores: List[float]) -> Dict[str, int]:
        """Categorize quality scores into bins."""
        if not scores:
            return {}
        
        categories = defaultdict(int)
        for score in scores:
            if score >= 80:
                categories["Excellent (80-100)"] += 1
            elif score >= 60:
                categories["Good (60-79)"] += 1
            elif score >= 40:
                categories["Fair (40-59)"] += 1
            else:
                categories["Poor (0-39)"] += 1
        
        return dict(categories)
    
    def _analyze_errors(self) -> Dict[str, int]:
        """Analyze and categorize errors."""
        error_types = defaultdict(int)
        
        for result in self.results:
            if not result["success"]:
                error = result.get("error", "Unknown error")
                
                # Categorize common error types
                if "timeout" in error.lower():
                    error_types["Timeout"] += 1
                elif "api key" in error.lower():
                    error_types["API Key Issue"] += 1
                elif "rate limit" in error.lower():
                    error_types["Rate Limit"] += 1
                elif "processing" in error.lower():
                    error_types["Processing Error"] += 1
                elif "gemini" in error.lower():
                    error_types["Gemini API Error"] += 1
                else:
                    error_types["Other"] += 1
        
        return dict(error_types)
    
    def _calculate_timing_percentiles(self, times: List[float]) -> Dict[str, float]:
        """Calculate timing percentiles."""
        if not times:
            return {}
        
        sorted_times = sorted(times)
        
        return {
            "p50": statistics.median(sorted_times),
            "p90": sorted_times[int(0.9 * len(sorted_times))] if len(sorted_times) > 10 else sorted_times[-1],
            "p95": sorted_times[int(0.95 * len(sorted_times))] if len(sorted_times) > 20 else sorted_times[-1],
            "p99": sorted_times[int(0.99 * len(sorted_times))] if len(sorted_times) > 100 else sorted_times[-1],
            "min": min(sorted_times),
            "max": max(sorted_times)
        }
    
    def get_detailed_analysis(self) -> Dict[str, Any]:
        """Get detailed analysis for reporting."""
        metrics = self.calculate_metrics()
        
        # Language analysis
        language_stats = Counter(r["language_detected"] for r in self.results if r["language_detected"])
        translation_count = sum(1 for r in self.results if r["translation_occurred"])
        
        # TCG match analysis
        no_matches = sum(1 for r in self.results if r["success"] and r["tcg_matches"] == 0)
        has_best_match = sum(1 for r in self.results if r["success"] and r["best_match"])
        
        # Model usage
        model_usage = Counter(r["model_used"] for r in self.results if r["model_used"])
        
        return {
            "overall_metrics": metrics,
            "language_analysis": {
                "detected_languages": dict(language_stats),
                "translations_performed": translation_count,
                "translation_rate": (translation_count / metrics.total_images * 100) if metrics.total_images > 0 else 0
            },
            "tcg_analysis": {
                "scans_with_no_matches": no_matches,
                "scans_with_best_match": has_best_match,
                "match_success_rate": (has_best_match / metrics.successful_scans * 100) if metrics.successful_scans > 0 else 0
            },
            "model_usage": dict(model_usage),
            "failed_scans": [
                {"filename": r["filename"], "error": r["error"], "status_code": r["status_code"]}
                for r in self.results if not r["success"]
            ]
        }