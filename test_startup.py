#!/usr/bin/env python3
"""Test script to verify the Pokemon card scanner can start up."""

import sys
import os
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    
    try:
        # Test basic schema imports
        from scanner.models.schemas import ScanRequest, ScanResponse
        print("✅ Schemas imported successfully")
        
        # Test cost tracker
        from scanner.utils.cost_tracker import CostTracker
        tracker = CostTracker()
        print("✅ Cost tracker imported and initialized")
        
        # Test image processor (without external deps)
        from scanner.services.image_processor import ImageProcessor
        processor = ImageProcessor()
        print("✅ Image processor imported and initialized")
        
        # Test basic functionality
        request = ScanRequest(image="test_data")
        print(f"✅ Schema validation works: {request.options.optimize_for_speed}")
        
        print("\n🎉 All basic components working!")
        return True
        
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False

def test_web_files():
    """Test that web files exist."""
    print("\nTesting web files...")
    
    web_dir = Path(__file__).parent / "web"
    required_files = ["index.html", "style.css", "script.js"]
    
    for file in required_files:
        file_path = web_dir / file
        if file_path.exists():
            print(f"✅ {file} exists")
        else:
            print(f"❌ {file} missing")
            return False
    
    print("✅ All web files present")
    return True

def test_project_structure():
    """Test project structure."""
    print("\nTesting project structure...")
    
    base_dir = Path(__file__).parent
    required_dirs = [
        "src/scanner",
        "src/scanner/routes", 
        "src/scanner/services",
        "src/scanner/models",
        "src/scanner/utils",
        "web",
        "tests"
    ]
    
    for dir_path in required_dirs:
        full_path = base_dir / dir_path
        if full_path.exists():
            print(f"✅ {dir_path} exists")
        else:
            print(f"❌ {dir_path} missing")
            return False
    
    print("✅ Project structure correct")
    return True

if __name__ == "__main__":
    print("🧪 Pokemon Card Scanner - Startup Test\n")
    
    success = True
    success &= test_project_structure()
    success &= test_imports()
    success &= test_web_files()
    
    if success:
        print("\n🚀 Project ready! You can now:")
        print("   1. Add your GOOGLE_API_KEY to .env")
        print("   2. Install dependencies: uv sync")
        print("   3. Run: uv run python -m src.scanner.main")
        print("   4. Open: http://localhost:8000")
    else:
        print("\n❌ Some issues found. Please fix them before running.")
        sys.exit(1)