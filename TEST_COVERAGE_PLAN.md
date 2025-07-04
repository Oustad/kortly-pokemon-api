# Pokemon Card Scanner - Test Coverage Improvement Plan

This document outlines the current state of test coverage and a comprehensive plan to improve unit test coverage across the codebase.

## 📊 Current Test Coverage Analysis

### **Existing Tests**
- **Basic API Tests**: `tests/test_basic.py` - Simple health check and basic scan test
- **Utility Tests**: 
  - `tests/test_image_processor.py` - Basic image processing tests
  - `tests/test_middleware.py` - Middleware functionality tests
- **Accuracy Testing**: `simple_accuracy_tester.py` - End-to-end accuracy testing tool (not unit tests)

### **Coverage Gaps**
The following critical components have **NO unit tests**:
- **Core Services**:
  - `gemini_service.py` - AI model integration
  - `tcg_client.py` - Pokemon TCG API client
  - `processing_pipeline.py` - Main orchestration logic
  - `quality_assessment.py` - Image quality evaluation
  - `webhook_service.py` - Webhook notifications
  - `metrics_service.py` - Metrics collection
- **Route Handlers**:
  - `scan.py` - Main scanning endpoint (2,541 lines!)
  - Complex matching logic
  - Error handling paths
- **Utilities**:
  - Card matching algorithms
  - Response parsing logic
  - Scoring calculations

### **Test Infrastructure**
- **Framework**: pytest (already configured)
- **Coverage Tools**: Not configured
- **CI/CD**: GitHub Actions workflow exists but minimal

---

## 🎯 Unit Test Coverage Plan

### **Phase 1: Test Infrastructure Setup** (2-3 hours)

#### 1.1 Install Coverage Tools
```bash
pip install pytest-cov coverage
```

#### 1.2 Create Coverage Configuration
Create `.coveragerc`:
```ini
[run]
source = src/
omit = 
    */tests/*
    */venv/*
    */__pycache__/*

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
```

#### 1.3 Update pytest Configuration
Create/update `pytest.ini`:
```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = --cov=src --cov-report=html --cov-report=term-missing
```

#### 1.4 Organize Test Structure
```
tests/
├── unit/
│   ├── services/
│   │   ├── test_gemini_service.py
│   │   ├── test_tcg_client.py
│   │   ├── test_processing_pipeline.py
│   │   └── test_quality_assessment.py
│   ├── routes/
│   │   └── test_scan.py
│   └── utils/
│       ├── test_image_processor.py
│       └── test_middleware.py
├── conftest.py  # Shared fixtures
└── __init__.py
```

---

### **Phase 2: Core Service Unit Tests** (8-10 hours)

#### 2.1 Gemini Service Tests (`test_gemini_service.py`)
```python
# Test cases to implement:
- test_gemini_service_initialization
- test_analyze_card_success
- test_analyze_card_retry_logic
- test_analyze_card_max_retries_exceeded
- test_prompt_generation
- test_response_parsing
- test_invalid_image_handling
- test_api_key_configuration
```

#### 2.2 TCG Client Tests (`test_tcg_client.py`)
```python
# Test cases to implement:
- test_tcg_client_initialization
- test_search_cards_success
- test_search_cards_with_filters
- test_search_cards_empty_results
- test_search_cards_api_error
- test_response_parsing
- test_pagination_handling
- test_rate_limiting
```

#### 2.3 Processing Pipeline Tests (`test_processing_pipeline.py`)
```python
# Test cases to implement:
- test_pipeline_initialization
- test_process_image_full_flow
- test_gemini_failure_handling
- test_tcg_search_failure_handling
- test_quality_threshold_rejection
- test_pipeline_metrics_collection
- test_webhook_notification_trigger
```

#### 2.4 Quality Assessment Tests (`test_quality_assessment.py`)
```python
# Test cases to implement:
- test_assess_quality_good_image
- test_assess_quality_blurry_image
- test_assess_quality_dark_image
- test_assess_quality_overexposed_image
- test_quality_score_calculation
- test_quality_feedback_generation
```

---

### **Phase 3: Route Handler Unit Tests** (6-8 hours)

#### 3.1 Scan Route Tests (`test_scan.py`)
Break down the massive scan.py into testable components first, then test:
```python
# Test cases to implement:
- test_scan_endpoint_success
- test_scan_endpoint_invalid_image
- test_scan_endpoint_quality_rejection
- test_scan_endpoint_no_matches_found
- test_match_scoring_algorithm
- test_variant_matching_logic
- test_set_size_extraction
- test_authenticity_filtering
- test_scratch_detection_logic
- test_error_response_formatting
```

#### 3.2 Health/Metrics Route Tests
```python
# Test cases to implement:
- test_health_check_healthy
- test_health_check_unhealthy
- test_metrics_endpoint
- test_ready_endpoint
```

---

### **Phase 4: Utility and Helper Tests** (4-5 hours)

#### 4.1 Enhanced Image Processor Tests
```python
# Additional test cases:
- test_image_resize_various_dimensions
- test_image_format_conversion
- test_image_enhancement
- test_invalid_image_handling
```

#### 4.2 Webhook Service Tests
```python
# Test cases to implement:
- test_webhook_notification_success
- test_webhook_retry_logic
- test_webhook_timeout_handling
- test_webhook_disabled_configuration
```

#### 4.3 Metrics Service Tests
```python
# Test cases to implement:
- test_metrics_collection
- test_metrics_aggregation
- test_metrics_export
```

---

### **Phase 5: Test Fixtures and Mocking** (3-4 hours)

#### 5.1 Common Fixtures (`conftest.py`)
```python
# Fixtures to create:
- sample_images (various quality levels)
- mock_gemini_responses
- mock_tcg_responses
- mock_pipeline_results
- test_configuration
```

#### 5.2 Mock Strategies
- Mock external API calls (Gemini, TCG)
- Mock file system operations
- Mock image processing operations
- Mock webhook HTTP requests

---

## 📈 Coverage Goals

### **Minimum Coverage Targets**
- **Overall**: 80% line coverage
- **Core Services**: 90% coverage
- **Routes**: 85% coverage  
- **Utilities**: 80% coverage

### **Critical Path Coverage**
Ensure 100% coverage for:
- Error handling paths
- Card matching algorithms
- Quality assessment logic
- Security/authentication

### **Coverage Reporting**
- Generate HTML coverage reports
- Add coverage badge to README
- Include coverage in CI/CD pipeline
- Fail builds if coverage drops below threshold

---

## 🚀 Implementation Priority

### **Week 1: Foundation**
1. Set up test infrastructure and coverage tools
2. Create test directory structure
3. Write common fixtures and mocks
4. Start with Gemini service tests

### **Week 2: Core Services**
1. Complete TCG client tests
2. Complete processing pipeline tests
3. Complete quality assessment tests
4. Achieve 90% coverage for services

### **Week 3: Routes and Integration**
1. Refactor scan.py for better testability
2. Write comprehensive scan endpoint tests
3. Complete remaining route tests
4. Achieve 85% coverage for routes

### **Week 4: Polish and Maintenance**
1. Fill remaining coverage gaps
2. Add edge case tests
3. Document testing best practices
4. Set up automated coverage reporting

---

## 🛠️ Tools and Dependencies

### **Required Packages**
```txt
pytest>=7.0.0
pytest-cov>=4.0.0
pytest-mock>=3.10.0
pytest-asyncio>=0.20.0
responses>=0.22.0  # For mocking HTTP requests
Pillow>=9.0.0  # For creating test images
factory-boy>=3.2.0  # For test data generation
```

### **Development Tools**
- Coverage.py for coverage analysis
- pytest-html for test reporting
- pytest-xdist for parallel test execution

---

## 📝 Best Practices

### **Test Structure**
- Use AAA pattern: Arrange, Act, Assert
- One assertion per test when possible
- Descriptive test names that explain the scenario
- Group related tests in classes

### **Mocking Strategy**
- Mock at the boundary (external services)
- Use real implementations for internal logic
- Verify mock interactions when important
- Keep mocks simple and focused

### **Test Data**
- Use factories for complex objects
- Keep test data minimal but realistic
- Use parametrized tests for multiple scenarios
- Store large test fixtures separately

### **Performance**
- Keep unit tests fast (<100ms per test)
- Use pytest marks for slow tests
- Run unit tests in parallel
- Mock expensive operations

---

## 🎯 Success Criteria

1. **Coverage**: Achieve 80%+ overall line coverage
2. **Speed**: Full unit test suite runs in <30 seconds
3. **Reliability**: Zero flaky tests
4. **Maintainability**: Easy to add new tests
5. **Documentation**: Clear test descriptions and assertions

---

## 📅 Timeline

**Total Estimated Time**: 23-30 hours

This can be implemented incrementally without disrupting development:
- Start with highest-risk components (Gemini service, matching logic)
- Add tests alongside new features
- Gradually improve coverage over 4-6 weeks

---

*Created: 2025-07-04*
*Status: Ready for implementation after cleanup phase*
*Priority: High - Critical for maintainability and reliability*