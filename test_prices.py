#!/usr/bin/env python3
"""Test price data in responses."""

import requests
import json
import base64
from pathlib import Path

# Read and encode the image file
image_path = "/home/mats/code/kortly/pokemon-card-scanner/test_results/images/IMG_5400.HEIC"
with open(image_path, "rb") as f:
    image_data = base64.b64encode(f.read()).decode('utf-8')

# Test detailed response
payload = {
    "image": image_data,
    "filename": "IMG_5400.HEIC",
    "options": {
        "response_format": "detailed",
        "include_cost_tracking": False
    }
}

response = requests.post("http://localhost:8000/api/v1/scan", json=payload)
data = response.json()

if data.get('best_match'):
    print("Best match found:")
    print(f"  Name: {data['best_match'].get('name')}")
    print(f"  Market prices: {data['best_match'].get('market_prices')}")
else:
    print("No best match found")

# Test simplified response 
payload['options']['response_format'] = 'simplified'
response = requests.post("http://localhost:8000/api/v1/scan", json=payload)
data = response.json()

print("\nSimplified response:")
print(f"  Name: {data.get('name')}")
print(f"  Market prices: {data.get('market_prices')}")