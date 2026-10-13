"""
AC-9: Punitive Disposition Code Lockdown Test.

Authoritative Requirement:
Punitive disposition codes ("Unapproved Concession", "Unauthorized Deal")
cannot be selected on Tier 1 or Tier 2 findings. They are permitted ONLY
when evidence tier is confirmed as Tier 3 Rule-Confirmed Exception.
(ORIGINAL_REQUEST.md § User Interface & Persistence Invariants, PROJECT.md R6.3, spec_report.md AC-9).
"""

import pytest

from tests.e2e.test_helpers import (
    validate_finding_transition,
    PUNITIVE_DISPOSITION_CODES,
    VALID_DISMISSAL_CATEGORIES,
)


def test_punitive_codes_strictly_blocked_on_tier_1():
    """
    AC-9: Setting punitive disposition codes on Tier 1 finding must be rejected.
    """
    for code in PUNITIVE_DISPOSITION_CODES:
        valid, msg = validate_finding_transition(
            evidence_tier="Tier 1",
            new_state="In Review",
            disposition_code=code,
        )
        assert valid is False, f"Expected punitive code '{code}' to be blocked on Tier 1"
        assert "locked for Tier 1" in msg or "Only permitted for Tier 3" in msg


def test_punitive_codes_strictly_blocked_on_tier_2():
    """
    AC-9: Setting punitive disposition codes on Tier 2 finding must be rejected.
    """
    for code in PUNITIVE_DISPOSITION_CODES:
        valid, msg = validate_finding_transition(
            evidence_tier="Tier 2",
            new_state="In Review",
            disposition_code=code,
        )
        assert valid is False, f"Expected punitive code '{code}' to be blocked on Tier 2"
        assert "locked for Tier 2" in msg or "Only permitted for Tier 3" in msg


def test_punitive_codes_permitted_on_tier_3():
    """
    AC-9: Setting punitive disposition codes on Tier 3 (Rule-Confirmed Exception) is permitted.
    """
    for code in PUNITIVE_DISPOSITION_CODES:
        valid, msg = validate_finding_transition(
            evidence_tier="Tier 3",
            new_state="In Review",
            disposition_code=code,
        )
        assert valid is True, f"Expected punitive code '{code}' to be permitted on Tier 3, got error: {msg}"


def test_non_punitive_commercial_codes_permitted_on_tier_1_and_2():
    """
    AC-9: Non-punitive commercial disposition codes must be permitted on Tier 1 and Tier 2.
    """
    commercial_codes = [
        "Statistical Anomaly",
        "Market Alignment",
        "Customer Volume Justified",
        "Legacy Contract Terms",
        "Pre-Approved Override",
    ]
    for tier in ["Tier 1", "Tier 2"]:
        for code in commercial_codes:
            valid, msg = validate_finding_transition(
                evidence_tier=tier,
                new_state="Dismissed",
                disposition_code=code,
                dismissal_category=code,
                snooze_date="2026-06-30",
            )
            assert valid is True, f"Expected commercial code '{code}' to be accepted on {tier}, got: {msg}"


def test_dismissal_governance_requires_category_and_snooze():
    """
    AC-9: Dismissals without mandatory category or snooze date must be rejected.
    """
    # Missing category
    valid, msg = validate_finding_transition(
        evidence_tier="Tier 1",
        new_state="Dismissed",
        dismissal_category=None,
        snooze_date="2026-06-30",
    )
    assert valid is False
    assert "Mandatory valid dismissal category" in msg

    # Missing snooze date
    valid, msg = validate_finding_transition(
        evidence_tier="Tier 1",
        new_state="Dismissed",
        dismissal_category="Statistical Anomaly",
        snooze_date=None,
    )
    assert valid is False
    assert "snooze/expiry date required" in msg
