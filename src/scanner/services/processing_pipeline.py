"""Tiered processing pipeline for optimal speed and quality balance."""

import logging
from typing import Dict, Any, Tuple, Optional
import time
from PIL import Image
import io

from .quality_assessment import QualityAssessment
from .image_processor import ImageProcessor
from .gemini_service import GeminiService

logger = logging.getLogger(__name__)


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
                'model': 'gemini-2.5-flash',
                'enhance_image': False,
                'target_time_ms': 1000,
                'quality_threshold': 80
            },
            'standard': {
                'max_size': (768, 768),
                'model': 'gemini-2.5-flash', 
                'enhance_image': True,
                'target_time_ms': 2000,
                'quality_threshold': 50
            },
            'enhanced': {
                'max_size': (1024, 1024),
                'model': 'gemini-2.5-flash',  # Could use Pro if available
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
            # Step 1: Quality Assessment
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
            
            # Step 2: Determine Processing Tier
            tier = self._determine_tier(quality_result['quality_score'], user_preferences)
            tier_config = self.tier_configs[tier]
            
            processing_log.append(f"Selected tier: {tier} (quality: {quality_result['quality_score']:.1f})")
            
            # Step 3: Image Preprocessing
            preprocess_start = time.time()
            processed_image_bytes = await self._preprocess_image(
                image_bytes, 
                tier_config,
                filename
            )
            preprocess_time = (time.time() - preprocess_start) * 1000
            
            processing_log.append(f"Image preprocessing: {preprocess_time:.1f}ms")
            
            # Step 4: Gemini Analysis
            gemini_start = time.time()
            gemini_result = await self.gemini_service.identify_pokemon_card(
                processed_image_bytes,
                optimize_for_speed=(tier == 'fast'),
                processing_tier=tier
            )
            gemini_time = (time.time() - gemini_start) * 1000
            
            processing_log.append(f"Gemini analysis: {gemini_time:.1f}ms")
            
            # Step 5: Compile Results
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
    
    def _determine_tier(
        self, 
        quality_score: float, 
        user_preferences: Optional[Dict] = None
    ) -> str:
        """Determine appropriate processing tier."""
        
        # User preference override
        if user_preferences:
            if user_preferences.get('prefer_speed') and quality_score >= 60:
                return 'fast'
            elif user_preferences.get('prefer_quality'):
                return 'enhanced'
            elif user_preferences.get('max_processing_time'):
                max_time = user_preferences['max_processing_time']
                if max_time <= 1500:
                    return 'fast'
                elif max_time <= 2500:
                    return 'standard'
        
        # Default tier selection based on quality
        return self.quality_assessor.get_processing_tier(quality_score)
    
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
                'quality_score': quality_result['quality_score'],
                'quality_feedback': quality_result['details'].get('feedback', {}),
                'processing_tier': tier,
                'target_time_ms': tier_config['target_time_ms'],
                'actual_time_ms': total_time,
                'model_used': tier_config['model'],
                'image_enhanced': tier_config['enhance_image'],
                'timing_breakdown': timing_breakdown,
                'processing_log': processing_log,
                'performance_rating': self._get_performance_rating(
                    total_time, 
                    tier_config['target_time_ms']
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
            quality_feedback = quality_result['details']['feedback']
        
        return {
            'success': False,
            'error': error_message,
            'processing': {
                'quality_score': quality_result['quality_score'] if quality_result else 0.0,
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
                    'target_time_ms': config['target_time_ms'],
                    'max_resolution': config['max_size'],
                    'quality_threshold': config['quality_threshold'],
                    'image_enhancement': config['enhance_image']
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