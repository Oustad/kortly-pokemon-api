"""Image processing utilities for accuracy testing."""

import base64
import io
from pathlib import Path
from typing import Optional

from PIL import Image
from pillow_heif import register_heif_opener

# Register HEIF/HEIC support for PIL
register_heif_opener()


class ImageProcessor:
    """Process images for testing purposes."""
    
    @staticmethod
    def image_to_base64(image_path: Path) -> Optional[str]:
        """
        Convert an image file to base64 string.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Base64 encoded string or None if failed
        """
        try:
            # Open image with PIL (supports HEIC via pillow-heif)
            with Image.open(image_path) as img:
                # Convert to RGB if needed
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Convert to JPEG for consistency
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=85)
                buffer.seek(0)
                
                # Encode to base64
                return base64.b64encode(buffer.getvalue()).decode('utf-8')
                
        except Exception as e:
            print(f"Error processing {image_path}: {e}")
            return None
    
    @staticmethod
    def get_image_info(image_path: Path) -> dict:
        """
        Get basic information about an image.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dictionary with image information
        """
        try:
            with Image.open(image_path) as img:
                return {
                    "filename": image_path.name,
                    "format": img.format,
                    "mode": img.mode,
                    "size": img.size,
                    "file_size": image_path.stat().st_size,
                }
        except Exception as e:
            return {
                "filename": image_path.name,
                "error": str(e),
                "file_size": image_path.stat().st_size if image_path.exists() else 0,
            }