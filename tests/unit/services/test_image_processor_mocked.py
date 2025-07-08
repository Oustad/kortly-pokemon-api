"""Properly mocked tests for image_processor.py to achieve higher coverage."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

# Create a simplified test that focuses on mocking properly
class TestImageProcessorMocked:
    """Test ImageProcessor with proper mocking."""

    def test_initialization_default_config(self):
        """Test processor initialization with default config."""
        with patch('src.scanner.services.image_processor.config') as mock_config:
            mock_config.image_max_dimension = 1024
            mock_config.image_jpeg_quality = 85
            mock_config.image_max_file_size_mb = 10
            
            from src.scanner.services.image_processor import ImageProcessor
            processor = ImageProcessor()
            
            assert processor.max_dimension == 1024
            assert processor.jpeg_quality == 85
            assert processor.max_file_size_mb == 10

    def test_initialization_custom_params(self):
        """Test processor initialization with custom parameters."""
        with patch('src.scanner.services.image_processor.config') as mock_config:
            mock_config.image_max_dimension = 1024
            mock_config.image_jpeg_quality = 85
            mock_config.image_max_file_size_mb = 10
            
            from src.scanner.services.image_processor import ImageProcessor
            processor = ImageProcessor(
                max_dimension=800,
                jpeg_quality=90,
                max_file_size_mb=5
            )
            
            assert processor.max_dimension == 800
            assert processor.jpeg_quality == 90
            assert processor.max_file_size_mb == 5

    def test_process_image_basic_jpeg(self):
        """Test basic image processing with JPEG."""
        with patch('src.scanner.services.image_processor.config') as mock_config:
            mock_config.image_max_dimension = 1024
            mock_config.image_jpeg_quality = 85
            mock_config.image_max_file_size_mb = 10
            
            from src.scanner.services.image_processor import ImageProcessor
            
            # Mock PIL Image
            mock_image = Mock()
            mock_image.format = "JPEG"
            mock_image.width = 500
            mock_image.height = 400
            mock_image.size = (500, 400)
            mock_image.mode = "RGB"
            mock_image.save = Mock()
            
            # Mock BytesIO
            mock_bytes_io = Mock()
            mock_bytes_io.getvalue.return_value = b"processed_jpeg_data"
            
            with patch('src.scanner.services.image_processor.Image.open', return_value=mock_image):
                with patch('src.scanner.services.image_processor.BytesIO', return_value=mock_bytes_io):
                    processor = ImageProcessor(max_dimension=1024)
                    
                    # Mock correct_orientation to return unchanged image
                    processor._correct_orientation = Mock(return_value=(mock_image, False))
                    
                    result_data, info = processor.process_image(b"test_image_data", "test.jpg")
                    
                    assert result_data == b"processed_jpeg_data"
                    assert info["original_format"] == "JPEG"
                    assert info["dimensions"] == "500x400"
                    assert info["resized"] is False
                    assert info["orientation_corrected"] is False

    def test_correct_orientation_no_exif(self):
        """Test orientation correction with no EXIF data."""
        with patch('src.scanner.services.image_processor.config') as mock_config:
            mock_config.image_max_dimension = 1024
            mock_config.image_jpeg_quality = 85
            mock_config.image_max_file_size_mb = 10
            
            from src.scanner.services.image_processor import ImageProcessor
            
            # Mock PIL Image
            mock_image = Mock()
            mock_image.getexif.return_value = {}
            
            processor = ImageProcessor()
            
            result_image, was_rotated = processor._correct_orientation(mock_image)
            
            assert result_image is mock_image
            assert was_rotated is False

    def test_correct_orientation_with_rotation(self):
        """Test orientation correction with rotation needed."""
        with patch('src.scanner.services.image_processor.config') as mock_config:
            mock_config.image_max_dimension = 1024
            mock_config.image_jpeg_quality = 85
            mock_config.image_max_file_size_mb = 10
            
            from src.scanner.services.image_processor import ImageProcessor
            
            # Mock PIL Image
            mock_image = Mock()
            mock_image.getexif.return_value = {0x0112: 6}  # 270 degree rotation
            
            # Mock rotated image
            mock_rotated_image = Mock()
            mock_image.rotate.return_value = mock_rotated_image
            
            processor = ImageProcessor()
            
            result_image, was_rotated = processor._correct_orientation(mock_image)
            
            assert result_image is mock_rotated_image
            assert was_rotated is True
            mock_image.rotate.assert_called_once_with(270, expand=True)

    def test_correct_orientation_with_180_rotation(self):
        """Test orientation correction with 180 degree rotation."""
        with patch('src.scanner.services.image_processor.config') as mock_config:
            mock_config.image_max_dimension = 1024
            mock_config.image_jpeg_quality = 85
            mock_config.image_max_file_size_mb = 10
            
            from src.scanner.services.image_processor import ImageProcessor
            
            # Mock PIL Image
            mock_image = Mock()
            mock_image.getexif.return_value = {0x0112: 3}  # 180 degree rotation
            
            # Mock rotated image
            mock_rotated_image = Mock()
            mock_image.rotate.return_value = mock_rotated_image
            
            processor = ImageProcessor()
            
            result_image, was_rotated = processor._correct_orientation(mock_image)
            
            assert result_image is mock_rotated_image
            assert was_rotated is True
            mock_image.rotate.assert_called_once_with(180, expand=True)

    def test_correct_orientation_with_90_rotation(self):
        """Test orientation correction with 90 degree rotation."""
        with patch('src.scanner.services.image_processor.config') as mock_config:
            mock_config.image_max_dimension = 1024
            mock_config.image_jpeg_quality = 85
            mock_config.image_max_file_size_mb = 10
            
            from src.scanner.services.image_processor import ImageProcessor
            
            # Mock PIL Image
            mock_image = Mock()
            mock_image.getexif.return_value = {0x0112: 8}  # 90 degree rotation
            
            # Mock rotated image
            mock_rotated_image = Mock()
            mock_image.rotate.return_value = mock_rotated_image
            
            processor = ImageProcessor()
            
            result_image, was_rotated = processor._correct_orientation(mock_image)
            
            assert result_image is mock_rotated_image
            assert was_rotated is True
            mock_image.rotate.assert_called_once_with(90, expand=True)

    def test_correct_orientation_no_rotation_needed(self):
        """Test orientation correction with no rotation needed."""
        with patch('src.scanner.services.image_processor.config') as mock_config:
            mock_config.image_max_dimension = 1024
            mock_config.image_jpeg_quality = 85
            mock_config.image_max_file_size_mb = 10
            
            from src.scanner.services.image_processor import ImageProcessor
            
            # Mock PIL Image
            mock_image = Mock()
            mock_image.getexif.return_value = {0x0112: 1}  # Normal orientation
            
            processor = ImageProcessor()
            
            result_image, was_rotated = processor._correct_orientation(mock_image)
            
            assert result_image is mock_image
            assert was_rotated is False

    def test_correct_orientation_error_handling(self):
        """Test orientation correction error handling."""
        with patch('src.scanner.services.image_processor.config') as mock_config:
            mock_config.image_max_dimension = 1024
            mock_config.image_jpeg_quality = 85
            mock_config.image_max_file_size_mb = 10
            
            from src.scanner.services.image_processor import ImageProcessor
            
            # Mock PIL Image
            mock_image = Mock()
            mock_image.getexif.side_effect = Exception("EXIF error")
            
            processor = ImageProcessor()
            
            result_image, was_rotated = processor._correct_orientation(mock_image)
            
            assert result_image is mock_image
            assert was_rotated is False

    def test_resize_image_width_larger(self):
        """Test image resizing when width is larger."""
        with patch('src.scanner.services.image_processor.config') as mock_config:
            mock_config.image_max_dimension = 1024
            mock_config.image_jpeg_quality = 85
            mock_config.image_max_file_size_mb = 10
            
            from src.scanner.services.image_processor import ImageProcessor
            
            # Mock PIL Image
            mock_image = Mock()
            mock_image.size = (1200, 800)
            
            # Mock resized image
            mock_resized_image = Mock()
            mock_image.resize.return_value = mock_resized_image
            
            processor = ImageProcessor()
            
            result = processor._resize_image(mock_image, 1000)
            
            assert result is mock_resized_image
            # Width should be 1000, height should be proportional: 800 * (1000/1200) = 667
            mock_image.resize.assert_called_once()
            call_args = mock_image.resize.call_args[0]
            assert call_args[0] == (1000, 666)

    def test_resize_image_height_larger(self):
        """Test image resizing when height is larger."""
        with patch('src.scanner.services.image_processor.config') as mock_config:
            mock_config.image_max_dimension = 1024
            mock_config.image_jpeg_quality = 85
            mock_config.image_max_file_size_mb = 10
            
            from src.scanner.services.image_processor import ImageProcessor
            
            # Mock PIL Image
            mock_image = Mock()
            mock_image.size = (800, 1200)
            
            # Mock resized image
            mock_resized_image = Mock()
            mock_image.resize.return_value = mock_resized_image
            
            processor = ImageProcessor()
            
            result = processor._resize_image(mock_image, 1000)
            
            assert result is mock_resized_image
            # Height should be 1000, width should be proportional: 800 * (1000/1200) = 667
            mock_image.resize.assert_called_once()
            call_args = mock_image.resize.call_args[0]
            assert call_args[0] == (666, 1000)

    def test_validate_image_file_size_exceeded(self):
        """Test image validation with file size exceeded."""
        with patch('src.scanner.services.image_processor.config') as mock_config:
            mock_config.image_max_dimension = 1024
            mock_config.image_jpeg_quality = 85
            mock_config.image_max_file_size_mb = 10
            
            from src.scanner.services.image_processor import ImageProcessor
            
            processor = ImageProcessor(max_file_size_mb=1)
            
            # Create 2MB of data
            large_data = b"x" * (2 * 1024 * 1024)
            
            is_valid, error_msg = processor.validate_image(large_data)
            
            assert is_valid is False
            assert "exceeds maximum" in error_msg

    def test_validate_image_dimensions_too_small(self):
        """Test image validation with dimensions too small."""
        with patch('src.scanner.services.image_processor.config') as mock_config:
            mock_config.image_max_dimension = 1024
            mock_config.image_jpeg_quality = 85
            mock_config.image_max_file_size_mb = 10
            mock_config.image_min_dimension = 100
            
            from src.scanner.services.image_processor import ImageProcessor
            
            # Mock PIL Image
            mock_image = Mock()
            mock_image.width = 50
            mock_image.height = 50
            
            with patch('src.scanner.services.image_processor.Image.open', return_value=mock_image):
                processor = ImageProcessor()
                
                is_valid, error_msg = processor.validate_image(b"small_image_data")
                
                assert is_valid is False
                assert "too small" in error_msg

    def test_validate_image_heic_not_supported(self):
        """Test image validation with HEIC format not supported."""
        with patch('src.scanner.services.image_processor.config') as mock_config:
            mock_config.image_max_dimension = 1024
            mock_config.image_jpeg_quality = 85
            mock_config.image_max_file_size_mb = 10
            mock_config.image_min_dimension = 100
            
            from src.scanner.services.image_processor import ImageProcessor
            
            # Mock PIL Image
            mock_image = Mock()
            mock_image.format = "HEIF"
            mock_image.width = 500
            mock_image.height = 400
            
            with patch('src.scanner.services.image_processor.Image.open', return_value=mock_image):
                with patch('src.scanner.services.image_processor.HEIC_SUPPORTED', False):
                    processor = ImageProcessor()
                    
                    is_valid, error_msg = processor.validate_image(b"heic_image_data")
                    
                    assert is_valid is False
                    assert "HEIC/HEIF format not supported" in error_msg

    def test_validate_image_valid(self):
        """Test image validation with valid image."""
        with patch('src.scanner.services.image_processor.config') as mock_config:
            mock_config.image_max_dimension = 1024
            mock_config.image_jpeg_quality = 85
            mock_config.image_max_file_size_mb = 10
            mock_config.image_min_dimension = 100
            
            from src.scanner.services.image_processor import ImageProcessor
            
            # Mock PIL Image
            mock_image = Mock()
            mock_image.format = "JPEG"
            mock_image.width = 500
            mock_image.height = 400
            
            with patch('src.scanner.services.image_processor.Image.open', return_value=mock_image):
                processor = ImageProcessor()
                
                is_valid, error_msg = processor.validate_image(b"valid_image_data")
                
                assert is_valid is True
                assert error_msg is None

    def test_validate_image_invalid_format(self):
        """Test image validation with invalid format."""
        with patch('src.scanner.services.image_processor.config') as mock_config:
            mock_config.image_max_dimension = 1024
            mock_config.image_jpeg_quality = 85
            mock_config.image_max_file_size_mb = 10
            mock_config.image_min_dimension = 100
            
            from src.scanner.services.image_processor import ImageProcessor
            
            with patch('src.scanner.services.image_processor.Image.open', side_effect=Exception("Invalid image format")):
                processor = ImageProcessor()
                
                is_valid, error_msg = processor.validate_image(b"invalid_image_data")
                
                assert is_valid is False
                assert "Invalid image file" in error_msg

    def test_get_supported_formats_with_heic(self):
        """Test getting supported formats with HEIC support."""
        with patch('src.scanner.services.image_processor.config') as mock_config:
            mock_config.image_max_dimension = 1024
            mock_config.image_jpeg_quality = 85
            mock_config.image_max_file_size_mb = 10
            
            from src.scanner.services.image_processor import ImageProcessor
            
            with patch('src.scanner.services.image_processor.HEIC_SUPPORTED', True):
                processor = ImageProcessor()
                
                formats = processor.get_supported_formats()
                
                assert formats["JPEG"] is True
                assert formats["PNG"] is True
                assert formats["HEIC/HEIF"] is True
                assert formats["WebP"] is True

    def test_get_supported_formats_without_heic(self):
        """Test getting supported formats without HEIC support."""
        with patch('src.scanner.services.image_processor.config') as mock_config:
            mock_config.image_max_dimension = 1024
            mock_config.image_jpeg_quality = 85
            mock_config.image_max_file_size_mb = 10
            
            from src.scanner.services.image_processor import ImageProcessor
            
            with patch('src.scanner.services.image_processor.HEIC_SUPPORTED', False):
                processor = ImageProcessor()
                
                formats = processor.get_supported_formats()
                
                assert formats["JPEG"] is True
                assert formats["PNG"] is True
                assert formats["HEIC/HEIF"] is False
                assert formats["WebP"] is True

    def test_process_image_error_handling(self):
        """Test image processing error handling."""
        with patch('src.scanner.services.image_processor.config') as mock_config:
            mock_config.image_max_dimension = 1024
            mock_config.image_jpeg_quality = 85
            mock_config.image_max_file_size_mb = 10
            
            from src.scanner.services.image_processor import ImageProcessor
            
            with patch('src.scanner.services.image_processor.Image.open', side_effect=Exception("Invalid image format")):
                processor = ImageProcessor()
                
                with pytest.raises(ValueError, match="Failed to process image"):
                    processor.process_image(b"invalid_image_data", "test.jpg")

    def test_process_image_with_resize(self):
        """Test image processing with resizing."""
        with patch('src.scanner.services.image_processor.config') as mock_config:
            mock_config.image_max_dimension = 1024
            mock_config.image_jpeg_quality = 85
            mock_config.image_max_file_size_mb = 10
            
            from src.scanner.services.image_processor import ImageProcessor
            
            # Mock PIL Image
            mock_image = Mock()
            mock_image.format = "PNG"
            mock_image.width = 2000
            mock_image.height = 1500
            mock_image.size = (2000, 1500)
            mock_image.mode = "RGB"
            mock_image.save = Mock()
            
            # Mock resized image
            mock_resized_image = Mock()
            mock_resized_image.width = 1024
            mock_resized_image.height = 768
            mock_resized_image.save = Mock()
            
            # Mock BytesIO
            mock_bytes_io = Mock()
            mock_bytes_io.getvalue.return_value = b"processed_jpeg_data"
            
            with patch('src.scanner.services.image_processor.Image.open', return_value=mock_image):
                with patch('src.scanner.services.image_processor.BytesIO', return_value=mock_bytes_io):
                    processor = ImageProcessor(max_dimension=1024)
                    
                    # Mock methods
                    processor._correct_orientation = Mock(return_value=(mock_image, False))
                    processor._resize_image = Mock(return_value=mock_resized_image)
                    
                    result_data, info = processor.process_image(b"test_image_data", "test.png")
                    
                    assert result_data == b"processed_jpeg_data"
                    assert info["original_format"] == "PNG"
                    assert info["dimensions"] == "2000x1500 -> 1024x768"
                    assert info["resized"] is True
                    
                    # Verify resize was called
                    processor._resize_image.assert_called_once_with(mock_image, 1024)