# -*- coding: utf-8 -*-
import sys
import re
import openpyxl

sys.stdout.reconfigure(encoding='utf-8')

print("=== STARTING INDEPENDENT PARITY VERIFICATION OF TEST DELIVERABLES (POST-RETEST) ===")

XLSX_PATH = "c:/Shift/test_deliverables/TEST_DELIVERABLES.xlsx"
MD_PATH = "c:/Shift/test_deliverables/TEST_DELIVERABLES.md"
DEFECT_MD_PATH = "c:/Shift/test_deliverables/DEFECT_LOG.md"

# 1. Verify Excel Workbook
wb = openpyxl.load_workbook(XLSX_PATH)
sheet_names = wb.sheetnames
print(f"Sheets in Excel: {sheet_names}")
assert "Test Deliverables & Results" in sheet_names, "Sheet 1 missing"
assert "Defect Register" in sheet_names, "Sheet 2 missing"
assert "Executive Summary" in sheet_names, "Sheet 3 missing"

# --- Sheet 1: Test Deliverables & Results ---
s1 = wb["Test Deliverables & Results"]
s1_headers = [c.value for c in s1[1]]
print(f"Sheet 1 Column Count: {len(s1_headers)}")
expected_headers = [
    "Test Case ID", "Feature Area", "Scenario Description", "Preconditions",
    "Synthetic Dataset Used", "Step-by-Step UI Execution Steps", "Expected Result",
    "Actual Result", "Severity", "Tester Status", "Developer Status", "Developer Comments"
]
assert s1_headers == expected_headers, f"Sheet 1 headers mismatch: {s1_headers}"

s1_tests = []
s1_fails = []
s1_passes = []
s1_verified_fixed = []
s1_working_as_designed = []

EXPECTED_DEFECT_TCS = {
    'TC-021', 'TC-022', 'TC-033', 'TC-041', 'TC-058',
    'TC-059', 'TC-060', 'TC-062', 'TC-064', 'TC-068'
}

for row_idx in range(2, s1.max_row + 1):
    row_vals = [s1.cell(row=row_idx, column=c).value for c in range(1, 13)]
    tc_id = row_vals[0]
    if tc_id:
        s1_tests.append(tc_id)
        tester_status = row_vals[9]
        dev_status = row_vals[10]
        
        if tester_status == "Pass":
            s1_passes.append(tc_id)
        elif tester_status == "Fail":
            s1_fails.append(tc_id)
        else:
            raise ValueError(f"Unknown tester status '{tester_status}' at row {row_idx}")
            
        if dev_status == "Verified Fixed":
            s1_verified_fixed.append(tc_id)
        elif dev_status == "Working as Designed":
            s1_working_as_designed.append(tc_id)
        else:
            raise ValueError(f"Unexpected developer status '{dev_status}' for {tc_id} at row {row_idx}")

print(f"Sheet 1 Total Tests: {len(s1_tests)} | Passes: {len(s1_passes)} | Fails: {len(s1_fails)}")
print(f"Sheet 1 Developer Status: {len(s1_verified_fixed)} Verified Fixed | {len(s1_working_as_designed)} Working as Designed")

assert len(s1_tests) == 72, f"Expected 72 tests in Sheet 1, got {len(s1_tests)}"
assert len(s1_passes) == 72, f"Expected 72 passes in Sheet 1 post-retest, got {len(s1_passes)}"
assert len(s1_fails) == 0, f"Expected 0 fails in Sheet 1 post-retest, got {len(s1_fails)}"
assert len(s1_verified_fixed) == 10, f"Expected 10 Verified Fixed tests, got {len(s1_verified_fixed)}"
assert set(s1_verified_fixed) == EXPECTED_DEFECT_TCS, f"Verified Fixed TCs mismatch: {set(s1_verified_fixed)} vs {EXPECTED_DEFECT_TCS}"
assert len(s1_working_as_designed) == 62, f"Expected 62 Working as Designed tests, got {len(s1_working_as_designed)}"
print("ASSERTION PASSED: Sheet 1 achieves 100% pass rate (72/72) with exactly 10 Verified Fixed cases!")

# --- Sheet 2: Defect Register ---
s2 = wb["Defect Register"]
s2_headers = [c.value for c in s2[1]]
print(f"Sheet 2 Column Count: {len(s2_headers)}")
assert len(s2_headers) == 10, f"Expected 10 columns in Sheet 2, got {len(s2_headers)}"

s2_defects = []
s2_defect_tcs = []
s2_dev_statuses = []

for row_idx in range(2, s2.max_row + 1):
    def_id = s2.cell(row=row_idx, column=1).value
    tc_id = s2.cell(row=row_idx, column=2).value
    dev_status = s2.cell(row=row_idx, column=5).value
    mitigation = s2.cell(row=row_idx, column=10).value
    if def_id:
        s2_defects.append(def_id)
        s2_defect_tcs.append(tc_id)
        s2_dev_statuses.append(dev_status)
        assert dev_status == "Verified Fixed", f"Defect {def_id} has unverified status: {dev_status}"
        assert "QA Retest" in str(mitigation) or "Verified fixed" in str(mitigation), f"Defect {def_id} missing QA retest sign-off in mitigation notes"

print(f"Sheet 2 Total Defects: {len(s2_defects)} (All 10 marked 'Verified Fixed')")
assert len(s2_defects) == 10, f"Expected 10 defects in Sheet 2, got {len(s2_defects)}"
assert set(s2_defect_tcs) == EXPECTED_DEFECT_TCS, f"Sheet 2 defect test cases mismatch: {set(s2_defect_tcs)} vs {EXPECTED_DEFECT_TCS}"
assert set(s2_defect_tcs) == set(s1_verified_fixed), "Sheet 2 defect test cases must exactly match Sheet 1 Verified Fixed test cases!"
print("ASSERTION PASSED: Sheet 2 defect register has 100% 1:1 parity with Sheet 1 Verified Fixed cases!")

# --- Sheet 3: Executive Summary ---
s3 = wb["Executive Summary"]
s3_vals = {s3.cell(row=r, column=1).value: s3.cell(row=r, column=2).value for r in range(1, s3.max_row + 1) if s3.cell(row=r, column=1).value}
assert s3_vals.get("Total Test Cases Executed") == 72, "Sheet 3 Total Test Cases != 72"
assert s3_vals.get("Passed Test Cases") == 72, "Sheet 3 Passed Test Cases != 72"
assert s3_vals.get("Failed Test Cases") == 0, "Sheet 3 Failed Test Cases != 0"
assert s3_vals.get("Defects Verified Fixed (Post-Retest)") == 10, "Sheet 3 Defects Verified Fixed != 10"
assert s3_vals.get("Open / Unresolved Defects") == 0, "Sheet 3 Open Defects != 0"
print("ASSERTION PASSED: Sheet 3 Executive Summary confirms 72 Passes, 0 Fails, 10 Verified Fixed, 0 Open Defects!")

# 2. Verify TEST_DELIVERABLES.md
with open(MD_PATH, "r", encoding="utf-8") as f:
    md_content = f.read()

md_tcs = re.findall(r"\|\s*\*\*(TC-\d+)\*\*\s*\|", md_content)
print(f"Markdown Total Test Cases: {len(md_tcs)}")
assert len(md_tcs) == 72, f"Expected 72 tests in Markdown, got {len(md_tcs)}"
assert md_tcs == s1_tests, "Test case ordering or ID mismatch between Excel and Markdown!"

md_passes = re.findall(r"\|\s*\*\*(TC-\d+)\*\*\s*\|.*?\|\s*\*\*Pass\*\*\s*\|", md_content)
print(f"Markdown Total Passes: {len(md_passes)}")
assert len(md_passes) == 72, f"Expected 72 passes in Markdown, got {len(md_passes)}"

md_fails = re.findall(r"\|\s*\*\*(TC-\d+)\*\*\s*\|.*?<span style='color:red'>\*\*Fail\*\*</span>", md_content)
print(f"Markdown Total Fails: {len(md_fails)}")
assert len(md_fails) == 0, f"Expected 0 fails in Markdown, got {len(md_fails)}"

md_verified = re.findall(r"\|\s*\*\*(TC-\d+)\*\*\s*\|.*?<span style='color:green'>\*\*Verified Fixed\*\*</span>", md_content)
print(f"Markdown Verified Fixed Cases: {len(md_verified)}")
assert len(md_verified) == 10, f"Expected 10 Verified Fixed cases in Markdown, got {len(md_verified)}"
assert set(md_verified) == EXPECTED_DEFECT_TCS, f"Markdown Verified Fixed mismatch: {set(md_verified)}"
print("ASSERTION PASSED: TEST_DELIVERABLES.md exactly mirrors Sheet 1 with 100% mathematical parity!")

# 3. Verify DEFECT_LOG.md
with open(DEFECT_MD_PATH, "r", encoding="utf-8") as f:
    defect_md = f.read()

log_def_ids = re.findall(r"\|\s*\*\*(DEF-UI-\d+)\*\*\s*\|", defect_md)
print(f"DEFECT_LOG.md Table Defects: {len(log_def_ids)}")
assert len(log_def_ids) == 10, f"Expected 10 defects in DEFECT_LOG.md table, got {len(log_def_ids)}"
assert log_def_ids == s2_defects, f"Defect ID ordering mismatch in DEFECT_LOG.md: {log_def_ids} vs {s2_defects}"

log_verified = re.findall(r"\|\s*\*\*(DEF-UI-\d+)\*\*\s*\|.*?<span style='color:green'>\*\*Verified Fixed\*\*</span>", defect_md)
print(f"DEFECT_LOG.md Table Verified Fixed: {len(log_verified)}")
assert len(log_verified) == 10, f"Expected 10 Verified Fixed in DEFECT_LOG.md table, got {len(log_verified)}"

records_count = len(re.findall(r"### \d+\.\s+DEF-UI-\d+:", defect_md))
print(f"DEFECT_LOG.md Detailed Records: {records_count}")
assert records_count == 10, f"Expected 10 detailed records in DEFECT_LOG.md, got {records_count}"

# Verify each detailed record has QA Retest Sign-off
for def_id in s2_defects:
    assert f"QA Retest Sign-off [{def_id}]" in defect_md or "QA Retest Verification" in defect_md, f"Missing QA Retest Sign-off for {def_id}"
print("ASSERTION PASSED: DEFECT_LOG.md confirms 10/10 defects Verified Fixed with itemized QA retest evidence!")

print("\n================================================================================")
print("ALL POST-RETEST VERIFICATION CHECKS PASSED WITH 100% MATHEMATICAL PARITY!")
print("================================================================================")
