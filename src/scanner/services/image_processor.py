"""
Simplified image processor for Pokemon card scanning.
Focuses on essential format conversion and optimization.
"""

import logging
import os
from io import BytesIO
from typing import Dict, Optional, Tuple

from PIL import Image

from ..config import get_config

logger = logging.getLogger(__name__)
config = get_config()

# Try to import HEIC support
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIC_SUPPORTED = True
except ImportError:
    HEIC_SUPPORTED = False
    logger.warning("HEIC support not available. Install pillow-heif for iPhone photo support.")


class ImageProcessor:
    """
    Simple image processor for Pokemon card images.
    
    Features:
    - Common format support (JPEG, PNG, HEIC)
    - Image resizing for API optimization
    - EXIF orientation correction
    - Basic validation
    """
    
    def __init__(
        self,
        max_dimension: Optional[int] = None,
        jpeg_quality: Optional[int] = None,
        max_file_size_mb: Optional[int] = None,
    ):
        """
        Initialize the image processor.
        
        Args:
            max_dimension: Maximum width/height for processed images (uses config if not provided)
            jpeg_quality: JPEG compression quality (1-100) (uses config if not provided)
            max_file_size_mb: Maximum file size in megabytes (uses config if not provided)
        """
        self.max_dimension = max_dimension or config.image_max_dimension
        self.jpeg_quality = jpeg_quality or config.image_jpeg_quality
        self.max_file_size_mb = max_file_size_mb or config.image_max_file_size_mb
    
    def process_image(
        self,
        image_data: bytes,
        filename: str = "",
    ) -> Tuple[bytes, Dict[str, any]]:
        """
        Process an image for Pokemon card scanning.
        
        Args:
            image_data: Raw image bytes
            filename: Optional filename for format detection
            
        Returns:
            Tuple of (processed_jpeg_bytes, processing_info)
        """
        logger.info(f"Processing image: {filename or 'unnamed'} ({len(image_data)} bytes)")
        
        # Initialize processing info
        info = {
            "original_size": len(image_data),
            "filename": filename,
            "original_format": None,
            "processed_size": None,
            "dimensions": None,
            "resized": False,
            "orientation_corrected": False,
        }
        
        try:
            # Open image
            image = Image.open(BytesIO(image_data))
            info["original_format"] = image.format
            info["dimensions"] = f"{image.width}x{image.height}"
            
            # Handle EXIF orientation
            image, was_rotated = self._correct_orientation(image)
            info["orientation_corrected"] = was_rotated
            
            # Convert to RGB if necessary
            if image.mode not in ("RGB", "L"):
                if image.mode == "RGBA":
                    # Create white background for transparent images
                    background = Image.new("RGB", image.size, (255, 255, 255))
                    background.paste(image, mask=image.split()[3])
                    image = background
                else:
                    image = image.convert("RGB")
            
            # Resize if needed
            original_size = image.size
            if max(image.size) > self.max_dimension:
                image = self._resize_image(image, self.max_dimension)
                info["resized"] = True
                info["dimensions"] = f"{original_size[0]}x{original_size[1]} -> {image.width}x{image.height}"
            
            # Convert to JPEG
            output_buffer = BytesIO()
            image.save(
                output_buffer,
                format="JPEG",
                quality=self.jpeg_quality,
                optimize=True,
            )
            processed_data = output_buffer.getvalue()
            
            # Update info
            info["processed_size"] = len(processed_data)
            info["size_reduction"] = 1 - (len(processed_data) / len(image_data))
            
            logger.info(
                f"Image processed: {info['original_format']} -> JPEG, "
                f"{info['original_size']} -> {info['processed_size']} bytes "
                f"({info['size_reduction']:.1%} reduction)"
            )
            
            return processed_data, info
            
        except Exception as e:
            logger.error(f"Failed to process image {filename}: {str(e)}")
            raise ValueError(f"Failed to process image: {str(e)}")
    
    def _correct_orientation(self, image: Image.Image) -> Tuple[Image.Image, bool]:
        """
        Correct image orientation based on EXIF data.
        
        Args:
            image: PIL Image object
            
        Returns:
            Tuple of (corrected_image, was_rotated)
        """
        try:
            # Get EXIF orientation tag
            exif = image.getexif()
            orientation = exif.get(0x0112)  # Orientation tag
            
            if orientation:
                # Apply rotation based on orientation value
                rotations = {
                    3: 180,
                    6: 270,
                    8: 90,
                }
                
                if orientation in rotations:
                    image = image.rotate(rotations[orientation], expand=True)
                    return image, True
                    
        except Exception as e:
            logger.debug(f"Could not process EXIF orientation: {e}")
        
        return image, False
    
    def _resize_image(self, image: Image.Image, max_dimension: int) -> Image.Image:
        """
        Resize image to fit within max_dimension while maintaining aspect ratio.
        
        Args:
            image: PIL Image object
            max_dimension: Maximum width or height
            
        Returns:
            Resized image
        """
        # Calculate new dimensions
        width, height = image.size
        if width > height:
            new_width = max_dimension
            new_height = int(height * (max_dimension / width))
        else:
            new_height = max_dimension
            new_width = int(width * (max_dimension / height))
        
        # Resize with high-quality resampling
        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    def validate_image(self, image_data: bytes) -> Tuple[bool, Optional[str]]:
        """
        Validate that image data meets requirements.
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check file size
        size_mb = len(image_data) / (1024 * 1024)
        if size_mb > self.max_file_size_mb:
            return False, f"Image size {size_mb:.1f}MB exceeds maximum {self.max_file_size_mb}MB"
        
        try:
            # Try to open image
            image = Image.open(BytesIO(image_data))
            
            # Check minimum dimensions
            min_dim = config.image_min_dimension
            if image.width < min_dim or image.height < min_dim:
                return False, f"Image dimensions {image.width}x{image.height} are too small (minimum {min_dim}x{min_dim})"
            
            # Check format
            if not HEIC_SUPPORTED and image.format == "HEIF":
                return False, "HEIC/HEIF format not supported. Please install pillow-heif."
            
            return True, None
            
        except Exception as e:
            return False, f"Invalid image file: {str(e)}"
    
    def get_supported_formats(self) -> Dict[str, bool]:
        """Get information about supported image formats."""
        return {
            "JPEG": True,
            "PNG": True,
            "GIF": True,
            "BMP": True,
            "TIFF": True,
            "HEIC/HEIF": HEIC_SUPPORTED,
            "WebP": True,  # Pillow has built-in WebP support
        }