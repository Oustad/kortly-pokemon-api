#!/usr/bin/env python3
"""
Simple accuracy tester for Pokemon card scanner.

A lightweight tool to test all images in a directory and generate a clean report.
No rate limiting, no complex features - just scan and report.

Usage:
    python simple_accuracy_tester.py --images-dir test_results/images
    python simple_accuracy_tester.py --images-dir test_results/images --output my_report.html
"""

import asyncio
import argparse
import base64
import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import aiohttp

def load_image_as_base64(image_path: Path) -> str:
    """Load an image file and convert to base64."""
    with open(image_path, "rb") as f:
        image_data = f.read()
    return base64.b64encode(image_data).decode('utf-8')

async def scan_image(session: aiohttp.ClientSession, image_path: Path, api_url: str) -> Dict[str, Any]:
    """Scan a single image using the API."""
    try:
        # Load and encode image
        image_base64 = load_image_as_base64(image_path)
        
        # Prepare request
        request_data = {
            "image": image_base64,
            "filename": image_path.name,
            "options": {
                "optimize_for_speed": False,  # Use standard tier
                "include_cost_tracking": False,
                "retry_on_truncation": True
            }
        }
        
        start_time = time.time()
        
        # Make API call
        async with session.post(f"{api_url}/api/v1/scan", json=request_data, timeout=60) as response:
            processing_time = (time.time() - start_time) * 1000
            response_data = await response.json()
            
            return {
                "filename": image_path.name,
                "success": response.status == 200,
                "status_code": response.status,
                "processing_time_ms": processing_time,
                "response": response_data if response.status == 200 else None,
                "error": response_data.get("detail") if response.status != 200 else None
            }
            
    except Exception as e:
        return {
            "filename": image_path.name,
            "success": False,
            "status_code": 0,
            "processing_time_ms": 0,
            "response": None,
            "error": str(e)
        }

def categorize_result(result: Dict[str, Any]) -> str:
    """Categorize the result into success, expected_non_identification, or failed."""
    if result["success"]:
        return "success"
    
    # Check for expected non-identification cases
    error_msg = str(result.get("error", ""))
    
    # Parse JSON error messages
    if error_msg.startswith("{"):
        try:
            import json
            error_obj = json.loads(error_msg)
            message = error_obj.get("message", "")
        except:
            message = error_msg
    else:
        message = error_msg
    
    # Check for expected cases
    if "Card back detected" in message:
        return "expected_non_identification"
    elif "quality too low" in message:
        return "expected_non_identification"
    elif "Non-Pokemon card detected" in message:
        return "expected_non_identification"
    else:
        return "failed"

def extract_card_info(result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract relevant card information from scan result."""
    category = categorize_result(result)
    
    if category == "success":
        response = result["response"]
        
        # Handle simplified response format
        if "name" in response and "quality_score" in response:
            return {
                "category": category,
                "card_name": response.get("name", "Unknown"),
                "set_name": response.get("set_name", ""),
                "quality_score": response.get("quality_score", 0),
                "error_message": ""
            }
        
        # Handle detailed response format (fallback)
        elif "card_identification" in response:
            card_id = response["card_identification"]
            structured_data = card_id.get("structured_data", {})
            processing = response.get("processing", {})
            
            return {
                "category": category,
                "card_name": structured_data.get("name", "Unknown"),
                "set_name": structured_data.get("set_name", ""),
                "quality_score": processing.get("quality_score", 0),
                "error_message": ""
            }
        
        else:
            return {
                "category": "failed",
                "card_name": "UNKNOWN_FORMAT",
                "set_name": "",
                "quality_score": 0,
                "error_message": "Unexpected response format"
            }
    
    elif category == "expected_non_identification":
        # Parse the error message for display
        error_msg = str(result.get("error", ""))
        if error_msg.startswith("{"):
            try:
                import json
                error_obj = json.loads(error_msg)
                display_message = error_obj.get("message", error_msg)
            except:
                display_message = error_msg
        else:
            display_message = error_msg
        
        return {
            "category": category,
            "card_name": "N/A (Expected)",
            "set_name": "",
            "quality_score": 0,  # We don't have quality score for these
            "error_message": display_message
        }
    
    else:  # failed
        return {
            "category": category,
            "card_name": "ERROR",
            "set_name": "",
            "quality_score": 0,
            "error_message": result.get("error", "Unknown error")
        }

def generate_html_report(results: List[Dict[str, Any]], output_file: str):
    """Generate a simple HTML report."""
    
    # Calculate stats by category
    total_images = len(results)
    successful_scans = sum(1 for r in results if r["card_info"]["category"] == "success")
    expected_non_id = sum(1 for r in results if r["card_info"]["category"] == "expected_non_identification")
    failed_scans = sum(1 for r in results if r["card_info"]["category"] == "failed")
    
    # Calculate success rate (excluding expected non-identification)
    identifiable_images = total_images - expected_non_id
    success_rate = (successful_scans / identifiable_images * 100) if identifiable_images > 0 else 0
    
    avg_processing_time = sum(r["processing_time_ms"] for r in results) / total_images if results else 0
    avg_quality_score = sum(r["card_info"]["quality_score"] for r in results if r["card_info"]["category"] == "success") / successful_scans if successful_scans > 0 else 0
    
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pokemon Card Scanner - Accuracy Test Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background: #3b82f6; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; margin-bottom: 20px; }}
        .stat-card {{ background: #f8fafc; padding: 15px; border-radius: 8px; border-left: 4px solid #3b82f6; }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #1e40af; }}
        .stat-label {{ color: #64748b; font-size: 14px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ text-align: left; padding: 12px; border-bottom: 1px solid #e2e8f0; }}
        th {{ background: #f1f5f9; font-weight: bold; }}
        .success {{ color: #10b981; }}
        .expected {{ color: #f59e0b; }}
        .failed {{ color: #ef4444; }}
        .quality-excellent {{ color: #10b981; }}
        .quality-good {{ color: #f59e0b; }}
        .quality-poor {{ color: #ef4444; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🎴 Pokemon Card Scanner Accuracy Report</h1>
        <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    
    <div class="stats">
        <div class="stat-card">
            <div class="stat-value">{total_images}</div>
            <div class="stat-label">Total Images</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{successful_scans}</div>
            <div class="stat-label">Successful Scans</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{expected_non_id}</div>
            <div class="stat-label">Expected Non-ID</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{failed_scans}</div>
            <div class="stat-label">Failed Scans</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{success_rate:.1f}%</div>
            <div class="stat-label">Success Rate</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{avg_processing_time:.0f}ms</div>
            <div class="stat-label">Avg Processing Time</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{avg_quality_score:.1f}</div>
            <div class="stat-label">Avg Quality Score</div>
        </div>
    </div>
    
    <table>
        <thead>
            <tr>
                <th>Image</th>
                <th>Status</th>
                <th>Card Name</th>
                <th>Set</th>
                <th>Quality Score</th>
                <th>Processing Time</th>
                <th>Error Message</th>
            </tr>
        </thead>
        <tbody>
"""
    
    for result in results:
        card_info = result["card_info"]
        category = card_info["category"]
        
        # Status styling and text based on category
        if category == "success":
            status_class = "success"
            status_text = "✅ Success"
        elif category == "expected_non_identification":
            status_class = "expected"
            status_text = "⚠️ Expected Non-ID"
        else:  # failed
            status_class = "failed"
            status_text = "❌ Failed"
        
        # Quality score styling
        quality_score = card_info["quality_score"]
        if quality_score >= 70:
            quality_class = "quality-excellent"
        elif quality_score >= 40:
            quality_class = "quality-good"
        else:
            quality_class = "quality-poor"
        
        # Format quality score display
        quality_display = f"{quality_score:.1f}" if quality_score > 0 else "N/A"
        
        html_content += f"""
            <tr>
                <td>{result['filename']}</td>
                <td class="{status_class}">{status_text}</td>
                <td>{card_info['card_name']}</td>
                <td>{card_info['set_name']}</td>
                <td class="{quality_class}">{quality_display}</td>
                <td>{result['processing_time_ms']:.0f}ms</td>
                <td>{card_info['error_message']}</td>
            </tr>
        """
    
    html_content += """
        </tbody>
    </table>
</body>
</html>
"""
    
    with open(output_file, 'w') as f:
        f.write(html_content)

async def main():
    parser = argparse.ArgumentParser(description="Simple Pokemon card scanner accuracy tester")
    parser.add_argument("--images-dir", type=str, default="test_results/images", 
                       help="Directory containing test images")
    parser.add_argument("--output", type=str, default=f"simple_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                       help="Output HTML report file")
    parser.add_argument("--api-url", type=str, default="http://localhost:8000",
                       help="API base URL")
    
    args = parser.parse_args()
    
    # Find all image files
    images_dir = Path(args.images_dir)
    if not images_dir.exists():
        print(f"❌ Images directory not found: {images_dir}")
        return
    
    image_files = []
    for ext in ['*.jpg', '*.jpeg', '*.png', '*.heic', '*.HEIC']:
        image_files.extend(images_dir.glob(ext))
    
    if not image_files:
        print(f"❌ No image files found in {images_dir}")
        return
    
    print(f"🔍 Found {len(image_files)} images to test")
    print(f"📊 API URL: {args.api_url}")
    print(f"📄 Report will be saved to: {args.output}")
    print()
    
    # Test API health
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{args.api_url}/api/v1/health", timeout=5) as response:
                if response.status != 200:
                    print(f"❌ API health check failed: {response.status}")
                    return
                print("✅ API is healthy")
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        return
    
    # Process images
    results = []
    
    async with aiohttp.ClientSession() as session:
        for i, image_path in enumerate(image_files, 1):
            print(f"[{i:3d}/{len(image_files)}] Processing {image_path.name}...", end=" ")
            
            result = await scan_image(session, image_path, args.api_url)
            result["card_info"] = extract_card_info(result)
            results.append(result)
            
            category = result['card_info']['category']
            if category == "success":
                print(f"✅ {result['card_info']['card_name']} ({result['processing_time_ms']:.0f}ms)")
            elif category == "expected_non_identification":
                print(f"⚠️ {result['card_info']['error_message']}")
            else:  # failed
                print(f"❌ {result['card_info']['error_message']}")
    
    # Generate report
    print(f"\n📊 Generating report: {args.output}")
    generate_html_report(results, args.output)
    
    # Print summary
    successful_scans = sum(1 for r in results if r["card_info"]["category"] == "success")
    expected_non_id = sum(1 for r in results if r["card_info"]["category"] == "expected_non_identification")
    failed_scans = sum(1 for r in results if r["card_info"]["category"] == "failed")
    
    # Calculate success rate (excluding expected non-identification)
    identifiable_images = len(results) - expected_non_id
    success_rate = (successful_scans / identifiable_images * 100) if identifiable_images > 0 else 0
    
    print(f"\n🎯 Test Summary:")
    print(f"   Total images: {len(results)}")
    print(f"   ✅ Successful: {successful_scans}")
    print(f"   ⚠️ Expected Non-ID: {expected_non_id}")
    print(f"   ❌ Failed: {failed_scans}")
    print(f"   Success rate: {success_rate:.1f}% (excluding expected non-ID)")
    print(f"   Report saved: {args.output}")

if __name__ == "__main__":
    asyncio.run(main())