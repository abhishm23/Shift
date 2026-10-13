"""
tests/test_m5_pvmc.py
Milestone 5 Comprehensive Test Suite:
Interaction Detection, Contractual Cap Stacking, Programmatic Tone Guard,
and Decoupled Macro PVMC Margin Bridge.

Test Coverage:
Section 1: Compound Concession Stacking (Additive vs Multiplicative) & Tier 3 Cap Breach.
Section 2: Programmatic Tone Guard Enforcement (R5.3).
Section 3: Statistical Exploratory Pairwise Interaction Modeling & FDR Control (R5.2).
Section 4: Decoupled Engine B Macro PVMC Bridge Decomposition & Penny Reconciliation (R5.4).
Section 5: Volume Homogeneity Rule (R5.5) across disparate UoMs.
Section 6: Turnover Isolation for New & Discontinued Business (R5.6).
Section 7: FastAPI Endpoints & Workspace Gating Integration.
"""

import json
import math
import tempfile
import os
import duckdb
import pytest
from fastapi.testclient import TestClient

from backend.app import app, state
from backend.storage import open_workspace, create_workspace, init_schema, close_workspace
from backend.interactions import (
    ToneGuard,
    ToneGuardViolationError,
    evaluate_contractual_cap_stacking,
    evaluate_interactions,
)
from backend.pvmc_bridge import (
    parse_period_filter,
    compute_pvmc_bridge,
)


@pytest.fixture
def memory_db():
    """Provides an in-memory DuckDB connection with canonical transactions schema."""
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE transactions (
            transaction_line_id VARCHAR PRIMARY KEY,
            invoice_id VARCHAR,
            account_id VARCHAR,
            parent_account_id VARCHAR,
            transaction_date DATE,
            currency VARCHAR DEFAULT 'USD',
            fx_rate_to_reporting DOUBLE DEFAULT 1.0,
            extended_list_amt DOUBLE,
            net_invoiced_amt DOUBLE,
            cogs_amt DOUBLE,
            off_invoice_rebate DOUBLE DEFAULT 0.0,
            reporting_list_amt DOUBLE,
            reporting_invoiced_amt DOUBLE,
            reporting_cogs_amt DOUBLE,
            reporting_rebate_amt DOUBLE DEFAULT 0.0,
            realized_discount_rate DOUBLE,
            defensible_gap DOUBLE DEFAULT 0.0,
            is_credit_reversal BOOLEAN DEFAULT FALSE,
            dimension_attributes JSON,
            sales_rep VARCHAR,
            discount_reason VARCHAR,
            product_family VARCHAR,
            quantity DOUBLE DEFAULT 1.0,
            uom VARCHAR DEFAULT 'EA'
        );
    """)
    yield con
    con.close()


@pytest.fixture
def client():
    """FastAPI TestClient with air-gap loopback headers."""
    return TestClient(app, headers={"host": "127.0.0.1:8765"})


# ===========================================================================
# Section 1: Compound Concession Stacking & Contractual Cap Evaluation
# ===========================================================================

def test_stacking_additive_vs_multiplicative(memory_db):
    """
    T-INT-01: Verifies additive vs multiplicative compounding mechanics.
    Formula Invariant:
      For positive concessions r1, r2 in (0, 1):
      r_additive = r1 + r2
      r_multiplicative = 1 - (1 - r1)*(1 - r2) = r1 + r2 - r1*r2
      Therefore: r_additive > r_multiplicative.
    """
    # 20% discount (List 1000, Net 800) and 10% rebate (100)
    memory_db.execute("""
        INSERT INTO transactions (
            transaction_line_id, invoice_id, account_id, transaction_date,
            extended_list_amt, net_invoiced_amt, cogs_amt, off_invoice_rebate,
            reporting_invoiced_amt, reporting_rebate_amt, is_credit_reversal
        ) VALUES (
            'TX-STACK-1', 'INV-1', 'ACCT-1', '2025-02-01',
            1000.0, 800.0, 500.0, 100.0,
            800.0, 100.0, FALSE
        );
    """)

    # Additive evaluation: 20% + 10% = 30.0%
    res_add = evaluate_contractual_cap_stacking(memory_db, cap_rate=0.29, stacking_mode="additive")
    assert res_add["status"] == "success"
    assert res_add["breach_count"] == 1
    assert abs(res_add["breached_records"][0]["compound_concession_rate"] - 0.30) < 1e-5
    assert abs(res_add["breached_records"][0]["excess_rate"] - 0.01) < 1e-5
    assert abs(res_add["breached_records"][0]["breach_exposure_dollars"] - 10.0) < 1e-5

    # Multiplicative evaluation: 1 - (1 - 0.20)*(1 - 0.10) = 1 - 0.72 = 28.0%
    res_mult = evaluate_contractual_cap_stacking(memory_db, cap_rate=0.29, stacking_mode="multiplicative")
    assert res_mult["status"] == "success"
    # 28% is below 29% cap, so no breach under multiplicative rules!
    assert res_mult["breach_count"] == 0

    # Under 25% cap: both breach, but additive compound rate > multiplicative
    res_add_25 = evaluate_contractual_cap_stacking(memory_db, cap_rate=0.25, stacking_mode="additive")
    res_mult_25 = evaluate_contractual_cap_stacking(memory_db, cap_rate=0.25, stacking_mode="multiplicative")
    rate_add = res_add_25["breached_records"][0]["compound_concession_rate"]
    rate_mult = res_mult_25["breached_records"][0]["compound_concession_rate"]
    assert rate_add > rate_mult
    assert abs(rate_add - 0.30) < 1e-5
    assert abs(rate_mult - 0.28) < 1e-5


def test_contractual_cap_breach_detection_and_exposure(memory_db):
    """
    T-INT-02: Verifies cap breach exposure calculation across a multi-transaction portfolio.
    """
    memory_db.execute("""
        INSERT INTO transactions (
            transaction_line_id, invoice_id, account_id, transaction_date,
            extended_list_amt, net_invoiced_amt, cogs_amt, off_invoice_rebate,
            reporting_invoiced_amt, reporting_rebate_amt, is_credit_reversal
        ) VALUES 
        ('TX-CAP-1', 'INV-1', 'ACCT-A', '2025-01-10', 10000.0, 6000.0, 3000.0, 0.0, 6000.0, 0.0, FALSE), -- 40%
        ('TX-CAP-2', 'INV-2', 'ACCT-B', '2025-01-11', 20000.0, 16000.0, 8000.0, 0.0, 16000.0, 0.0, FALSE), -- 20%
        ('TX-CAP-3', 'INV-3', 'ACCT-C', '2025-01-12', 15000.0, 9000.0, 4000.0, 1500.0, 9000.0, 1500.0, FALSE); -- 40% + 10% = 50%
    """)

    # Contractual Cap = 35%
    res = evaluate_contractual_cap_stacking(memory_db, cap_rate=0.35, stacking_mode="additive")
    assert res["total_evaluated_transactions"] == 3
    assert res["breach_count"] == 2  # TX-CAP-1 (40%) and TX-CAP-3 (50%)
    assert res["breach_rate"] == round(2 / 3, 4)

    # TX-CAP-1: Excess = 40% - 35% = 5% of 10,000 = $500.00
    # TX-CAP-3: Excess = 50% - 35% = 15% of 15,000 = $2,250.00
    # Total breach exposure = $2,750.00
    assert abs(res["total_breached_exposure"] - 2750.00) < 1e-2


def test_contractual_cap_evidence_tier_3(memory_db):
    """
    T-INT-03: Verifies that contractual cap breaches are formally classified
    as Tier 3 'Rule-Confirmed Exception'.
    """
    memory_db.execute("""
        INSERT INTO transactions (
            transaction_line_id, invoice_id, account_id, transaction_date,
            extended_list_amt, net_invoiced_amt, cogs_amt, off_invoice_rebate,
            reporting_invoiced_amt, reporting_rebate_amt, is_credit_reversal
        ) VALUES (
            'TX-TIER3-1', 'INV-1', 'ACCT-1', '2025-03-01',
            5000.0, 3000.0, 1500.0, 500.0,
            3000.0, 500.0, FALSE
        );
    """)
    res = evaluate_contractual_cap_stacking(memory_db, cap_rate=0.30, stacking_mode="additive")
    assert res["evidence_tier"] == "Tier 3"
    assert res["classification"] == "Rule-Confirmed Exception"
    record = res["breached_records"][0]
    assert record["evidence_tier"] == "Tier 3"
    assert record["classification"] == "Rule-Confirmed Exception"
    assert record["governance_status"] == "Contractual Cap Breach"


# ===========================================================================
# Section 2: Programmatic Tone Guard Enforcement (R5.3)
# ===========================================================================

def test_tone_guard_blocks_policy_violation_statistical():
    """
    T-INT-09: Verifies that ToneGuard strictly raises ToneGuardViolationError
    when attempting to use 'Policy Violation' or punitive terminology in statistical mode.
    """
    forbidden_variants = [
        "Policy Violation",
        "policy violation",
        "POLICY_VIOLATION",
        "policy-violation",
        "policyviolation",
        "Unapproved Concession",
        "Unauthorized Deal",
        "Breach of Policy",
        "off-policy deal",
    ]

    for term in forbidden_variants:
        assert not ToneGuard.is_safe(term, mode="statistical")
        with pytest.raises(ToneGuardViolationError):
            ToneGuard.validate(term, mode="statistical")
            pytest.fail(f"ToneGuard should have raised exception for forbidden term: {term}")


def test_tone_guard_allows_mandatory_label():
    """
    T-INT-10: Verifies that the mandatory canonical commercial label passes Tone Guard.
    """
    label = ToneGuard.MANDATORY_INTERACTION_LABEL
    assert ToneGuard.is_safe(label, mode="statistical")
    # Must not raise
    ToneGuard.validate(label, mode="statistical")


def test_tone_guard_allows_cap_breach_in_tier_3():
    """
    T-INT-11: Verifies that rule-based compliance terminology is permitted in rule_based mode.
    """
    term = "Contractual Cap Breach: Policy Violation Confirmed"
    assert ToneGuard.is_safe(term, mode="rule_based")
    ToneGuard.validate(term, mode="rule_based")


def test_tone_guard_sanitizer():
    """
    Verifies that ToneGuard.sanitize cleanly replaces punitive terms in statistical mode.
    """
    raw = "Identified policy violation and unapproved concession on account."
    sanitized = ToneGuard.sanitize(raw, mode="statistical")
    assert "policy violation" not in sanitized.lower()
    assert "unapproved concession" not in sanitized.lower()
    assert "Statistical Interaction Anomaly" in sanitized
    assert "Anomalous Joint Concession" in sanitized


# ===========================================================================
# Section 3: Statistical Pairwise Interaction Detection & FDR Control
# ===========================================================================

def test_statistical_interaction_rate_formulation(memory_db):
    """
    T-INT-04: Verifies the exact interaction rate formula:
      r_hat_AB = r_A + r_B - r_global
      I_rate = r_AB - r_hat_AB
    """
    # Create controlled dataset:
    # 4 accounts, 2 reps (Alice, Bob), 2 reasons (Volume, Promo)
    idx = 1
    rows = []
    for i in range(6):
        rows.append((f"TX-{idx}", f"ACCT-{i%3+1}", "Alice", "Volume", 1000.0, 800.0, 0.20))
        idx += 1
    for i in range(5):
        rows.append((f"TX-{idx}", f"ACCT-{i%3+1}", "Alice", "Promo", 1000.0, 550.0, 0.45))
        idx += 1
    for i in range(5):
        rows.append((f"TX-{idx}", f"ACCT-{i%3+1}", "Bob", "Volume", 1000.0, 850.0, 0.15))
        idx += 1
    for i in range(4):
        rows.append((f"TX-{idx}", f"ACCT-{i%3+1}", "Bob", "Promo", 1000.0, 750.0, 0.25))
        idx += 1

    for tx in rows:
        memory_db.execute(f"""
            INSERT INTO transactions (
                transaction_line_id, account_id, sales_rep, discount_reason,
                transaction_date, extended_list_amt, net_invoiced_amt,
                reporting_invoiced_amt, realized_discount_rate, is_credit_reversal
            ) VALUES ('{tx[0]}', '{tx[1]}', '{tx[2]}', '{tx[3]}', '2025-01-01', {tx[4]}, {tx[5]}, {tx[5]}, {tx[6]}, FALSE);
        """)

    results = evaluate_interactions(
        con=memory_db,
        dim_a="sales_rep",
        dim_b="discount_reason",
        min_support_tx=3,
        min_support_accts=2,
    )

    assert len(results) > 0

    # Find Alice + Promo
    alice_promo = next(r for r in results if r["val_a"] == "Alice" and r["val_b"] == "Promo")

    # Check observed rate is exactly 0.45
    assert abs(alice_promo["observed_rate"] - 0.45) < 1e-4

    # Verify formula: expected_rate = mean_a + mean_b - global_mean
    exp_calc = alice_promo["marginal_rate_a"] + alice_promo["marginal_rate_b"] - alice_promo["global_rate"]
    assert abs(alice_promo["expected_rate"] - exp_calc) < 1e-5

    # Verify I_rate = observed_rate - expected_rate
    i_rate_calc = alice_promo["observed_rate"] - alice_promo["expected_rate"]
    assert abs(alice_promo["interaction_rate"] - i_rate_calc) < 1e-5

    # Super-additive synergy: I_rate > 0
    assert alice_promo["interaction_rate"] > 0
    assert alice_promo["interaction_dollar_gap"] > 0


def test_superadditive_anomalous_joint_concession(memory_db):
    """
    T-INT-05: Verifies that a statistically significant super-additive interaction
    is labeled with the verbatim mandatory commercial text.
    """
    # 3 reps, 3 reasons factorial design
    reps = ["Charlie", "Dave", "Eve"]
    reasons = ["Override", "Standard", "Volume"]

    idx = 1
    for rep in reps:
        for reason in reasons:
            for i in range(10):
                acct = f"ACCT-{rep}-{reason}-{i%4}"
                if rep == "Charlie" and reason == "Override":
                    rate = 0.55
                    amt = 20000.0
                else:
                    rate = 0.15 + (i % 3) * 0.02
                    amt = 5000.0
                net = amt * (1.0 - rate)
                memory_db.execute(f"""
                    INSERT INTO transactions (
                        transaction_line_id, account_id, sales_rep, discount_reason,
                        transaction_date, extended_list_amt, net_invoiced_amt,
                        reporting_invoiced_amt, realized_discount_rate, is_credit_reversal
                    ) VALUES ('TX-{idx}', '{acct}', '{rep}', '{reason}', '2025-02-01', {amt}, {net}, {net}, {rate}, FALSE);
                """)
                idx += 1

    results = evaluate_interactions(
        con=memory_db,
        dim_a="sales_rep",
        dim_b="discount_reason",
        min_support_tx=5,
        min_support_accts=3,
    )

    top = results[0]
    assert top["val_a"] == "Charlie"
    assert top["val_b"] == "Override"
    assert top["interaction_rate"] > 0.10
    assert top["z_score"] > 2.0
    assert top["is_significant"] is True
    assert top["label"] == ToneGuard.MANDATORY_INTERACTION_LABEL
    assert "policy violation" not in top["label"].lower()


def test_subadditive_dampening_interaction(memory_db):
    """
    T-INT-06: Verifies that sub-additive interaction (I_rate < 0)
    is NOT labeled as an anomalous joint concession.
    """
    # Factorial design with 2 reps (Frank, George) and 2 reasons (Executive, Standard):
    # Frank + Standard: 20 txs @ 40% discount
    # George + Executive: 20 txs @ 40% discount
    # George + Standard: 20 txs @ 40% discount
    # Frank + Executive: 20 txs @ 10% discount (sub-additive dampening!)
    idx = 1
    for i in range(20):
        memory_db.execute(f"""
            INSERT INTO transactions (
                transaction_line_id, account_id, sales_rep, discount_reason,
                transaction_date, extended_list_amt, net_invoiced_amt,
                reporting_invoiced_amt, realized_discount_rate, is_credit_reversal
            ) VALUES ('TX-SUB-{idx}', 'ACCT-FS-{i%4}', 'Frank', 'Standard', '2025-02-01', 1000.0, 600.0, 600.0, 0.40, FALSE);
        """)
        idx += 1

    for i in range(20):
        memory_db.execute(f"""
            INSERT INTO transactions (
                transaction_line_id, account_id, sales_rep, discount_reason,
                transaction_date, extended_list_amt, net_invoiced_amt,
                reporting_invoiced_amt, realized_discount_rate, is_credit_reversal
            ) VALUES ('TX-SUB-{idx}', 'ACCT-GE-{i%4}', 'George', 'Executive', '2025-02-01', 1000.0, 600.0, 600.0, 0.40, FALSE);
        """)
        idx += 1

    for i in range(20):
        memory_db.execute(f"""
            INSERT INTO transactions (
                transaction_line_id, account_id, sales_rep, discount_reason,
                transaction_date, extended_list_amt, net_invoiced_amt,
                reporting_invoiced_amt, realized_discount_rate, is_credit_reversal
            ) VALUES ('TX-SUB-{idx}', 'ACCT-GS-{i%4}', 'George', 'Standard', '2025-02-01', 1000.0, 600.0, 600.0, 0.40, FALSE);
        """)
        idx += 1

    for i in range(20):
        memory_db.execute(f"""
            INSERT INTO transactions (
                transaction_line_id, account_id, sales_rep, discount_reason,
                transaction_date, extended_list_amt, net_invoiced_amt,
                reporting_invoiced_amt, realized_discount_rate, is_credit_reversal
            ) VALUES ('TX-SUB-{idx}', 'ACCT-FE-{i%4}', 'Frank', 'Executive', '2025-02-01', 1000.0, 900.0, 900.0, 0.10, FALSE);
        """)
        idx += 1

    results = evaluate_interactions(con=memory_db, dim_a="sales_rep", dim_b="discount_reason", min_support_tx=5, min_support_accts=2)
    frank_exec = next(r for r in results if r["val_a"] == "Frank" and r["val_b"] == "Executive")
    assert frank_exec["interaction_rate"] < 0
    assert frank_exec["is_significant"] is False
    assert frank_exec["label"] != ToneGuard.MANDATORY_INTERACTION_LABEL


def test_support_fence_suppression(memory_db):
    """
    T-INT-07: Verifies that cells with small sample size or low account diversity
    are suppressed from significant interaction classification.
    """
    # Only 2 transactions and 1 customer account
    memory_db.execute("""
        INSERT INTO transactions (
            transaction_line_id, account_id, sales_rep, discount_reason,
            transaction_date, extended_list_amt, net_invoiced_amt,
            reporting_invoiced_amt, realized_discount_rate, is_credit_reversal
        ) VALUES 
        ('TX-FE-1', 'SOLO-ACCT', 'RepTiny', 'ReasonTiny', '2025-02-01', 1000.0, 500.0, 500.0, 0.50, FALSE),
        ('TX-FE-2', 'SOLO-ACCT', 'RepTiny', 'ReasonTiny', '2025-02-01', 1000.0, 500.0, 500.0, 0.50, FALSE);
    """)

    results = evaluate_interactions(
        con=memory_db,
        dim_a="sales_rep",
        dim_b="discount_reason",
        min_support_tx=5,
        min_support_accts=3,
    )

    tiny = next((r for r in results if r["val_a"] == "RepTiny" and r["val_b"] == "ReasonTiny"), None)
    if tiny:
        assert tiny["has_support"] is False
        assert tiny["is_significant"] is False
        assert "Insufficient Support" in tiny["label"]


# ===========================================================================
# Section 4: Decoupled Engine B Macro PVMC Bridge Decomposition
# ===========================================================================

def test_pvmc_exact_penny_reconciliation(memory_db):
    """
    T-PVMC-01: Verifies exact penny reconciliation across a multi-SKU portfolio:
      BaseMargin(T0) + Price + Cost + Volume + Mix + New & Discontinued == FinalMargin(T1)
      with strictly 0.00 residual.
    """
    # T0 transactions (2024-H1)
    # SKU-A: 100 units @ $100 price, $60 cost -> Margin = $4,000
    # SKU-B: 200 units @ $50 price, $30 cost -> Margin = $4,000
    # SKU-C (Will be discontinued): 50 units @ $80 price, $40 cost -> Margin = $2,000
    # Base Margin T0 = $10,000.00
    memory_db.execute("""
        INSERT INTO transactions (
            transaction_line_id, transaction_date, product_family, quantity, uom,
            reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt
        ) VALUES 
        ('T0-1', '2024-03-01', 'SKU-A', 100.0, 'EA', 10000.0, 6000.0, 0.0),
        ('T0-2', '2024-04-01', 'SKU-B', 200.0, 'EA', 10000.0, 6000.0, 0.0),
        ('T0-3', '2024-05-01', 'SKU-C', 50.0, 'EA', 4000.0, 2000.0, 0.0);
    """)

    # T1 transactions (2025-H1)
    # SKU-A: 120 units @ $110 price (price up $10), $65 cost (cost up $5) -> Margin = 120 * $45 = $5,400
    # SKU-B: 250 units @ $50 price, $28 cost (cost down $2) -> Margin = 250 * $22 = $5,500
    # SKU-D (New introduction): 80 units @ $75 price, $45 cost -> Margin = 80 * $30 = $2,400
    # Final Margin T1 = 5,400 + 5,500 + 2,400 = $13,300.00
    memory_db.execute("""
        INSERT INTO transactions (
            transaction_line_id, transaction_date, product_family, quantity, uom,
            reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt
        ) VALUES 
        ('T1-1', '2025-03-01', 'SKU-A', 120.0, 'EA', 13200.0, 7800.0, 0.0),
        ('T1-2', '2025-04-01', 'SKU-B', 250.0, 'EA', 12500.0, 7000.0, 0.0),
        ('T1-3', '2025-05-01', 'SKU-D', 80.0, 'EA', 6000.0, 3600.0, 0.0);
    """)

    bridge = compute_pvmc_bridge(memory_db, t0_filter="2024-H1", t1_filter="2025-H1")

    assert bridge["status"] == "success"
    assert abs(bridge["base_margin_t0"] - 10000.00) < 1e-2
    assert abs(bridge["final_margin_t1"] - 13300.00) < 1e-2
    assert abs(bridge["delta_margin"] - 3300.00) < 1e-2

    # Verify penny reconciliation invariant:
    # Base + Price + Cost + Volume + Mix + Turnover == Final
    components_sum = (
        bridge["base_margin_t0"]
        + bridge["price_effect"]
        + bridge["cost_effect"]
        + bridge["volume_effect"]
        + bridge["mix_effect"]
        + bridge["new_and_discontinued"]
    )
    assert abs(components_sum - bridge["final_margin_t1"]) < 1e-2
    assert bridge["reconciliation_delta"] <= 0.01
    assert bridge["reconciliation_certified"] is True

    # Check New and Discontinued isolation
    assert abs(bridge["new_business_turnover"] - 2400.00) < 1e-2
    assert abs(bridge["discontinued_business_turnover"] - (-2000.00)) < 1e-2
    assert abs(bridge["new_and_discontinued"] - 400.00) < 1e-2


def test_pvmc_pure_price_shock(memory_db):
    """
    T-PVMC-02: Pure price increase of +10%. Volumes and unit costs unchanged.
    Asserts: Price == DeltaMargin, Cost == 0, Volume == 0, Mix == 0.
    """
    # T0: 100 units @ $100 price, $50 cost -> Margin = $5,000
    memory_db.execute("""
        INSERT INTO transactions (
            transaction_line_id, transaction_date, product_family, quantity, uom,
            reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt
        ) VALUES ('P-T0', '2024-01-15', 'PROD-1', 100.0, 'EA', 10000.0, 5000.0, 0.0);
    """)

    # T1: 100 units @ $110 price, $50 cost -> Margin = $6,000 (+$1,000)
    memory_db.execute("""
        INSERT INTO transactions (
            transaction_line_id, transaction_date, product_family, quantity, uom,
            reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt
        ) VALUES ('P-T1', '2025-01-15', 'PROD-1', 100.0, 'EA', 11000.0, 5000.0, 0.0);
    """)

    bridge = compute_pvmc_bridge(memory_db, t0_filter="2024-H1", t1_filter="2025-H1")
    assert abs(bridge["delta_margin"] - 1000.0) < 1e-2
    assert abs(bridge["price_effect"] - 1000.0) < 1e-2
    assert abs(bridge["cost_effect"] - 0.0) < 1e-2
    assert abs(bridge["volume_effect"] - 0.0) < 1e-2
    assert abs(bridge["mix_effect"] - 0.0) < 1e-2
    assert abs(bridge["new_and_discontinued"] - 0.0) < 1e-2
    assert bridge["reconciliation_delta"] == 0.0


def test_pvmc_pure_cost_shock(memory_db):
    """
    T-PVMC-03: Pure cost inflation: Unit COGS increases by $5. Volume and prices unchanged.
    Asserts: Cost == DeltaMargin < 0, Price == 0, Volume == 0, Mix == 0.
    """
    # T0: 100 units @ $100 price, $50 cost -> Margin = $5,000
    memory_db.execute("""
        INSERT INTO transactions (
            transaction_line_id, transaction_date, product_family, quantity, uom,
            reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt
        ) VALUES ('C-T0', '2024-02-15', 'PROD-1', 100.0, 'EA', 10000.0, 5000.0, 0.0);
    """)
    # T1: 100 units @ $100 price, $55 cost -> Margin = $4,500 (-$500)
    memory_db.execute("""
        INSERT INTO transactions (
            transaction_line_id, transaction_date, product_family, quantity, uom,
            reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt
        ) VALUES ('C-T1', '2025-02-15', 'PROD-1', 100.0, 'EA', 10000.0, 5500.0, 0.0);
    """)

    bridge = compute_pvmc_bridge(memory_db, t0_filter="2024-H1", t1_filter="2025-H1")
    assert abs(bridge["delta_margin"] - (-500.0)) < 1e-2
    assert abs(bridge["cost_effect"] - (-500.0)) < 1e-2
    assert abs(bridge["price_effect"] - 0.0) < 1e-2
    assert abs(bridge["volume_effect"] - 0.0) < 1e-2
    assert abs(bridge["mix_effect"] - 0.0) < 1e-2
    assert bridge["reconciliation_delta"] == 0.0


def test_pvmc_pure_volume_shock(memory_db):
    """
    T-PVMC-04: Pure volume expansion of 1.5x. Prices, costs, and portfolio mix strictly constant.
    Asserts: Volume == DeltaMargin = 0.5 * M0, Price == 0, Cost == 0, Mix == 0.
    """
    # T0: SKU-1: 100 @ ($100, $50); SKU-2: 200 @ ($80, $40)
    # M0 = 100*50 + 200*40 = 5000 + 8000 = 13,000
    memory_db.execute("""
        INSERT INTO transactions (
            transaction_line_id, transaction_date, product_family, quantity, uom,
            reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt
        ) VALUES 
        ('V-T0-1', '2024-01-10', 'SKU-1', 100.0, 'EA', 10000.0, 5000.0, 0.0),
        ('V-T0-2', '2024-01-11', 'SKU-2', 200.0, 'EA', 16000.0, 8000.0, 0.0);
    """)

    # T1: Exactly 1.5x volumes: SKU-1: 150 @ ($100, $50); SKU-2: 300 @ ($80, $40)
    # M1 = 150*50 + 300*40 = 7500 + 12000 = 19,500. DeltaMargin = +6,500
    memory_db.execute("""
        INSERT INTO transactions (
            transaction_line_id, transaction_date, product_family, quantity, uom,
            reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt
        ) VALUES 
        ('V-T1-1', '2025-01-10', 'SKU-1', 150.0, 'EA', 15000.0, 7500.0, 0.0),
        ('V-T1-2', '2025-01-11', 'SKU-2', 300.0, 'EA', 24000.0, 12000.0, 0.0);
    """)

    bridge = compute_pvmc_bridge(memory_db, t0_filter="2024-H1", t1_filter="2025-H1")
    assert abs(bridge["delta_margin"] - 6500.0) < 1e-2
    assert abs(bridge["volume_effect"] - 6500.0) < 1e-2
    assert abs(bridge["price_effect"] - 0.0) < 1e-2
    assert abs(bridge["cost_effect"] - 0.0) < 1e-2
    assert abs(bridge["mix_effect"] - 0.0) < 1e-2
    assert bridge["reconciliation_delta"] == 0.0


def test_pvmc_pure_mix_shift(memory_db):
    """
    T-PVMC-05: Total volume constant (200 units). Prices and costs constant.
    50 units shifted from low-margin SKU ($10/unit) to high-margin SKU ($50/unit).
    Asserts: Mix == DeltaMargin > 0, Price == 0, Cost == 0, Volume == 0.
    """
    # T0: Low: 150 units @ ($100, $90) -> unit_m = $10. Margin = $1,500
    #     High: 50 units @ ($100, $50) -> unit_m = $50. Margin = $2,500
    # Total Q0 = 200. Total M0 = $4,000
    memory_db.execute("""
        INSERT INTO transactions (
            transaction_line_id, transaction_date, product_family, quantity, uom,
            reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt
        ) VALUES 
        ('M-T0-1', '2024-02-01', 'SKU-LOW', 150.0, 'EA', 15000.0, 13500.0, 0.0),
        ('M-T0-2', '2024-02-02', 'SKU-HIGH', 50.0, 'EA', 5000.0, 2500.0, 0.0);
    """)

    # T1: Shift 50 units to high margin: Low = 100 units, High = 100 units
    # Total Q1 = 200 (Delta Q = 0).
    # M1 = 100 * 10 + 100 * 50 = 1000 + 5000 = $6,000 (Delta M = +$2,000)
    memory_db.execute("""
        INSERT INTO transactions (
            transaction_line_id, transaction_date, product_family, quantity, uom,
            reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt
        ) VALUES 
        ('M-T1-1', '2025-02-01', 'SKU-LOW', 100.0, 'EA', 10000.0, 9000.0, 0.0),
        ('M-T1-2', '2025-02-02', 'SKU-HIGH', 100.0, 'EA', 10000.0, 5000.0, 0.0);
    """)

    bridge = compute_pvmc_bridge(memory_db, t0_filter="2024-H1", t1_filter="2025-H1")
    assert abs(bridge["delta_margin"] - 2000.0) < 1e-2
    assert abs(bridge["mix_effect"] - 2000.0) < 1e-2
    assert abs(bridge["volume_effect"] - 0.0) < 1e-2
    assert abs(bridge["price_effect"] - 0.0) < 1e-2
    assert abs(bridge["cost_effect"] - 0.0) < 1e-2
    assert bridge["reconciliation_delta"] == 0.0


# ===========================================================================
# Section 5: Volume Homogeneity Rule Across UoMs (R5.5)
# ===========================================================================

def test_volume_homogeneity_enforcement_multi_uom(memory_db):
    """
    T-PVMC-08: Portfolio with multiple disparate Units of Measure ('EA', 'KG', 'HRS').
    Verifies:
      1. Automated detection of heterogeneous UoMs.
      2. Segment-level decomposition without summing invalid units.
      3. Exact penny reconciliation across dollar aggregations.
    """
    # T0
    memory_db.execute("""
        INSERT INTO transactions (
            transaction_line_id, transaction_date, product_family, quantity, uom,
            reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt
        ) VALUES 
        ('U-T0-1', '2024-03-01', 'WIDGET-EA', 100.0, 'EA', 10000.0, 6000.0, 0.0),   -- Margin = 4000
        ('U-T0-2', '2024-03-02', 'CHEM-KG', 500.0, 'KG', 25000.0, 15000.0, 0.0),     -- Margin = 10000
        ('U-T0-3', '2024-03-03', 'CONSULT-HR', 20.0, 'HRS', 4000.0, 1000.0, 0.0);    -- Margin = 3000
        -- Total M0 = 17,000
    """)

    # T1
    memory_db.execute("""
        INSERT INTO transactions (
            transaction_line_id, transaction_date, product_family, quantity, uom,
            reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt
        ) VALUES 
        ('U-T1-1', '2025-03-01', 'WIDGET-EA', 110.0, 'EA', 12100.0, 6600.0, 0.0),   -- Price & Vol up
        ('U-T1-2', '2025-03-02', 'CHEM-KG', 550.0, 'KG', 27500.0, 17600.0, 0.0),     -- Cost inflation
        ('U-T1-3', '2025-03-03', 'CONSULT-HR', 30.0, 'HRS', 6600.0, 1500.0, 0.0);    -- Vol up
    """)

    bridge = compute_pvmc_bridge(memory_db, t0_filter="2024-H1", t1_filter="2025-H1")

    assert bridge["status"] == "success"
    assert bridge["volume_homogeneity_passed"] is True
    assert len(bridge["uom_segments"]) == 3

    segment_uoms = {s["uom"] for s in bridge["uom_segments"]}
    assert segment_uoms == {"EA", "KG", "HRS"}

    # Dollar additivity holds exactly across disparate UoMs
    seg_sum = sum(
        s["price_effect"] + s["cost_effect"] + s["volume_effect"] + s["mix_effect"] + s["new_and_discontinued"]
        for s in bridge["uom_segments"]
    )
    assert abs(seg_sum - bridge["delta_margin"]) < 1e-2
    assert bridge["reconciliation_delta"] <= 0.01


def test_volume_homogeneity_single_uom_pass(memory_db):
    """
    T-PVMC-09: Portfolio with single uniform UoM ('EA') passes homogeneity rule directly.
    """
    memory_db.execute("""
        INSERT INTO transactions (
            transaction_line_id, transaction_date, product_family, quantity, uom,
            reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt
        ) VALUES 
        ('HOMO-1', '2024-01-01', 'ITEM-1', 10.0, 'EA', 1000.0, 500.0, 0.0),
        ('HOMO-2', '2025-01-01', 'ITEM-1', 12.0, 'EA', 1200.0, 600.0, 0.0);
    """)

    bridge = compute_pvmc_bridge(memory_db, t0_filter="2024-H1", t1_filter="2025-H1")
    assert bridge["volume_homogeneity_passed"] is True
    assert len(bridge["uom_segments"]) == 1
    assert bridge["uom_segments"][0]["uom"] == "EA"


def test_pvmc_empty_periods_and_zero_division(memory_db):
    """
    T-PVMC-10: Robustness test on empty periods. Must not crash with ZeroDivisionError.
    """
    # No transactions for 2023
    bridge = compute_pvmc_bridge(memory_db, t0_filter="2023-H1", t1_filter="2023-H2")
    assert bridge["status"] == "success"
    assert bridge["base_margin_t0"] == 0.0
    assert bridge["final_margin_t1"] == 0.0
    assert bridge["delta_margin"] == 0.0
    assert bridge["reconciliation_delta"] == 0.0


def test_pvmc_credit_reversals_and_returns(memory_db):
    """
    T-PVMC-11: Verifies that credit notes and negative return line items
    are appropriately netted without corrupting unit rates.
    """
    # T0: Sale of 100 units, then return of 10 units
    memory_db.execute("""
        INSERT INTO transactions (
            transaction_line_id, transaction_date, product_family, quantity, uom,
            reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt, is_credit_reversal
        ) VALUES 
        ('CR-T0-1', '2024-01-10', 'SKU-RET', 100.0, 'EA', 10000.0, 5000.0, 0.0, FALSE),
        ('CR-T0-2', '2024-01-20', 'SKU-RET', -10.0, 'EA', -1000.0, -500.0, 0.0, TRUE);
    """)
    # T1: Clean sale of 90 units @ same price and cost
    memory_db.execute("""
        INSERT INTO transactions (
            transaction_line_id, transaction_date, product_family, quantity, uom,
            reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt, is_credit_reversal
        ) VALUES 
        ('CR-T1-1', '2025-01-10', 'SKU-RET', 90.0, 'EA', 9000.0, 4500.0, 0.0, FALSE);
    """)

    bridge = compute_pvmc_bridge(memory_db, t0_filter="2024-H1", t1_filter="2025-H1")
    # Net T0: 90 units, Margin = 4,500. Net T1: 90 units, Margin = 4,500.
    # Delta Margin should be exactly 0.0
    assert abs(bridge["delta_margin"] - 0.0) < 1e-2
    assert abs(bridge["base_margin_t0"] - 4500.0) < 1e-2
    assert abs(bridge["final_margin_t1"] - 4500.0) < 1e-2
    assert bridge["reconciliation_delta"] == 0.0


# ===========================================================================
# Section 7: FastAPI Endpoints Integration
# ===========================================================================

def test_fastapi_interaction_endpoint(client, tmp_path):
    """
    T-INT-12: Verifies POST /api/interactions/evaluate integration with open workspace.
    """
    mxa_path = str(tmp_path / "test_interactions.mxa")
    open_res = client.post("/api/workspace/open", json={"path": mxa_path})
    assert open_res.status_code == 200

    try:
        # Ingest minimal transactions into canonical schema with dimension_attributes
        con = state.connection
        for i in range(10):
            dims = json.dumps({"sales_rep": "RepAlpha", "discount_reason": "PromoX"})
            con.execute(f"""
                INSERT INTO transactions (
                    transaction_line_id, invoice_id, account_id, transaction_date,
                    currency, fx_rate_to_reporting,
                    extended_list_amt, net_invoiced_amt, reporting_list_amt, reporting_invoiced_amt,
                    realized_discount_rate, dimension_attributes, is_credit_reversal
                ) VALUES (
                    'TX-API-{i}', 'INV-{i}', 'ACCT-{i%3}', '2025-01-01',
                    'USD', 1.0,
                    1000.0, 750.0, 1000.0, 750.0,
                    0.25, '{dims}', FALSE
                );
            """)

        res = client.post("/api/interactions/evaluate", json={
            "dim_a": "sales_rep",
            "dim_b": "discount_reason",
            "min_support_tx": 3,
            "min_support_accts": 2,
        })
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert "interactions" in data
        assert data["interactions_count"] == len(data["interactions"])
    finally:
        client.post("/api/workspace/close")


def test_fastapi_pvmc_bridge_endpoint(client, tmp_path):
    """
    T-PVMC-12: Verifies POST /api/pvmc/bridge integration and schema keys
    matching PVMCBridgeView.jsx.
    """
    mxa_path = str(tmp_path / "test_pvmc.mxa")
    client.post("/api/workspace/open", json={"path": mxa_path})

    try:
        con = state.connection
        dims_t0 = json.dumps({"product_family": "SKU-A", "quantity": 10.0, "uom": "EA"})
        dims_t1 = json.dumps({"product_family": "SKU-A", "quantity": 10.0, "uom": "EA"})
        con.execute(f"""
            INSERT INTO transactions (
                transaction_line_id, invoice_id, account_id, transaction_date,
                currency, fx_rate_to_reporting,
                extended_list_amt, net_invoiced_amt, reporting_list_amt, reporting_invoiced_amt,
                cogs_amt, reporting_cogs_amt, realized_discount_rate, dimension_attributes, is_credit_reversal
            ) VALUES 
            ('P-T0', 'INV-1', 'A1', '2024-03-01', 'USD', 1.0, 1000.0, 800.0, 1000.0, 800.0, 500.0, 500.0, 0.20, '{dims_t0}', FALSE),
            ('P-T1', 'INV-2', 'A1', '2025-03-01', 'USD', 1.0, 1200.0, 950.0, 1200.0, 950.0, 550.0, 550.0, 0.2083, '{dims_t1}', FALSE);
        """)

        res = client.post("/api/pvmc/bridge", json={
            "t0_filter": "2024-H1",
            "t1_filter": "2025-H1",
        })
        assert res.status_code == 200
        data = res.json()

        # Check required fields expected by PVMCBridgeView.jsx
        required_fields = [
            "base_margin_t0",
            "price_effect",
            "cost_effect",
            "volume_effect",
            "mix_effect",
            "new_and_discontinued",
            "final_margin_t1",
            "volume_homogeneity_passed",
            "reconciliation_delta",
        ]
        for field in required_fields:
            assert field in data, f"Missing expected key '{field}' for frontend PVMCBridgeView.jsx"

        assert data["reconciliation_delta"] == 0.0
    finally:
        client.post("/api/workspace/close")


def test_api_endpoints_require_open_workspace(client):
    """
    Verifies that M5 endpoints return 400 Bad Request when no workspace is open.
    """
    client.post("/api/workspace/close")

    res1 = client.post("/api/interactions/evaluate", json={"dim_a": "rep", "dim_b": "reason"})
    assert res1.status_code == 400
    assert "No workspace currently open" in res1.json()["detail"]

    res2 = client.post("/api/pvmc/bridge", json={"t0_filter": "2024-H1", "t1_filter": "2025-H1"})
    assert res2.status_code == 400
    assert "No workspace currently open" in res2.json()["detail"]
