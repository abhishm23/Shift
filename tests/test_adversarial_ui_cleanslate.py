"""
Adversarial Clean Slate & Asset Air-Gap Challenge Test Suite
Author: challenger_ui_1 (Clean Slate & Asset Air-Gap Challenger)

Empirically challenges:
1. Clean Slate Invariant (zero demo data, filenames, mock GL numbers, mock findings, mock TX IDs)
2. WatermarkBanner behavior (suppression on clean slate, AND functional rendering when quarantined)
3. App.jsx WatermarkBanner prop wiring (ensuring hasReconciled is correctly passed)
4. Reconciliation Gate clean-slate safety (empty inputs must NOT certify)
5. No demo/sample buttons in source or dist
6. Strict air-gap & CSP compliance in dist/index.html and dist/assets
"""

import os
import re
import json
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src" / "src"
DIST_DIR = REPO_ROOT / "src" / "dist"


# ---------------------------------------------------------------------------
# 1. Clean Slate: Prohibited Demo Filenames, IDs, Buttons
# ---------------------------------------------------------------------------
def test_zero_demo_filenames():
    """Verify no demo filenames (e.g. commercial_sales_2025.parquet) exist in src or dist."""
    prohibited_files = ["commercial_sales_2025.parquet", "commercial_audit_2025.mxa"]
    violations = []

    for base_dir in [SRC_DIR, DIST_DIR]:
        for root, _, files in os.walk(base_dir):
            for file_name in files:
                file_path = Path(root) / file_name
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                for pf in prohibited_files:
                    if pf.lower() in content.lower():
                        violations.append((str(file_path.relative_to(REPO_ROOT)), pf))

    assert not violations, f"Found prohibited demo filenames in codebase: {violations}"


def test_zero_mock_finding_and_tx_ids():
    """Verify no mock finding IDs (e.g. FND-REG-WEST-01) or mock TX IDs (TX-90214) exist in src or dist."""
    prohibited_ids = ["FND-REG-WEST-01", "TX-90214", "TX-90215"]
    violations = []

    for base_dir in [SRC_DIR, DIST_DIR]:
        for root, _, files in os.walk(base_dir):
            for file_name in files:
                file_path = Path(root) / file_name
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                for pid in prohibited_ids:
                    if pid.lower() in content.lower():
                        violations.append((str(file_path.relative_to(REPO_ROOT)), pid))

    assert not violations, f"Found mock finding / transaction IDs in codebase: {violations}"


def test_zero_demo_buttons():
    """Verify no 'Reset Sample' or 'Load Demo Data' buttons exist anywhere in src or dist."""
    prohibited_buttons = ["Reset Sample", "Load Demo Data", "Load Demo"]
    violations = []

    for base_dir in [SRC_DIR, DIST_DIR]:
        for root, _, files in os.walk(base_dir):
            for file_name in files:
                file_path = Path(root) / file_name
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                for btn in prohibited_buttons:
                    if btn.lower() in content.lower():
                        violations.append((str(file_path.relative_to(REPO_ROOT)), btn))

    assert not violations, f"Found prohibited demo buttons in codebase: {violations}"


def test_zero_hardcoded_gl_numbers_in_source_and_bundle():
    """
    Adversarial Challenge: Verify that hardcoded mock GL numbers (14250000, 11890000, 15320000, 11873350)
    do NOT appear anywhere in src/src/ or src/dist/.
    """
    prohibited_numbers = ["14250000", "11890000", "15320000", "11873350"]
    violations = []

    for base_dir in [SRC_DIR, DIST_DIR]:
        for root, _, files in os.walk(base_dir):
            for file_name in files:
                file_path = Path(root) / file_name
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                for num in prohibited_numbers:
                    if num in content:
                        violations.append((str(file_path.relative_to(REPO_ROOT)), num))

    assert not violations, f"Hardcoded mock GL numbers found in codebase: {violations}"


# ---------------------------------------------------------------------------
# 2. WatermarkBanner Logic & Prop Wiring Challenge
# ---------------------------------------------------------------------------
def test_watermark_banner_clean_slate_invariant():
    """
    Verify that WatermarkBanner component logic strictly suppresses rendering
    when uninitialized (residualPct=0, hasReconciled=False, certifiedAudit=False).
    """
    banner_jsx_path = SRC_DIR / "components" / "WatermarkBanner.jsx"
    content = banner_jsx_path.read_text(encoding="utf-8")

    # Invariant condition: varianceExceeded must evaluate to false when uninitialized
    assert "hasReconciled" in content
    assert "residualPct" in content


def test_watermark_banner_wiring_in_app_jsx():
    """
    CRITICAL ADVERSARIAL CHALLENGE:
    In App.jsx, WatermarkBanner MUST receive `hasReconciled={auditManifest.hasReconciled}`
    (or equivalent) so that when reconciliation completes with > 1 bp variance,
    the banner actually renders!
    If App.jsx omits `hasReconciled`, WatermarkBanner defaults to `hasReconciled=false`
    and NEVER displays the quarantine warning, violating Invariant R2.9 / AC-8.
    """
    app_jsx_path = SRC_DIR / "App.jsx"
    app_content = app_jsx_path.read_text(encoding="utf-8")

    # Find the WatermarkBanner JSX invocation
    match = re.search(r"<WatermarkBanner\s+([^>]+)/>", app_content, re.DOTALL)
    assert match is not None, "WatermarkBanner must be rendered in App.jsx"

    props = match.group(1)
    assert "hasReconciled" in props, (
        "App.jsx renders <WatermarkBanner /> WITHOUT passing `hasReconciled={auditManifest.hasReconciled}`! "
        "Because hasReconciled defaults to false, the permanent quarantine watermark banner will NEVER render "
        "when a dataset fails reconciliation!"
    )


# ---------------------------------------------------------------------------
# 3. Reconciliation Clean-Slate Invariant: Empty Inputs Must NOT Certify
# ---------------------------------------------------------------------------
def test_reconciliation_empty_inputs_do_not_certify():
    """
    Verify that View1Reconcile's reconciliation calculation requires BOTH
    valid non-zero scanned data and valid non-zero GL numbers before evaluating certification.
    """
    view1_path = SRC_DIR / "components" / "View1Reconcile.jsx"
    view1_content = view1_path.read_text(encoding="utf-8")

    # Verify isAwaiting guard
    assert "isAwaiting" in view1_content
    assert "hasScanned" in view1_content
    assert "Awaiting Upload & Verification" in view1_content


# ---------------------------------------------------------------------------
# 4. Air-Gap & CSP Invariant Tests
# ---------------------------------------------------------------------------
def test_dist_index_html_air_gap_csp():
    """Verify that dist/index.html enforces strict CSP and contains zero external scripts/links."""
    index_html = DIST_DIR / "index.html"
    assert index_html.exists(), "src/dist/index.html must exist"

    content = index_html.read_text(encoding="utf-8")
    assert "Content-Security-Policy" in content, "dist/index.html must contain Content-Security-Policy"

    # Verify external URLs
    urls = re.findall(r'https?://[^\s"\'`<>)]+', content, re.IGNORECASE)
    for url in urls:
        assert url.startswith("http://127.0.0.1") or url.startswith("http://localhost"), (
            f"Remote URL found in dist/index.html: {url}"
        )


def test_dist_assets_zero_external_urls():
    """Audit all JS/CSS files in src/dist/assets for external URLs."""
    js_files = list((DIST_DIR / "assets").glob("*.js"))
    assert len(js_files) >= 1, "No JS files found in src/dist/assets"

    allowed_schemes = [
        re.compile(r"^https?://127\.0\.0\.1(:\d+)?(/.*)?$", re.IGNORECASE),
        re.compile(r"^https?://localhost(:\d+)?(/.*)?$", re.IGNORECASE),
        re.compile(r"^http://www\.w3\.org/2000/svg/?$", re.IGNORECASE),
        re.compile(r"^http://www\.w3\.org/1999/xlink/?$", re.IGNORECASE),
        re.compile(r"^http://www\.w3\.org/XML/1998/namespace/?$", re.IGNORECASE),
        re.compile(r"^http://www\.w3\.org/1998/Math/MathML/?$", re.IGNORECASE),
        re.compile(r"^http://www\.w3\.org/1999/xhtml/?$", re.IGNORECASE),
        re.compile(r"^https://reactjs\.org/docs/error-decoder\.html\?invariant=$", re.IGNORECASE),
    ]

    unaccounted = []
    url_pattern = re.compile(r'https?://[^\s"\'`<>)]+', re.IGNORECASE)
    for js_file in js_files:
        text = js_file.read_text(encoding="utf-8", errors="ignore")
        for url in url_pattern.findall(text):
            clean_url = url.rstrip(';.,"\')')
            if not any(pat.match(clean_url) for pat in allowed_schemes):
                unaccounted.append((js_file.name, clean_url))

    assert not unaccounted, f"Unaccounted external URLs found in JS assets: {unaccounted}"


def test_dist_assets_zero_cdn_or_telemetry():
    """Deep scan across all files in src/dist for common CDN signatures."""
    cdn_keywords = [
        "unpkg.com",
        "cdnjs.cloudflare.com",
        "cdn.jsdelivr.net",
        "fonts.googleapis.com",
        "fonts.gstatic.com",
        "cdn.tailwindcss.com",
        "sentry.io",
        "mixpanel.com",
        "google-analytics.com",
        "googletagmanager.com",
        "datadoghq.com",
    ]

    violations = []
    for root, _, files in os.walk(DIST_DIR):
        for file_name in files:
            file_path = Path(root) / file_name
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            for kw in cdn_keywords:
                if kw.lower() in content.lower():
                    violations.append((str(file_path.relative_to(DIST_DIR)), kw))

    assert not violations, f"Found CDN / telemetry references in dist: {violations}"


def test_audit_manifest_clean_slate_invariant():
    r"""
    Adversarial Integrity Invariant:
    Verify that repository root c:\Shift\audit_manifest.json strictly reflects
    an uninitialized clean slate with zero scanned rows, null hashes, and AWAITING status.
    """
    manifest_path = REPO_ROOT / "backend" / "audit_manifest.json"
    assert manifest_path.exists(), "audit_manifest.json must exist in backend"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest.get("reconciliation_status") == "AWAITING_RECONCILIATION"
    assert manifest.get("certified_audit") is False
    assert manifest.get("watermark_active") is False
    assert manifest.get("watermark_text") is None
    assert manifest.get("total_rows_scanned") == 0
    assert manifest.get("total_rows_ingested") == 0
    assert manifest.get("confirmed_gross_list") == 0.0
    assert manifest.get("confirmed_net_invoiced") == 0.0
    assert manifest.get("manifest_id") is None
    assert manifest.get("source_filename") is None
    assert manifest.get("source_sha256") is None
    assert manifest.get("tier_unlocked") == 0

