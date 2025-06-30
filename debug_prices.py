#!/usr/bin/env python3
"""Debug price data issue."""

import asyncio
import logging
from src.scanner.services.tcg_client import PokemonTcgClient

logging.basicConfig(level=logging.INFO)

async def main():
    client = PokemonTcgClient()
    
    # Search for Machamp cards
    results = await client.search_cards(name="Machamp", number="68")
    
    print(f"Found {len(results.get('data', []))} cards")
    
    for card in results.get('data', [])[:5]:
        print(f"\nCard: {card.get('name')} #{card.get('number')}")
        print(f"  Set: {card.get('set', {}).get('name')}")
        print(f"  ID: {card.get('id')}")
        print(f"  Market prices: {card.get('tcgplayer', {}).get('prices')}")

asyncio.run(main())