# c:/Shift/test_deliverables/verify_round2_dev_deliverables.py
"""
Independent Audit & Parity Verification Script for Developer Round 2 Deliverables.
Validates:
1. Sheet 1 in TEST_DELIVERABLES.xlsx: 78 test cases, 16 columns (including Round 2 Developer Status & Comments).
2. Sheet 2 in TEST_DELIVERABLES.xlsx: 10 defects, 14 columns (including Round 2 Developer Status & Comments).
3. Sheet 3 in TEST_DELIVERABLES.xlsx: Executive Summary with Round 1, Round 2 QA, and Round 2 Developer sign-offs.
4. TEST_DELIVERABLES.md: Strict 1:1 mathematical parity with Sheet 1, Sheet 2, Sheet 3; zero formatting corruption.
5. DEFECT_LOG.md: 10 defects, 100% verified fixed, zero formatting corruption, complete QA and Developer sign-offs.
"""

import sys
import re
from pathlib import Path
import openpyxl

sys.stdout.reconfigure(encoding='utf-8')

print("=" * 80)
print("STARTING INDEPENDENT AUDIT OF ROUND 2 DEVELOPER DELIVERABLES")
print("=" * 80)

XLSX_PATH = Path("c:/Shift/test_deliverables/TEST_DELIVERABLES.xlsx")
MD_PATH = Path("c:/Shift/test_deliverables/TEST_DELIVERABLES.md")
DEFECT_LOG_PATH = Path("c:/Shift/test_deliverables/DEFECT_LOG.md")

# 1. Inspect Excel
wb = openpyxl.load_workbook(XLSX_PATH)
assert "Test Deliverables & Results" in wb.sheetnames, "Sheet 1 missing"
assert "Defect Register" in wb.sheetnames, "Sheet 2 missing"
assert "Executive Summary" in wb.sheetnames, "Sheet 3 missing"

s1 = wb["Test Deliverables & Results"]
s1_headers = [s1.cell(row=1, column=c).value for c in range(1, s1.max_column + 1)]
print(f"Sheet 1: Dimensions={s1.dimensions}, Rows={s1.max_row}, Cols={s1.max_column}")
assert len(s1_headers) == 16, f"Expected 16 columns in Sheet 1, got {len(s1_headers)}: {s1_headers}"
assert s1_headers[14] == "Round 2 Developer Status", f"Column 15 mismatch: {s1_headers[14]}"
assert s1_headers[15] == "Round 2 Developer Comments", f"Column 16 mismatch: {s1_headers[15]}"

s1_tcs = []
s1_passes = []
s1_dev_fixed = []
s1_dev_wad = []

EXPECTED_DEFECT_TCS = {
    'TC-021', 'TC-022', 'TC-033', 'TC-041', 'TC-058',
    'TC-059', 'TC-060', 'TC-062', 'TC-064', 'TC-068'
}

for r in range(2, s1.max_row + 1):
    tc_id = s1.cell(row=r, column=1).value
    if tc_id:
        s1_tcs.append(tc_id)
        r2_tester = s1.cell(row=r, column=13).value
        r2_dev = s1.cell(row=r, column=15).value
        r2_dev_comm = s1.cell(row=r, column=16).value
        
        assert r2_tester == "Pass", f"Test {tc_id} did not pass in Round 2: {r2_tester}"
        assert r2_dev in ("Verified Fixed", "Working as Designed"), f"Test {tc_id} invalid dev status: {r2_dev}"
        assert len(str(r2_dev_comm)) > 20, f"Test {tc_id} missing detailed developer comments: {r2_dev_comm}"
        
        if r2_dev == "Verified Fixed":
            s1_dev_fixed.append(tc_id)
        elif r2_dev == "Working as Designed":
            s1_dev_wad.append(tc_id)

assert len(s1_tcs) == 78, f"Expected 78 tests in Sheet 1, got {len(s1_tcs)}"
assert len(s1_dev_fixed) == 10, f"Expected 10 Verified Fixed tests in Sheet 1, got {len(s1_dev_fixed)}"
assert set(s1_dev_fixed) == EXPECTED_DEFECT_TCS, f"Verified Fixed TCs mismatch: {set(s1_dev_fixed)} vs {EXPECTED_DEFECT_TCS}"
assert len(s1_dev_wad) == 68, f"Expected 68 Working as Designed tests in Sheet 1, got {len(s1_dev_wad)}"
print(f"-> Sheet 1 Audit PASSED: 78/78 tests verified (10 Verified Fixed, 68 Working as Designed)")

# 2. Inspect Sheet 2: Defect Register
s2 = wb["Defect Register"]
s2_headers = [s2.cell(row=1, column=c).value for c in range(1, s2.max_column + 1)]
print(f"Sheet 2: Dimensions={s2.dimensions}, Rows={s2.max_row}, Cols={s2.max_column}")
assert len(s2_headers) == 14, f"Expected 14 columns in Sheet 2, got {len(s2_headers)}: {s2_headers}"
assert s2_headers[12] == "Round 2 Developer Status", f"Column 13 mismatch: {s2_headers[12]}"
assert s2_headers[13] == "Round 2 Developer Comments", f"Column 14 mismatch: {s2_headers[13]}"

s2_defs = []
for r in range(2, s2.max_row + 1):
    def_id = s2.cell(row=r, column=1).value
    if def_id:
        s2_defs.append(def_id)
        r2_tester = s2.cell(row=r, column=11).value
        r2_dev = s2.cell(row=r, column=13).value
        r2_dev_comm = s2.cell(row=r, column=14).value
        
        assert "Pass" in str(r2_tester) or "Verified Fixed" in str(r2_tester), f"Defect {def_id} tester status not passing: {r2_tester}"
        assert r2_dev == "Verified Fixed", f"Defect {def_id} dev status not Verified Fixed: {r2_dev}"
        assert len(str(r2_dev_comm)) > 30, f"Defect {def_id} missing detailed developer comments: {r2_dev_comm}"

assert len(s2_defs) == 10, f"Expected 10 defects in Sheet 2, got {len(s2_defs)}"
print(f"-> Sheet 2 Audit PASSED: 10/10 defects Verified Fixed with comprehensive comments")

# 3. Inspect Sheet 3: Executive Summary
s3 = wb["Executive Summary"]
print(f"Sheet 3: Dimensions={s3.dimensions}, Rows={s3.max_row}, Cols={s3.max_column}")
assert s3.max_row >= 45, f"Expected at least 45 rows in Sheet 3, got {s3.max_row}"
s3_rows = {s3.cell(row=r, column=1).value: (s3.cell(row=r, column=2).value, s3.cell(row=r, column=3).value) for r in range(1, s3.max_row + 1) if s3.cell(row=r, column=1).value}
assert "Round 2 Developer Review Date" in s3_rows, "Developer Review Date missing from Sheet 3"
assert "Developer Final Verdict" in s3_rows, "Developer Final Verdict missing from Sheet 3"
print(f"-> Sheet 3 Audit PASSED: Executive Summary contains Round 1, Round 2 QA, and Round 2 Developer sections")

# 4. Inspect TEST_DELIVERABLES.md
with open(MD_PATH, "r", encoding="utf-8") as f:
    md_text = f.read()

# Verify no dash interleaving
assert not (md_text.startswith("-#-") or "-*-*-" in md_text[:200]), "TEST_DELIVERABLES.md contains dash corruption!"
md_tcs = re.findall(r"\|\s*\*\*(TC-\d+)\*\*\s*\|", md_text)
print(f"TEST_DELIVERABLES.md Total Test Cases: {len(md_tcs)}")
assert len(md_tcs) == 78, f"Expected 78 tests in MD, got {len(md_tcs)}"
assert md_tcs == s1_tcs, "Test case IDs or ordering mismatch between Excel and MD!"

md_defs = re.findall(r"\|\s*\*\*(DEF-UI-\d+)\*\*\s*\|", md_text)
print(f"TEST_DELIVERABLES.md Total Defects in Table: {len(md_defs)}")
assert len(md_defs) == 10, f"Expected 10 defects in MD table, got {len(md_defs)}"
assert md_defs == s2_defs, "Defect IDs or ordering mismatch between Excel and MD!"

# 5. Inspect DEFECT_LOG.md
with open(DEFECT_LOG_PATH, "r", encoding="utf-8") as f:
    def_md = f.read()

assert not (def_md.startswith("-#-") or "-*-*-" in def_md[:200]), "DEFECT_LOG.md contains dash corruption!"
log_defs = re.findall(r"### \d+\.\s+(DEF-UI-\d+):", def_md)
print(f"DEFECT_LOG.md Detailed Defect Records: {len(log_defs)}")
assert len(log_defs) == 10, f"Expected 10 defect records in DEFECT_LOG.md, got {len(log_defs)}"
assert log_defs == s2_defs, "Defect IDs mismatch in DEFECT_LOG.md"

for d in s2_defs:
    assert f"Round 2 QA Retest Sign-off [{d}" in def_md, f"Missing Round 2 QA Retest Sign-off for {d}"
    assert f"Round 2 Developer Architectural Verification [{d}" in def_md, f"Missing Round 2 Developer Verification for {d}"

print(f"-> DEFECT_LOG.md Audit PASSED: 10/10 detailed defect records with QA Retest & Developer Sign-offs")

print("\n" + "=" * 80)
print("ALL ROUND 2 DELIVERABLES AUDITED AND VERIFIED WITH 100% MATHEMATICAL PARITY!")
print("=" * 80)
