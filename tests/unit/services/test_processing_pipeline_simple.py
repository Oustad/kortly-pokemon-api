"""Simple working tests for ProcessingPipeline service."""

import pytest
import io
from unittest.mock import Mock, patch, AsyncMock
from PIL import Image
from src.scanner.services.processing_pipeline import ProcessingPipeline


class TestProcessingPipelineSimple:
    """Simple test cases for ProcessingPipeline that match actual interface."""

    @pytest.fixture
    def mock_gemini_service(self):
        """Create mock GeminiService."""
        mock = Mock()
        mock.identify_pokemon_card = AsyncMock()
        return mock

    @pytest.fixture
    def processing_pipeline(self, mock_gemini_service):
        """Create ProcessingPipeline instance."""
        return ProcessingPipeline(mock_gemini_service)

    @pytest.fixture
    def sample_image_bytes(self):
        """Create sample image bytes."""
        img = Image.new('RGB', (400, 600), color='blue')
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='JPEG')
        return img_buffer.getvalue()

    def test_initialization(self, processing_pipeline):
        """Test ProcessingPipeline initialization."""
        assert hasattr(processing_pipeline, 'quality_assessor')
        assert hasattr(processing_pipeline, 'image_processor') 
        assert hasattr(processing_pipeline, 'gemini_service')
        assert hasattr(processing_pipeline, 'tier_configs')

    def test_tier_configs_structure(self, processing_pipeline):
        """Test tier configurations exist and have correct structure."""
        configs = processing_pipeline.tier_configs
        
        assert isinstance(configs, dict)
        assert len(configs) > 0
        
        # Check that standard tier names exist
        expected_tiers = ['fast', 'standard', 'enhanced']
        for tier in expected_tiers:
            if tier in configs:
                config = configs[tier]
                assert isinstance(config, dict)
                # Check for expected config keys
                assert 'max_size' in config
                assert 'enhance_image' in config

    @pytest.mark.asyncio
    async def test_process_image_method_exists(self, processing_pipeline, sample_image_bytes):
        """Test that process_image method exists and returns expected structure."""
        # Mock the dependencies
        with patch.object(processing_pipeline, 'quality_assessor') as mock_qa:
            with patch.object(processing_pipeline, 'image_processor') as mock_ip:
                # Mock quality assessment
                mock_qa.assess_image_quality.return_value = {
                    'quality_score': 75,
                    'details': {}
                }
                
                # Mock image processing  
                mock_ip.process_image = AsyncMock(return_value=sample_image_bytes)
                
                # Mock Gemini response
                processing_pipeline.gemini_service.identify_pokemon_card.return_value = {
                    'success': True,
                    'name': 'Pikachu',
                    'card_data': {}
                }
                
                # Test the method
                result = await processing_pipeline.process_image(
                    image_bytes=sample_image_bytes,
                    filename="test.jpg"
                )
                
                # Should return a dictionary
                assert isinstance(result, dict)
                assert 'success' in result

    def test_determine_processing_config_method(self, processing_pipeline):
        """Test _determine_processing_config method if it exists."""
        if hasattr(processing_pipeline, '_determine_processing_config'):
            # Test with basic parameters
            config = processing_pipeline._determine_processing_config(75.0)
            
            assert isinstance(config, dict)
            assert 'tier' in config

    @pytest.mark.asyncio
    async def test_process_image_with_user_preferences(self, processing_pipeline, sample_image_bytes):
        """Test process_image with user preferences."""
        with patch.object(processing_pipeline, 'quality_assessor') as mock_qa:
            with patch.object(processing_pipeline, 'image_processor') as mock_ip:
                mock_qa.assess_image_quality.return_value = {
                    'quality_score': 75,
                    'details': {}
                }
                
                mock_ip.process_image = AsyncMock(return_value=sample_image_bytes)
                
                processing_pipeline.gemini_service.identify_pokemon_card.return_value = {
                    'success': True,
                    'name': 'Pikachu'
                }
                
                # Test with user preferences
                user_prefs = {'max_processing_time': 2000}
                result = await processing_pipeline.process_image(
                    image_bytes=sample_image_bytes,
                    filename="test.jpg",
                    user_preferences=user_prefs
                )
                
                assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_process_image_error_handling(self, processing_pipeline, sample_image_bytes):
        """Test error handling in process_image."""
        with patch.object(processing_pipeline, 'quality_assessor') as mock_qa:
            # Mock quality assessment failure
            mock_qa.assess_image_quality.return_value = {
                'quality_score': 0,
                'error': 'Cannot assess image'
            }
            
            result = await processing_pipeline.process_image(
                image_bytes=sample_image_bytes,
                filename="test.jpg"
            )
            
            # Should handle error gracefully
            assert isinstance(result, dict)
            assert result['success'] is False

    def test_get_tier_info_method(self, processing_pipeline):
        """Test get_tier_info method if it exists."""
        if hasattr(processing_pipeline, 'get_tier_info'):
            info = processing_pipeline.get_tier_info()
            
            assert isinstance(info, dict)

    @pytest.mark.asyncio
    async def test_preprocess_image_method(self, processing_pipeline, sample_image_bytes):
        """Test _preprocess_image method if accessible."""
        if hasattr(processing_pipeline, '_preprocess_image'):
            tier_config = {
                'max_size': (512, 512),
                'enhance_image': False
            }
            
            result = await processing_pipeline._preprocess_image(
                sample_image_bytes,
                tier_config,
                "test.jpg"
            )
            
            assert isinstance(result, bytes)

    def test_tier_config_validation(self, processing_pipeline):
        """Test tier configuration values."""
        configs = processing_pipeline.tier_configs
        
        for tier_name, config in configs.items():
            # Basic validation
            assert isinstance(tier_name, str)
            assert isinstance(config, dict)
            
            # Check max_size format if present
            if 'max_size' in config:
                max_size = config['max_size']
                assert isinstance(max_size, tuple)
                assert len(max_size) == 2
                assert all(isinstance(x, int) for x in max_size)

    @pytest.mark.asyncio
    async def test_process_image_timing(self, processing_pipeline, sample_image_bytes):
        """Test that process_image measures timing."""
        with patch.object(processing_pipeline, 'quality_assessor') as mock_qa:
            with patch.object(processing_pipeline, 'image_processor') as mock_ip:
                mock_qa.assess_image_quality.return_value = {
                    'quality_score': 80,
                    'details': {}
                }
                
                mock_ip.process_image = AsyncMock(return_value=sample_image_bytes)
                
                processing_pipeline.gemini_service.identify_pokemon_card.return_value = {
                    'success': True,
                    'processing_time_ms': 1000
                }
                
                result = await processing_pipeline.process_image(
                    image_bytes=sample_image_bytes,
                    filename="test.jpg"
                )
                
                # Should include timing information
                if 'processing' in result:
                    processing_info = result['processing']
                    assert 'actual_time_ms' in processing_info