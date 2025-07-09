"""Shared fixtures for Pokemon Card Scanner tests."""

import base64
import io
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import Mock

import pytest
from PIL import Image
import responses

# Test configuration
TEST_CONFIG = {
    "gemini": {
        "api_key": "test_api_key",
        "model": "gemini-pro",
        "max_tokens": 2000,
        "temperature": 0.1
    },
    "tcg": {
        "api_key": "test_tcg_key",
        "base_url": "https://api.pokemontcg.io/v2"
    },
    "quality": {
        "min_score": 50,
        "foil_threshold": 30
    }
}


@pytest.fixture
def test_config():
    """Provide test configuration."""
    return TEST_CONFIG.copy()


@pytest.fixture
def sample_card_image():
    """Create a sample card image for testing."""
    # Create a simple test image
    img = Image.new('RGB', (400, 600), color=(0, 0, 255))
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='JPEG')
    img_buffer.seek(0)
    return img_buffer.getvalue()


@pytest.fixture 
def sample_card_image_base64(sample_card_image):
    """Provide sample card image as base64 string."""
    return base64.b64encode(sample_card_image).decode('utf-8')


@pytest.fixture
def sample_blurry_image():
    """Create a blurry test image."""
    img = Image.new('RGB', (200, 300), color=(128, 128, 128))
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='JPEG', quality=20)
    img_buffer.seek(0)
    return img_buffer.getvalue()


@pytest.fixture
def sample_high_quality_image():
    """Create a high quality test image."""
    img = Image.new('RGB', (800, 1200), color=(255, 255, 255))
    # Add some detail/texture
    for x in range(0, 800, 50):
        for y in range(0, 1200, 50):
            if (x + y) % 100 == 0:
                for dx in range(10):
                    for dy in range(10):
                        if x + dx < 800 and y + dy < 1200:
                            img.putpixel((x + dx, y + dy), (0, 0, 0))
    
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='JPEG', quality=95)
    img_buffer.seek(0)
    return img_buffer.getvalue()


@pytest.fixture
def mock_gemini_response():
    """Mock successful Gemini API response."""
    return {
        "name": "Pikachu",
        "set_name": "Base Set",
        "number": "25",
        "types": ["Electric"],
        "hp": "60",
        "rarity": "Common",
        "set_size": 102,
        "visual_features": {
            "card_series": "classic",
            "visual_era": "vintage",
            "foil_pattern": "none"
        }
    }


@pytest.fixture
def mock_tcg_response():
    """Mock successful TCG API response."""
    return {
        "data": [
            {
                "id": "base1-25",
                "name": "Pikachu",
                "number": "25",
                "types": ["Lightning"],
                "hp": "60",
                "rarity": "Common",
                "set": {
                    "id": "base1",
                    "name": "Base",
                    "total": 102
                },
                "images": {
                    "small": "https://images.pokemontcg.io/base1/25.png",
                    "large": "https://images.pokemontcg.io/base1/25_hires.png"
                },
                "tcgplayer": {
                    "prices": {
                        "normal": {
                            "low": 0.25,
                            "mid": 1.50,
                            "high": 5.00,
                            "market": 1.25
                        }
                    }
                }
            }
        ]
    }


@pytest.fixture 
def mock_tcg_empty_response():
    """Mock empty TCG API response."""
    return {"data": []}


@pytest.fixture
def mock_quality_assessment_good():
    """Mock good quality assessment."""
    return {
        "overall_score": 85.0,
        "blur_score": 90.0,
        "resolution_score": 80.0,
        "lighting_score": 85.0,
        "card_detection_score": 85.0,
        "foil_interference": "low",
        "condition_assessment": "excellent",
        "feedback": "Good quality image suitable for scanning"
    }


@pytest.fixture
def mock_quality_assessment_poor():
    """Mock poor quality assessment."""
    return {
        "overall_score": 35.0,
        "blur_score": 20.0,
        "resolution_score": 40.0,
        "lighting_score": 45.0,
        "card_detection_score": 35.0,
        "foil_interference": "high",
        "condition_assessment": "poor",
        "feedback": "Image quality too low for accurate scanning"
    }


@pytest.fixture
def mock_processing_info():
    """Mock processing information."""
    return {
        "total_time": 1500,
        "gemini_time": 800,
        "tcg_search_time": 300,
        "quality_time": 100,
        "processing_tier": "standard",
        "image_enhancements": ["resize", "contrast"]
    }


@pytest.fixture
def mock_webhook_config():
    """Mock webhook configuration."""
    return {
        "enabled": True,
        "url": "http://localhost:3000/webhook",
        "timeout": 10,
        "min_level": "ERROR",
        "rate_limit": 5
    }


@pytest.fixture
def mock_scan_request():
    """Mock scan request payload."""
    return {
        "image": "base64_encoded_image_data",
        "filename": "test_card.jpg",
        "options": {
            "optimize_for_speed": False,
            "include_cost_tracking": True
        }
    }


@pytest.fixture
def sample_card_matches():
    """Sample card match data for testing."""
    return [
        {
            "card": {
                "id": "base1-25",
                "name": "Pikachu", 
                "number": "25",
                "set": {"name": "Base", "total": 102}
            },
            "score": 8500,
            "score_breakdown": {
                "name_exact": 1500,
                "number_exact": 2000,
                "set_exact": 2000,
                "set_number_name_triple": 5000
            }
        },
        {
            "card": {
                "id": "base2-25", 
                "name": "Pikachu",
                "number": "25",
                "set": {"name": "Base Set 2", "total": 130}
            },
            "score": 4500,
            "score_breakdown": {
                "name_exact": 1500,
                "number_exact": 2000,
                "set_partial": 500,
                "set_number_combo": 3000
            }
        }
    ]


# Test helpers
class TestImageFactory:
    """Factory for creating test images."""
    
    @staticmethod
    def create_card_image(width=400, height=600, color=(0, 0, 255), quality=95):
        """Create a test card image."""
        img = Image.new('RGB', (width, height), color=color)
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='JPEG', quality=quality)
        img_buffer.seek(0)
        return img_buffer.getvalue()
    
    @staticmethod
    def create_base64_image(width=400, height=600, color=(0, 0, 255), quality=95):
        """Create a base64 encoded test image."""
        image_data = TestImageFactory.create_card_image(width, height, color, quality)
        return base64.b64encode(image_data).decode('utf-8')


@pytest.fixture
def image_factory():
    """Provide image factory for tests."""
    return TestImageFactory