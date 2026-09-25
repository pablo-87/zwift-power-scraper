"""Tests for database models and operations.

This module tests database functionality including:
- Table creation via init_db()
- RiderProfile and RiderEvent model constraints
- Custom psql_insert_do_nothing() insertion method
- Duplicate handling
"""

from typing import Generator
import pytest
import pandas as pd
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError
from database import (
    Base,
    RiderProfile,
    RiderEvent,
    init_db,
    psql_insert_do_nothing,
    engine as production_engine
)


# ============================================================================
# Database Initialization Tests
# ============================================================================

class TestInitDb:
    """Test suite for database initialization functionality."""

    def test_init_db_creates_tables(self, test_db_engine) -> None:
        """Validates that init_db creates all required tables.
        
        Args:
            test_db_engine: Fixture providing test database engine
        """
        # Tables should already be created by fixture
        inspector = inspect(test_db_engine)
        table_names = inspector.get_table_names()
        
        assert "rider_profiles" in table_names
        assert "rider_events" in table_names

    def test_init_db_idempotent(self, test_db_engine) -> None:
        """Validates that init_db can be called multiple times safely.
        
        Args:
            test_db_engine: Fixture providing test database engine
        """
        # Call init multiple times
        Base.metadata.create_all(test_db_engine)
        Base.metadata.create_all(test_db_engine)
        
        inspector = inspect(test_db_engine)
        table_names = inspector.get_table_names()
        
        # Should still have exactly these tables
        assert "rider_profiles" in table_names
        assert "rider_events" in table_names

    def test_rider_profile_columns(self, test_db_engine) -> None:
        """Validates RiderProfile table has all expected columns.
        
        Args:
            test_db_engine: Fixture providing test database engine
        """
        inspector = inspect(test_db_engine)
        columns = [col["name"] for col in inspector.get_columns("rider_profiles")]
        
        expected_columns = [
            "id", "zid", "fetched_at", "cat", "racing_score", "zpoints",
            "country", "team", "zftp", "weight", "age",
            "watts_15s", "pct_15s", "watts_1m", "pct_1m",
            "watts_5m", "pct_5m", "watts_20m", "pct_20m"
        ]
        
        for col in expected_columns:
            assert col in columns

    def test_rider_event_columns(self, test_db_engine) -> None:
        """Validates RiderEvent table has all expected columns.
        
        Args:
            test_db_engine: Fixture providing test database engine
        """
        inspector = inspect(test_db_engine)
        columns = [col["name"] for col in inspector.get_columns("rider_events")]
        
        # Check key columns
        assert "zid" in columns
        assert "res_id" in columns
        assert "name" in columns
        assert "event_date" in columns
        assert "query_zid" in columns

    def test_rider_profile_primary_key(self, test_db_engine) -> None:
        """Validates RiderProfile has correct primary key.
        
        Args:
            test_db_engine: Fixture providing test database engine
        """
        inspector = inspect(test_db_engine)
        pk = inspector.get_pk_constraint("rider_profiles")
        
        assert "id" in pk["constrained_columns"]

    def test_rider_event_composite_primary_key(self, test_db_engine) -> None:
        """Validates RiderEvent has composite primary key (zid, res_id).
        
        Args:
            test_db_engine: Fixture providing test database engine
        """
        inspector = inspect(test_db_engine)
        pk = inspector.get_pk_constraint("rider_events")
        
        assert "zid" in pk["constrained_columns"]
        assert "res_id" in pk["constrained_columns"]


# ============================================================================
# RiderProfile Model Tests
# ============================================================================

class TestRiderProfileModel:
    """Test suite for RiderProfile model operations."""

    def test_create_rider_profile(
        self, 
        test_db_session: Session,
        sample_rider_profile: dict
    ) -> None:
        """Validates creating a new RiderProfile record.
        
        Args:
            test_db_session: Fixture providing test database session
            sample_rider_profile: Fixture with sample profile data
        """
        profile = RiderProfile(**sample_rider_profile)
        test_db_session.add(profile)
        test_db_session.commit()
        
        # Query back
        result = test_db_session.query(RiderProfile).filter_by(zid=1714370).first()
        
        assert result is not None
        assert result.zid == 1714370
        assert result.cat == "A"
        assert result.weight == 67.4

    def test_rider_profile_unique_constraint(
        self,
        test_db_session: Session,
        sample_rider_profile: dict
    ) -> None:
        """Validates unique constraint on (zid, fetched_at).
        
        Args:
            test_db_session: Fixture providing test database session
            sample_rider_profile: Fixture with sample profile data
        """
        # Insert first profile
        profile1 = RiderProfile(**sample_rider_profile)
        test_db_session.add(profile1)
        test_db_session.commit()
        
        # Try to insert duplicate with same zid and fetched_at
        profile2 = RiderProfile(**sample_rider_profile)
        test_db_session.add(profile2)
        
        with pytest.raises(IntegrityError):
            test_db_session.commit()

    def test_rider_profile_different_timestamps(
        self,
        test_db_session: Session,
        sample_rider_profile: dict
    ) -> None:
        """Validates same zid can have multiple records with different timestamps.
        
        Args:
            test_db_session: Fixture providing test database session
            sample_rider_profile: Fixture with sample profile data
        """
        import datetime
        
        # Insert first profile
        profile1 = RiderProfile(**sample_rider_profile)
        test_db_session.add(profile1)
        test_db_session.commit()
        
        # Insert second profile with different timestamp
        profile2_data = sample_rider_profile.copy()
        profile2_data["fetched_at"] = pd.Timestamp.now() + datetime.timedelta(hours=1)
        profile2 = RiderProfile(**profile2_data)
        test_db_session.add(profile2)
        test_db_session.commit()
        
        # Should have 2 records
        count = test_db_session.query(RiderProfile).filter_by(zid=1714370).count()
        assert count == 2

    def test_rider_profile_nullable_fields(
        self,
        test_db_session: Session
    ) -> None:
        """Validates that optional fields can be NULL.
        
        Args:
            test_db_session: Fixture providing test database session
        """
        profile = RiderProfile(
            zid=9999999,
            fetched_at=pd.Timestamp.now()
            # All other fields are optional
        )
        test_db_session.add(profile)
        test_db_session.commit()
        
        result = test_db_session.query(RiderProfile).filter_by(zid=9999999).first()
        assert result is not None
        assert result.cat is None
        assert result.team is None

    def test_rider_profile_power_metrics(
        self,
        test_db_session: Session,
        sample_rider_profile: dict
    ) -> None:
        """Validates power metrics are stored correctly.
        
        Args:
            test_db_session: Fixture providing test database session
            sample_rider_profile: Fixture with sample profile data
        """
        profile = RiderProfile(**sample_rider_profile)
        test_db_session.add(profile)
        test_db_session.commit()
        
        result = test_db_session.query(RiderProfile).filter_by(zid=1714370).first()
        
        assert result.watts_15s == 650
        assert result.pct_15s == 85.5
        assert result.watts_1m == 420
        assert result.watts_20m == 290


# ============================================================================
# RiderEvent Model Tests
# ============================================================================

class TestRiderEventModel:
    """Test suite for RiderEvent model operations."""

    def test_create_rider_event(
        self,
        test_db_session: Session,
        sample_rider_event: dict
    ) -> None:
        """Validates creating a new RiderEvent record.
        
        Args:
            test_db_session: Fixture providing test database session
            sample_rider_event: Fixture with sample event data
        """
        event = RiderEvent(**sample_rider_event)
        test_db_session.add(event)
        test_db_session.commit()
        
        result = test_db_session.query(RiderEvent).filter_by(
            zid=1714370, 
            res_id="5703166.23"
        ).first()
        
        assert result is not None
        assert result.name == "Test Rider"
        assert result.pos == 5

    def test_rider_event_composite_key_uniqueness(
        self,
        test_db_session: Session,
        sample_rider_event: dict
    ) -> None:
        """Validates composite primary key prevents duplicates.
        
        Args:
            test_db_session: Fixture providing test database session
            sample_rider_event: Fixture with sample event data
        """
        # Insert first event
        event1 = RiderEvent(**sample_rider_event)
        test_db_session.add(event1)
        test_db_session.commit()
        
        # Try to insert duplicate
        event2 = RiderEvent(**sample_rider_event)
        test_db_session.add(event2)
        
        with pytest.raises(IntegrityError):
            test_db_session.commit()

    def test_rider_event_different_res_id(
        self,
        test_db_session: Session,
        sample_rider_event: dict
    ) -> None:
        """Validates same zid can have multiple events with different res_id.
        
        Args:
            test_db_session: Fixture providing test database session
            sample_rider_event: Fixture with sample event data
        """
        # Insert first event
        event1 = RiderEvent(**sample_rider_event)
        test_db_session.add(event1)
        test_db_session.commit()
        
        # Insert second event with different res_id
        event2_data = sample_rider_event.copy()
        event2_data["res_id"] = "5703167.45"
        event2 = RiderEvent(**event2_data)
        test_db_session.add(event2)
        test_db_session.commit()
        
        count = test_db_session.query(RiderEvent).filter_by(zid=1714370).count()
        assert count == 2

    def test_rider_event_power_metrics(
        self,
        test_db_session: Session,
        sample_rider_event: dict
    ) -> None:
        """Validates power and performance metrics are stored correctly.
        
        Args:
            test_db_session: Fixture providing test database session
            sample_rider_event: Fixture with sample event data
        """
        event = RiderEvent(**sample_rider_event)
        test_db_session.add(event)
        test_db_session.commit()
        
        result = test_db_session.query(RiderEvent).filter_by(
            zid=1714370,
            res_id="5703166.23"
        ).first()
        
        assert result.avg_power == 275
        assert result.avg_wkg == 4.08
        assert result.ftp == 285

    def test_rider_event_string_res_id(
        self,
        test_db_session: Session
    ) -> None:
        """Validates res_id is stored as string to preserve precision.
        
        Args:
            test_db_session: Fixture providing test database session
        """
        event = RiderEvent(
            zid=1714370,
            res_id="5703166.23456789",  # High precision
            name="Test"
        )
        test_db_session.add(event)
        test_db_session.commit()
        
        result = test_db_session.query(RiderEvent).filter_by(zid=1714370).first()
        assert result.res_id == "5703166.23456789"
        assert isinstance(result.res_id, str)


# ============================================================================
# Custom Insertion Method Tests
# ============================================================================

class TestPsqlInsertDoNothing:
    """Test suite for custom psql_insert_do_nothing insertion method."""

    def test_insert_new_profiles(
        self,
        test_db_engine,
        sample_rider_profile: dict
    ) -> None:
        """Validates insertion of new profile records.
        
        Args:
            test_db_engine: Fixture providing test database engine
            sample_rider_profile: Fixture with sample profile data
        """
        df = pd.DataFrame([sample_rider_profile])
        
        # Remove 'id' column as it's auto-generated
        if 'id' in df.columns:
            df = df.drop(columns=['id'])
        
        df.to_sql(
            name="rider_profiles",
            con=test_db_engine,
            if_exists="append",
            index=False,
            method=psql_insert_do_nothing
        )
        
        # Verify insertion
        result_df = pd.read_sql("SELECT * FROM rider_profiles", test_db_engine)
        assert len(result_df) == 1
        assert result_df["zid"].iloc[0] == 1714370

    def test_insert_duplicate_profiles_ignored(
        self,
        test_db_engine,
        sample_rider_profile: dict
    ) -> None:
        """Validates that duplicate profiles are silently ignored.
        
        Args:
            test_db_engine: Fixture providing test database engine
            sample_rider_profile: Fixture with sample profile data
        """
        df = pd.DataFrame([sample_rider_profile])
        if 'id' in df.columns:
            df = df.drop(columns=['id'])
        
        # Insert first time
        df.to_sql(
            name="rider_profiles",
            con=test_db_engine,
            if_exists="append",
            index=False,
            method=psql_insert_do_nothing
        )
        
        # Insert duplicate - should not raise error
        df.to_sql(
            name="rider_profiles",
            con=test_db_engine,
            if_exists="append",
            index=False,
            method=psql_insert_do_nothing
        )
        
        # Should still have only 1 record
        result_df = pd.read_sql("SELECT * FROM rider_profiles", test_db_engine)
        assert len(result_df) == 1

    def test_insert_new_events(
        self,
        test_db_engine,
        sample_rider_event: dict
    ) -> None:
        """Validates insertion of new event records.
        
        Args:
            test_db_engine: Fixture providing test database engine
            sample_rider_event: Fixture with sample event data
        """
        df = pd.DataFrame([sample_rider_event])
        
        df.to_sql(
            name="rider_events",
            con=test_db_engine,
            if_exists="append",
            index=False,
            method=psql_insert_do_nothing
        )
        
        result_df = pd.read_sql("SELECT * FROM rider_events", test_db_engine)
        assert len(result_df) == 1
        assert result_df["zid"].iloc[0] == 1714370

    def test_insert_duplicate_events_ignored(
        self,
        test_db_engine,
        sample_rider_event: dict
    ) -> None:
        """Validates that duplicate events are silently ignored.
        
        Args:
            test_db_engine: Fixture providing test database engine
            sample_rider_event: Fixture with sample event data
        """
        df = pd.DataFrame([sample_rider_event])
        
        # Insert first time
        df.to_sql(
            name="rider_events",
            con=test_db_engine,
            if_exists="append",
            index=False,
            method=psql_insert_do_nothing
        )
        
        # Insert duplicate
        df.to_sql(
            name="rider_events",
            con=test_db_engine,
            if_exists="append",
            index=False,
            method=psql_insert_do_nothing
        )
        
        result_df = pd.read_sql("SELECT * FROM rider_events", test_db_engine)
        assert len(result_df) == 1

    def test_insert_mixed_new_and_duplicate(
        self,
        test_db_engine,
        sample_rider_event: dict
    ) -> None:
        """Validates handling of batch with both new and duplicate records.
        
        Args:
            test_db_engine: Fixture providing test database engine
            sample_rider_event: Fixture with sample event data
        """
        # Create first event
        event1 = sample_rider_event.copy()
        
        # Create second event with different res_id
        event2 = sample_rider_event.copy()
        event2["res_id"] = "5703167.45"
        
        # Insert first event
        df1 = pd.DataFrame([event1])
        df1.to_sql(
            name="rider_events",
            con=test_db_engine,
            if_exists="append",
            index=False,
            method=psql_insert_do_nothing
        )
        
        # Insert batch with duplicate event1 and new event2
        df2 = pd.DataFrame([event1, event2])
        df2.to_sql(
            name="rider_events",
            con=test_db_engine,
            if_exists="append",
            index=False,
            method=psql_insert_do_nothing
        )
        
        # Should have 2 records (event1 once, event2 once)
        result_df = pd.read_sql("SELECT * FROM rider_events", test_db_engine)
        assert len(result_df) == 2

    def test_insert_empty_dataframe(self, test_db_engine) -> None:
        """Validates handling of empty DataFrame insertion.
        
        Args:
            test_db_engine: Fixture providing test database engine
        """
        df = pd.DataFrame(columns=["zid", "res_id", "name"])
        
        # Should not raise error
        df.to_sql(
            name="rider_events",
            con=test_db_engine,
            if_exists="append",
            index=False,
            method=psql_insert_do_nothing
        )
        
        result_df = pd.read_sql("SELECT * FROM rider_events", test_db_engine)
        assert len(result_df) == 0


# ============================================================================
# Data Type Tests
# ============================================================================

class TestDataTypes:
    """Test suite for database column data types."""

    def test_profile_numeric_types(
        self,
        test_db_session: Session,
        sample_rider_profile: dict
    ) -> None:
        """Validates numeric columns accept float values.
        
        Args:
            test_db_session: Fixture providing test database session
            sample_rider_profile: Fixture with sample profile data
        """
        profile = RiderProfile(**sample_rider_profile)
        test_db_session.add(profile)
        test_db_session.commit()
        
        result = test_db_session.query(RiderProfile).filter_by(zid=1714370).first()
        
        assert isinstance(result.weight, float)
        assert isinstance(result.zftp, float)
        assert isinstance(result.racing_score, float)

    def test_event_bigint_columns(
        self,
        test_db_session: Session
    ) -> None:
        """Validates BigInteger columns handle large values.
        
        Args:
            test_db_session: Fixture providing test database session
        """
        event = RiderEvent(
            zid=1714370,
            res_id="test123",
            uid=987654321987654321,  # Large number
            rt=1695052800000  # Large timestamp
        )
        test_db_session.add(event)
        test_db_session.commit()
        
        result = test_db_session.query(RiderEvent).filter_by(zid=1714370).first()
        assert result.uid == 987654321987654321
        assert result.rt == 1695052800000

    def test_string_columns_accept_text(
        self,
        test_db_session: Session
    ) -> None:
        """Validates string columns accept text values.
        
        Args:
            test_db_session: Fixture providing test database session
        """
        profile = RiderProfile(
            zid=1714370,
            fetched_at=pd.Timestamp.now(),
            country="Uruguay",
            team="Test Team Name",
            cat="A"
        )
        test_db_session.add(profile)
        test_db_session.commit()
        
        result = test_db_session.query(RiderProfile).filter_by(zid=1714370).first()
        assert result.country == "Uruguay"
        assert result.team == "Test Team Name"
