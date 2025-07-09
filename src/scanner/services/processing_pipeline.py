"""Tiered processing pipeline for optimal speed and quality balance."""

import logging
from typing import Dict, Any, Tuple, Optional
import time
from PIL import Image
import io

from .quality_assessment import QualityAssessment
from .image_processor import ImageProcessor
from .gemini_service import GeminiService
from ..config import get_config

logger = logging.getLogger(__name__)
config = get_config()


class ProcessingPipeline:
    """Multi-tier processing pipeline that routes images based on quality assessment."""
    
    def __init__(self, gemini_service: GeminiService):
        self.quality_assessor = QualityAssessment()
        self.image_processor = ImageProcessor()
        self.gemini_service = gemini_service
        
        # Tier configurations
        self.tier_configs = {
            'fast': {
                'max_size': (512, 512),
                'enhance_image': False,
                'target_time_ms': 1000,
                'quality_threshold': 80
            },
            'standard': {
                'max_size': (768, 768),
                'enhance_image': True,
                'target_time_ms': 2000,
                'quality_threshold': 50
            },
            'enhanced': {
                'max_size': (1024, 1024),
                'enhance_image': True,
                'target_time_ms': 4000,
                'quality_threshold': 0
            }
        }
    
    async def process_image(
        self, 
        image_bytes: bytes, 
        filename: str,
        user_preferences: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Process image through appropriate tier based on quality assessment.
        
        Args:
            image_bytes: Raw image data
            filename: Original filename for context
            user_preferences: Optional user processing preferences
            
        Returns:
            Complete processing result with metadata
        """
        start_time = time.time()
        processing_log = []
        
        try:
            assessment_start = time.time()
            quality_result = self.quality_assessor.assess_image_quality(image_bytes)
            assessment_time = (time.time() - assessment_start) * 1000
            
            processing_log.append(f"Quality assessment: {assessment_time:.1f}ms")
            
            if quality_result['quality_score'] == 0:
                return self._create_error_result(
                    "Image quality assessment failed",
                    quality_result,
                    processing_log,
                    start_time
                )
            
            # Check if quality score is below acceptable threshold
            if quality_result['quality_score'] < 40:
                result = self._create_error_result(
                    "Image quality too low for accurate scanning",
                    quality_result,
                    processing_log,
                    start_time
                )
                # Add error_type for proper handling in scan route
                result['error_type'] = 'image_quality'
                result['quality_score'] = quality_result.get('quality_score', 0.0)
                result['quality_issues'] = []
                
                # Extract specific quality issues
                if quality_result.get('details', {}).get('blur_score', 100) < 20:
                    result['quality_issues'].append("Image is too blurry")
                if quality_result.get('details', {}).get('card_detection_confidence', 0) < 50:
                    result['quality_issues'].append("Card not clearly visible in image")
                
                return result
            
            processing_config = self._determine_processing_config(quality_result['quality_score'], user_preferences)
            tier = processing_config['tier']  # Extract tier for backwards compatibility
            tier_config = self.tier_configs[tier]
            
            processing_log.append(f"Using comprehensive analysis with authenticity detection (quality: {quality_result['quality_score']:.1f})")
            
            preprocess_start = time.time()
            processed_image_bytes = await self._preprocess_image(
                image_bytes, 
                tier_config,
                filename
            )
            preprocess_time = (time.time() - preprocess_start) * 1000
            
            processing_log.append(f"Image preprocessing: {preprocess_time:.1f}ms")
            
            gemini_start = time.time()
            gemini_result = await self.gemini_service.identify_pokemon_card(
                processed_image_bytes,
                optimize_for_speed=True  # Always optimize for speed with comprehensive prompt
            )
            gemini_time = (time.time() - gemini_start) * 1000
            
            processing_log.append(f"Gemini analysis: {gemini_time:.1f}ms")
            
            # Check if Gemini processing failed
            if not gemini_result.get('success', False):
                return self._create_error_result(
                    f"Gemini processing failed: {gemini_result.get('error', 'Unknown error')}",
                    quality_result,
                    processing_log,
                    start_time
                )
            
            total_time = (time.time() - start_time) * 1000
            
            return self._create_success_result(
                gemini_result,
                quality_result,
                tier,
                tier_config,
                processing_log,
                total_time,
                {
                    'assessment_ms': assessment_time,
                    'preprocess_ms': preprocess_time,
                    'gemini_ms': gemini_time,
                    'total_ms': total_time
                },
                processed_image_bytes
            )
            
        except Exception as e:
            logger.error(f"Processing pipeline failed: {e}")
            total_time = (time.time() - start_time) * 1000
            return self._create_error_result(
                f"Processing failed: {str(e)}",
                quality_result if 'quality_result' in locals() else None,
                processing_log,
                start_time
            )
    
    def _determine_processing_config(
        self, 
        quality_score: float, 
        user_preferences: Optional[Dict] = None
    ) -> Dict:
        """Get comprehensive processing configuration."""
        
        # Always use comprehensive analysis with authenticity detection
        config = self.quality_assessor.get_processing_configuration(quality_score)
        
        # Apply user time preferences to target time
        if user_preferences and user_preferences.get('max_processing_time'):
            max_time = user_preferences['max_processing_time']
            if max_time < config['target_time_ms']:
                config['target_time_ms'] = max_time
        
        return config
    
    async def _preprocess_image(
        self, 
        image_bytes: bytes, 
        tier_config: Dict,
        filename: str
    ) -> bytes:
        """Preprocess image according to tier configuration."""
        
        # Load image
        image = Image.open(io.BytesIO(image_bytes))
        
        # Resize if needed
        max_size = tier_config['max_size']
        if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
            # Calculate resize maintaining aspect ratio
            ratio = min(max_size[0] / image.size[0], max_size[1] / image.size[1])
            new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        # Basic enhancement for standard/enhanced tiers
        if tier_config['enhance_image']:
            image = self._enhance_image(image, tier_config)
        
        # Convert to RGB if necessary (JPEG doesn't support transparency)
        if image.mode not in ("RGB", "L"):
            if image.mode == "RGBA":
                # Create white background for transparent images
                background = Image.new("RGB", image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[3])
                image = background
            else:
                image = image.convert("RGB")
        
        # Convert back to bytes
        output_buffer = io.BytesIO()
        
        # Optimize format based on tier
        if tier_config == self.tier_configs['fast']:
            # Fast tier: prioritize speed over file size
            image.save(output_buffer, format='JPEG', quality=85, optimize=False)
        else:
            # Standard/Enhanced: balance quality and speed
            image.save(output_buffer, format='JPEG', quality=90, optimize=True)
        
        return output_buffer.getvalue()
    
    def _enhance_image(self, image: Image.Image, tier_config: Dict) -> Image.Image:
        """Apply basic image enhancements."""
        from PIL import ImageEnhance
        
        try:
            # Contrast enhancement
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.1)  # Slight contrast boost
            
            # Sharpness enhancement for enhanced tier
            if tier_config == self.tier_configs['enhanced']:
                enhancer = ImageEnhance.Sharpness(image)
                image = enhancer.enhance(1.2)  # Moderate sharpening
            
            return image
            
        except Exception as e:
            logger.warning(f"Image enhancement failed: {e}")
            return image  # Return original if enhancement fails
    
    def _create_success_result(
        self,
        gemini_result: Dict,
        quality_result: Dict, 
        tier: str,
        tier_config: Dict,
        processing_log: list,
        total_time: float,
        timing_breakdown: Dict,
        processed_image_data: bytes = None
    ) -> Dict[str, Any]:
        """Create successful processing result."""
        
        result = {
            'success': True,
            'card_data': gemini_result,
            'processing': {
                'quality_score': quality_result.get('quality_score', 0),
                'quality_feedback': quality_result.get('details', {}).get('feedback', {}),
                'processing_tier': tier,
                'target_time_ms': tier_config.get('target_time_ms', 0),
                'actual_time_ms': total_time,
                'model_used': config.gemini_model,
                'image_enhanced': tier_config.get('enhance_image', False),
                'timing_breakdown': timing_breakdown,
                'processing_log': processing_log,
                'performance_rating': self._get_performance_rating(
                    total_time, 
                    tier_config.get('target_time_ms', 0)
                )
            }
        }
        
        # Include processed image data if available
        if processed_image_data:
            result['processed_image_data'] = processed_image_data
            
        return result
    
    def _create_error_result(
        self,
        error_message: str,
        quality_result: Optional[Dict],
        processing_log: list,
        start_time: float
    ) -> Dict[str, Any]:
        """Create error processing result."""
        
        total_time = (time.time() - start_time) * 1000
        
        # Create default quality feedback if none available
        quality_feedback = {
            'overall': 'unknown',
            'issues': ['Processing failed'],
            'suggestions': ['Check API configuration and try again']
        }
        
        if quality_result and quality_result.get('details', {}).get('feedback'):
            quality_feedback = quality_result.get('details', {}).get('feedback', {})
        
        return {
            'success': False,
            'error': error_message,
            'processing': {
                'quality_score': quality_result.get('quality_score', 0.0) if quality_result else 0.0,
                'quality_feedback': quality_feedback,
                'processing_tier': 'failed',
                'target_time_ms': 2000,  # Default target
                'actual_time_ms': total_time,
                'model_used': 'none',
                'image_enhanced': False,
                'performance_rating': 'failed',
                'timing_breakdown': {'error_ms': total_time},
                'processing_log': processing_log + [f"Error: {error_message}"]
            }
        }
    
    def _get_performance_rating(self, actual_time: float, target_time: float) -> str:
        """Rate performance against target time."""
        ratio = actual_time / target_time
        
        if ratio <= 0.8:
            return 'excellent'
        elif ratio <= 1.0:
            return 'good'
        elif ratio <= 1.5:
            return 'acceptable'
        else:
            return 'slow'
    
    def get_tier_info(self) -> Dict[str, Any]:
        """Get information about available processing tiers."""
        return {
            'tiers': {
                tier: {
                    'description': self._get_tier_description(tier),
                    'target_time_ms': config.get('target_time_ms', 0),
                    'max_resolution': config.get('max_size', 0),
                    'quality_threshold': config.get('quality_threshold', 0),
                    'image_enhancement': config.get('enhance_image', False)
                }
                for tier, config in self.tier_configs.items()
            }
        }
    
    def _get_tier_description(self, tier: str) -> str:
        """Get human-readable tier description."""
        descriptions = {
            'fast': 'Optimized for speed with high-quality images',
            'standard': 'Balanced processing for good quality images', 
            'enhanced': 'Comprehensive processing for challenging images'
        }
        return descriptions.get(tier, 'Unknown tier')