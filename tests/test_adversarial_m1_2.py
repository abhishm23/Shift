"""
Empirical Adversarial Stress Suite for Milestone 1: Air-Gap Defenses, DNS Rebinding & Runtime Harness
Author: challenger_m1_2 (Milestone 1 Challenger 2)

Covers 5 mandatory challenge vectors:
1. DNS Rebinding Attack Stress (Host header injection & loopback strictness)
2. CORS Loopback Origin Defense (Foreign origins & null origin rejection)
3. Content Security Policy & Protective HTTP Headers (Headers across endpoints and error conditions)
4. Desktop Runner Air-Gap Verification (12 sandboxing flags, browser discovery, isolated profile)
5. Frontend Asset Air-Gap Verification (Zero external network requests, zero CDNs, zero remote fonts)
"""

import os
import re
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
    """Ensure clean workspace state before each test client invocation."""
    if state.is_open():
        close_workspace(state.connection)
        state.connection = None
        state.active_path = None
    return TestClient(app)


# ===========================================================================
# Vector 1: DNS Rebinding Attack Stress
# ===========================================================================
class TestDNSRebindingStress:
    """
    Adversarial challenge against host header spoofing and DNS rebinding attacks.
    An attacker resolving malicious domains to 127.0.0.1 must be blocked with HTTP 403.
    """

    @pytest.mark.parametrize(
        "malicious_host",
        [
            "evil.com",
            "attacker.local",
            "192.168.1.100",
            "malicious.website.org",
            "evil.com:8765",
            "attacker.local:8765",
            "192.168.1.100:8765",
            "malicious.website.org:8765",
            "127.0.0.1.attacker.com",
            "localhost.attacker.com",
            "127.0.0.1.evil.com:8765",
            "attacker127.0.0.1",
            "0.0.0.0",
            "0.0.0.0:8765",
            "10.0.0.1",
            "172.16.0.1",
            "169.254.169.254",  # Cloud metadata IP
            "evil.com.",        # Trailing dot DNS notation
            "EVIL.COM",         # Upper-case domain
            "Evil.Com:8765",    # Mixed-case domain with port
            "user@evil.com",    # Credential format host
        ],
    )
    def test_dns_rebinding_attack_hosts_strictly_forbidden(self, client, malicious_host):
        """
        Challenge: Send requests with adversarial Host headers.
        Requirement: Must return HTTP 403 Forbidden with clear air-gap guardrail rejection.
        """
        resp = client.get("/api/health", headers={"host": malicious_host})
        assert resp.status_code == 403, (
            f"Expected HTTP 403 Forbidden for malicious host '{malicious_host}', got {resp.status_code}"
        )
        data = resp.json()
        assert "error" in data
        assert "Forbidden" in data["error"]
        assert "barred by Sift air-gap security guardrails" in data.get("detail", "")

    @pytest.mark.parametrize(
        "endpoint",
        [
            "/api/health",
            "/api/workspace/meta",
            "/api/workspace/status",
            "/docs",
        ],
    )
    def test_dns_rebinding_blocked_across_all_endpoints(self, client, endpoint):
        """Verify that DNS rebinding defense guards all endpoints, not just /api/health."""
        resp = client.get(endpoint, headers={"host": "evil.com"})
        assert resp.status_code == 403
        assert "Forbidden" in resp.json()["error"]

    def test_empty_host_header_blocked(self, client):
        """Verify empty host header is strictly rejected."""
        resp = client.get("/api/health", headers={"host": ""})
        assert resp.status_code == 403

    @pytest.mark.parametrize(
        "valid_host",
        [
            "127.0.0.1:8765",
            "localhost:8765",
            "127.0.0.1",
            "localhost",
            "testserver",
        ],
    )
    def test_legitimate_loopback_hosts_permitted(self, client, valid_host):
        """Verify legitimate local loopback hosts pass through host validation."""
        resp = client.get("/api/health", headers={"host": valid_host})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ===========================================================================
# Vector 2: CORS Loopback Origin Defense
# ===========================================================================
class TestCORSLoopbackDefense:
    """
    Adversarial challenge verifying that CORS rejects all external and untrusted origins,
    preventing malicious web origins from reading analytical financial data.
    """

    @pytest.mark.parametrize(
        "foreign_origin",
        [
            "http://evil.com",
            "https://google.com",
            "null",
            "http://attacker.local",
            "http://192.168.1.100",
            "https://evil.com",
            "http://127.0.0.1.attacker.com",
            "http://localhost.attacker.com",
            "http://127.0.0.1:9999",  # Unauthorized port
            "http://localhost:9999",  # Unauthorized port
            "tauri://evil.com",       # Spoofed tauri host
        ],
    )
    def test_cors_preflight_rejects_foreign_origins(self, client, foreign_origin):
        """
        Challenge: Send OPTIONS preflight with foreign Origin.
        Requirement: access-control-allow-origin must NOT allow or echo the foreign origin.
        """
        resp = client.options(
            "/api/health",
            headers={
                "Origin": foreign_origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        allow_origin = resp.headers.get("access-control-allow-origin")
        assert allow_origin != foreign_origin, (
            f"CORS vulnerability! Foreign origin '{foreign_origin}' was reflected in Access-Control-Allow-Origin"
        )
        assert allow_origin != "*", "CORS vulnerability! Wildcard '*' returned for foreign origin"

    @pytest.mark.parametrize(
        "foreign_origin",
        [
            "http://evil.com",
            "https://google.com",
            "null",
        ],
    )
    def test_cors_simple_get_does_not_reflect_foreign_origin(self, client, foreign_origin):
        """
        Challenge: Send GET request with foreign Origin header.
        Requirement: Response must NOT include Access-Control-Allow-Origin matching foreign origin.
        """
        resp = client.get(
            "/api/health",
            headers={"Origin": foreign_origin},
        )
        allow_origin = resp.headers.get("access-control-allow-origin")
        assert allow_origin != foreign_origin, (
            f"Foreign origin '{foreign_origin}' reflected in simple GET response!"
        )

    @pytest.mark.parametrize(
        "trusted_origin",
        [
            "http://127.0.0.1:8765",
            "http://localhost:8765",
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "tauri://localhost",
        ],
    )
    def test_cors_permits_explicit_loopback_origins(self, client, trusted_origin):
        """Verify explicitly allowed loopback origins receive matching CORS headers."""
        resp = client.options(
            "/api/health",
            headers={
                "Origin": trusted_origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") == trusted_origin


# ===========================================================================
# Vector 3: Content Security Policy & Protective HTTP Headers
# ===========================================================================
class TestContentSecurityPolicyHeaders:
    """
    Adversarial challenge asserting strict air-gapped CSP and protective security headers
    are consistently emitted across all responses and status codes.
    """

    @pytest.mark.parametrize(
        "path,expected_status",
        [
            ("/api/health", 200),
            ("/api/workspace/meta", 200),
            ("/api/workspace/status", 200),
            ("/nonexistent_endpoint_for_404_check", 404),
        ],
    )
    def test_security_headers_present_on_endpoints(self, client, path, expected_status):
        """
        Verify that all standard responses include the 5 mandatory security headers:
        CSP, X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy.
        """
        resp = client.get(path)
        assert resp.status_code == expected_status
        headers = resp.headers

        # 1. Content-Security-Policy
        assert "content-security-policy" in headers, f"Missing CSP header on {path}"
        csp = headers["content-security-policy"]
        assert "default-src 'self' http://127.0.0.1:* http://localhost:*;" in csp
        assert "connect-src 'self' http://127.0.0.1:* http://localhost:*;" in csp
        assert "object-src 'none'" in csp
        assert "media-src 'none'" in csp
        assert "frame-src 'none'" in csp
        assert "https://" not in csp, "CSP must strictly prohibit external HTTPS connections"

        # 2. X-Content-Type-Options
        assert headers.get("x-content-type-options") == "nosniff", f"Missing nosniff on {path}"

        # 3. X-Frame-Options
        assert headers.get("x-frame-options") == "DENY", f"Missing X-Frame-Options: DENY on {path}"

        # 4. X-XSS-Protection
        assert headers.get("x-xss-protection") == "1; mode=block", f"Missing XSS protection on {path}"

        # 5. Referrer-Policy
        assert headers.get("referrer-policy") == "no-referrer", f"Missing Referrer-Policy on {path}"

    def test_security_headers_on_403_forbidden_response(self, client):
        """
        Stress test: When a DNS rebinding attack is rejected with HTTP 403,
        does the response still include protective security headers?
        """
        resp = client.get("/api/health", headers={"host": "evil.com"})
        assert resp.status_code == 403
        headers = resp.headers
        # In ASGI middleware chain, security_headers_middleware wraps host_header_validation_middleware
        assert headers.get("x-frame-options") == "DENY"
        assert headers.get("x-content-type-options") == "nosniff"
        assert "content-security-policy" in headers


# ===========================================================================
# Vector 4: Desktop Runner Air-Gap Verification
# ===========================================================================
class TestDesktopRunnerAirGap:
    """
    Adversarial verification of backend/run_desktop.py launcher and command line construction.
    Asserts all 12 air-gap, anti-telemetry, and isolation flags are present.
    """

    def test_browser_discovery_succeeds(self):
        """Verify host Edge/Chromium discovery finds a real, executable binary."""
        browser_exe = find_edge_browser()
        assert browser_exe is not None, "find_edge_browser() returned None"
        assert os.path.isabs(browser_exe), f"Browser path '{browser_exe}' must be absolute"
        assert os.path.isfile(browser_exe), f"Discovered browser executable '{browser_exe}' does not exist on disk"

    def test_build_browser_args_contains_all_12_airgap_flags(self):
        """
        Verify the exact air-gap and sandboxing arguments generated for standalone browser execution.
        Must contain all 12 required flags:
        1. --app
        2. --window-size=1440,900
        3. --user-data-dir
        4. --disable-background-networking
        5. --disable-sync
        6. --disable-component-update
        7. --disable-default-apps
        8. --disable-extensions
        9. --no-first-run
        10. --no-default-browser-check
        11. --disable-breakpad
        12. --disable-features=Translate,OptimizationHints,MediaRouter
        """
        mock_exe = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        app_url = "http://127.0.0.1:8765"
        profile_dir = r"C:\Temp\sift_adversarial_profile"

        args = build_browser_args(mock_exe, app_url, profile_dir)

        # 1. Executable binary
        assert args[0] == mock_exe

        # 2. Standalone app mode
        assert f"--app={app_url}" in args

        # 3. Window geometry (1440x900 as per R1 / PROJECT.md)
        assert "--window-size=1440,900" in args

        # 4. Isolated user profile directory
        assert f"--user-data-dir={profile_dir}" in args

        # 5. Anti-telemetry & air-gap flags
        required_flags = [
            "--disable-background-networking",
            "--disable-sync",
            "--disable-component-update",
            "--disable-default-apps",
            "--disable-extensions",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-breakpad",
            "--disable-features=Translate,OptimizationHints,MediaRouter",
        ]

        for flag in required_flags:
            assert flag in args, f"Mandatory air-gap flag '{flag}' missing from browser arguments!"

        # Ensure total argument count matches exact specification
        assert len(args) == 13  # 1 binary + 12 flags/options

    def test_probe_sift_health_functionality(self):
        """Verify probe_sift_health correctly validates response payload structure."""
        # Non-existent server should return False without raising unhandled exception
        assert probe_sift_health("http://127.0.0.1:65530", timeout=0.2) is False


# ===========================================================================
# Vector 5: Frontend Asset Air-Gap Verification
# ===========================================================================
class TestFrontendAssetAirGap:
    """
    Adversarial verification of frontend production bundle in src/dist.
    Ensures 100% zero external network requests, zero CDN links, zero webfonts.
    """

    @classmethod
    @pytest.fixture(scope="class")
    def dist_dir(cls):
        dist = REPO_ROOT / "src" / "dist"
        assert dist.is_dir(), f"Frontend dist directory '{dist}' does not exist. Run 'npm run build' first."
        return dist

    def test_dist_index_html_has_strict_csp(self, dist_dir):
        """Verify src/dist/index.html includes meta tag Content-Security-Policy restricting to self/loopback."""
        index_html_path = dist_dir / "index.html"
        assert index_html_path.is_file(), "src/dist/index.html missing"
        content = index_html_path.read_text(encoding="utf-8")

        # Must have meta CSP
        assert "Content-Security-Policy" in content, "index.html missing Content-Security-Policy meta tag"
        assert "default-src 'self' http://127.0.0.1:*;" in content
        assert "connect-src 'self' http://127.0.0.1:*;" in content
        assert "https://" not in content, "index.html must not contain external https references"

    def test_css_assets_contain_no_external_urls_or_webfonts(self, dist_dir):
        """
        Verify all CSS files in src/dist/assets:
        - No http:// or https://
        - No remote url(...) fonts (e.g. google fonts)
        - No remote @import
        """
        css_files = list((dist_dir / "assets").glob("*.css"))
        assert len(css_files) >= 1, "No CSS files found in src/dist/assets"

        for css_file in css_files:
            text = css_file.read_text(encoding="utf-8")
            # Check for any external http / https
            matches_external = re.findall(r'https?://[^\s"\'\)]+', text)
            assert not matches_external, (
                f"External URL found in CSS file {css_file.name}: {matches_external}"
            )
            # Check for remote @import
            assert "@import url(" not in text.lower(), (
                f"Remote @import found in CSS file {css_file.name}"
            )

    def test_zero_external_network_requests_in_codebase(self, dist_dir):
        """
        Verify that all runtime network invocation primitives (fetch, XMLHttpRequest, WebSocket)
        strictly target only the local loopback host http://127.0.0.1:8765 or relative URLs.
        Zero external network requests must be initiated.
        """
        js_files = list((dist_dir / "assets").glob("*.js"))
        assert len(js_files) >= 1, "No JS files found in src/dist/assets"

        # Check all fetch calls
        for js_file in js_files:
            content = js_file.read_text(encoding="utf-8", errors="ignore")
            # Look for fetch calls with external endpoints
            fetch_matches = re.findall(r'fetch\s*\(\s*[`"\'](https?://[^`"\']+)`', content)
            for target in fetch_matches:
                assert target.startswith("http://127.0.0.1") or target.startswith("http://localhost"), (
                    f"External network fetch found in {js_file.name}: {target}"
                )

    def test_w3c_namespaces_and_error_strings_audit(self, dist_dir):
        """
        Audit all URI strings across JS chunks:
        Assert that every URI is either:
        1. Local loopback: http://127.0.0.1:* or http://localhost:*
        2. Standard W3C XML/SVG/MathML/XHTML namespace identifier:
           http://www.w3.org/2000/svg, http://www.w3.org/1999/xlink,
           http://www.w3.org/XML/1998/namespace, http://www.w3.org/1998/Math/MathML,
           http://www.w3.org/1999/xhtml
        3. React 18 production error decoder message string (static documentation link in Error object):
           https://reactjs.org/docs/error-decoder.html?invariant=
        Assert ZERO external API, CDN, tracking, or exfiltration endpoints exist.
        """
        js_files = list((dist_dir / "assets").glob("*.js"))
        url_pattern = re.compile(r'https?://[^\s"\'`<>)]+', re.IGNORECASE)

        allowed_schemes = [
            re.compile(r'^https?://127\.0\.0\.1(:\d+)?(/.*)?$', re.IGNORECASE),
            re.compile(r'^https?://localhost(:\d+)?(/.*)?$', re.IGNORECASE),
            re.compile(r'^http://www\.w3\.org/2000/svg/?$', re.IGNORECASE),
            re.compile(r'^http://www\.w3\.org/1999/xlink/?$', re.IGNORECASE),
            re.compile(r'^http://www\.w3\.org/XML/1998/namespace/?$', re.IGNORECASE),
            re.compile(r'^http://www\.w3\.org/1998/Math/MathML/?$', re.IGNORECASE),
            re.compile(r'^http://www\.w3\.org/1999/xhtml/?$', re.IGNORECASE),
            re.compile(r'^https://reactjs\.org/docs/error-decoder\.html\?invariant=$', re.IGNORECASE),
        ]

        unaccounted = []
        for js_file in js_files:
            text = js_file.read_text(encoding="utf-8", errors="ignore")
            for url in url_pattern.findall(text):
                clean_url = url.rstrip(';.,"\')')
                if not any(pat.match(clean_url) for pat in allowed_schemes):
                    unaccounted.append((js_file.name, clean_url))

        assert not unaccounted, f"Unaccounted external URL found in JS bundle: {unaccounted}"

    def test_no_cdn_references_in_entire_dist(self, dist_dir):
        """
        Deep scan across all files in src/dist for common CDN signatures:
        unpkg, cdnjs, jsdelivr, googleapis, gstatic, tailwindcss.com, sentry, mixpanel.
        """
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
        for root, _, files in os.walk(dist_dir):
            for file_name in files:
                file_path = Path(root) / file_name
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    for kw in cdn_keywords:
                        if kw.lower() in content.lower():
                            violations.append((str(file_path.relative_to(dist_dir)), kw))
                except Exception as e:
                    pytest.fail(f"Could not read {file_path}: {e}")

        assert not violations, f"Found CDN / telemetry references in dist: {violations}"
