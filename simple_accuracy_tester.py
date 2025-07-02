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
                "response_format": "detailed",  # Use advanced endpoint for full data
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

def extract_top_matches(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract top 3 matches from detailed response."""
    if not result["success"] or not result["response"]:
        return []
    
    response = result["response"]
    
    # Extract from all_tcg_matches (detailed response format)
    if "all_tcg_matches" in response and response["all_tcg_matches"]:
        matches = []
        for match_score in response["all_tcg_matches"][:3]:  # Top 3
            card = match_score.get("card", {})
            images = card.get("images", {})
            matches.append({
                "name": card.get("name", "Unknown"),
                "set_name": card.get("set_name", ""),
                "number": card.get("number", ""),
                "hp": card.get("hp", ""),
                "types": card.get("types", []),
                "rarity": card.get("rarity", ""),
                "score": match_score.get("score", 0),
                "confidence": match_score.get("confidence", "unknown"),
                "reasoning": match_score.get("reasoning", []),
                "score_breakdown": match_score.get("score_breakdown", {}),
                "image_small": images.get("small", ""),
                "image_large": images.get("large", ""),
                "tcg_player_url": f"https://www.tcgplayer.com/search/pokemon/product?productLineName=pokemon&q={card.get('name', '').replace(' ', '%20')}&view=grid"
            })
        return matches
    
    # Fallback: extract best match only
    elif "best_match" in response and response["best_match"]:
        card = response["best_match"]
        images = card.get("images", {})
        return [{
            "name": card.get("name", "Unknown"),
            "set_name": card.get("set_name", ""),
            "number": card.get("number", ""),
            "hp": card.get("hp", ""),
            "types": card.get("types", []),
            "rarity": card.get("rarity", ""),
            "score": 999999,  # Best match gets max score
            "confidence": "high",
            "reasoning": ["Best match from search results"],
            "score_breakdown": {"best_match": 999999},
            "image_small": images.get("small", ""),
            "image_large": images.get("large", ""),
            "tcg_player_url": f"https://www.tcgplayer.com/search/pokemon/product?productLineName=pokemon&q={card.get('name', '').replace(' ', '%20')}&view=grid"
        }]
    
    return []


def extract_card_info(result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract relevant card information from scan result."""
    category = categorize_result(result)
    
    if category == "success":
        response = result["response"]
        
        # Handle detailed response format (new primary format)
        if "card_identification" in response and "processing" in response:
            card_id = response["card_identification"]
            structured_data = card_id.get("structured_data", {})
            processing = response.get("processing", {})
            best_match = response.get("best_match")
            
            # Get primary card name - prefer best match, fall back to structured data
            primary_name = "Unknown"
            primary_set = ""
            if best_match:
                primary_name = best_match.get("name", primary_name)
                primary_set = best_match.get("set_name", "")
            elif structured_data:
                primary_name = structured_data.get("name", primary_name)
                primary_set = structured_data.get("set_name", "")
            
            return {
                "category": category,
                "card_name": primary_name,
                "set_name": primary_set,
                "quality_score": processing.get("quality_score", 0),
                "error_message": "",
                "top_matches": extract_top_matches(result)
            }
        
        # Handle simplified response format (fallback)
        elif "name" in response and "quality_score" in response:
            return {
                "category": category,
                "card_name": response.get("name", "Unknown"),
                "set_name": response.get("set_name", ""),
                "quality_score": response.get("quality_score", 0),
                "error_message": "",
                "top_matches": []
            }
        
        else:
            return {
                "category": "failed",
                "card_name": "UNKNOWN_FORMAT",
                "set_name": "",
                "quality_score": 0,
                "error_message": "Unexpected response format",
                "top_matches": []
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
            "error_message": display_message,
            "top_matches": []
        }
    
    else:  # failed
        return {
            "category": category,
            "card_name": "ERROR",
            "set_name": "",
            "quality_score": 0,
            "error_message": result.get("error", "Unknown error"),
            "top_matches": []
        }

def generate_html_report(results: List[Dict[str, Any]], output_file: str):
    """Generate an enhanced HTML report with top 3 matches and images."""
    
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
    <title>Pokemon Card Scanner - Enhanced Accuracy Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8fafc; }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
        
        /* Header */
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 12px; margin-bottom: 30px; text-align: center; }}
        .header h1 {{ font-size: 2.5rem; margin-bottom: 10px; }}
        .header p {{ font-size: 1.1rem; opacity: 0.9; }}
        
        /* Stats */
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 20px; margin-bottom: 40px; }}
        .stat-card {{ background: white; padding: 20px; border-radius: 12px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: 1px solid #e2e8f0; }}
        .stat-value {{ font-size: 2rem; font-weight: bold; color: #2563eb; margin-bottom: 5px; }}
        .stat-label {{ color: #64748b; font-size: 0.9rem; }}
        
        /* Test Results */
        .test-result {{ background: white; border-radius: 12px; padding: 25px; margin-bottom: 30px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: 1px solid #e2e8f0; }}
        .result-header {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 2px solid #f1f5f9; }}
        .result-title {{ font-size: 1.3rem; font-weight: bold; }}
        .result-status {{ padding: 8px 16px; border-radius: 20px; font-weight: 500; font-size: 0.9rem; }}
        .status-success {{ background: #dcfce7; color: #166534; }}
        .status-expected {{ background: #fef3c7; color: #92400e; }}
        .status-failed {{ background: #fee2e2; color: #991b1b; }}
        
        /* Image Comparison */
        .comparison-section {{ margin: 20px 0; }}
        .uploaded-image {{ text-align: center; margin-bottom: 25px; }}
        .uploaded-image img {{ max-width: 300px; max-height: 400px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.15); }}
        .uploaded-image h4 {{ margin-bottom: 15px; color: #374151; }}
        
        /* Top Matches */
        .matches-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }}
        .match-card {{ background: #f8fafc; border: 2px solid #e2e8f0; border-radius: 12px; padding: 20px; transition: all 0.3s ease; }}
        .match-card:hover {{ transform: translateY(-2px); box-shadow: 0 8px 16px rgba(0,0,0,0.1); }}
        .match-card.rank-1 {{ border-color: #10b981; background: #f0fdf4; }}
        .match-card.rank-2 {{ border-color: #f59e0b; background: #fffbeb; }}
        .match-card.rank-3 {{ border-color: #ef4444; background: #fef2f2; }}
        
        .match-header {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 15px; }}
        .match-rank {{ background: #374151; color: white; padding: 6px 12px; border-radius: 15px; font-weight: bold; font-size: 0.8rem; }}
        .match-rank.rank-1 {{ background: #10b981; }}
        .match-rank.rank-2 {{ background: #f59e0b; }}
        .match-rank.rank-3 {{ background: #ef4444; }}
        .match-score {{ font-weight: bold; font-size: 1.1rem; color: #374151; }}
        
        .match-image {{ text-align: center; margin-bottom: 15px; }}
        .match-image img {{ max-width: 150px; height: auto; border-radius: 6px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .match-image .no-image {{ display: inline-block; padding: 40px 20px; background: #f3f4f6; border: 2px dashed #d1d5db; border-radius: 6px; color: #6b7280; }}
        
        .match-info {{ line-height: 1.6; }}
        .match-name {{ font-weight: bold; font-size: 1.1rem; color: #1f2937; margin-bottom: 8px; }}
        .match-details {{ color: #6b7280; font-size: 0.9rem; margin-bottom: 6px; }}
        .match-confidence {{ display: inline-block; padding: 4px 8px; border-radius: 12px; font-size: 0.8rem; font-weight: 500; }}
        .confidence-high {{ background: #dcfce7; color: #166534; }}
        .confidence-medium {{ background: #fef3c7; color: #92400e; }}
        .confidence-low {{ background: #fee2e2; color: #991b1b; }}
        
        /* Score Breakdown */
        .score-breakdown {{ margin-top: 15px; padding-top: 15px; border-top: 1px solid #e5e7eb; }}
        .score-breakdown summary {{ cursor: pointer; font-weight: 500; color: #374151; padding: 5px 0; }}
        .score-items {{ margin-top: 10px; font-size: 0.8rem; }}
        .score-item {{ display: flex; justify-content: space-between; padding: 2px 0; color: #6b7280; }}
        
        /* Links */
        .tcg-link {{ display: inline-block; margin-top: 10px; padding: 8px 12px; background: #3b82f6; color: white; text-decoration: none; border-radius: 6px; font-size: 0.8rem; }}
        .tcg-link:hover {{ background: #2563eb; }}
        
        /* Error states */
        .error-details {{ padding: 20px; background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; color: #991b1b; }}
        
        /* Responsive */
        @media (max-width: 768px) {{
            .container {{ padding: 15px; }}
            .header {{ padding: 20px; }}
            .header h1 {{ font-size: 2rem; }}
            .matches-grid {{ grid-template-columns: 1fr; }}
            .result-header {{ flex-direction: column; gap: 15px; text-align: center; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎴 Pokemon Card Scanner Enhanced Report</h1>
            <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} • Advanced Analysis with Top 3 Matches</p>
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
"""

    # Generate individual test results
    for result in results:
        card_info = result["card_info"]
        category = card_info["category"]
        
        # Status styling
        if category == "success":
            status_class = "status-success"
            status_text = "✅ Success"
        elif category == "expected_non_identification":
            status_class = "status-expected"
            status_text = "⚠️ Expected Non-ID"
        else:
            status_class = "status-failed"
            status_text = "❌ Failed"
        
        quality_display = f"{card_info['quality_score']:.1f}" if card_info['quality_score'] > 0 else "N/A"
        
        html_content += f"""
        <div class="test-result">
            <div class="result-header">
                <div class="result-title">{result['filename']}</div>
                <div class="result-status {status_class}">{status_text}</div>
            </div>
            
            <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 30px; align-items: start;">
                <div>
                    <div class="uploaded-image">
                        <h4>📄 Uploaded Image</h4>
                        <div style="color: #6b7280; font-size: 0.9rem; margin-bottom: 10px;">
                            Quality: {quality_display} • Processing: {result['processing_time_ms']:.0f}ms
                        </div>
                        <div style="background: #f3f4f6; padding: 40px 20px; border: 2px dashed #d1d5db; border-radius: 8px; color: #6b7280;">
                            📁 {result['filename']}<br/>
                            <small>Original image not embedded</small>
                        </div>
                    </div>
                </div>
                
                <div class="comparison-section">"""
        
        if category == "success" and card_info.get("top_matches"):
            html_content += f"""
                    <h4 style="margin-bottom: 20px; color: #374151;">🏆 Top {len(card_info['top_matches'])} Match{'es' if len(card_info['top_matches']) > 1 else ''}</h4>
                    <div class="matches-grid">"""
            
            for i, match in enumerate(card_info["top_matches"], 1):
                rank_class = f"rank-{i}"
                confidence_class = f"confidence-{match.get('confidence', 'unknown')}"
                
                # Format types
                types_str = ", ".join(match.get("types", [])) if match.get("types") else "Unknown"
                
                # Format score breakdown
                score_breakdown_items = ""
                for key, value in match.get("score_breakdown", {}).items():
                    formatted_key = key.replace("_", " ").title()
                    score_breakdown_items += f'<div class="score-item"><span>{formatted_key}</span><span>+{value}</span></div>'
                
                html_content += f"""
                        <div class="match-card {rank_class}">
                            <div class="match-header">
                                <div class="match-rank {rank_class}">#{i}</div>
                                <div class="match-score">Score: {match.get('score', 0):,}</div>
                            </div>
                            
                            <div class="match-image">"""
                
                if match.get("image_small"):
                    html_content += f'<img src="{match["image_small"]}" alt="{match.get("name", "Unknown")}" onerror="this.style.display=\'none\'; this.nextElementSibling.style.display=\'block\';">'
                    html_content += f'<div class="no-image" style="display: none;">🎴 No Image</div>'
                else:
                    html_content += '<div class="no-image">🎴 No Image Available</div>'
                
                html_content += f"""
                            </div>
                            
                            <div class="match-info">
                                <div class="match-name">{match.get('name', 'Unknown')}</div>
                                <div class="match-details">Set: {match.get('set_name', 'Unknown')}</div>
                                <div class="match-details">Number: {match.get('number', 'N/A')} | HP: {match.get('hp', 'N/A')}</div>
                                <div class="match-details">Types: {types_str}</div>
                                <div class="match-details">Rarity: {match.get('rarity', 'Unknown')}</div>
                                <div style="margin: 10px 0;">
                                    <span class="match-confidence {confidence_class}">{match.get('confidence', 'unknown').title()} Confidence</span>
                                </div>
                                
                                <details class="score-breakdown">
                                    <summary>Score Breakdown ({match.get('score', 0):,} total)</summary>
                                    <div class="score-items">
                                        {score_breakdown_items}
                                    </div>
                                </details>
                                
                                <a href="{match.get('tcg_player_url', '#')}" target="_blank" class="tcg-link">🔗 View on TCGPlayer</a>
                            </div>
                        </div>"""
            
            html_content += """
                    </div>"""
        
        elif category == "expected_non_identification" or category == "failed":
            html_content += f"""
                    <div class="error-details">
                        <h4>ℹ️ Details</h4>
                        <p>{card_info.get('error_message', 'No additional details available.')}</p>
                    </div>"""
        
        html_content += """
                </div>
            </div>
        </div>"""
    
    html_content += """
    </div>
</body>
</html>
"""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

async def main():
    parser = argparse.ArgumentParser(description="Simple Pokemon card scanner accuracy tester")
    parser.add_argument("--images-dir", type=str, default="../test-images-kortly", 
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