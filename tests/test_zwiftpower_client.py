"""Tests for ZwiftPowerClient class.

This module tests the HTTP client functionality including:
- Authentication with valid/invalid cookies
- Profile HTML parsing
- Event history JSON parsing
- Session verification
"""

from typing import Any
from unittest.mock import Mock, patch, MagicMock
import pytest
import pandas as pd
from all_in_one import ZwiftPowerClient, CookieExpiredError


# ============================================================================
# Authentication Tests
# ============================================================================

class TestAuthentication:
    """Test suite for ZwiftPowerClient authentication functionality."""

    def test_authenticate_with_valid_cookies(self, mock_env_vars: None) -> None:
        """Validates that valid environment cookies are loaded into session.
        
        Args:
            mock_env_vars: Fixture providing mock environment variables
        """
        with patch('all_in_one.requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            client = ZwiftPowerClient()
            
            # Verify cookies were updated in session
            assert mock_session.cookies.update.called
            call_args = mock_session.cookies.update.call_args[0][0]
            
            assert "phpbb3_lswlk_sid" in call_args
            assert "phpbb3_lswlk_u" in call_args
            assert "CloudFront-Key-Pair-Id" in call_args
            assert call_args["phpbb3_lswlk_sid"] == "test_session_id_12345"

    def test_authenticate_with_missing_cookies(self, mock_empty_env_vars: None) -> None:
        """Validates behavior when no cookies are present in environment.
        
        Args:
            mock_empty_env_vars: Fixture that clears environment variables
        """
        with patch('all_in_one.requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            client = ZwiftPowerClient()
            
            # Should still initialize but log warning
            # Cookies update should be called with empty dict or not at all
            if mock_session.cookies.update.called:
                call_args = mock_session.cookies.update.call_args[0][0]
                assert len(call_args) == 0

    def test_authenticate_with_partial_cookies(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Validates that only valid cookies are loaded when some are missing.
        
        Args:
            monkeypatch: pytest fixture for modifying environment
        """
        monkeypatch.setenv("PHPBB3_SID", "test_sid")
        monkeypatch.setenv("PHPBB3_U", "test_u")
        # CloudFront cookies intentionally missing
        
        with patch('all_in_one.requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            client = ZwiftPowerClient()
            
            assert mock_session.cookies.update.called
            call_args = mock_session.cookies.update.call_args[0][0]
            
            # Only phpBB cookies should be present
            assert "phpbb3_lswlk_sid" in call_args
            assert "phpbb3_lswlk_u" in call_args
            assert "CloudFront-Key-Pair-Id" not in call_args


# ============================================================================
# Profile Parsing Tests
# ============================================================================

class TestProfileParsing:
    """Test suite for HTML profile parsing functionality."""

    def test_parse_profile_html_complete(self, mock_profile_html: str) -> None:
        """Validates parsing of complete profile HTML with all fields.
        
        Args:
            mock_profile_html: Fixture providing complete mock HTML
        """
        result = ZwiftPowerClient._parse_profile_html(mock_profile_html, "1714370")
        
        # Verify basic fields
        assert result["zid"] == "1714370"
        assert result["cat"] == "A"
        assert result["racing_score"] == "652.3"
        assert result["zpoints"] == "7,301"
        assert result["country"] == "Uruguay"
        assert result["team"] == "Test Team"
        assert result["zftp"] == "285 watts"
        assert result["weight"] == "67.4 kg"
        assert result["age"] == "35"
        
        # Verify power metrics from JavaScript
        assert result["watts_15s"] == 650
        assert result["pct_15s"] == 85.5
        assert result["watts_1m"] == 420
        assert result["pct_1m"] == 78.2
        assert result["watts_5m"] == 310
        assert result["pct_5m"] == 72.1
        assert result["watts_20m"] == 290
        assert result["pct_20m"] == 68.9

    def test_parse_profile_html_minimal(self, mock_profile_html_minimal: str) -> None:
        """Validates parser handles missing optional fields gracefully.
        
        Args:
            mock_profile_html_minimal: Fixture with minimal HTML
        """
        result = ZwiftPowerClient._parse_profile_html(mock_profile_html_minimal, "1234567")
        
        assert result["zid"] == "1234567"
        assert result["cat"] == "B"
        assert result["country"] == "USA"
        
        # Optional fields should not be present
        assert "racing_score" not in result
        assert "zpoints" not in result
        assert "team" not in result
        assert "watts_15s" not in result

    def test_parse_profile_html_empty(self) -> None:
        """Validates parser handles empty HTML without crashing."""
        result = ZwiftPowerClient._parse_profile_html("", "9999999")
        
        assert result["zid"] == "9999999"
        assert len(result) == 1  # Only zid should be present

    def test_parse_profile_html_malformed(self) -> None:
        """Validates parser handles malformed HTML gracefully."""
        malformed_html = "<html><body><table><tr><th>Category</body></html>"
        result = ZwiftPowerClient._parse_profile_html(malformed_html, "8888888")
        
        assert result["zid"] == "8888888"
        # Should not crash, may have partial data


# ============================================================================
# Profile Fetching Tests
# ============================================================================

class TestGetProfiles:
    """Test suite for profile fetching functionality."""

    @patch('all_in_one.requests.Session')
    def test_get_profiles_success(
        self, 
        mock_session_class: Mock, 
        mock_profile_html: str,
        mock_env_vars: None
    ) -> None:
        """Validates successful profile fetching for multiple ZIDs.
        
        Args:
            mock_session_class: Mocked requests.Session
            mock_profile_html: Mock HTML response
            mock_env_vars: Mock environment variables
        """
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = mock_profile_html
        mock_session.get.return_value = mock_response
        
        client = ZwiftPowerClient()
        result = client.get_profiles([1714370, 1815308])
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert "zid" in result.columns
        assert mock_session.get.call_count == 2

    @patch('all_in_one.requests.Session')
    def test_get_profiles_http_error(
        self, 
        mock_session_class: Mock,
        mock_env_vars: None
    ) -> None:
        """Validates handling of HTTP errors during profile fetching.
        
        Args:
            mock_session_class: Mocked requests.Session
            mock_env_vars: Mock environment variables
        """
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        # Mock 403 Forbidden response
        mock_response = Mock()
        mock_response.status_code = 403
        mock_session.get.return_value = mock_response
        
        client = ZwiftPowerClient()
        result = client.get_profiles([1714370])
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["zid"] == "1714370"

    @patch('all_in_one.requests.Session')
    def test_get_profiles_exception(
        self, 
        mock_session_class: Mock,
        mock_env_vars: None
    ) -> None:
        """Validates handling of exceptions during profile fetching.
        
        Args:
            mock_session_class: Mocked requests.Session
            mock_env_vars: Mock environment variables
        """
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        # Mock exception during request
        mock_session.get.side_effect = Exception("Network error")
        
        client = ZwiftPowerClient()
        result = client.get_profiles([1714370])
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["zid"] == "1714370"

    @patch('all_in_one.requests.Session')
    @patch('all_in_one.time.sleep')
    def test_get_profiles_rate_limiting(
        self, 
        mock_sleep: Mock,
        mock_session_class: Mock,
        mock_profile_html: str,
        mock_env_vars: None
    ) -> None:
        """Validates rate limiting between profile requests.
        
        Args:
            mock_sleep: Mocked time.sleep
            mock_session_class: Mocked requests.Session
            mock_profile_html: Mock HTML response
            mock_env_vars: Mock environment variables
        """
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = mock_profile_html
        mock_session.get.return_value = mock_response
        
        client = ZwiftPowerClient()
        client.get_profiles([1714370, 1815308, 1002137])
        
        # Should sleep between each request
        assert mock_sleep.call_count == 3
        mock_sleep.assert_called_with(0.5)


# ============================================================================
# Event History Tests
# ============================================================================

class TestGetEventHistories:
    """Test suite for event history fetching functionality."""

    @patch('all_in_one.requests.Session')
    def test_get_event_histories_success(
        self, 
        mock_session_class: Mock,
        mock_event_json: dict,
        mock_env_vars: None
    ) -> None:
        """Validates successful event history fetching.
        
        Args:
            mock_session_class: Mocked requests.Session
            mock_event_json: Mock JSON event data
            mock_env_vars: Mock environment variables
        """
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_event_json
        mock_session.get.return_value = mock_response
        
        client = ZwiftPowerClient()
        result = client.get_event_histories([1714370])
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert "query_zid" in result.columns
        assert all(result["query_zid"] == "1714370")

    @patch('all_in_one.requests.Session')
    def test_get_event_histories_empty(
        self, 
        mock_session_class: Mock,
        mock_empty_event_json: dict,
        mock_env_vars: None
    ) -> None:
        """Validates handling of empty event history.
        
        Args:
            mock_session_class: Mocked requests.Session
            mock_empty_event_json: Empty JSON response
            mock_env_vars: Mock environment variables
        """
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_empty_event_json
        mock_session.get.return_value = mock_response
        
        client = ZwiftPowerClient()
        result = client.get_event_histories([1714370])
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    @patch('all_in_one.requests.Session')
    def test_get_event_histories_404(
        self, 
        mock_session_class: Mock,
        mock_env_vars: None
    ) -> None:
        """Validates handling of 404 responses (no cache file).
        
        Args:
            mock_session_class: Mocked requests.Session
            mock_env_vars: Mock environment variables
        """
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 404
        mock_session.get.return_value = mock_response
        
        client = ZwiftPowerClient()
        result = client.get_event_histories([1714370])
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    @patch('all_in_one.requests.Session')
    def test_get_event_histories_malformed_json(
        self, 
        mock_session_class: Mock,
        mock_env_vars: None
    ) -> None:
        """Validates handling of malformed JSON responses.
        
        Args:
            mock_session_class: Mocked requests.Session
            mock_env_vars: Mock environment variables
        """
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_session.get.return_value = mock_response
        
        client = ZwiftPowerClient()
        result = client.get_event_histories([1714370])
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    @patch('all_in_one.requests.Session')
    def test_get_event_histories_multiple_zids(
        self, 
        mock_session_class: Mock,
        mock_event_json: dict,
        mock_env_vars: None
    ) -> None:
        """Validates concatenation of events from multiple ZIDs.
        
        Args:
            mock_session_class: Mocked requests.Session
            mock_event_json: Mock JSON event data
            mock_env_vars: Mock environment variables
        """
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_event_json
        mock_session.get.return_value = mock_response
        
        client = ZwiftPowerClient()
        result = client.get_event_histories([1714370, 1815308])
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 4  # 2 events per ZID
        assert mock_session.get.call_count == 2

    @patch('all_in_one.requests.Session')
    def test_get_event_histories_headers(
        self, 
        mock_session_class: Mock,
        mock_event_json: dict,
        mock_env_vars: None
    ) -> None:
        """Validates that required AJAX headers are sent.
        
        Args:
            mock_session_class: Mocked requests.Session
            mock_event_json: Mock JSON event data
            mock_env_vars: Mock environment variables
        """
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_event_json
        mock_session.get.return_value = mock_response
        
        client = ZwiftPowerClient()
        client.get_event_histories([1714370])
        
        # Verify headers were passed
        call_kwargs = mock_session.get.call_args[1]
        headers = call_kwargs.get("headers", {})
        
        assert "X-Requested-With" in headers
        assert headers["X-Requested-With"] == "XMLHttpRequest"
        assert "Referer" in headers


# ============================================================================
# Session Verification Tests
# ============================================================================

class TestSessionVerification:
    """Test suite for session verification functionality."""

    @patch('all_in_one.requests.Session')
    def test_verify_session_success(
        self, 
        mock_session_class: Mock,
        mock_env_vars: None
    ) -> None:
        """Validates successful session verification with valid cookies.
        
        Args:
            mock_session_class: Mocked requests.Session
            mock_env_vars: Mock environment variables
        """
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_session.head.return_value = mock_response
        
        client = ZwiftPowerClient()
        # Should not raise exception
        client.verify_session()

    @patch('all_in_one.requests.Session')
    def test_verify_session_expired_cookies(
        self, 
        mock_session_class: Mock,
        mock_env_vars: None
    ) -> None:
        """Validates CookieExpiredError is raised on 403 response.
        
        Args:
            mock_session_class: Mocked requests.Session
            mock_env_vars: Mock environment variables
        """
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 403
        mock_session.head.return_value = mock_response
        
        client = ZwiftPowerClient()
        
        with pytest.raises(CookieExpiredError) as exc_info:
            client.verify_session()
        
        assert "obsolete" in str(exc_info.value).lower()

    @patch('all_in_one.requests.Session')
    def test_verify_session_unexpected_status(
        self, 
        mock_session_class: Mock,
        mock_env_vars: None
    ) -> None:
        """Validates handling of unexpected status codes during verification.
        
        Args:
            mock_session_class: Mocked requests.Session
            mock_env_vars: Mock environment variables
        """
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 500
        mock_session.head.return_value = mock_response
        
        client = ZwiftPowerClient()
        # Should not raise exception, just log warning
        client.verify_session()


# ============================================================================
# Helper Method Tests
# ============================================================================

class TestHelperMethods:
    """Test suite for static helper methods."""

    def test_extract_regex_match(self) -> None:
        """Validates regex extraction with successful match."""
        text = "Racing Score: 652.3 points"
        pattern = r"Score:\s*([\d.]+)"
        result = ZwiftPowerClient._extract_regex(text, pattern)
        
        assert result == "652.3"

    def test_extract_regex_no_match(self) -> None:
        """Validates regex extraction returns None when no match."""
        text = "No score here"
        pattern = r"Score:\s*([\d.]+)"
        result = ZwiftPowerClient._extract_regex(text, pattern)
        
        assert result is None

    def test_get_span_text_valid_index(self) -> None:
        """Validates span text extraction with valid index."""
        from bs4 import BeautifulSoup
        html = "<div><span>First</span><span>Second</span></div>"
        soup = BeautifulSoup(html, "html.parser")
        spans = soup.find_all("span")
        
        result = ZwiftPowerClient._get_span_text(spans, 1)
        assert result == "Second"

    def test_get_span_text_invalid_index(self) -> None:
        """Validates span text extraction returns None for invalid index."""
        from bs4 import BeautifulSoup
        html = "<div><span>First</span></div>"
        soup = BeautifulSoup(html, "html.parser")
        spans = soup.find_all("span")
        
        result = ZwiftPowerClient._get_span_text(spans, 5)
        assert result is None
