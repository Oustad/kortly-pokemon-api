"""Quality assessment module for Pokemon card images."""

import logging
from typing import Dict, List, Tuple
import cv2
import numpy as np
from PIL import Image
import io
from pillow_heif import register_heif_opener

# Register HEIF/HEIC support for PIL
register_heif_opener()

logger = logging.getLogger(__name__)


class QualityAssessment:
    """Assess image quality for optimal processing pipeline routing."""
    
    def __init__(self):
        self.min_resolution = (150, 200)  # Minimum card dimensions (lowered for mobile photos)
        self.optimal_resolution = (400, 600)  # More realistic optimal card dimensions
        
    def assess_image_quality(self, image_bytes: bytes) -> Dict:
        """
        Comprehensive image quality assessment.
        
        Returns quality score (0-100) and detailed metrics.
        """
        try:
            # First try to load with PIL (handles more formats including HEIC)
            pil_img = Image.open(io.BytesIO(image_bytes))
            
            # Convert PIL image to OpenCV format
            # Convert to RGB if not already (handles RGBA, etc.)
            if pil_img.mode != 'RGB':
                pil_img = pil_img.convert('RGB')
            
            # Convert PIL to OpenCV
            img_array = np.array(pil_img)
            img = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            
            if img is None or img.size == 0:
                return self._create_quality_result(0, "Cannot decode image")
                
        except Exception as decode_error:
            # Fallback to direct OpenCV decoding for standard formats
            try:
                nparr = np.frombuffer(image_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if img is None:
                    return self._create_quality_result(0, f"Cannot decode image: {str(decode_error)}")
                
                # Create PIL image from OpenCV for consistency
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(img_rgb)
                
            except Exception as e:
                return self._create_quality_result(0, f"Image decode failed: {str(e)}")
        
        try:
            # Run all quality checks
            blur_score = self._assess_blur(img)
            resolution_score = self._assess_resolution(pil_img)
            lighting_score = self._assess_lighting(img)
            card_detection_score = self._assess_card_presence(img)
            
            # Debug logging for quality scores
            logger.info(f"🔍 Quality Assessment Breakdown:")
            logger.info(f"   📐 Resolution: {resolution_score:.1f}/100 (size: {pil_img.size})")
            logger.info(f"   🌟 Blur/Sharpness: {blur_score:.1f}/100")
            logger.info(f"   💡 Lighting: {lighting_score:.1f}/100")
            logger.info(f"   🎴 Card Detection: {card_detection_score:.1f}/100")
            
            # Calculate composite score
            composite_score = self._calculate_composite_score({
                'blur': blur_score,
                'resolution': resolution_score, 
                'lighting': lighting_score,
                'card_detection': card_detection_score
            })
            
            logger.info(f"   🏆 Composite Score: {composite_score:.1f}/100")
            
            # Generate feedback
            feedback = self._generate_feedback({
                'blur': blur_score,
                'resolution': resolution_score,
                'lighting': lighting_score, 
                'card_detection': card_detection_score,
                'composite': composite_score
            })
            
            return self._create_quality_result(
                composite_score,
                "Assessment complete",
                {
                    'blur_score': blur_score,
                    'resolution_score': resolution_score,
                    'lighting_score': lighting_score,
                    'card_detection_score': card_detection_score,
                    'image_size': pil_img.size,
                    'feedback': feedback
                }
            )
            
        except Exception as e:
            logger.error(f"Quality assessment failed: {e}")
            return self._create_quality_result(0, f"Assessment failed: {str(e)}")
    
    def _assess_blur(self, img: np.ndarray) -> float:
        """Assess image blur using Laplacian variance method."""
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            variance = laplacian.var()
            
            # Scale variance to 0-100 score
            # Sharp images typically have variance > 300 (adjusted from 500)
            # Blurry images have variance < 100
            if variance > 300:
                score = 100.0
            elif variance > 150:
                score = 85.0 + (variance - 150) * 15.0 / 150.0
            elif variance > 50:
                score = 50.0 + (variance - 50) * 35.0 / 100.0
            else:
                score = variance * 50.0 / 50.0
            
            logger.debug(f"      Blur analysis: Laplacian variance = {variance:.1f}, Score = {score:.1f}")
            return score
                
        except Exception as e:
            logger.warning(f"Blur assessment failed: {e}")
            return 50.0  # Default middle score
    
    def _assess_resolution(self, img: Image.Image) -> float:
        """Assess image resolution adequacy."""
        width, height = img.size
        
        # Check minimum requirements
        if width < self.min_resolution[0] or height < self.min_resolution[1]:
            return 0.0
        
        # Score based on how close to optimal resolution
        optimal_pixels = self.optimal_resolution[0] * self.optimal_resolution[1]
        current_pixels = width * height
        
        if current_pixels >= optimal_pixels:
            return 100.0
        else:
            # Linear scaling from minimum to optimal
            min_pixels = self.min_resolution[0] * self.min_resolution[1]
            ratio = (current_pixels - min_pixels) / (optimal_pixels - min_pixels)
            return max(0.0, min(100.0, ratio * 100.0))
    
    def _assess_lighting(self, img: np.ndarray) -> float:
        """Assess lighting conditions (over/under exposure)."""
        try:
            # Convert to HSV for better lighting analysis
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            v_channel = hsv[:, :, 2]  # Value channel
            
            # Calculate histogram
            hist = cv2.calcHist([v_channel], [0], None, [256], [0, 256])
            hist_norm = hist.flatten() / hist.sum()
            
            # Check for over/under exposure (more lenient thresholds)
            underexposed = hist_norm[:40].sum()  # Very dark pixels
            overexposed = hist_norm[220:].sum()   # Very bright pixels
            mid_range = hist_norm[40:220].sum()   # Good lighting range
            
            # Debug logging
            logger.debug(f"      Lighting analysis: underexposed={underexposed:.3f}, overexposed={overexposed:.3f}, mid_range={mid_range:.3f}")
            
            # More forgiving lighting assessment
            if underexposed > 0.6:  # Severely underexposed
                score = max(30.0, 70.0 - underexposed * 80.0)
            elif overexposed > 0.4:  # Severely overexposed  
                score = max(30.0, 80.0 - overexposed * 100.0)
            else:
                # Good lighting - base score of 70, bonus for good mid-range distribution
                score = 70.0 + min(30.0, mid_range * 35.0)
            
            logger.debug(f"      Lighting score: {score:.1f}")
            return score
                
        except Exception as e:
            logger.warning(f"Lighting assessment failed: {e}")
            return 70.0  # Default good score
    
    def _assess_card_presence(self, img: np.ndarray) -> float:
        """Detect if a card-like object is present."""
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Edge detection
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            
            # Find contours
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                return 30.0
            
            # Look for rectangular shapes
            img_area = img.shape[0] * img.shape[1]
            best_score = 0.0
            
            for contour in contours:
                # Approximate contour to polygon
                epsilon = 0.02 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                
                # Check if it's roughly rectangular (4 corners)
                if len(approx) >= 4:
                    area = cv2.contourArea(contour)
                    area_ratio = area / img_area
                    
                    # Cards should occupy reasonable portion of image (more forgiving)
                    if 0.05 < area_ratio < 0.9:
                        # Calculate aspect ratio
                        rect = cv2.minAreaRect(contour)
                        width, height = rect[1]
                        if width > 0 and height > 0:
                            aspect = max(width, height) / min(width, height)
                            # More forgiving aspect ratio for card-like shapes
                            if 1.1 < aspect < 2.2:  # More lenient card-like aspect ratio
                                score = min(100.0, area_ratio * 150.0 + (2.2 - abs(aspect - 1.4)) * 25.0)
                                best_score = max(best_score, score)
            
            logger.debug(f"      Card detection: Found {len(contours)} contours, Best score = {best_score:.1f}")
            return max(30.0, best_score)  # Minimum score for any detected shapes
            
        except Exception as e:
            logger.warning(f"Card detection failed: {e}")
            return 60.0  # Default reasonable score
    
    def _calculate_composite_score(self, scores: Dict[str, float]) -> float:
        """Calculate weighted composite quality score."""
        weights = {
            'blur': 0.4,           # Most important for OCR/AI
            'resolution': 0.15,     # Less important - mobile photos are often smaller
            'lighting': 0.25,       # Important for visibility
            'card_detection': 0.2   # Important but can be compensated
        }
        
        composite = sum(scores[key] * weights[key] for key in weights)
        return min(100.0, max(0.0, composite))
    
    def _generate_feedback(self, scores: Dict[str, float]) -> Dict:
        """Generate actionable feedback based on quality scores."""
        feedback = {
            'overall': self._get_overall_rating(scores['composite']),
            'issues': [],
            'suggestions': []
        }
        
        # Specific feedback based on individual scores
        if scores['blur'] < 60:
            feedback['issues'].append('Image appears blurry')
            feedback['suggestions'].append('Hold camera steady and ensure good focus')
        
        if scores['resolution'] < 50:
            feedback['issues'].append('Image resolution is too low')
            feedback['suggestions'].append('Move closer to the card or use higher resolution')
        
        if scores['lighting'] < 50:
            feedback['issues'].append('Poor lighting conditions')
            feedback['suggestions'].append('Improve lighting or avoid shadows/glare')
        
        if scores['card_detection'] < 40:
            feedback['issues'].append('Card not clearly visible')
            feedback['suggestions'].append('Center the card in frame and ensure clear edges')
        
        # Positive feedback for good scores
        if scores['composite'] > 80:
            feedback['suggestions'].append('Excellent image quality - processing will be fast')
        elif scores['composite'] > 60:
            feedback['suggestions'].append('Good image quality detected')
        
        return feedback
    
    def _get_overall_rating(self, score: float) -> str:
        """Convert numeric score to rating."""
        if score >= 80:
            return 'excellent'
        elif score >= 60:
            return 'good'
        elif score >= 40:
            return 'fair'
        else:
            return 'poor'
    
    def _create_quality_result(self, score: float, message: str, details: Dict = None) -> Dict:
        """Create standardized quality assessment result."""
        return {
            'quality_score': score,
            'message': message,
            'details': details or {}
        }
    
    def get_processing_tier(self, quality_score: float) -> str:
        """Determine processing tier based on quality score."""
        # OVERRIDE: Always use enhanced prompt for comprehensive card analysis
        # This ensures Prime cards, HGSS era cards, and complex cards are properly detected
        original_tier = 'fast' if quality_score >= 80 else ('standard' if quality_score >= 50 else 'enhanced')
        logger.info(f"🚀 Forcing enhanced prompt (was: {original_tier}, quality: {quality_score:.1f}) for comprehensive analysis")
        return 'enhanced'