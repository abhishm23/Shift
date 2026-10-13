"""
DuckDB and Storage Configuration for Sift Desktop Application.
Enforces 4GB memory ceiling, automatic disk spilling, and concurrency settings.
"""

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional
import duckdb


@dataclass
class DuckDBConfig:
    """Configuration container for in-process DuckDB engine."""
    max_memory: str = "4GB"
    temp_directory: str = ""
    threads: int = 4
    preserve_insertion_order: bool = False
    default_order: str = "asc"

    def get_spill_directory(self) -> str:
        """
        Returns verified, writable temporary spilling directory.
        Creates the directory if it does not exist.
        """
        if self.temp_directory:
            spill_path = os.path.abspath(self.temp_directory)
        else:
            base_dir = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
            spill_path = os.path.join(base_dir, "Sift", "duckdb_spill")

        os.makedirs(spill_path, exist_ok=True)
        return spill_path

    def to_connect_config(self) -> Dict[str, Any]:
        """Returns dictionary of connection parameters accepted by duckdb.connect."""
        return {
            "max_memory": self.max_memory,
            "temp_directory": self.get_spill_directory(),
            "threads": str(self.threads),
            "preserve_insertion_order": str(self.preserve_insertion_order).lower(),
            "default_order": self.default_order,
        }

    def apply_to_connection(self, con: duckdb.DuckDBPyConnection) -> None:
        """Applies configuration pragmas directly to an existing DuckDB connection."""
        spill_dir = self.get_spill_directory().replace("\\", "/")
        con.execute(f"SET max_memory = '{self.max_memory}';")
        con.execute(f"SET temp_directory = '{spill_dir}';")
        con.execute(f"SET threads = {self.threads};")
        con.execute(f"SET preserve_insertion_order = {str(self.preserve_insertion_order).lower()};")
        con.execute(f"SET default_order = '{self.default_order}';")
