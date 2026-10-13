"""
Pytest configuration and shared fixtures for Sift test suite.
"""

import os
import sys
import tempfile
import pytest
import pandas as pd

# Add repository root and tests directory to sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tests.synthetic_data import (
    generate_50k_canonical_dataset,
    generate_waterline_null_dataset,
    generate_reconciliation_dataset,
    save_dataset_csv,
    save_dataset_parquet,
)


@pytest.fixture(scope="session")
def canonical_50k_data():
    """Generates and caches 50,000-row synthetic dataset with 15 planted exceptions."""
    df, meta = generate_50k_canonical_dataset(seed=42, inject_exceptions=True)
    return df, meta


@pytest.fixture(scope="session")
def waterline_data():
    """Generates and caches waterline uniform null distribution dataset."""
    df = generate_waterline_null_dataset(n_rows=20000, seed=101)
    return df


@pytest.fixture
def temp_workspace_dir():
    """Provides a fresh isolated temporary directory for test artifacts and .mxa files."""
    with tempfile.TemporaryDirectory(prefix="sift_test_ws_") as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_controls():
    """Default comparability controls."""
    return ["product_family", "sales_region"]


@pytest.fixture
def sample_investigation_dims():
    """Default investigation dimensions."""
    return ["sales_rep", "discount_reason", "channel"]
