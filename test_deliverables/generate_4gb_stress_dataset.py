# c:/Shift/test_deliverables/generate_4gb_stress_dataset.py
"""
Generates the 4 GB - 5 GB+ Multi-Million Row Stress Dataset for Project Sift Round 2 QA.
Utilizes existing schema and generator routines from generate_stress_datasets.py.

File target: c:/Shift/test_deliverables/datasets/dataset_stress_4gb_plus_wide.csv
Rows: 3,750,000 rows
Columns: 87 columns
Target Size: ~5.12 GB (> 4.77 GiB)
"""

import os
import sys
import time
from pathlib import Path
import numpy as np
import pyarrow.csv as pacsv

# Import generator routines from existing test harness module
sys.path.insert(0, str(Path(__file__).parent))
from generate_stress_datasets import (
    build_pyarrow_schema,
    generate_batch_table,
    CulpritStatsAccumulator,
    compute_file_sha256
)

DATASETS_DIR = Path(r"c:/Shift/test_deliverables/datasets")
DATASETS_DIR.mkdir(parents=True, exist_ok=True)
TARGET_CSV = DATASETS_DIR / "dataset_stress_4gb_plus_wide.csv"

def generate_4gb_dataset():
    print("=" * 80)
    print("Project Sift: Generating 4 GB - 5 GB+ Multi-Million Row Stress Dataset")
    print(f"Target file: {TARGET_CSV}")
    print("=" * 80)
    
    total_rows = 3_750_000
    chunk_size = 250_000
    num_chunks = total_rows // chunk_size
    seed = 8842

    acc_alpha = CulpritStatsAccumulator("Culprit Alpha (4-Level)", "EMEA + Gold + MultiYear + EnterpriseCloud")
    acc_beta = CulpritStatsAccumulator("Culprit Beta (5-Level)", "Americas + Financial Services + SI + Tier 4 Gov + Software Solutions")
    acc_gamma = CulpritStatsAccumulator("Culprit Gamma (3-Level)", "APAC + Sovereign Air-Gap + Ultra Five-Nines")

    schema = build_pyarrow_schema()
    t0 = time.time()

    with open(TARGET_CSV, "wb") as f_out:
        writer = pacsv.CSVWriter(f_out, schema)
        for c in range(num_chunks):
            t_chunk_0 = time.time()
            start_row = c * chunk_size + 1
            rng = np.random.default_rng(seed + c)
            
            table = generate_batch_table(
                start_row_idx=start_row,
                batch_size=chunk_size,
                rng=rng,
                id_prefix="TX-4GB",
                acc_alpha=acc_alpha,
                acc_beta=acc_beta,
                acc_gamma=acc_gamma,
            )
            writer.write_table(table)
            t_chunk_1 = time.time()
            current_size_mb = TARGET_CSV.stat().st_size / (1024 * 1024)
            print(f"  -> Chunk {c+1}/{num_chunks} written ({start_row:,} to {start_row + chunk_size - 1:,}) in {t_chunk_1 - t_chunk_0:.2f}s | Current file size: {current_size_mb:.2f} MB")
        writer.close()

    t1 = time.time()
    file_size_bytes = TARGET_CSV.stat().st_size
    file_size_mb = file_size_bytes / (1024 * 1024)
    file_size_gb = file_size_bytes / (1024 * 1024 * 1024)

    print("\n" + "=" * 80)
    print("4 GB - 5 GB+ STRESS DATASET GENERATION COMPLETE")
    print(f"Elapsed Time: {t1 - t0:.2f}s")
    print(f"Row Count: {total_rows:,}")
    print(f"Column Count: {len(schema.names)}")
    print(f"File Size (Bytes): {file_size_bytes:,} bytes")
    print(f"File Size (MB): {file_size_mb:.2f} MB")
    print(f"File Size (GiB): {file_size_gb:.2f} GiB ({file_size_bytes / 1e9:.2f} GB)")
    print("=" * 80)

    assert file_size_bytes >= 4_000_000_000, f"File size {file_size_bytes} is under 4GB!"
    print("Verification SUCCESS: File size exceeds 4 GB - 5 GB+ requirement!")

if __name__ == "__main__":
    generate_4gb_dataset()
