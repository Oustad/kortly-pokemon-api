#!/usr/bin/env python3
"""Test Quality of Life improvements."""

import requests
import json
import sys
from pathlib import Path

def test_image(image_path: str, response_format: str = "simplified"):
    """Test scanning an image and display the results."""
    print(f"\n🔍 Testing image: {image_path} (Format: {response_format})")
    
    url = "http://localhost:8000/api/v1/scan"
    
    # Read and encode the image file
    import base64
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')
    
    # Create the request payload
    payload = {
        "image": image_data,
        "filename": Path(image_path).name,
        "options": {
            "include_cost_tracking": False,
            "response_format": response_format
        }
    }
    
    response = requests.post(url, json=payload)
    
    print(f"📊 Status Code: {response.status_code}")
    
    try:
        result = response.json()
        
        # Check if it's an error response
        if response.status_code >= 400:
            print(f"❌ Error Response:")
            # Try to parse JSON error detail
            if isinstance(result.get("detail"), str):
                try:
                    detail = json.loads(result["detail"])
                    print(f"   Message: {detail.get('message')}")
                    if "quality_feedback" in detail:
                        feedback = detail["quality_feedback"]
                        print(f"   Overall: {feedback.get('overall')}")
                        print(f"   Issues: {', '.join(feedback.get('issues', []))}")
                        print(f"   Suggestions: {', '.join(feedback.get('suggestions', []))}")
                except:
                    print(f"   {result.get('detail')}")
            else:
                print(f"   {result.get('detail')}")
        else:
            # Success response
            print(f"✅ Success!")
            
            # Check for simplified response
            if "name" in result and "card_identification" not in result:
                print(f"   📋 Simplified Response:")
                print(f"   Name: {result.get('name')}")
                print(f"   Set: {result.get('set_name', 'N/A')}")
                print(f"   Number: {result.get('number', 'N/A')}")
                print(f"   HP: {result.get('hp', 'N/A')}")
                print(f"   Types: {', '.join(result.get('types', [])) if result.get('types') else 'N/A'}")
                print(f"   Rarity: {result.get('rarity', 'N/A')}")
                print(f"   Quality Score: {result.get('quality_score', 'N/A')}")
                if result.get('market_prices'):
                    prices = result['market_prices']
                    print(f"   Market Price: ${prices.get('market', 'N/A')}")
            else:
                # Detailed response
                processing = result.get("processing", {})
                print(f"   Quality Score: {processing.get('quality_score', 'N/A')}")
                print(f"   Processing Tier: {processing.get('processing_tier', 'N/A')}")
                
                # Card type info if available
                card_info = result.get("card_identification", {})
                if card_info.get("card_type_info"):
                    card_type = card_info["card_type_info"]["card_type"]
                    print(f"   Card Type: {card_type}")
                
    except Exception as e:
        print(f"❌ Failed to parse response: {e}")
        print(f"   Raw response: {response.text[:200]}...")

def test_web_interface():
    """Test via web interface to see UI behavior."""
    print("\n📱 Testing via web interface...")
    print("Open http://localhost:8000 in your browser")
    print("Try uploading:")
    print("  1. A blurry/low quality image")
    print("  2. A card back image")
    print("  3. A non-Pokemon card")
    print("  4. A good quality Pokemon card")

if __name__ == "__main__":
    # Test with a sample image
    test_images = [
        "/home/mats/code/kortly/pokemon-card-scanner/test_results/images/IMG_5400.HEIC",
        # Add more test images as needed
    ]
    
    for image in test_images:
        if Path(image).exists():
            # Test simplified response (default)
            test_image(image, "simplified")
            
            # Test detailed response
            test_image(image, "detailed")
        else:
            print(f"⚠️  Image not found: {image}")
    
    test_web_interface()