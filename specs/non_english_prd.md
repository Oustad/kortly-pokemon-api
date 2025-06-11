# Non-English Pokemon Card Support - Product Requirements Document
================================================================

Status: PLANNING - Future Enhancement
Created: 2025-06-11
Priority: P2 (Post-MVP)

## Executive Summary

This PRD outlines comprehensive multi-language support for the Pokemon Card Scanner, enabling accurate identification and pricing for non-English Pokemon cards. Currently, the system translates foreign names to English and shows English equivalent data, which provides functional but not fully accurate results for collectors of international cards.

## Current State (MVP Implementation)

### ✅ What We Have Now
- **Language Detection**: Gemini identifies card language (en, fr, ja, de, es, etc.)
- **Name Translation**: Automatic translation of foreign names to English (e.g., "Goupix" → "Vulpix")
- **Transparency**: Clear UI indicators when translation occurs
- **Fallback Support**: Graceful handling when foreign cards are encountered

### ⚠️ Current Limitations
- Shows English pricing data for non-English cards
- No access to language-specific market values
- Limited to Pokemon TCG API (English-only)
- No region-specific pricing or availability data

## Problem Statement

**Market Reality**: French, Japanese, and other non-English Pokemon cards often have different market values compared to their English equivalents. Current MVP provides functional results but may mislead collectors about actual card values.

**User Impact**: 
- International collectors get inaccurate pricing information
- Card shops dealing in multiple languages need manual verification
- Competitive players need to know tournament legality by region

## Market Research Summary

### Value Differences by Language
1. **Japanese Cards**: Often 20-50% higher value due to superior print quality and lower supply
2. **French Cards**: Generally 10-30% lower value than English in global market
3. **German Cards**: Similar to French, slightly lower demand outside German-speaking regions
4. **1st Edition/Special Sets**: Language differences can be 100%+ for rare cards

### Market Data Sources
- **TCGdx API**: Multi-language support for 10+ languages
- **Cardmarket**: European market data (German, French, Italian, Spanish)
- **Yahoo Auctions Japan**: Japanese market pricing
- **Regional TCG shops**: Local market data APIs

## Solution Options Analysis

### Option 1: TCGdx API Integration (Recommended)
**Scope**: Full multi-language card database with native pricing

**Advantages**:
- ✅ Native support for 10+ languages
- ✅ Language-specific card data and images
- ✅ Consistent API structure similar to Pokemon TCG API
- ✅ Active development and maintenance
- ✅ Free tier available

**Implementation**:
```python
# Pseudo-code for dual API approach
if language_info.detected_language == 'en':
    results = await pokemon_tcg_api.search(name)
else:
    results = await tcgdx_api.search(name, language=detected_language)
    fallback_results = await pokemon_tcg_api.search(translated_name)
```

**Estimated Effort**: 3-4 weeks
**Complexity**: Medium
**Cost**: Free tier + potential premium features

### Option 2: Regional Market API Integration
**Scope**: Add region-specific pricing sources

**Implementation**:
- Cardmarket API for European pricing
- Yahoo Auctions Japan for Japanese market
- eBay international for global comparison

**Advantages**:
- ✅ Real market pricing data
- ✅ Regional availability information
- ✅ Historical price trends

**Challenges**:
- ❌ Multiple API integrations to maintain
- ❌ Different data formats and rate limits
- ❌ Authentication complexity
- ❌ Data quality consistency issues

**Estimated Effort**: 6-8 weeks
**Complexity**: High
**Cost**: Multiple API subscriptions

### Option 3: Hybrid Translation + Notation
**Scope**: Enhanced current approach with better context

**Implementation**:
- Detect card language and region
- Provide English equivalent data with clear disclaimers
- Add estimated value adjustments based on language
- Link to appropriate regional marketplaces

**Advantages**:
- ✅ Minimal code changes
- ✅ Uses existing reliable APIs
- ✅ Clear user expectations

**Challenges**:
- ❌ Still not fully accurate
- ❌ Value adjustments based on assumptions
- ❌ Limited scalability

**Estimated Effort**: 1-2 weeks
**Complexity**: Low
**Cost**: Minimal

### Option 4: Community-Driven Database
**Scope**: User-contributed pricing and market data

**Implementation**:
- User submission system for non-English card pricing
- Community verification and moderation
- Integration with existing card identification

**Advantages**:
- ✅ Crowdsourced accuracy
- ✅ Community engagement
- ✅ Covers niche/rare cards

**Challenges**:
- ❌ Data quality control
- ❌ Moderation overhead
- ❌ Slow initial data population
- ❌ Potential bias and manipulation

**Estimated Effort**: 8-12 weeks
**Complexity**: High
**Cost**: Moderation and hosting costs

## Recommended Implementation Plan

### Phase 1: Research and Validation (2 weeks)
1. **TCGdx API Evaluation**
   - API endpoint testing
   - Data quality assessment
   - Rate limit and pricing analysis
   - Integration complexity review

2. **User Research**
   - Survey international card collectors
   - Interview card shop owners
   - Analyze current usage patterns
   - Validate market size and demand

### Phase 2: TCGdx Integration (3-4 weeks)
1. **Core Integration**
   - Add TCGdx client alongside existing Pokemon TCG client
   - Implement language-based routing logic
   - Create unified response format
   - Add comprehensive error handling

2. **UI Enhancements**
   - Language-specific result displays
   - Comparison views (native vs English equivalent)
   - Market source attribution
   - Regional availability indicators

### Phase 3: Advanced Features (2-3 weeks)
1. **Price Comparison**
   - Side-by-side native vs English pricing
   - Historical price trends by language
   - Market volatility indicators
   - Investment recommendations

2. **Regional Context**
   - Tournament legality by region
   - Shipping and import considerations
   - Currency conversion
   - Tax implications

### Phase 4: Quality and Optimization (1-2 weeks)
1. **Data Quality**
   - Cross-validation between sources
   - Automated data quality checks
   - User reporting system for errors
   - Regular data synchronization

2. **Performance**
   - Caching strategies for multi-API calls
   - Response time optimization
   - Fallback mechanisms
   - Load balancing

## Technical Architecture

### API Layer Design
```python
class MultiLanguageCardService:
    def __init__(self):
        self.pokemon_tcg_client = PokemonTcgClient()
        self.tcgdx_client = TCGdxClient()
        
    async def search_cards(self, search_params: Dict, language_info: LanguageInfo):
        if language_info.detected_language == 'en':
            return await self._search_english(search_params)
        else:
            return await self._search_multi_language(search_params, language_info)
            
    async def _search_multi_language(self, search_params, language_info):
        # Primary search in native language
        native_results = await self.tcgdx_client.search(
            search_params, 
            language=language_info.detected_language
        )
        
        # Fallback search in English for comparison
        if language_info.translated_name:
            english_results = await self.pokemon_tcg_client.search({
                **search_params,
                'name': language_info.translated_name
            })
        
        return self._merge_results(native_results, english_results)
```

### Data Model Extensions
```python
class MultiLanguageCard(BaseModel):
    # Existing fields...
    language: str
    original_name: str
    translated_names: Dict[str, str]
    regional_pricing: Dict[str, MarketPrice]
    availability_regions: List[str]
    tournament_legal_regions: List[str]
```

### UI Components
- Language selection dropdown
- Market source toggle (native vs international)
- Price comparison charts
- Regional availability map
- Currency conversion tools

## Cost-Benefit Analysis

### Implementation Costs
- **Development**: 8-10 weeks (1-2 developers)
- **TCGdx API**: Free tier initially, ~$50-200/month for higher usage
- **Infrastructure**: Additional caching and processing, ~$20-50/month
- **Maintenance**: ~20% of development time ongoing

### Business Benefits
- **Expanded Market**: Access to international collectors (30-40% of market)
- **Competitive Advantage**: First mover in multi-language card scanning
- **User Retention**: More accurate results increase user satisfaction
- **Premium Features**: Potential monetization through advanced regional data

### Risk Assessment
- **Technical Risk**: Medium - API dependencies and data quality
- **Market Risk**: Low - Clear demand from international users
- **Maintenance Risk**: Medium - Multiple API integrations to maintain

## Success Metrics

### Technical Metrics
- Multi-language query response time: <3 seconds
- Data accuracy rate: >95% for supported languages
- API uptime: >99.5% across all sources
- Cache hit rate: >70% for popular cards

### Business Metrics
- International user adoption: >25% of total users
- User satisfaction (non-English cards): >4.5/5
- Regional market coverage: 5+ major markets
- Revenue impact: 15-20% increase in premium subscriptions

## Future Roadmap

### Year 1: Foundation
- TCGdx integration for major languages (FR, DE, ES, IT, JA)
- Basic price comparison functionality
- Regional tournament legality data

### Year 2: Expansion
- Additional market data sources (Cardmarket, Yahoo Auctions)
- Historical price tracking and trends
- Mobile app with region detection

### Year 3: Advanced Features
- AI-powered price prediction by region
- Automated arbitrage opportunity detection
- Professional dealer tools and APIs

## Competitive Landscape

### Current Competitors
- **TCGPlayer**: English-only, strong North American focus
- **Cardmarket**: European focus, limited mobile experience
- **PriceCharting**: Multi-language data but limited AI features

### Competitive Advantages
- **AI Integration**: Advanced image recognition with language detection
- **Unified Experience**: Single app for global card data
- **Real-time Processing**: Instant results vs manual lookup
- **Mobile-First**: Optimized for on-the-go card scanning

## Technical Dependencies

### Required APIs
1. **TCGdx API**: Primary multi-language source
2. **Pokemon TCG API**: Fallback and comparison data
3. **Currency Exchange API**: Real-time conversion rates
4. **Geographic API**: Region detection and localization

### Infrastructure Requirements
- Enhanced caching layer for multiple API responses
- Queue system for batch processing
- Monitoring for multi-API health checks
- Backup data sources for high availability

## Implementation Risks and Mitigation

### Risk 1: API Rate Limits
**Mitigation**: Implement intelligent caching, request queuing, and multiple API keys

### Risk 2: Data Quality Inconsistencies
**Mitigation**: Cross-validation algorithms, user reporting system, manual verification for high-value cards

### Risk 3: Currency Fluctuation Impact
**Mitigation**: Real-time exchange rates, historical price normalization, clear timestamp indicators

### Risk 4: Regional Legal Compliance
**Mitigation**: Legal review for data usage, privacy compliance by region, clear terms of service

## Conclusion

Multi-language Pokemon card support represents a significant opportunity to expand the user base and provide more accurate results for international collectors. The recommended TCGdx integration approach balances implementation complexity with feature completeness, providing a clear path to market leadership in international card recognition.

The MVP's current translation approach successfully handles the most common use cases while providing transparency about limitations. This PRD outlines a clear evolution path that maintains backward compatibility while adding substantial value for international users.

**Recommendation**: Proceed with Phase 1 research and validation, followed by TCGdx integration if user demand and technical feasibility are confirmed.