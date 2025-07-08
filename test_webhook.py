#!/usr/bin/env python3
"""
Webhook Test Script for Pokemon Card Scanner

This script triggers various error scenarios to test the webhook functionality
with the fake Slack webhook server.

Usage:
    python test_webhook.py

Prerequisites:
    1. Run fake_slack_webhook.py in another terminal
    2. Update .env with ERROR_WEBHOOK_URL=http://localhost:3000/webhook
    3. Set ERROR_WEBHOOK_ENABLED=true in .env
"""

import asyncio
import base64
import json
import sys
from pathlib import Path

import aiohttp


def create_test_image() -> str:
    """Create a small test image as base64 for testing."""
    # 1x1 pixel PNG image
    tiny_png = bytes([
        137, 80, 78, 71, 13, 10, 26, 10, 0, 0, 0, 13, 73, 72, 68, 82, 0, 0, 0, 1, 0, 0, 0, 1, 8, 2, 0, 0, 0, 144, 119, 83, 222, 0, 0, 0, 12, 73, 68, 65, 84, 8, 215, 99, 248, 15, 0, 0, 1, 0, 1, 0, 24, 221, 219, 219, 0, 0, 0, 0, 73, 69, 78, 68, 174, 66, 96, 130
    ])
    return base64.b64encode(tiny_png).decode('utf-8')


async def test_invalid_image():
    """Test invalid base64 image data."""
    print("🧪 Testing invalid image data...")
    
    async with aiohttp.ClientSession() as session:
        request_data = {
            "image": "invalid_base64_data",
            "filename": "test_invalid.jpg",
            "options": {}
        }
        
        try:
            async with session.post("http://localhost:8000/api/v1/scan", json=request_data) as response:
                result = await response.json()
                print(f"   📤 Response: {response.status} - {result.get('detail', 'No detail')}")
        except Exception as e:
            print(f"   ❌ Request failed: {e}")


async def test_processing_error():
    """Test with a valid image that should trigger processing errors."""
    print("🧪 Testing processing error...")
    
    # Use tiny image that will likely fail quality checks
    test_image = create_test_image()
    
    async with aiohttp.ClientSession() as session:
        request_data = {
            "image": test_image,
            "filename": "test_tiny.png",
            "options": {
                "optimize_for_speed": False,
                "include_cost_tracking": True
            }
        }
        
        try:
            async with session.post("http://localhost:8000/api/v1/scan", json=request_data) as response:
                result = await response.json()
                print(f"   📤 Response: {response.status} - {result.get('detail', result.get('error', 'Success'))}")
        except Exception as e:
            print(f"   ❌ Request failed: {e}")


async def test_api_health():
    """Test API health to make sure it's running."""
    print("🔍 Checking API health...")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("http://localhost:8000/api/v1/health") as response:
                if response.status == 200:
                    print("   ✅ API is running")
                    return True
                else:
                    print(f"   ❌ API health check failed: {response.status}")
                    return False
        except Exception as e:
            print(f"   ❌ Cannot connect to API: {e}")
            return False


async def test_webhook_server():
    """Test if webhook server is running."""
    print("🔍 Checking webhook server...")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("http://localhost:3000/health") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Webhook server is running (received {data.get('webhooks_received', 0)} webhooks)")
                    return True
                else:
                    print(f"   ❌ Webhook server health check failed: {response.status}")
                    return False
        except Exception as e:
            print(f"   ❌ Cannot connect to webhook server: {e}")
            return False


async def trigger_multiple_errors():
    """Trigger multiple errors to test rate limiting and different error types."""
    print("🧪 Testing multiple errors (rate limiting)...")
    
    test_image = create_test_image()
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        
        for i in range(3):  # Trigger 3 errors quickly
            request_data = {
                "image": test_image,
                "filename": f"test_batch_{i}.png",
                "options": {}
            }
            
            task = session.post("http://localhost:8000/api/v1/scan", json=request_data)
            tasks.append(task)
        
        # Execute all requests concurrently
        try:
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            for i, response in enumerate(responses):
                if isinstance(response, Exception):
                    print(f"   ❌ Request {i+1} failed: {response}")
                else:
                    async with response:
                        result = await response.json()
                        print(f"   📤 Request {i+1}: {response.status}")
        except Exception as e:
            print(f"   ❌ Batch request failed: {e}")


async def check_webhook_stats():
    """Check webhook server statistics."""
    print("📊 Checking webhook statistics...")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("http://localhost:3000/stats") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   📈 Total webhooks: {data.get('total_webhooks', 0)}")
                    by_level = data.get('by_level', {})
                    for level, count in by_level.items():
                        print(f"      {level}: {count}")
                else:
                    print(f"   ❌ Failed to get stats: {response.status}")
        except Exception as e:
            print(f"   ❌ Cannot get webhook stats: {e}")


def print_instructions():
    """Print setup instructions."""
    print("🔧 Setup Instructions:")
    print("1. Start the fake webhook server:")
    print("   python fake_slack_webhook.py")
    print("2. Update .env file:")
    print("   ERROR_WEBHOOK_URL=http://localhost:3000/webhook")
    print("   ERROR_WEBHOOK_ENABLED=true")
    print("   ERROR_WEBHOOK_MIN_LEVEL=INFO")
    print("3. Start the Pokemon scanner:")
    print("   uv run python -m src.scanner.main")
    print("4. Run this test script:")
    print("   python test_webhook.py")
    print()


async def main():
    """Main test function."""
    print("🚀 Pokemon Card Scanner Webhook Test")
    print("=" * 50)
    
    # Check if both services are running
    api_running = await test_api_health()
    webhook_running = await test_webhook_server()
    
    if not api_running:
        print("\n❌ Pokemon Card Scanner API is not running!")
        print("Start it with: uv run python -m src.scanner.main")
        return
    
    if not webhook_running:
        print("\n❌ Fake webhook server is not running!")
        print("Start it with: python fake_slack_webhook.py")
        return
    
    print("\n✅ Both services are running. Starting tests...\n")
    
    # Run test scenarios
    await test_invalid_image()
    await asyncio.sleep(1)  # Brief pause between tests
    
    await test_processing_error()
    await asyncio.sleep(1)
    
    await trigger_multiple_errors()
    await asyncio.sleep(2)  # Wait for webhooks to be processed
    
    # Check final stats
    await check_webhook_stats()
    
    print("\n✅ Tests completed!")
    print("Check the webhook server terminal for detailed webhook output.")


if __name__ == "__main__":
    # Check for required dependencies
    try:
        import aiohttp
    except ImportError:
        print("❌ Missing dependency: aiohttp")
        print("💡 Install with: pip install aiohttp")
        sys.exit(1)
    
    print_instructions()
    
    # Ask user to confirm setup
    response = input("Have you completed the setup steps above? (y/n): ")
    if response.lower() not in ['y', 'yes']:
        print("👋 Please complete the setup steps first, then run this script again.")
        sys.exit(0)
    
    # Run the tests
    asyncio.run(main())