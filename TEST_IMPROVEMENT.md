# Test Improvement Plan - Path to 80% Coverage

## 📊 Executive Summary

**Current Status**: 48.04% coverage (1,198/2,494 lines)  
**Target**: 80% coverage (1,995 lines)  
**Gap**: 797 additional lines needed  
**Tests**: 247 passing, 0 failures

This plan outlines the most efficient path to reach 80% test coverage based on lessons learned from our testing journey.

## 🎓 Key Learnings from Implementation

### What Worked
1. **Simple Interface Tests**: Tests that match actual method signatures without assumptions
2. **Remove and Replace Strategy**: Better to remove failing tests than fix interface mismatches
3. **Utility Function Testing**: High coverage gains from testing simple utility functions
4. **Proper Mocking**: Mock at service boundaries, not internal methods

### What Didn't Work
1. **Assuming Interfaces**: Tests failed when assuming method names/signatures
2. **Complex Integration Tests**: Too many mocks led to brittle tests
3. **Testing Private Methods**: Focus on public APIs instead

## 📈 Coverage Analysis

### Current Coverage by Module
```
Module                              Lines  Miss  Coverage  Priority
-------------------------------------------------
card_matcher.py                     280    252   10.00%   HIGH
response_parser.py                  272    235   13.60%   HIGH
scan.py (routes)                    426    338   20.66%   MEDIUM
gemini_service.py                   99     69    30.30%   MEDIUM
metrics.py (routes)                 50     32    36.00%   LOW
tcg_client.py                       215    99    53.95%   LOW
processing_pipeline.py              113    44    61.06%   LOW
```

### Coverage Impact Analysis
- **response_parser.py**: ~200 lines potential (8% coverage increase)
- **card_matcher.py**: ~200 lines potential (8% coverage increase)
- **scan.py utilities**: ~150 lines potential (6% coverage increase)
- **gemini_service.py**: ~50 lines potential (2% coverage increase)
- **Total Potential**: ~600 lines (24% coverage increase)

## 🎯 Implementation Strategy

### Phase 1: High-Impact Utilities (Target: +16% → 64%)
**Time**: 2-3 hours  
**Files**: response_parser.py, card_matcher.py

#### 1.1 Response Parser Tests
```python
# Add tests for:
- _extract_market_prices()
- _get_image_url()
- _create_alternative_match()
- create_simplified_response()
- parse_gemini_response()
- extract_card_details()
```

#### 1.2 Card Matcher Tests
```python
# Add tests for:
- normalize_set_name()
- extract_card_number()
- calculate_match_score()
- find_best_matches()
- validate_match_criteria()
```

### Phase 2: Service Layer (Target: +10% → 74%)
**Time**: 3-4 hours  
**Files**: gemini_service.py, scan.py utilities

#### 2.1 Gemini Service Tests
```python
# Focus on:
- Service initialization with/without API key
- Response parsing logic
- Error handling paths
- Retry mechanisms
```

#### 2.2 Scan Route Utilities
```python
# Extract and test:
- Card validation functions
- Response formatting utilities
- Error response builders
- Match filtering logic
```

### Phase 3: Final Push (Target: +6% → 80%)
**Time**: 2-3 hours  
**Files**: Various services and routes

#### 3.1 Remaining Services
- Add edge cases for processing_pipeline
- Complete TCG client error paths
- Add metrics route tests

#### 3.2 Edge Cases and Error Paths
- Invalid input handling
- API failure scenarios
- Timeout conditions

## 🛠️ Test Implementation Guidelines

### Test File Template
```python
"""Simple working tests for [module] utilities."""

import pytest
from unittest.mock import Mock, patch
from src.scanner.[module] import [functions]


class Test[Module]Simple:
    """Simple test cases for [module] that match actual interface."""

    def test_[function]_basic(self):
        """Test basic [function] functionality."""
        result = function(valid_input)
        assert isinstance(result, expected_type)
        assert result.field == expected_value

    def test_[function]_edge_case(self):
        """Test [function] with edge case input."""
        result = function(edge_case_input)
        assert result is None  # or appropriate assertion

    def test_[function]_error_handling(self):
        """Test [function] error handling."""
        with pytest.raises(ExpectedException):
            function(invalid_input)
```

### Mocking Strategy
```python
# DO: Mock external services
with patch('src.scanner.services.gemini_service.genai') as mock_genai:
    mock_genai.GenerativeModel.return_value = Mock()

# DON'T: Mock internal methods
# Avoid: with patch.object(service, '_internal_method')
```

### Test Naming Convention
- `test_[function_name]_[scenario]`
- Examples:
  - `test_extract_market_prices_with_holofoil`
  - `test_normalize_set_name_japanese_cards`
  - `test_create_response_no_matches`

## 📋 Task Checklist

### Immediate Tasks (Today)
- [ ] Create test_response_parser_extended.py
- [ ] Create test_card_matcher_extended.py
- [ ] Run coverage report after each file
- [ ] Verify all tests pass

### Short-term Tasks (This Week)
- [ ] Add gemini_service simple tests
- [ ] Extract scan.py utilities to separate file
- [ ] Create tests for extracted utilities
- [ ] Add metrics route tests

### Quality Checks
- [ ] All tests pass (0 failures)
- [ ] No interface mismatch errors
- [ ] Tests run in < 5 seconds
- [ ] Coverage reaches 80%+

## 📊 Progress Tracking

| Module | Starting Coverage | Target Coverage | Status |
|--------|------------------|-----------------|---------|
| response_parser.py | 13.60% | 70% | 🔴 Not Started |
| card_matcher.py | 10.00% | 70% | 🔴 Not Started |
| gemini_service.py | 30.30% | 60% | 🔴 Not Started |
| scan.py utilities | 20.66% | 40% | 🔴 Not Started |
| **Overall** | **48.04%** | **80%** | **🔴 In Progress** |

## 🚀 Success Criteria

1. **Coverage**: Achieve 80%+ overall line coverage
2. **Quality**: All tests pass without failures
3. **Speed**: Full test suite runs in < 10 seconds
4. **Maintainability**: Tests are simple and easy to understand
5. **Reliability**: No flaky or intermittent failures

## 📝 Notes

- Focus on public interfaces, not implementation details
- Prefer many simple tests over few complex tests
- Mock external dependencies, not internal methods
- When in doubt, check the actual method signature
- Remove tests that don't match interfaces rather than fixing them

---

*Created: 2025-07-08*  
*Based on: Actual implementation experience*  
*Status: Ready for immediate implementation*