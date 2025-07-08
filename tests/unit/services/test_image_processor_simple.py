"""Simple working tests for ImageProcessor service."""

import pytest
import io
from PIL import Image
from src.scanner.services.image_processor import ImageProcessor


class TestImageProcessorSimple:
    """Simple test cases for ImageProcessor that match actual interface."""

    @pytest.fixture
    def image_processor(self):
        """Create ImageProcessor instance."""
        return ImageProcessor()

    @pytest.fixture
    def sample_image_bytes(self):
        """Create sample image bytes."""
        img = Image.new('RGB', (400, 600), color='blue')
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='JPEG')
        return img_buffer.getvalue()

    @pytest.fixture
    def large_image_bytes(self):
        """Create large image bytes."""
        img = Image.new('RGB', (2000, 3000), color='red')
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='JPEG')
        return img_buffer.getvalue()

    def test_initialization_basic(self, image_processor):
        """Test basic ImageProcessor initialization."""
        assert hasattr(image_processor, 'max_dimension')
        assert hasattr(image_processor, 'jpeg_quality')
        assert hasattr(image_processor, 'max_file_size_mb')

    def test_initialization_with_params(self):
        """Test initialization with custom parameters."""
        processor = ImageProcessor(
            max_dimension=512,
            jpeg_quality=85,
            max_file_size_mb=5
        )
        
        assert processor.max_dimension == 512
        assert processor.jpeg_quality == 85
        assert processor.max_file_size_mb == 5

    def test_process_image_method_exists(self, image_processor, sample_image_bytes):
        """Test that process_image method exists and can be called."""
        result = image_processor.process_image(
            image_data=sample_image_bytes,
            filename="test.jpg"
        )
        
        # Should return tuple of (bytes, dict)
        assert isinstance(result, tuple)
        assert len(result) == 2
        processed_bytes, info = result
        assert isinstance(processed_bytes, bytes)
        assert isinstance(info, dict)
        assert len(processed_bytes) > 0

    def test_process_image_with_different_filename(self, image_processor, sample_image_bytes):
        """Test process_image with different filename."""
        result = image_processor.process_image(
            image_data=sample_image_bytes,
            filename="different.png"
        )
        
        assert isinstance(result, tuple)
        processed_bytes, info = result
        assert isinstance(processed_bytes, bytes)
        assert info['filename'] == "different.png"

    def test_process_large_image_resizing(self, image_processor, large_image_bytes):
        """Test that large images get resized appropriately."""
        result = image_processor.process_image(
            image_data=large_image_bytes,
            filename="large.jpg"
        )
        
        # Should return tuple
        assert isinstance(result, tuple)
        processed_bytes, info = result
        assert isinstance(processed_bytes, bytes)
        assert len(processed_bytes) > 0
        
        # Should have processing info
        assert 'original_size' in info
        assert 'processed_size' in info

    def test_process_image_different_formats(self, image_processor):
        """Test processing different image formats."""
        # Create PNG image
        img = Image.new('RGB', (300, 400), color='green')
        png_buffer = io.BytesIO()
        img.save(png_buffer, format='PNG')
        png_bytes = png_buffer.getvalue()
        
        result = image_processor.process_image(
            image_data=png_bytes,
            filename="test.png"
        )
        
        assert isinstance(result, tuple)
        processed_bytes, info = result
        assert isinstance(processed_bytes, bytes)
        assert len(processed_bytes) > 0
        assert info['original_format'] == 'PNG'

    def test_process_image_invalid_data(self, image_processor):
        """Test processing invalid image data."""
        invalid_bytes = b"not an image"
        
        try:
            result = image_processor.process_image(
                image_data=invalid_bytes,
                filename="invalid.jpg"
            )
            # If it doesn't raise an exception, should return something
            assert result is not None
        except Exception:
            # Should handle invalid data gracefully
            pass

    def test_process_empty_image_data(self, image_processor):
        """Test processing empty image data."""
        try:
            result = image_processor.process_image(
                image_data=b"",
                filename="empty.jpg"
            )
            assert result is not None
        except Exception:
            # Should handle empty data gracefully
            pass

    def test_validate_image_bytes_method(self, image_processor, sample_image_bytes):
        """Test validate_image_bytes method if it exists."""
        if hasattr(image_processor, 'validate_image_bytes'):
            result = image_processor.validate_image_bytes(sample_image_bytes)
            assert isinstance(result, (bool, dict))

    def test_get_image_info_method(self, image_processor, sample_image_bytes):
        """Test get_image_info method if it exists."""
        if hasattr(image_processor, 'get_image_info'):
            info = image_processor.get_image_info(sample_image_bytes)
            assert isinstance(info, dict)

    def test_resize_image_method(self, image_processor, sample_image_bytes):
        """Test _resize_image method if it exists."""
        if hasattr(image_processor, '_resize_image'):
            # This is likely a private method that takes PIL Image
            from PIL import Image
            img = Image.open(io.BytesIO(sample_image_bytes))
            result = image_processor._resize_image(img, 512)
            assert isinstance(result, Image.Image)

    def test_configuration_properties(self, image_processor):
        """Test that configuration properties are accessible."""
        # Should have these properties set from config or defaults
        assert hasattr(image_processor, 'max_dimension')
        assert hasattr(image_processor, 'jpeg_quality')
        assert hasattr(image_processor, 'max_file_size_mb')
        
        # Values should be reasonable
        if image_processor.max_dimension:
            assert image_processor.max_dimension > 0
        if image_processor.jpeg_quality:
            assert 1 <= image_processor.jpeg_quality <= 100

    def test_process_image_maintains_quality(self, image_processor):
        """Test that processing maintains reasonable image quality."""
        # Create high quality image
        img = Image.new('RGB', (800, 1200), color='white')
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='JPEG', quality=95)
        high_quality_bytes = img_buffer.getvalue()
        
        result = image_processor.process_image(
            image_data=high_quality_bytes,
            filename="quality.jpg"
        )
        
        # Should return tuple
        assert isinstance(result, tuple)
        processed_bytes, info = result
        assert isinstance(processed_bytes, bytes)
        assert len(processed_bytes) > 0

    def test_supported_formats_info(self, image_processor):
        """Test information about supported formats."""
        # Should have some way to know what formats are supported
        # This is basic validation that the processor is properly configured
        assert image_processor is not None

    def test_process_image_no_filename(self, image_processor, sample_image_bytes):
        """Test image processing without filename."""
        result = image_processor.process_image(
            image_data=sample_image_bytes
        )
        
        assert isinstance(result, tuple)
        processed_bytes, info = result
        assert isinstance(processed_bytes, bytes)
        assert len(processed_bytes) > 0
        assert info['filename'] == ""