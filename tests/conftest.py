"""Shared pytest fixtures for Zwift Racing Scraper tests.

This module provides reusable test fixtures including:
- Mock HTML responses for profile pages
- Mock JSON event data
- Test database setup/teardown
- Sample dataframes for testing
"""

from typing import Generator
import os
import pytest
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from database.engine import Base
from database.models import RiderProfile, RiderEvent


# ============================================================================
# Mock HTML Responses
# ============================================================================

@pytest.fixture
def mock_profile_html() -> str:
    """Returns a realistic mock HTML profile page from ZwiftPower.
    
    This fixture simulates the HTML structure returned by ZwiftPower's
    profile.php endpoint, including table data and inline JavaScript
    with Highcharts power metrics.
    
    Returns:
        str: Mock HTML content with profile data for ZID 1714370
    """
    return """
    <html>
    <body>
        <table>
            <tr>
                <th>Category</th>
                <td><span class="label-as-badge">A</span></td>
            </tr>
            <tr>
                <th>Racing Score</th>
                <td>652.3 points</td>
            </tr>
            <tr>
                <th>ZPoints</th>
                <td><b>7,301</b></td>
            </tr>
            <tr>
                <th>Country</th>
                <td>Uruguay</td>
            </tr>
            <tr>
                <th>Team</th>
                <td>Test Team</td>
            </tr>
            <tr>
                <th>zFTP</th>
                <td>285 watts</td>
            </tr>
            <tr>
                <th>Weight</th>
                <td>67.4 kg</td>
            </tr>
            <tr>
                <th>Age</th>
                <td>35</td>
            </tr>
        </table>
        <script>
        Highcharts.chart('container', {
            tooltip: {
                formatter: function() {
                    return '<b>15 seconds</b>: 650 <rsmall>watts</rsmall><br/>y: 85.5';
                }
            }
        });
        Highcharts.chart('container2', {
            tooltip: {
                formatter: function() {
                    return '<b>1 minute</b>: 420 <rsmall>watts</rsmall><br/>y: 78.2';
                }
            }
        });
        Highcharts.chart('container3', {
            tooltip: {
                formatter: function() {
                    return '<b>5 minutes</b>: 310 <rsmall>watts</rsmall><br/>y: 72.1';
                }
            }
        });
        Highcharts.chart('container4', {
            tooltip: {
                formatter: function() {
                    return '<b>20 minutes</b>: 290 <rsmall>watts</rsmall><br/>y: 68.9';
                }
            }
        });
        </script>
    </body>
    </html>
    """


@pytest.fixture
def mock_profile_html_minimal() -> str:
    """Returns minimal HTML profile with missing optional fields.
    
    Used to test parser robustness when some profile fields are absent.
    
    Returns:
        str: Minimal HTML with only required fields
    """
    return """
    <html>
    <body>
        <table>
            <tr>
                <th>Category</th>
                <td>B</td>
            </tr>
            <tr>
                <th>Country</th>
                <td>USA</td>
            </tr>
        </table>
    </body>
    </html>
    """


# ============================================================================
# Mock JSON Event Data
# ============================================================================

@pytest.fixture
def mock_event_json() -> dict:
    """Returns mock JSON event history data from ZwiftPower cache endpoint.
    
    Simulates the structure returned by cache3/profile/{zid}_all.json,
    including nested list values and Unix timestamps.
    
    Returns:
        dict: Mock JSON payload with event data
    """
    return {
        "data": [
            {
                "DT_RowId": "row_12345",
                "ftp": 285,
                "friend": 0,
                "pt": "A",
                "label": 1,
                "zid": 1714370,
                "pos": 5,
                "position_in_cat": 3,
                "name": "Test Rider",
                "cp": 100,
                "zwid": 123456,
                "res_id": "5703166.23",
                "lag": 0,
                "uid": 987654321,
                "time": ["3600.5", 0],
                "time_gun": 3605.2,
                "gap": 12.3,
                "vtta": "",
                "vttat": 0.0,
                "male": 1,
                "tid": 456,
                "topen": "1",
                "tname": "Test Event",
                "tc": "#FF0000",
                "tbc": "#000000",
                "tbd": "",
                "zeff": 95,
                "category": "A",
                "height": ["175", 0],
                "flag": "uy",
                "avg_hr": 165,
                "max_hr": 185,
                "hrmax": 190,
                "hrm": 1,
                "weight": ["67.4", 0],
                "power_type": 1,
                "display_pos": 5,
                "src": 1,
                "age": "35",
                "zada": 0,
                "note": "",
                "div": 0,
                "divw": 0,
                "skill": 850,
                "skill_b": 800,
                "skill_gain": 50,
                "np": 280,
                "hrr": 0.87,
                "hreff": 92,
                "avg_power": 275,
                "avg_wkg": ["4.08", 0],
                "wkg_ftp": 4.23,
                "wftp": 285,
                "wkg_guess": 0,
                "wkg1200": 3.8,
                "wkg300": 5.2,
                "wkg120": 5.8,
                "wkg60": 6.5,
                "wkg30": 7.2,
                "wkg15": 8.1,
                "wkg5": 9.5,
                "w1200": 256,
                "w300": 350,
                "w120": 391,
                "w60": 438,
                "w30": 485,
                "w15": 546,
                "w5": 640,
                "is_guess": 0,
                "upg": 0,
                "penalty": "",
                "reg": 1,
                "fl": "",
                "pts": "100",
                "pts_pos": "5",
                "info": 0,
                "info_notes": "",
                "strike": 0,
                "event_title": "Test Race Series",
                "f_t": "race",
                "distance": 42.5,
                "event_date": 1695052800,
                "rt": 1695052800000,
                "laps": 3,
                "dur": 3600,
                "query_zid": 1714370
            },
            {
                "DT_RowId": "row_12346",
                "ftp": 285,
                "friend": 0,
                "pt": "A",
                "label": 1,
                "zid": 1714370,
                "pos": 8,
                "position_in_cat": 5,
                "name": "Test Rider",
                "cp": 100,
                "zwid": 123456,
                "res_id": "5703167.45",
                "lag": 0,
                "uid": 987654321,
                "time": ["3720.8", 0],
                "time_gun": 3725.5,
                "gap": 25.6,
                "vtta": "",
                "vttat": 0.0,
                "male": 1,
                "tid": 457,
                "topen": "1",
                "tname": "Another Test Event",
                "tc": "#00FF00",
                "tbc": "#FFFFFF",
                "tbd": "",
                "zeff": 93,
                "category": "A",
                "height": ["175", 0],
                "flag": "uy",
                "avg_hr": 162,
                "max_hr": 182,
                "hrmax": 190,
                "hrm": 1,
                "weight": ["67.4", 0],
                "power_type": 1,
                "display_pos": 8,
                "src": 1,
                "age": "35",
                "zada": 0,
                "note": "",
                "div": 0,
                "divw": 0,
                "skill": 845,
                "skill_b": 850,
                "skill_gain": -5,
                "np": 270,
                "hrr": 0.85,
                "hreff": 90,
                "avg_power": 265,
                "avg_wkg": ["3.93", 0],
                "wkg_ftp": 4.23,
                "wftp": 285,
                "wkg_guess": 0,
                "wkg1200": 3.7,
                "wkg300": 5.0,
                "wkg120": 5.6,
                "wkg60": 6.3,
                "wkg30": 7.0,
                "wkg15": 7.9,
                "wkg5": 9.2,
                "w1200": 249,
                "w300": 337,
                "w120": 377,
                "w60": 425,
                "w30": 472,
                "w15": 532,
                "w5": 620,
                "is_guess": 0,
                "upg": 0,
                "penalty": "",
                "reg": 1,
                "fl": "",
                "pts": "85",
                "pts_pos": "8",
                "info": 0,
                "info_notes": "",
                "strike": 0,
                "event_title": "Test Race Series 2",
                "f_t": "race",
                "distance": 38.2,
                "event_date": 1694966400,
                "rt": 1694966400000,
                "laps": 2,
                "dur": 3720,
                "query_zid": 1714370
            }
        ]
    }


@pytest.fixture
def mock_empty_event_json() -> dict:
    """Returns empty event history JSON (no races found).
    
    Returns:
        dict: Empty data payload
    """
    return {"data": []}


# ============================================================================
# Sample DataFrames
# ============================================================================

@pytest.fixture
def sample_profile_df() -> pd.DataFrame:
    """Returns a sample profile DataFrame for testing transformations.
    
    Returns:
        pd.DataFrame: Sample profile data with various data types
    """
    return pd.DataFrame([
        {
            "zid": "1714370",
            "cat": "A",
            "racing_score": "652.3 points",
            "zpoints": "7,301",
            "country": "Uruguay",
            "team": "Test Team",
            "zftp": "285 watts",
            "weight": "67.4 kg",
            "age": "35",
            "watts_15s": 650,
            "pct_15s": 85.5,
            "watts_1m": 420,
            "pct_1m": 78.2,
            "watts_5m": 310,
            "pct_5m": 72.1,
            "watts_20m": 290,
            "pct_20m": 68.9
        }
    ])


@pytest.fixture
def sample_events_df() -> pd.DataFrame:
    """Returns a sample events DataFrame with list columns and timestamps.
    
    Returns:
        pd.DataFrame: Sample event data requiring unpacking and formatting
    """
    return pd.DataFrame([
        {
            "zid": 1714370,
            "res_id": "5703166.23",
            "name": "Test Rider",
            "pos": 5,
            "time": ["3600.5", 0],
            "weight": ["67.4", 0],
            "avg_wkg": ["4.08", 0],
            "event_date": 1695052800,
            "event_title": "Test Race",
            "query_zid": 1714370
        },
        {
            "zid": 1714370,
            "res_id": "5703167.45",
            "name": "Test Rider",
            "pos": 8,
            "time": ["3720.8", 0],
            "weight": ["67.4", 0],
            "avg_wkg": ["3.93", 0],
            "event_date": 1694966400,
            "event_title": "Another Test Race",
            "query_zid": 1714370
        }
    ])


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def test_db_engine():
    """Creates an in-memory SQLite database engine for testing.
    
    This fixture provides an isolated database for each test function,
    ensuring tests don't interfere with each other or production data.
    
    Yields:
        Engine: SQLAlchemy engine connected to in-memory SQLite database
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def test_db_session(test_db_engine) -> Generator[Session, None, None]:
    """Creates a database session for testing with automatic rollback.
    
    Args:
        test_db_engine: The test database engine fixture
        
    Yields:
        Session: SQLAlchemy session for database operations
    """
    SessionLocal = sessionmaker(bind=test_db_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def sample_rider_profile() -> dict:
    """Returns sample data for creating a RiderProfile model instance.
    
    Returns:
        dict: Valid profile data matching RiderProfile schema
    """
    return {
        "zid": 1714370,
        "fetched_at": pd.Timestamp.now(),
        "cat": "A",
        "racing_score": 652.3,
        "zpoints": 7301.0,
        "country": "Uruguay",
        "team": "Test Team",
        "zftp": 285.0,
        "weight": 67.4,
        "age": "35",
        "watts_15s": 650,
        "pct_15s": 85.5,
        "watts_1m": 420,
        "pct_1m": 78.2,
        "watts_5m": 310,
        "pct_5m": 72.1,
        "watts_20m": 290,
        "pct_20m": 68.9
    }


@pytest.fixture
def sample_rider_event() -> dict:
    """Returns sample data for creating a RiderEvent model instance.
    
    Returns:
        dict: Valid event data matching RiderEvent schema
    """
    return {
        "zid": 1714370,
        "res_id": "5703166.23",
        "name": "Test Rider",
        "pos": 5,
        "position_in_cat": 3,
        "ftp": 285,
        "time": 3600.5,
        "weight": 67.4,
        "avg_wkg": 4.08,
        "avg_power": 275,
        "event_date": pd.Timestamp("2023-09-18"),
        "event_title": "Test Race",
        "distance": 42.5,
        "query_zid": 1714370
    }


# ============================================================================
# Environment Fixtures
# ============================================================================

@pytest.fixture
def mock_env_vars(monkeypatch) -> None:
    """Sets up mock environment variables for testing authentication.
    
    Args:
        monkeypatch: pytest's monkeypatch fixture for modifying environment
    """
    monkeypatch.setenv("PHPBB3_SID", "test_session_id_12345")
    monkeypatch.setenv("PHPBB3_U", "test_user_67890")
    monkeypatch.setenv("CLOUDFRONT_KEY_PAIR_ID", "test_key_pair_id")
    monkeypatch.setenv("CLOUDFRONT_POLICY", "test_policy_string")
    monkeypatch.setenv("CLOUDFRONT_SIGNATURE", "test_signature_hash")
    monkeypatch.setenv("DB_USER", "test_user")
    monkeypatch.setenv("DB_PASS", "test_pass")
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "test_db")


@pytest.fixture
def mock_empty_env_vars(monkeypatch) -> None:
    """Clears all ZwiftPower environment variables for testing missing auth.
    
    Args:
        monkeypatch: pytest's monkeypatch fixture for modifying environment
    """
    for key in ["PHPBB3_SID", "PHPBB3_U", "CLOUDFRONT_KEY_PAIR_ID", 
                "CLOUDFRONT_POLICY", "CLOUDFRONT_SIGNATURE"]:
        monkeypatch.delenv(key, raising=False)
