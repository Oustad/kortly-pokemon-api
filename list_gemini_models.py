#!/usr/bin/env python3
"""
Simple script to list available Gemini models.

This script queries the Google Generative AI API to show all available models
that support content generation, which can be used for Pokemon card identification.

Usage:
    python list_gemini_models.py
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

import google.generativeai as genai
from scanner.config import get_config

def list_gemini_models():
    """List all available Gemini models that support content generation."""
    
    # Get configuration
    config = get_config()
    
    # Check for API key
    if not config.google_api_key:
        print("❌ Error: GOOGLE_API_KEY environment variable is not set")
        print("Please set your Google API key to list available models.")
        return
    
    # Configure Gemini
    genai.configure(api_key=config.google_api_key)
    
    try:
        print("🔍 Fetching available Gemini models...")
        print()
        
        # Get all models
        models = genai.list_models()
        
        # Filter for models that support generateContent
        content_models = [m for m in models if 'generateContent' in m.supported_generation_methods]
        
        if not content_models:
            print("❌ No models found that support content generation")
            return
        
        print(f"📋 Found {len(content_models)} models that support content generation:")
        print("=" * 80)
        
        # Show current model being used
        current_model = config.gemini_model
        print(f"🎯 Currently configured model: {current_model}")
        print()
        
        # List all available models
        for i, model in enumerate(content_models, 1):
            model_name = model.name
            
            # Highlight if this is the current model
            marker = "👈 CURRENT" if model_name == current_model else ""
            
            print(f"{i:2d}. {model_name} {marker}")
            
            # Show model details if available
            if hasattr(model, 'display_name') and model.display_name:
                print(f"    Display Name: {model.display_name}")
            
            if hasattr(model, 'description') and model.description:
                # Truncate long descriptions
                desc = model.description
                if len(desc) > 100:
                    desc = desc[:97] + "..."
                print(f"    Description: {desc}")
            
            # Show supported methods
            methods = getattr(model, 'supported_generation_methods', [])
            if methods:
                print(f"    Supported Methods: {', '.join(methods)}")
            
            # Show input/output token limits if available
            if hasattr(model, 'input_token_limit'):
                print(f"    Input Token Limit: {model.input_token_limit:,}")
            if hasattr(model, 'output_token_limit'):
                print(f"    Output Token Limit: {model.output_token_limit:,}")
            
            print()
        
        print("=" * 80)
        print("💡 Tips:")
        print("   - Models with 'flash' are optimized for speed")
        print("   - Models with 'pro' offer higher quality analysis") 
        print("   - Models with 'exp' are experimental versions")
        print(f"   - To change models, update GEMINI_MODEL environment variable")
        
    except Exception as e:
        print(f"❌ Error fetching models: {str(e)}")
        print("Please check your API key and internet connection.")

if __name__ == "__main__":
    list_gemini_models()