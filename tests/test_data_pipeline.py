"""Tests for DataPipeline class.

This module tests data transformation utilities including:
- Unpacking list/tuple columns
- Cleaning numeric columns with units
- Formatting Unix timestamps to dates
- CSV export functionality
"""

from typing import Any
import os
import tempfile
import shutil
import pytest
import pandas as pd
import numpy as np
from all_in_one import DataPipeline


# ============================================================================
# Unpack List Columns Tests
# ============================================================================

class TestUnpackListColumns:
    """Test suite for list/tuple column unpacking functionality."""

    def test_unpack_list_columns_basic(self) -> None:
        """Validates unpacking of simple list columns."""
        df = pd.DataFrame({
            "time": [["3600.5", 0], ["3720.8", 0]],
            "weight": [["67.4", 0], ["68.2", 0]],
            "name": ["Rider A", "Rider B"]
        })
        
        result = DataPipeline.unpack_list_columns(df)
        
        assert result["time"].iloc[0] == "3600.5"
        assert result["time"].iloc[1] == "3720.8"
        assert result["weight"].iloc[0] == "67.4"
        assert result["name"].iloc[0] == "Rider A"

    def test_unpack_list_columns_numeric_conversion(self) -> None:
        """Validates automatic numeric conversion after unpacking."""
        df = pd.DataFrame({
            "value": [["100", 0], ["200", 0], ["300", 0]]
        })
        
        result = DataPipeline.unpack_list_columns(df)
        
        # Should convert to numeric if possible
        assert pd.api.types.is_numeric_dtype(result["value"])
        assert result["value"].iloc[0] == 100

    def test_unpack_list_columns_tuple(self) -> None:
        """Validates unpacking works with tuples as well as lists."""
        df = pd.DataFrame({
            "data": [("value1", 0), ("value2", 0)]
        })
        
        result = DataPipeline.unpack_list_columns(df)
        
        assert result["data"].iloc[0] == "value1"
        assert result["data"].iloc[1] == "value2"

    def test_unpack_list_columns_empty_list(self) -> None:
        """Validates handling of empty lists."""
        df = pd.DataFrame({
            "data": [[], ["value", 0]]
        })
        
        result = DataPipeline.unpack_list_columns(df)
        
        # Empty list should remain as is or become NaN
        assert pd.isna(result["data"].iloc[0]) or result["data"].iloc[0] == []

    def test_unpack_list_columns_mixed_types(self) -> None:
        """Validates handling of columns with mixed list and non-list values."""
        df = pd.DataFrame({
            "mixed": [["value", 0], "plain_string", ["another", 0]]
        })
        
        result = DataPipeline.unpack_list_columns(df)
        
        # Should handle mixed types gracefully
        assert isinstance(result, pd.DataFrame)

    def test_unpack_list_columns_empty_dataframe(self) -> None:
        """Validates handling of empty DataFrame."""
        df = pd.DataFrame()
        
        result = DataPipeline.unpack_list_columns(df)
        
        assert result.empty
        assert isinstance(result, pd.DataFrame)

    def test_unpack_list_columns_no_lists(self) -> None:
        """Validates DataFrame without list columns remains unchanged."""
        df = pd.DataFrame({
            "name": ["Alice", "Bob"],
            "age": [25, 30],
            "score": [95.5, 87.3]
        })
        
        result = DataPipeline.unpack_list_columns(df)
        
        pd.testing.assert_frame_equal(result, df)

    def test_unpack_list_columns_with_nan(self) -> None:
        """Validates handling of NaN values in list columns."""
        df = pd.DataFrame({
            "data": [["value", 0], np.nan, ["another", 0]]
        })
        
        result = DataPipeline.unpack_list_columns(df)
        
        assert result["data"].iloc[0] == "value"
        assert pd.isna(result["data"].iloc[1])
        assert result["data"].iloc[2] == "another"


# ============================================================================
# Clean Numeric Columns Tests
# ============================================================================

class TestCleanNumericColumns:
    """Test suite for numeric column cleaning functionality."""

    def test_clean_numeric_columns_with_units(self) -> None:
        """Validates extraction of numbers from strings with units."""
        df = pd.DataFrame({
            "weight": ["67.4 kg", "68.2 kg", "70.1 kg"],
            "power": ["285 watts", "300 watts", "275 watts"]
        })
        
        result = DataPipeline.clean_numeric_columns(df, ["weight", "power"])
        
        assert result["weight"].iloc[0] == 67.4
        assert result["weight"].iloc[1] == 68.2
        assert result["power"].iloc[0] == 285.0
        assert pd.api.types.is_float_dtype(result["weight"])

    def test_clean_numeric_columns_already_numeric(self) -> None:
        """Validates handling of already numeric columns."""
        df = pd.DataFrame({
            "value": [100, 200, 300]
        })
        
        result = DataPipeline.clean_numeric_columns(df, ["value"])
        
        assert result["value"].iloc[0] == 100.0
        assert pd.api.types.is_float_dtype(result["value"])

    def test_clean_numeric_columns_negative_numbers(self) -> None:
        """Validates extraction of negative numbers."""
        df = pd.DataFrame({
            "temp": ["-5.2 °C", "10.5 °C", "-12.8 °C"]
        })
        
        result = DataPipeline.clean_numeric_columns(df, ["temp"])
        
        assert result["temp"].iloc[0] == -5.2
        assert result["temp"].iloc[2] == -12.8

    def test_clean_numeric_columns_decimal_only(self) -> None:
        """Validates extraction of decimal numbers."""
        df = pd.DataFrame({
            "ratio": ["0.85", "0.92", "0.78"]
        })
        
        result = DataPipeline.clean_numeric_columns(df, ["ratio"])
        
        assert result["ratio"].iloc[0] == 0.85
        assert result["ratio"].iloc[1] == 0.92

    def test_clean_numeric_columns_no_numbers(self) -> None:
        """Validates handling of strings without numbers."""
        df = pd.DataFrame({
            "text": ["no numbers here", "also none", "still none"]
        })
        
        result = DataPipeline.clean_numeric_columns(df, ["text"])
        
        # Should result in NaN values
        assert pd.isna(result["text"].iloc[0])

    def test_clean_numeric_columns_mixed_formats(self) -> None:
        """Validates handling of mixed numeric formats."""
        df = pd.DataFrame({
            "value": ["100.5 kg", "200", "300.75 lbs", "400"]
        })
        
        result = DataPipeline.clean_numeric_columns(df, ["value"])
        
        assert result["value"].iloc[0] == 100.5
        assert result["value"].iloc[1] == 200.0
        assert result["value"].iloc[2] == 300.75

    def test_clean_numeric_columns_nonexistent_column(self) -> None:
        """Validates handling of columns that don't exist in DataFrame."""
        df = pd.DataFrame({
            "existing": ["100 kg", "200 kg"]
        })
        
        result = DataPipeline.clean_numeric_columns(df, ["nonexistent"])
        
        # Should not crash, just skip the column
        assert "existing" in result.columns
        assert "nonexistent" not in result.columns

    def test_clean_numeric_columns_empty_dataframe(self) -> None:
        """Validates handling of empty DataFrame."""
        df = pd.DataFrame()
        
        result = DataPipeline.clean_numeric_columns(df, ["any_column"])
        
        assert result.empty

    def test_clean_numeric_columns_with_commas(self, sample_profile_df: pd.DataFrame) -> None:
        """Validates handling of numbers with comma separators.
        
        Args:
            sample_profile_df: Fixture providing sample profile data
        """
        # Note: The regex in clean_numeric_columns doesn't handle commas
        # This test documents current behavior
        df = pd.DataFrame({
            "zpoints": ["7,301", "8,542", "6,123"]
        })
        
        result = DataPipeline.clean_numeric_columns(df, ["zpoints"])
        
        # Will extract first number before comma
        assert result["zpoints"].iloc[0] == 7.0

    def test_clean_numeric_columns_scientific_notation(self) -> None:
        """Validates handling of scientific notation."""
        df = pd.DataFrame({
            "value": ["1.5e3", "2.3e-2", "4.5e1"]
        })
        
        result = DataPipeline.clean_numeric_columns(df, ["value"])
        
        assert result["value"].iloc[0] == 1.5


# ============================================================================
# Format Event Dates Tests
# ============================================================================

class TestFormatEventDates:
    """Test suite for Unix timestamp formatting functionality."""

    def test_format_event_dates_basic(self) -> None:
        """Validates conversion of Unix timestamps to YYYY/MM/DD format."""
        df = pd.DataFrame({
            "event_date": [1695052800, 1694966400, 1694880000],
            "name": ["Event A", "Event B", "Event C"]
        })
        
        result = DataPipeline.format_event_dates(df, "event_date")
        
        assert result["event_date"].iloc[0] == "2023/09/18"
        assert result["event_date"].iloc[1] == "2023/09/17"
        assert isinstance(result["event_date"].iloc[0], str)

    def test_format_event_dates_sorting(self) -> None:
        """Validates that dates are sorted in descending order."""
        df = pd.DataFrame({
            "event_date": [1694880000, 1695052800, 1694966400],
            "name": ["Event C", "Event A", "Event B"]
        })
        
        result = DataPipeline.format_event_dates(df, "event_date")
        
        # Should be sorted newest first
        assert result["event_date"].iloc[0] == "2023/09/18"
        assert result["event_date"].iloc[1] == "2023/09/17"
        assert result["event_date"].iloc[2] == "2023/09/16"

    def test_format_event_dates_custom_column(self) -> None:
        """Validates formatting with custom column name."""
        df = pd.DataFrame({
            "custom_date": [1695052800, 1694966400],
            "name": ["Event A", "Event B"]
        })
        
        result = DataPipeline.format_event_dates(df, "custom_date")
        
        assert result["custom_date"].iloc[0] == "2023/09/18"

    def test_format_event_dates_missing_column(self) -> None:
        """Validates handling when date column doesn't exist."""
        df = pd.DataFrame({
            "name": ["Event A", "Event B"]
        })
        
        result = DataPipeline.format_event_dates(df, "event_date")
        
        # Should return DataFrame unchanged
        assert "event_date" not in result.columns
        assert "name" in result.columns

    def test_format_event_dates_empty_dataframe(self) -> None:
        """Validates handling of empty DataFrame."""
        df = pd.DataFrame()
        
        result = DataPipeline.format_event_dates(df, "event_date")
        
        assert result.empty

    def test_format_event_dates_invalid_timestamps(self) -> None:
        """Validates handling of invalid timestamp values."""
        df = pd.DataFrame({
            "event_date": ["invalid", 1695052800, None],
            "name": ["Event A", "Event B", "Event C"]
        })
        
        result = DataPipeline.format_event_dates(df, "event_date")
        
        # Invalid values should become NaT/NaN
        assert pd.isna(result["event_date"].iloc[0]) or result["event_date"].iloc[0] == "NaT"
        assert result["event_date"].iloc[1] == "2023/09/18"

    def test_format_event_dates_string_timestamps(self) -> None:
        """Validates conversion of string Unix timestamps."""
        df = pd.DataFrame({
            "event_date": ["1695052800", "1694966400"],
            "name": ["Event A", "Event B"]
        })
        
        result = DataPipeline.format_event_dates(df, "event_date")
        
        assert result["event_date"].iloc[0] == "2023/09/18"


# ============================================================================
# Export to CSV Tests
# ============================================================================

class TestExportToCsv:
    """Test suite for CSV export functionality."""

    def test_export_to_csv_basic(self, tmp_path: Any) -> None:
        """Validates basic CSV export functionality.
        
        Args:
            tmp_path: pytest fixture providing temporary directory
        """
        df = pd.DataFrame({
            "name": ["Alice", "Bob"],
            "score": [95, 87]
        })
        
        output_dir = str(tmp_path / "output")
        filepath = DataPipeline.export_to_csv(df, "test.csv", output_dir)
        
        assert os.path.exists(filepath)
        assert filepath.endswith("test.csv")
        
        # Verify content
        loaded_df = pd.read_csv(filepath)
        assert len(loaded_df) == 2
        assert "name" in loaded_df.columns

    def test_export_to_csv_creates_directory(self, tmp_path: Any) -> None:
        """Validates that output directory is created if it doesn't exist.
        
        Args:
            tmp_path: pytest fixture providing temporary directory
        """
        df = pd.DataFrame({"col": [1, 2, 3]})
        
        output_dir = str(tmp_path / "new_output_dir")
        assert not os.path.exists(output_dir)
        
        filepath = DataPipeline.export_to_csv(df, "test.csv", output_dir)
        
        assert os.path.exists(output_dir)
        assert os.path.exists(filepath)

    def test_export_to_csv_utf8_encoding(self, tmp_path: Any) -> None:
        """Validates UTF-8 encoding for special characters.
        
        Args:
            tmp_path: pytest fixture providing temporary directory
        """
        df = pd.DataFrame({
            "name": ["José", "François", "北京"],
            "country": ["Uruguay", "France", "China"]
        })
        
        output_dir = str(tmp_path / "output")
        filepath = DataPipeline.export_to_csv(df, "unicode_test.csv", output_dir)
        
        # Read back with UTF-8 encoding
        loaded_df = pd.read_csv(filepath, encoding="utf-8")
        assert loaded_df["name"].iloc[0] == "José"
        assert loaded_df["name"].iloc[2] == "北京"

    def test_export_to_csv_empty_dataframe(self, tmp_path: Any) -> None:
        """Validates handling of empty DataFrame (should skip export).
        
        Args:
            tmp_path: pytest fixture providing temporary directory
        """
        df = pd.DataFrame()
        
        output_dir = str(tmp_path / "output")
        filepath = DataPipeline.export_to_csv(df, "empty.csv", output_dir)
        
        assert filepath == ""
        assert not os.path.exists(os.path.join(output_dir, "empty.csv"))

    def test_export_to_csv_no_index(self, tmp_path: Any) -> None:
        """Validates that index is not written to CSV.
        
        Args:
            tmp_path: pytest fixture providing temporary directory
        """
        df = pd.DataFrame({"col": [1, 2, 3]})
        
        output_dir = str(tmp_path / "output")
        filepath = DataPipeline.export_to_csv(df, "no_index.csv", output_dir)
        
        # Read and check that there's no unnamed index column
        loaded_df = pd.read_csv(filepath)
        assert "Unnamed: 0" not in loaded_df.columns
        assert len(loaded_df.columns) == 1

    def test_export_to_csv_large_dataframe(self, tmp_path: Any) -> None:
        """Validates export of larger DataFrame.
        
        Args:
            tmp_path: pytest fixture providing temporary directory
        """
        df = pd.DataFrame({
            "id": range(1000),
            "value": np.random.rand(1000)
        })
        
        output_dir = str(tmp_path / "output")
        filepath = DataPipeline.export_to_csv(df, "large.csv", output_dir)
        
        assert os.path.exists(filepath)
        loaded_df = pd.read_csv(filepath)
        assert len(loaded_df) == 1000

    def test_export_to_csv_default_output_dir(self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        """Validates default output directory is used when not specified.
        
        Args:
            tmp_path: pytest fixture providing temporary directory
            monkeypatch: pytest fixture for modifying environment
        """
        # Change to temp directory for this test
        monkeypatch.chdir(tmp_path)
        
        df = pd.DataFrame({"col": [1, 2]})
        filepath = DataPipeline.export_to_csv(df, "default.csv")
        
        assert "output" in filepath
        assert os.path.exists(filepath)


# ============================================================================
# Integration Tests for DataPipeline
# ============================================================================

class TestDataPipelineIntegration:
    """Integration tests for complete data transformation pipeline."""

    def test_full_profile_transformation(self, sample_profile_df: pd.DataFrame) -> None:
        """Validates complete profile data transformation pipeline.
        
        Args:
            sample_profile_df: Fixture providing sample profile data
        """
        # Clean numeric columns
        numeric_cols = ["weight", "zftp", "zpoints", "racing_score"]
        result = DataPipeline.clean_numeric_columns(sample_profile_df, numeric_cols)
        
        assert result["weight"].iloc[0] == 67.4
        assert result["zftp"].iloc[0] == 285.0
        assert result["racing_score"].iloc[0] == 652.3
        assert pd.api.types.is_float_dtype(result["weight"])

    def test_full_events_transformation(self, sample_events_df: pd.DataFrame) -> None:
        """Validates complete events data transformation pipeline.
        
        Args:
            sample_events_df: Fixture providing sample events data
        """
        # Unpack list columns
        unpacked = DataPipeline.unpack_list_columns(sample_events_df)
        
        # Format dates
        formatted = DataPipeline.format_event_dates(unpacked, "event_date")
        
        assert formatted["time"].iloc[0] == "3600.5"
        assert formatted["weight"].iloc[0] == "67.4"
        assert formatted["event_date"].iloc[0] == "2023/09/18"
        assert formatted["event_date"].iloc[1] == "2023/09/17"

    def test_chained_transformations_preserve_data(self) -> None:
        """Validates that chained transformations don't lose data."""
        df = pd.DataFrame({
            "id": [1, 2, 3],
            "value": [["100", 0], ["200", 0], ["300", 0]],
            "weight": ["67.4 kg", "68.2 kg", "70.1 kg"],
            "date": [1695052800, 1694966400, 1694880000]
        })
        
        # Apply all transformations
        result = DataPipeline.unpack_list_columns(df)
        result = DataPipeline.clean_numeric_columns(result, ["weight"])
        result = DataPipeline.format_event_dates(result, "date")
        
        assert len(result) == 3
        assert "id" in result.columns
        assert result["value"].iloc[0] == 100
        assert result["weight"].iloc[0] == 67.4
        assert result["date"].iloc[0] == "2023/09/18"
