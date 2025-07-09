"""Focused tests for the scan endpoint to improve coverage."""

import base64
import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from PIL import Image
import io

from src.scanner.main import app


class TestScanEndpointFocused:
    """Focused tests for the scan endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def valid_image_base64(self):
        """Create valid base64 image for testing."""
        img = Image.new('RGB', (400, 600), color='blue')
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='JPEG')
        image_data = img_buffer.getvalue()
        return base64.b64encode(image_data).decode('utf-8')
    
    def test_scan_endpoint_missing_image_field(self, client):
        """Test scan endpoint with missing image field."""
        request_data = {
            "filename": "test_card.jpg",
            "options": {}
        }
        
        response = client.post("/api/v1/scan", json=request_data)
        
        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "detail" in data
    
    def test_scan_endpoint_empty_image(self, client):
        """Test scan endpoint with empty image."""
        request_data = {
            "image": "",
            "filename": "test_card.jpg",
            "options": {}
        }
        
        response = client.post("/api/v1/scan", json=request_data)
        
        # Empty image actually gets processed and fails later
        assert response.status_code == 503  # Service unavailable
        data = response.json()
        assert "detail" in data
    
    def test_scan_endpoint_invalid_base64(self, client):
        """Test scan endpoint with invalid base64 data."""
        request_data = {
            "image": "invalid_base64_data!!!",
            "filename": "test_card.jpg",
            "options": {}
        }
        
        response = client.post("/api/v1/scan", json=request_data)
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "Invalid base64 image data" in data["detail"]
    
    def test_scan_endpoint_invalid_json(self, client):
        """Test scan endpoint with invalid JSON."""
        response = client.post("/api/v1/scan", data="invalid json")
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
    
    def test_scan_endpoint_request_validation_basic(self, client, valid_image_base64):
        """Test basic request validation with valid data."""
        request_data = {
            "image": valid_image_base64,
            "filename": "test_card.jpg",
            "options": {}
        }
        
        # This will fail due to missing services, but should pass validation
        response = client.post("/api/v1/scan", json=request_data)
        
        # Should not be a validation error (422), but a service error
        assert response.status_code != 422
    
    def test_scan_endpoint_options_validation(self, client, valid_image_base64):
        """Test options validation."""
        request_data = {
            "image": valid_image_base64,
            "filename": "test_card.jpg",
            "options": {
                "prefer_speed": True,
                "prefer_quality": False
            }
        }
        
        response = client.post("/api/v1/scan", json=request_data)
        
        # Should not be a validation error
        assert response.status_code != 422
    
    def test_scan_endpoint_without_filename(self, client, valid_image_base64):
        """Test scan endpoint without filename."""
        request_data = {
            "image": valid_image_base64,
            "options": {}
        }
        
        response = client.post("/api/v1/scan", json=request_data)
        
        # Should not be a validation error
        assert response.status_code != 422
    
    def test_scan_endpoint_invalid_options_ignored(self, client, valid_image_base64):
        """Test that invalid options are ignored."""
        request_data = {
            "image": valid_image_base64,
            "filename": "test_card.jpg",
            "options": {
                "invalid_option": True,
                "another_invalid": "value"
            }
        }
        
        response = client.post("/api/v1/scan", json=request_data)
        
        # Should not be a validation error
        assert response.status_code != 422
    
    @patch('src.scanner.routes.scan.ProcessingPipeline')
    @patch('src.scanner.routes.scan.GeminiService')
    def test_scan_endpoint_service_initialization(self, mock_gemini_service, mock_pipeline, client, valid_image_base64):
        """Test that services are initialized correctly."""
        # Setup mocks
        mock_pipeline_instance = Mock()
        mock_pipeline.return_value = mock_pipeline_instance
        mock_pipeline_instance.process_image = AsyncMock(return_value={
            "success": False,
            "error": "Test error"
        })
        
        request_data = {
            "image": valid_image_base64,
            "filename": "test_card.jpg",
            "options": {}
        }
        
        response = client.post("/api/v1/scan", json=request_data)
        
        # Verify services were initialized
        mock_gemini_service.assert_called_once()
        mock_pipeline.assert_called_once()
        mock_pipeline_instance.process_image.assert_called_once()
    
    
    @patch('src.scanner.routes.scan.CostTracker')
    @patch('src.scanner.routes.scan.ProcessingPipeline')
    @patch('src.scanner.routes.scan.GeminiService')
    def test_scan_endpoint_cost_tracking_initialized(self, mock_gemini_service, mock_pipeline, mock_cost_tracker, client, valid_image_base64):
        """Test that cost tracking is initialized."""
        # Setup mocks
        mock_pipeline_instance = Mock()
        mock_pipeline.return_value = mock_pipeline_instance
        mock_pipeline_instance.process_image = AsyncMock(return_value={
            "success": False,
            "error": "Test error"
        })
        
        mock_tracker_instance = Mock()
        mock_cost_tracker.return_value = mock_tracker_instance
        
        request_data = {
            "image": valid_image_base64,
            "filename": "test_card.jpg",
            "options": {}
        }
        
        response = client.post("/api/v1/scan", json=request_data)
        
        # Verify cost tracker was initialized
        mock_cost_tracker.assert_called_once()
    
