# Test Suite Documentation

## Overview

This comprehensive test suite provides extensive coverage for the Zwift Racing Scraper project, including unit tests, integration tests, and database tests.

## Test Structure

```
tests/
├── __init__.py                    # Test package initialization
├── conftest.py                    # Shared pytest fixtures
├── test_zwiftpower_client.py     # ZwiftPowerClient tests
├── test_data_pipeline.py         # DataPipeline transformation tests
├── test_database.py              # Database model and operation tests
└── test_integration.py           # End-to-end integration tests
```

## Installation

Install testing dependencies:

```bash
pip install -r requirements-dev.txt
```

## Running Tests

### Run All Tests
```bash
pytest
```

### Run Specific Test File
```bash
pytest tests/test_zwiftpower_client.py
pytest tests/test_data_pipeline.py
pytest tests/test_database.py
pytest tests/test_integration.py
```

### Run Specific Test Class
```bash
pytest tests/test_zwiftpower_client.py::TestAuthentication
pytest tests/test_data_pipeline.py::TestUnpackListColumns
```

### Run Specific Test Function
```bash
pytest tests/test_zwiftpower_client.py::TestAuthentication::test_authenticate_with_valid_cookies
```

### Run with Coverage Report
```bash
pytest --cov=. --cov-report=html
```

Then open `htmlcov/index.html` in your browser to view the coverage report.

### Run Tests in Parallel
```bash
pytest -n auto
```

### Run Only Fast Tests (Skip Slow Tests)
```bash
pytest -m "not slow"
```

## Test Coverage Areas

### 1. ZwiftPowerClient Tests ([`test_zwiftpower_client.py`](tests/test_zwiftpower_client.py))

**Authentication Tests:**
- ✅ Valid cookie loading from environment
- ✅ Missing cookie handling
- ✅ Partial cookie handling

**Profile Parsing Tests:**
- ✅ Complete HTML profile parsing
- ✅ Minimal HTML with missing fields
- ✅ Empty HTML handling
- ✅ Malformed HTML handling

**Profile Fetching Tests:**
- ✅ Successful multi-ZID fetching
- ✅ HTTP error handling (403, 404)
- ✅ Exception handling
- ✅ Rate limiting verification

**Event History Tests:**
- ✅ Successful event fetching
- ✅ Empty event history
- ✅ 404 responses
- ✅ Malformed JSON handling
- ✅ Multiple ZID concatenation
- ✅ Required AJAX headers

**Session Verification Tests:**
- ✅ Successful verification
- ✅ Expired cookie detection
- ✅ Unexpected status codes

### 2. DataPipeline Tests ([`test_data_pipeline.py`](tests/test_data_pipeline.py))

**List Column Unpacking:**
- ✅ Basic list unpacking
- ✅ Numeric conversion after unpacking
- ✅ Tuple handling
- ✅ Empty list handling
- ✅ Mixed type handling
- ✅ NaN value handling

**Numeric Column Cleaning:**
- ✅ Extraction from strings with units (e.g., "67.4 kg")
- ✅ Already numeric columns
- ✅ Negative numbers
- ✅ Decimal-only numbers
- ✅ Strings without numbers
- ✅ Mixed formats

**Date Formatting:**
- ✅ Unix timestamp to YYYY/MM/DD conversion
- ✅ Descending date sorting
- ✅ Custom column names
- ✅ Missing columns
- ✅ Invalid timestamps
- ✅ String timestamps

**CSV Export:**
- ✅ Basic export functionality
- ✅ Directory creation
- ✅ UTF-8 encoding for special characters
- ✅ Empty DataFrame handling
- ✅ Index exclusion
- ✅ Large DataFrame handling

### 3. Database Tests ([`test_database.py`](tests/test_database.py))

**Initialization Tests:**
- ✅ Table creation
- ✅ Idempotent initialization
- ✅ Column verification
- ✅ Primary key constraints

**RiderProfile Model Tests:**
- ✅ Record creation
- ✅ Unique constraint (zid, fetched_at)
- ✅ Multiple timestamps for same ZID
- ✅ Nullable fields
- ✅ Power metrics storage

**RiderEvent Model Tests:**
- ✅ Record creation
- ✅ Composite primary key uniqueness
- ✅ Multiple events per ZID
- ✅ Power metrics storage
- ✅ String res_id precision preservation

**Custom Insertion Method Tests:**
- ✅ New record insertion
- ✅ Duplicate silently ignored
- ✅ Mixed new and duplicate handling
- ✅ Empty DataFrame handling

### 4. Integration Tests ([`test_integration.py`](tests/test_integration.py))

**Full Pipeline Tests:**
- ✅ Profile scraping to DataFrame
- ✅ Event scraping to DataFrame
- ✅ Profile to database insertion
- ✅ Event to database insertion

**Chunked Insertion Tests:**
- ✅ Small dataset (< chunk size)
- ✅ Large dataset (> chunk size)
- ✅ Duplicates across chunks

**Error Handling Tests:**
- ✅ Partial failure continuation
- ✅ Network error recovery
- ✅ Invalid data filtering
- ✅ Empty string to NULL conversion

**Cookie Refresh Tests:**
- ✅ Automatic refresh on expiration
- ✅ Failed refresh handling

**Data Consistency Tests:**
- ✅ ZID consistency across pipeline
- ✅ Data type consistency
- ✅ No data loss in transformations

**Performance Tests:**
- ✅ Large batch insertion
- ✅ Multiple ZID concurrent processing

## Fixtures

### Mock Data Fixtures ([`conftest.py`](tests/conftest.py))

- `mock_profile_html` - Complete HTML profile page
- `mock_profile_html_minimal` - Minimal HTML with missing fields
- `mock_event_json` - JSON event history data
- `mock_empty_event_json` - Empty event history
- `sample_profile_df` - Sample profile DataFrame
- `sample_events_df` - Sample events DataFrame

### Database Fixtures

- `test_db_engine` - In-memory SQLite database engine
- `test_db_session` - Database session with automatic rollback
- `sample_rider_profile` - Valid profile data dict
- `sample_rider_event` - Valid event data dict

### Environment Fixtures

- `mock_env_vars` - Mock environment variables for authentication
- `mock_empty_env_vars` - Cleared environment variables

## Configuration

### pytest.ini

The [`pytest.ini`](pytest.ini) file configures:
- Test discovery patterns
- Verbose output with local variables
- Coverage reporting (HTML, terminal, XML)
- Custom test markers
- Coverage exclusions

### Coverage Goals

- **Target Coverage:** 80%+ overall
- **Critical Paths:** 90%+ coverage
- **Integration Tests:** Focus on real-world scenarios

## Best Practices

1. **Isolation:** Each test is independent and doesn't affect others
2. **Mocking:** External dependencies (HTTP, database) are mocked
3. **Fixtures:** Reusable test data via pytest fixtures
4. **Descriptive Names:** Test names clearly describe what they validate
5. **Docstrings:** All tests have docstrings explaining their purpose
6. **Type Hints:** All test functions use type hints
7. **Assertions:** Clear, specific assertions with helpful messages

## Continuous Integration

To integrate with CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    pip install -r requirements-dev.txt
    pytest --cov=. --cov-report=xml
    
- name: Upload coverage
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
```

## Troubleshooting

### Import Errors

If you encounter import errors, ensure you're running pytest from the project root:

```bash
cd /path/to/zwift_racing_scrap
pytest
```

### Database Tests Failing

Database tests use SQLite in-memory databases. If tests fail:
1. Check that SQLAlchemy is installed
2. Verify database models are correctly defined
3. Ensure fixtures are properly set up

### Mock Issues

If mocking isn't working:
1. Verify the patch path matches the import location
2. Check that `pytest-mock` is installed
3. Ensure fixtures are properly injected

## Adding New Tests

When adding new functionality:

1. **Create test file** if needed (follow naming convention `test_*.py`)
2. **Add fixtures** to `conftest.py` if reusable
3. **Write tests** following existing patterns
4. **Update this README** with new coverage areas
5. **Run tests** to ensure they pass
6. **Check coverage** to ensure adequate coverage

## Example Test

```python
def test_example_functionality(mock_env_vars: None) -> None:
    """Validates example functionality works correctly.
    
    Args:
        mock_env_vars: Fixture providing mock environment variables
    """
    # Arrange
    client = ZwiftPowerClient()
    
    # Act
    result = client.some_method()
    
    # Assert
    assert result is not None
    assert result.status == "success"
```

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-mock Documentation](https://pytest-mock.readthedocs.io/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [SQLAlchemy Testing](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites)
