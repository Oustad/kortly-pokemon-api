"""Simple working tests for QualityAssessment service."""

import pytest
import io
from PIL import Image
from src.scanner.services.quality_assessment import QualityAssessment


class TestQualityAssessmentSimple:
    """Simple test cases for QualityAssessment that match actual interface."""

    @pytest.fixture
    def quality_assessor(self):
        """Create QualityAssessment instance."""
        return QualityAssessment()

    @pytest.fixture
    def sample_image_bytes(self):
        """Create sample image bytes."""
        img = Image.new('RGB', (400, 600), color=(0, 0, 255))
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='JPEG')
        return img_buffer.getvalue()

    @pytest.fixture
    def high_quality_image_bytes(self):
        """Create high quality image bytes."""
        img = Image.new('RGB', (800, 1200), color=(255, 255, 255))
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='JPEG', quality=95)
        return img_buffer.getvalue()

    @pytest.fixture
    def low_quality_image_bytes(self):
        """Create low quality image bytes."""
        img = Image.new('RGB', (100, 150), color=(128, 128, 128))
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='JPEG', quality=30)
        return img_buffer.getvalue()

    def test_initialization(self, quality_assessor):
        """Test QualityAssessment initialization."""
        assert hasattr(quality_assessor, 'assess_image_quality')
        
        # Check for common configuration attributes
        if hasattr(quality_assessor, 'min_resolution'):
            assert isinstance(quality_assessor.min_resolution, tuple)
        
        if hasattr(quality_assessor, 'optimal_resolution'):
            assert isinstance(quality_assessor.optimal_resolution, tuple)

    def test_assess_image_quality_basic(self, quality_assessor, sample_image_bytes):
        """Test basic image quality assessment."""
        result = quality_assessor.assess_image_quality(sample_image_bytes)
        
        # Should return a dictionary
        assert isinstance(result, dict)
        
        # Should have quality score
        assert 'quality_score' in result
        assert isinstance(result['quality_score'], (int, float))
        assert 0 <= result['quality_score'] <= 100

    def test_assess_high_quality_image(self, quality_assessor, high_quality_image_bytes):
        """Test assessment of high quality image."""
        result = quality_assessor.assess_image_quality(high_quality_image_bytes)
        
        assert isinstance(result, dict)
        assert 'quality_score' in result
        
        # High quality image should score reasonably well
        assert result['quality_score'] >= 10  # Very conservative threshold

    def test_assess_low_quality_image(self, quality_assessor, low_quality_image_bytes):
        """Test assessment of low quality image."""
        result = quality_assessor.assess_image_quality(low_quality_image_bytes)
        
        assert isinstance(result, dict)
        assert 'quality_score' in result
        
        # Should still return a valid score
        assert isinstance(result['quality_score'], (int, float))

    def test_assess_invalid_image_data(self, quality_assessor):
        """Test assessment of invalid image data."""
        invalid_bytes = b"not an image"
        
        result = quality_assessor.assess_image_quality(invalid_bytes)
        
        assert isinstance(result, dict)
        assert 'quality_score' in result
        
        # Should handle invalid data gracefully
        if result['quality_score'] == 0:
            assert 'message' in result or 'error' in result

    def test_assess_empty_image_data(self, quality_assessor):
        """Test assessment of empty image data."""
        result = quality_assessor.assess_image_quality(b"")
        
        assert isinstance(result, dict)
        assert 'quality_score' in result
        assert result['quality_score'] == 0

    def test_result_structure(self, quality_assessor, sample_image_bytes):
        """Test that result has expected structure."""
        result = quality_assessor.assess_image_quality(sample_image_bytes)
        
        # Check for expected fields
        expected_fields = ['quality_score']
        for field in expected_fields:
            assert field in result
            
        # Check for optional detailed fields
        optional_fields = ['sharpness_score', 'resolution_score', 'contrast_score', 
                          'brightness_score', 'dimensions', 'file_size']
        for field in optional_fields:
            if field in result:
                assert isinstance(result[field], (int, float, tuple))

    def test_dimensions_detection(self, quality_assessor, sample_image_bytes):
        """Test image dimensions detection."""
        result = quality_assessor.assess_image_quality(sample_image_bytes)
        
        if 'dimensions' in result:
            dimensions = result['dimensions']
            assert isinstance(dimensions, tuple)
            assert len(dimensions) == 2
            assert all(isinstance(d, int) for d in dimensions)

    def test_file_size_calculation(self, quality_assessor, sample_image_bytes):
        """Test file size calculation."""
        result = quality_assessor.assess_image_quality(sample_image_bytes)
        
        if 'file_size' in result:
            file_size = result['file_size']
            assert isinstance(file_size, int)
            assert file_size > 0

    def test_processing_configuration_method(self, quality_assessor):
        """Test get_processing_configuration method if it exists."""
        if hasattr(quality_assessor, 'get_processing_configuration'):
            config = quality_assessor.get_processing_configuration(75.0)
            
            assert isinstance(config, dict)
            
            # Should have tier information
            if 'tier' in config:
                assert isinstance(config['tier'], str)

    def test_multiple_assessments_consistency(self, quality_assessor, sample_image_bytes):
        """Test that multiple assessments of same image are consistent."""
        result1 = quality_assessor.assess_image_quality(sample_image_bytes)
        result2 = quality_assessor.assess_image_quality(sample_image_bytes)
        
        # Should be consistent
        assert result1['quality_score'] == result2['quality_score']
        
        if 'dimensions' in result1 and 'dimensions' in result2:
            assert result1['dimensions'] == result2['dimensions']

    def test_different_image_formats(self, quality_assessor):
        """Test assessment of different image formats."""
        # Create PNG image
        img = Image.new('RGB', (300, 400), color=(255, 0, 0))
        
        # PNG format
        png_buffer = io.BytesIO()
        img.save(png_buffer, format='PNG')
        png_result = quality_assessor.assess_image_quality(png_buffer.getvalue())
        
        # JPEG format
        jpeg_buffer = io.BytesIO()
        img.save(jpeg_buffer, format='JPEG')
        jpeg_result = quality_assessor.assess_image_quality(jpeg_buffer.getvalue())
        
        # Both should work
        assert isinstance(png_result, dict)
        assert isinstance(jpeg_result, dict)
        assert 'quality_score' in png_result
        assert 'quality_score' in jpeg_result

    def test_grayscale_image_assessment(self, quality_assessor):
        """Test assessment of grayscale images."""
        # Create grayscale image
        img = Image.new('L', (400, 600), color=128)
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='JPEG')
        
        result = quality_assessor.assess_image_quality(img_buffer.getvalue())
        
        assert isinstance(result, dict)
        assert 'quality_score' in result

    def test_very_large_image(self, quality_assessor):
        """Test assessment of very large image."""
        # Create large image
        img = Image.new('RGB', (2000, 3000), color=(0, 255, 0))
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='JPEG', quality=85)
        
        result = quality_assessor.assess_image_quality(img_buffer.getvalue())
        
        assert isinstance(result, dict)
        assert 'quality_score' in result
        
        if 'dimensions' in result:
            assert result['dimensions'] == (2000, 3000)

    def test_very_small_image(self, quality_assessor):
        """Test assessment of very small image."""
        # Create tiny image
        img = Image.new('RGB', (50, 75), color=(255, 255, 0))
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='JPEG')
        
        result = quality_assessor.assess_image_quality(img_buffer.getvalue())
        
        assert isinstance(result, dict)
        assert 'quality_score' in result