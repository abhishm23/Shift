"""
Milestone 1 Test Suite: Desktop Shell & Local Runtime Harness
Verifies Tauri packaging configuration, Edge standalone app mode arguments,
FastAPI security headers, Host header validation, loopback CORS, and workspace lifecycle endpoints.
"""

import os
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent

from backend.app import app, state, ALLOWED_HOSTS
from backend.storage import close_workspace
from backend.run_desktop import (
    find_edge_browser,
    build_browser_args,
    probe_sift_health,
)


@pytest.fixture
def client():
    # Ensure clean state before each test
    if state.is_open():
        close_workspace(state.connection)
        state.connection = None
        state.active_path = None
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. Tauri Configuration & Schema Verification
# ---------------------------------------------------------------------------
def test_tauri_conf_schema_and_geometry():
    """Verifies that src-tauri/tauri.conf.json exists, parses, and has correct geometry/file associations."""
    tauri_conf_path = REPO_ROOT / "src-tauri" / "tauri.conf.json"
    assert tauri_conf_path.is_file(), "src-tauri/tauri.conf.json must exist"

    with open(tauri_conf_path, "r", encoding="utf-8") as f:
        conf = json.load(f)

    # Package metadata
    assert conf["package"]["productName"] == "Sift"
    assert conf["tauri"]["bundle"]["identifier"] == "com.sift.audit"

    # Window geometry specification
    windows = conf["tauri"]["windows"]
    assert len(windows) >= 1
    main_win = windows[0]
    assert main_win["width"] == 1440
    assert main_win["height"] == 900
    assert main_win["minWidth"] == 1024
    assert main_win["minHeight"] == 700
    assert "Sift" in main_win["title"]

    # File association for .mxa
    file_assocs = conf["tauri"]["bundle"]["windows"]["fileAssociations"]
    assert any("mxa" in assoc["ext"] for assoc in file_assocs)


def test_tauri_csp_blocks_external_network():
    """Verifies that tauri.conf.json security CSP restricts connections strictly to local loopback."""
    tauri_conf_path = REPO_ROOT / "src-tauri" / "tauri.conf.json"
    with open(tauri_conf_path, "r", encoding="utf-8") as f:
        conf = json.load(f)

    csp = conf["tauri"]["security"]["csp"]
    assert "default-src 'self'" in csp
    assert "connect-src 'self'" in csp
    assert "https://" not in csp, "CSP must not allow external https domains"
    assert "http://127.0.0.1:*" in csp
    assert "object-src 'none'" in csp


def test_cargo_toml_manifest():
    """Verifies that src-tauri/Cargo.toml exists and defines tauri 1.6 and serde dependencies."""
    cargo_path = REPO_ROOT / "src-tauri" / "Cargo.toml"
    assert cargo_path.is_file(), "src-tauri/Cargo.toml must exist"

    content = cargo_path.read_text(encoding="utf-8")
    assert 'name = "sift-shell"' in content or 'name = "sift"' in content
    assert 'tauri = {' in content
    assert 'version = "1.6"' in content
    assert 'serde = {' in content


def test_tauri_rust_entrypoint_files():
    """Verifies that main.rs and build.rs exist in src-tauri."""
    main_rs = REPO_ROOT / "src-tauri" / "src" / "main.rs"
    build_rs = REPO_ROOT / "src-tauri" / "build.rs"
    assert main_rs.is_file(), "src-tauri/src/main.rs must exist"
    assert build_rs.is_file(), "src-tauri/build.rs must exist"


# ---------------------------------------------------------------------------
# 2. Edge Standalone App Mode & Harness Verification
# ---------------------------------------------------------------------------
def test_browser_discovery_finds_host_edge():
    """Verifies find_edge_browser discovers Microsoft Edge or Chromium on host."""
    browser_exe = find_edge_browser()
    assert browser_exe is not None, "find_edge_browser() must find Edge or Chromium on host"
    assert os.path.isfile(browser_exe), f"Discovered browser path '{browser_exe}' must exist"


def test_build_browser_args_contains_airgap_flags():
    """Verifies build_browser_args includes --app, window size, profile dir, and anti-telemetry flags."""
    mock_exe = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    app_url = "http://127.0.0.1:8765"
    profile_dir = r"C:\Temp\sift_profile"

    args = build_browser_args(mock_exe, app_url, profile_dir)

    assert args[0] == mock_exe
    assert f"--app={app_url}" in args
    assert "--window-size=1440,900" in args
    assert f"--user-data-dir={profile_dir}" in args
    assert "--disable-background-networking" in args
    assert "--disable-sync" in args
    assert "--disable-component-update" in args
    assert "--disable-extensions" in args
    assert "--no-first-run" in args
    assert "--no-default-browser-check" in args
    assert "--disable-breakpad" in args
    assert "--disable-features=Translate,OptimizationHints,MediaRouter" in args


# ---------------------------------------------------------------------------
# 3. FastAPI Bootstrap & Security Endpoints
# ---------------------------------------------------------------------------
def test_api_health_endpoint(client):
    """Verifies GET /api/health returns status ok, app sift, version 0.1.0, and air_gapped True."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "sift"
    assert data["version"] == "0.1.0"
    assert data["air_gapped"] is True
    assert data["mode"] == "air_gapped_desktop"
    assert data["duckdb_version"] == "1.0.0"


def test_host_header_validation_blocks_dns_rebinding(client):
    """Verifies host header validation blocks external hosts and permits loopback."""
    # Valid loopback host
    res_valid = client.get("/api/health", headers={"host": "127.0.0.1:8765"})
    assert res_valid.status_code == 200

    # Valid localhost
    res_local = client.get("/api/health", headers={"host": "localhost:8765"})
    assert res_local.status_code == 200

    # Malicious host (DNS rebinding attempt)
    res_invalid = client.get("/api/health", headers={"host": "evil.attacker.com"})
    assert res_invalid.status_code == 403
    assert "Forbidden" in res_invalid.json()["error"]


def test_security_headers_present(client):
    """Verifies that security headers (CSP, nosniff, DENY, etc.) are returned on responses."""
    response = client.get("/api/health")
    headers = response.headers
    assert "content-security-policy" in headers
    assert "default-src 'self'" in headers["content-security-policy"]
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-frame-options") == "DENY"
    assert headers.get("referrer-policy") == "no-referrer"


def test_cors_loopback_policy(client):
    """Verifies CORS policy permits loopback origins and rejects external origins."""
    # Allowed origin
    res_cors = client.options(
        "/api/health",
        headers={
            "Origin": "http://127.0.0.1:8765",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res_cors.status_code == 200
    assert res_cors.headers.get("access-control-allow-origin") == "http://127.0.0.1:8765"

    # Tauri origin
    res_tauri = client.options(
        "/api/health",
        headers={
            "Origin": "tauri://localhost",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res_tauri.status_code == 200
    assert res_tauri.headers.get("access-control-allow-origin") == "tauri://localhost"

    # Barred external origin
    res_blocked = client.options(
        "/api/health",
        headers={
            "Origin": "http://external-malicious-site.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res_blocked.headers.get("access-control-allow-origin") is None


def test_workspace_endpoints_lifecycle(client, temp_workspace_dir):
    """Verifies /api/workspace/create, /api/workspace/meta, /api/workspace/checkpoint, and /api/workspace/close."""
    ws_path = os.path.join(temp_workspace_dir, "api_test.mxa")

    # Initial metadata when no workspace is open
    meta_none = client.get("/api/workspace/meta").json()
    assert meta_none["open"] is False

    # Create workspace via API
    res_create = client.post(
        "/api/workspace/create",
        json={"path": ws_path, "project_name": "API Commercial Audit", "reporting_currency": "USD"},
    )
    assert res_create.status_code == 200
    create_data = res_create.json()
    assert create_data["status"] == "created"
    assert create_data["tables_initialized"] == 8

    # Query metadata of opened workspace
    res_meta = client.get("/api/workspace/meta")
    assert res_meta.status_code == 200
    meta_data = res_meta.json()
    assert meta_data["open"] is True
    assert meta_data["project_name"] == "API Commercial Audit"
    assert meta_data["reporting_currency"] == "USD"

    # Checkpoint workspace
    res_chk = client.post("/api/workspace/checkpoint")
    assert res_chk.status_code == 200
    assert res_chk.json()["status"] == "checkpointed"

    # Close workspace
    res_close = client.post("/api/workspace/close")
    assert res_close.status_code == 200
    assert res_close.json()["status"] == "closed"

    # Close when already closed returns already_closed
    res_close_again = client.post("/api/workspace/close")
    assert res_close_again.status_code == 200
    assert res_close_again.json()["status"] == "already_closed"

    # Re-open workspace via /api/workspace/open
    res_open = client.post("/api/workspace/open", json={"path": ws_path})
    assert res_open.status_code == 200
    open_data = res_open.json()
    assert open_data["status"] == "opened"
    assert open_data["project_name"] == "API Commercial Audit"

    # Close again
    client.post("/api/workspace/close")
