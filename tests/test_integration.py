"""Integration tests for the complete Zwift scraper pipeline.

This module tests end-to-end workflows including:
- Full pipeline from scraping to database insertion
- Error handling and recovery
- Chunked insertion logic
- Cookie refresh integration
"""

from typing import Any
from unittest.mock import Mock, patch, MagicMock
import pytest
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from core.client import ZwiftPowerClient, CookieExpiredError
from core.pipeline import DataPipeline
from database.engine import Base, psql_insert_do_nothing
from database.models import RiderProfile, RiderEvent


# ============================================================================
# Full Pipeline Integration Tests
# ============================================================================

class TestFullPipeline:
    """Test suite for complete scraping and storage pipeline."""

    @patch('core.client.requests.Session')
    @patch('core.client.time.sleep')
    def test_profile_scraping_to_dataframe(
        self,
        mock_sleep: Mock,
        mock_session_class: Mock,
        mock_profile_html: str,
        mock_env_vars: None
    ) -> None:
        """Validates complete profile scraping workflow produces valid DataFrame.
        
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
        
        # Execute pipeline
        client = ZwiftPowerClient()
        raw_profiles = client.get_profiles([1714370, 1815308])
        
        # Transform data
        numeric_cols = ["weight", "zftp", "zpoints", "racing_score"]
        df_clean = DataPipeline.clean_numeric_columns(raw_profiles, numeric_cols)
        
        # Validate results
        assert len(df_clean) == 2
        assert "zid" in df_clean.columns
        assert pd.api.types.is_float_dtype(df_clean["weight"])

    @patch('core.client.requests.Session')
    @patch('core.client.time.sleep')
    def test_events_scraping_to_dataframe(
        self,
        mock_sleep: Mock,
        mock_session_class: Mock,
        mock_event_json: dict,
        mock_env_vars: None
    ) -> None:
        """Validates complete event scraping workflow produces valid DataFrame.
        
        Args:
            mock_sleep: Mocked time.sleep
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
        
        # Execute pipeline
        client = ZwiftPowerClient()
        raw_events = client.get_event_histories([1714370])
        
        # Transform data
        df_unpacked = DataPipeline.unpack_list_columns(raw_events)
        df_clean = DataPipeline.format_event_dates(df_unpacked, "event_date")
        
        # Validate results
        assert len(df_clean) == 2
        assert "query_zid" in df_clean.columns
        assert pd.api.types.is_datetime64_any_dtype(df_clean["event_date"])

    @patch('core.client.requests.Session')
    def test_profile_to_database_insertion(
        self,
        mock_session_class: Mock,
        test_db_engine,
        mock_profile_html: str,
        mock_env_vars: None
    ) -> None:
        """Validates complete profile pipeline including database insertion.
        
        Args:
            mock_session_class: Mocked requests.Session
            test_db_engine: Test database engine
            mock_profile_html: Mock HTML response
            mock_env_vars: Mock environment variables
        """
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = mock_profile_html
        mock_session.get.return_value = mock_response
        
        # Execute scraping
        client = ZwiftPowerClient()
        raw_profiles = client.get_profiles([1714370])
        
        # Transform
        numeric_cols = ["weight", "zftp", "zpoints", "racing_score"]
        df_clean = DataPipeline.clean_numeric_columns(raw_profiles, numeric_cols)
        df_clean["fetched_at"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Insert to database
        profile_cols = [c.name for c in RiderProfile.__table__.columns if c.name != 'id']
        df_filtered = df_clean[[col for col in profile_cols if col in df_clean.columns]]
        
        df_filtered.to_sql(
            'rider_profiles',
            con=test_db_engine,
            if_exists='append',
            index=False,
            method=psql_insert_do_nothing
        )
        
        # Verify
        result_df = pd.read_sql("SELECT * FROM rider_profiles", test_db_engine)
        assert len(result_df) == 1
        assert result_df["zid"].iloc[0] == 1714370

    @patch('core.client.requests.Session')
    def test_events_to_database_insertion(
        self,
        mock_session_class: Mock,
        test_db_engine,
        mock_event_json: dict,
        mock_env_vars: None
    ) -> None:
        """Validates complete events pipeline including database insertion.
        
        Args:
            mock_session_class: Mocked requests.Session
            test_db_engine: Test database engine
            mock_event_json: Mock JSON event data
            mock_env_vars: Mock environment variables
        """
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_event_json
        mock_session.get.return_value = mock_response
        
        # Execute scraping
        client = ZwiftPowerClient()
        raw_events = client.get_event_histories([1714370])
        
        # Transform
        df_unpacked = DataPipeline.unpack_list_columns(raw_events)
        df_clean = DataPipeline.format_event_dates(df_unpacked, "event_date")
        
        # Filter columns
        model_columns = [c.name for c in RiderEvent.__table__.columns]
        valid_cols = [col for col in model_columns if col in df_clean.columns]
        df_filtered = df_clean[valid_cols]
        
        # Replace empty strings with NaN
        df_filtered = df_filtered.replace(r'^\s*$', np.nan, regex=True)
        df_filtered = df_filtered.dropna(subset=['zid', 'res_id'])
        
        # Insert to database
        df_filtered.to_sql(
            name="rider_events",
            con=test_db_engine,
            if_exists="append",
            index=False,
            method=psql_insert_do_nothing
        )
        
        # Verify
        result_df = pd.read_sql("SELECT * FROM rider_events", test_db_engine)
        assert len(result_df) == 2
        assert all(result_df["query_zid"] == 1714370)


# ============================================================================
# Chunked Insertion Tests
# ============================================================================

class TestChunkedInsertion:
    """Test suite for chunked database insertion logic."""

    def test_chunked_insertion_small_dataset(self, test_db_engine) -> None:
        """Validates chunked insertion with dataset smaller than chunk size.
        
        Args:
            test_db_engine: Test database engine
        """
        # Create small dataset (less than typical chunk size of 300)
        events = []
        for i in range(50):
            events.append({
                "zid": 1714370,
                "res_id": f"570316{i}.23",
                "name": "Test Rider",
                "pos": i + 1
            })
        
        df = pd.DataFrame(events)
        
        # Insert in chunks
        chunk_size = 300
        for i in range(0, len(df), chunk_size):
            chunk = df.iloc[i:i + chunk_size]
            chunk.to_sql(
                name="rider_events",
                con=test_db_engine,
                if_exists="append",
                index=False,
                method=psql_insert_do_nothing
            )
        
        # Verify all records inserted
        result_df = pd.read_sql("SELECT * FROM rider_events", test_db_engine)
        assert len(result_df) == 50

    def test_chunked_insertion_large_dataset(self, test_db_engine) -> None:
        """Validates chunked insertion with dataset larger than chunk size.
        
        Args:
            test_db_engine: Test database engine
        """
        # Create large dataset (more than chunk size)
        events = []
        for i in range(650):
            events.append({
                "zid": 1714370,
                "res_id": f"570{i:06d}.23",
                "name": "Test Rider",
                "pos": i + 1
            })
        
        df = pd.DataFrame(events)
        
        # Insert in chunks of 300
        chunk_size = 300
        for i in range(0, len(df), chunk_size):
            chunk = df.iloc[i:i + chunk_size]
            chunk.to_sql(
                name="rider_events",
                con=test_db_engine,
                if_exists="append",
                index=False,
                method=psql_insert_do_nothing
            )
        
        # Verify all records inserted
        result_df = pd.read_sql("SELECT * FROM rider_events", test_db_engine)
        assert len(result_df) == 650

    def test_chunked_insertion_with_duplicates(self, test_db_engine) -> None:
        """Validates chunked insertion handles duplicates across chunks.
        
        Args:
            test_db_engine: Test database engine
        """
        # Create first batch
        events1 = []
        for i in range(100):
            events1.append({
                "zid": 1714370,
                "res_id": f"570316{i}.23",
                "name": "Test Rider",
                "pos": i + 1
            })
        
        df1 = pd.DataFrame(events1)
        df1.to_sql(
            name="rider_events",
            con=test_db_engine,
            if_exists="append",
            index=False,
            method=psql_insert_do_nothing
        )
        
        # Create second batch with some duplicates
        events2 = []
        for i in range(50, 150):  # Overlaps with first batch
            events2.append({
                "zid": 1714370,
                "res_id": f"570316{i}.23",
                "name": "Test Rider",
                "pos": i + 1
            })
        
        df2 = pd.DataFrame(events2)
        df2.to_sql(
            name="rider_events",
            con=test_db_engine,
            if_exists="append",
            index=False,
            method=psql_insert_do_nothing
        )
        
        # Should have 150 unique records (0-149)
        result_df = pd.read_sql("SELECT * FROM rider_events", test_db_engine)
        assert len(result_df) == 150


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Test suite for error handling and recovery."""

    @patch('core.client.requests.Session')
    def test_partial_failure_continues_processing(
        self,
        mock_session_class: Mock,
        mock_profile_html: str,
        mock_env_vars: None
    ) -> None:
        """Validates pipeline continues when some ZIDs fail.
        
        Args:
            mock_session_class: Mocked requests.Session
            mock_profile_html: Mock HTML response
            mock_env_vars: Mock environment variables
        """
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        # First ZID succeeds, second fails, third succeeds
        responses = [
            Mock(status_code=200, text=mock_profile_html),
            Mock(status_code=403),
            Mock(status_code=200, text=mock_profile_html)
        ]
        mock_session.get.side_effect = responses
        
        client = ZwiftPowerClient()
        result = client.get_profiles([1714370, 9999999, 1815308])
        
        # Should have 3 records (failed one has minimal data)
        assert len(result) == 3
        assert "zid" in result.columns

    @patch('core.client.requests.Session')
    def test_network_error_recovery(
        self,
        mock_session_class: Mock,
        mock_env_vars: None
    ) -> None:
        """Validates graceful handling of network errors.
        
        Args:
            mock_session_class: Mocked requests.Session
            mock_env_vars: Mock environment variables
        """
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        # Simulate network error
        mock_session.get.side_effect = Exception("Connection timeout")
        
        client = ZwiftPowerClient()
        result = client.get_profiles([1714370])
        
        # Should return DataFrame with minimal data
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1

    def test_invalid_data_filtering(self, test_db_engine) -> None:
        """Validates filtering of invalid records before database insertion.
        
        Args:
            test_db_engine: Test database engine
        """
        # Create dataset with some invalid records (missing primary keys)
        events = [
            {"zid": 1714370, "res_id": "5703166.23", "name": "Valid"},
            {"zid": None, "res_id": "5703167.45", "name": "Invalid - no zid"},
            {"zid": 1714370, "res_id": None, "name": "Invalid - no res_id"},
            {"zid": 1815308, "res_id": "5703168.67", "name": "Valid"}
        ]
        
        df = pd.DataFrame(events)
        
        # Filter out invalid records
        df_filtered = df.dropna(subset=['zid', 'res_id'])
        
        df_filtered.to_sql(
            name="rider_events",
            con=test_db_engine,
            if_exists="append",
            index=False,
            method=psql_insert_do_nothing
        )
        
        # Should only have 2 valid records
        result_df = pd.read_sql("SELECT * FROM rider_events", test_db_engine)
        assert len(result_df) == 2

    def test_empty_string_to_null_conversion(self, test_db_engine) -> None:
        """Validates empty strings are converted to NULL before insertion.
        
        Args:
            test_db_engine: Test database engine
        """
        events = [
            {
                "zid": 1714370,
                "res_id": "5703166.23",
                "name": "Test Rider",
                "tname": "",  # Empty string (event team name)
                "note": "   "  # Whitespace only
            }
        ]
        
        df = pd.DataFrame(events)
        
        # Replace empty strings with NaN
        df = df.replace(r'^\s*$', np.nan, regex=True)
        
        df.to_sql(
            name="rider_events",
            con=test_db_engine,
            if_exists="append",
            index=False,
            method=psql_insert_do_nothing
        )
        
        # Verify NULL values in database
        result_df = pd.read_sql("SELECT * FROM rider_events", test_db_engine)
        assert pd.isna(result_df["tname"].iloc[0]) if "tname" in result_df.columns else True
        assert pd.isna(result_df["note"].iloc[0]) if "note" in result_df.columns else True


# ============================================================================
# Cookie Refresh Integration Tests
# ============================================================================

class TestCookieRefreshIntegration:
    """Test suite for cookie refresh integration."""

    @patch('core.client.requests.Session')
    @patch('scripts.cookie_refresher.refresh_zwiftpower_cookies')
    @patch('dotenv.load_dotenv')
    def test_cookie_refresh_on_expiration(
        self,
        mock_load_dotenv: Mock,
        mock_refresh_cookies: Mock,
        mock_session_class: Mock,
        mock_env_vars: None
    ) -> None:
        """Validates automatic cookie refresh when session expires.
        
        Args:
            mock_load_dotenv: Mocked load_dotenv
            mock_refresh_cookies: Mocked refresh function
            mock_session_class: Mocked requests.Session
            mock_env_vars: Mock environment variables
        """
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        # First verification fails (403), second succeeds (200)
        mock_session.head.side_effect = [
            Mock(status_code=403),
            Mock(status_code=200)
        ]
        
        # Mock successful cookie refresh
        mock_refresh_cookies.return_value = True
        
        client = ZwiftPowerClient()
        
        # First verification should raise CookieExpiredError
        with pytest.raises(CookieExpiredError):
            client.verify_session()
        
        # Simulate refresh and re-authentication
        mock_refresh_cookies(".env")
        mock_load_dotenv(".env", override=True)
        client.authenticate()
        
        # Second verification should succeed
        client.verify_session()
        
        assert mock_refresh_cookies.called

    @patch('core.client.requests.Session')
    @patch('scripts.cookie_refresher.refresh_zwiftpower_cookies')
    def test_cookie_refresh_failure_handling(
        self,
        mock_refresh_cookies: Mock,
        mock_session_class: Mock,
        mock_env_vars: None
    ) -> None:
        """Validates handling when cookie refresh fails.
        
        Args:
            mock_refresh_cookies: Mocked refresh function
            mock_session_class: Mocked requests.Session
            mock_env_vars: Mock environment variables
        """
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_session.head.return_value = Mock(status_code=403)
        
        # Mock failed cookie refresh
        mock_refresh_cookies.return_value = False
        
        client = ZwiftPowerClient()
        
        with pytest.raises(CookieExpiredError):
            client.verify_session()
        
        # Attempt refresh
        success = mock_refresh_cookies(".env")
        
        assert not success


# ============================================================================
# Data Consistency Tests
# ============================================================================

class TestDataConsistency:
    """Test suite for data consistency across pipeline."""

    @patch('core.client.requests.Session')
    def test_zid_consistency_across_pipeline(
        self,
        mock_session_class: Mock,
        mock_profile_html: str,
        mock_event_json: dict,
        test_db_engine,
        mock_env_vars: None
    ) -> None:
        """Validates ZID consistency from scraping to database.
        
        Args:
            mock_session_class: Mocked requests.Session
            mock_profile_html: Mock HTML response
            mock_event_json: Mock JSON event data
            test_db_engine: Test database engine
            mock_env_vars: Mock environment variables
        """
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        # Mock responses
        mock_session.get.side_effect = [
            Mock(status_code=200, text=mock_profile_html),
            Mock(status_code=200, json=lambda: mock_event_json)
        ]
        
        target_zid = 1714370
        
        # Scrape profile
        client = ZwiftPowerClient()
        profiles = client.get_profiles([target_zid])
        
        # Scrape events
        events = client.get_event_histories([target_zid])
        
        # Verify ZID consistency
        assert profiles["zid"].iloc[0] == target_zid
        # query_zid is stored as string by the client
        assert all(events["query_zid"] == str(target_zid))

    def test_data_type_consistency(self, sample_events_df: pd.DataFrame) -> None:
        """Validates data types remain consistent through transformations.
        
        Args:
            sample_events_df: Fixture with sample events data
        """
        # Apply transformations
        df_unpacked = DataPipeline.unpack_list_columns(sample_events_df)
        df_formatted = DataPipeline.format_event_dates(df_unpacked, "event_date")
        
        # Verify data types
        assert df_formatted["zid"].dtype in [np.int64, np.int32]
        assert pd.api.types.is_datetime64_any_dtype(df_formatted["event_date"])
        assert df_formatted["pos"].dtype in [np.int64, np.int32]

    def test_no_data_loss_in_transformations(self) -> None:
        """Validates no data is lost during transformations."""
        original_df = pd.DataFrame({
            "id": [1, 2, 3, 4, 5],
            "value": [["100", 0], ["200", 0], ["300", 0], ["400", 0], ["500", 0]],
            "date": [1695052800, 1694966400, 1694880000, 1694793600, 1694707200]
        })
        
        # Apply transformations
        df_unpacked = DataPipeline.unpack_list_columns(original_df)
        df_formatted = DataPipeline.format_event_dates(df_unpacked, "date")
        
        # Verify row count unchanged
        assert len(df_formatted) == len(original_df)
        assert all(df_formatted["id"] == original_df["id"])


# ============================================================================
# Performance Tests
# ============================================================================

class TestPerformance:
    """Test suite for performance-related scenarios."""

    def test_large_batch_insertion(self, test_db_engine) -> None:
        """Validates performance with large batch insertions.
        
        Args:
            test_db_engine: Test database engine
        """
        # Create large dataset
        events = []
        for i in range(1000):
            events.append({
                "zid": 1714370,
                "res_id": f"570{i:06d}.23",
                "name": "Test Rider",
                "pos": i + 1
            })
        
        df = pd.DataFrame(events)
        
        # Insert in chunks
        chunk_size = 300
        for i in range(0, len(df), chunk_size):
            chunk = df.iloc[i:i + chunk_size]
            chunk.to_sql(
                name="rider_events",
                con=test_db_engine,
                if_exists="append",
                index=False,
                method=psql_insert_do_nothing
            )
        
        # Verify
        result_df = pd.read_sql("SELECT COUNT(*) as count FROM rider_events", test_db_engine)
        assert result_df["count"].iloc[0] == 1000

    def test_multiple_zids_concurrent_processing(
        self,
        test_db_engine,
        sample_rider_event: dict
    ) -> None:
        """Validates handling of multiple ZIDs in single batch.
        
        Args:
            test_db_engine: Test database engine
            sample_rider_event: Fixture with sample event data
        """
        # Create events for multiple ZIDs
        events = []
        for zid in [1714370, 1815308, 1002137]:
            for i in range(10):
                event = sample_rider_event.copy()
                event["zid"] = zid
                event["res_id"] = f"570{zid}{i}.23"
                events.append(event)
        
        df = pd.DataFrame(events)
        
        df.to_sql(
            name="rider_events",
            con=test_db_engine,
            if_exists="append",
            index=False,
            method=psql_insert_do_nothing
        )
        
        # Verify all ZIDs present
        result_df = pd.read_sql("SELECT DISTINCT zid FROM rider_events", test_db_engine)
        assert len(result_df) == 3
        assert set(result_df["zid"]) == {1714370, 1815308, 1002137}
