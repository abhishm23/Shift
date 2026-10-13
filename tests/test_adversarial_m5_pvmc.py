"""
tests/test_adversarial_m5_pvmc.py
Adversarial Stress Suite for Milestone 5:
Tone Guard Bypass Vulnerabilities & PVMC Exact Penny Reconciliation Under Extreme Financial Shocks.

Target:
  - backend/interactions.py (ToneGuard, evaluate_contractual_cap_stacking, evaluate_interactions)
  - backend/pvmc_bridge.py (compute_pvmc_bridge, compute_homogeneous_segment_pvmc)
"""

import json
import math
import duckdb
import pytest

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
def canonical_schema_db():
    """Initializes an in-memory DuckDB connection with canonical transactions schema."""
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


# ===========================================================================
# CHALLENGE 1: ToneGuard Adversarial Bypass & Formatting/Delimiter Attacks
# ===========================================================================

def test_adversarial_tone_guard_casing_variations():
    """
    Challenge 1.1: Verify case variations (UPPER, lower, mIxEd, Title) are strictly blocked.
    """
    variants = [
        "policy violation",
        "Policy Violation",
        "POLICY VIOLATION",
        "pOlIcY vIoLaTiOn",
        "PoLiCy ViOlAtIoN",
        "POLICY violation",
        "policy VIOLATION",
    ]
    for text in variants:
        assert not ToneGuard.is_safe(text, mode="statistical"), f"Failed to detect: {text}"
        with pytest.raises(ToneGuardViolationError):
            ToneGuard.validate(text, mode="statistical")


def test_adversarial_tone_guard_delimiter_and_whitespace_tricks():
    """
    Challenge 1.2: Verify delimiter injections (dots, dashes, underscores, slashes, tabs, newlines)
    are strictly blocked.
    """
    tricks = [
        "policy_violation",
        "policy-violation",
        "policy--violation",
        "policy__violation",
        "policy___violation",
        "policy.violation",
        "policy...violation",
        "policy/violation",
        "policy\\violation",
        "policy:violation",
        "policy;violation",
        "policy|violation",
        "policy~violation",
        "policy!violation",
        "policy@violation",
        "policy#violation",
        "policy%violation",
        "policy^violation",
        "policy&violation",
        "policy*violation",
        "policy \t \n \r violation",
        "policy       violation",
        "policy\u200bviolation",  # zero-width space
        "policy\xa0violation",    # non-breaking space
        "p.o.l.i.c.y.v.i.o.l.a.t.i.o.n",
        "p-o-l-i-c-y-v-i-o-l-a-t-i-o-n",
        "p_o_l_i_c_y_v_i_o_l_a_t_i_o_n",
        "P O L I C Y   V I O L A T I O N",
    ]
    for text in tricks:
        assert not ToneGuard.is_safe(text, mode="statistical"), f"Bypass succeeded on trick: {text}"
        with pytest.raises(ToneGuardViolationError):
            ToneGuard.validate(text, mode="statistical")


def test_adversarial_tone_guard_punitive_phrases():
    """
    Challenge 1.3: Verify all blacklisted punitive phrases are blocked under permutations.
    """
    phrases = [
        "unapproved concession",
        "UNAPPROVED_CONCESSION",
        "u-n-a-p-p-r-o-v-e-d  c-o-n-c-e-s-s-i-o-n",
        "unauthorized deal",
        "UNAUTHORIZED-DEAL",
        "u.n.a.u.t.h.o.r.i.z.e.d d.e.a.l",
        "breach of policy",
        "BREACH_OF_POLICY",
        "off-policy deal",
        "off policy deal",
    ]
    for text in phrases:
        assert not ToneGuard.is_safe(text, mode="statistical"), f"Punitive phrase bypassed: {text}"
        with pytest.raises(ToneGuardViolationError):
            ToneGuard.validate(text, mode="statistical")


def test_adversarial_tone_guard_data_injection_blocked(canonical_schema_db):
    """
    Challenge 1.4: Verify that attempting to inject forbidden terminology into transaction
    dimension values fails closed and is blocked from being emitted by evaluate_interactions.
    """
    for i in range(8):
        canonical_schema_db.execute(f"""
            INSERT INTO transactions (
                transaction_line_id, invoice_id, account_id, transaction_date,
                extended_list_amt, net_invoiced_amt, reporting_invoiced_amt,
                realized_discount_rate, is_credit_reversal, sales_rep, discount_reason
            ) VALUES (
                'TX-INJ-{i}', 'INV-{i}', 'ACCT-1', '2025-01-01',
                1000.0, 750.0, 750.0, 0.25, FALSE, 'Policy Violation', 'Standard'
            );
        """)

    with pytest.raises(AssertionError) as exc_info:
        evaluate_interactions(
            con=canonical_schema_db,
            dim_a="sales_rep",
            dim_b="discount_reason",
            min_support_tx=2,
            min_support_accts=1,
            mode="statistical",
        )
    assert "ToneGuard invariant violated in output record" in str(exc_info.value)


# ===========================================================================
# CHALLENGE 2: PVMC Margin Bridge Stress Testing Under Extreme Shocks
# ===========================================================================

def test_adversarial_pvmc_1000x_price_shock_up(canonical_schema_db):
    """
    Challenge 2.1: Extreme 1000x price surge: $10.00 -> $10,000.00 per unit.
    Exact penny reconciliation must hold with 0.00 residual.
    """
    # T0: 500 units @ $10.00 price, $6.00 cost -> Margin = $2,000.00
    canonical_schema_db.execute("""
        INSERT INTO transactions (
            transaction_line_id, invoice_id, account_id, transaction_date,
            extended_list_amt, net_invoiced_amt, cogs_amt,
            reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt,
            product_family, quantity, uom, is_credit_reversal
        ) VALUES (
            'T0-SURGE', 'INV-1', 'A1', '2024-01-15',
            5000.0, 5000.0, 3000.0, 5000.0, 3000.0, 0.0,
            'SURGE-SKU', 500.0, 'EA', FALSE
        );
    """)

    # T1: 500 units @ $10,000.00 price, $6.00 cost -> Margin = 500 * $9,994.00 = $4,997,000.00
    canonical_schema_db.execute("""
        INSERT INTO transactions (
            transaction_line_id, invoice_id, account_id, transaction_date,
            extended_list_amt, net_invoiced_amt, cogs_amt,
            reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt,
            product_family, quantity, uom, is_credit_reversal
        ) VALUES (
            'T1-SURGE', 'INV-2', 'A1', '2025-01-15',
            5000000.0, 5000000.0, 3000.0, 5000000.0, 3000.0, 0.0,
            'SURGE-SKU', 500.0, 'EA', FALSE
        );
    """)

    bridge = compute_pvmc_bridge(canonical_schema_db, "2024-H1", "2025-H1")
    assert bridge["status"] == "success"
    assert bridge["reconciliation_certified"] is True
    assert bridge["reconciliation_delta"] == 0.0
    assert abs(bridge["delta_margin"] - 4995000.0) < 1e-2
    assert abs(bridge["price_effect"] - 4995000.0) < 1e-2
    assert abs(bridge["volume_effect"] - 0.0) < 1e-2
    assert abs(bridge["mix_effect"] - 0.0) < 1e-2


def test_adversarial_pvmc_1000x_price_shock_collapse(canonical_schema_db):
    """
    Challenge 2.2: Extreme price collapse (1000x drop): $1000.00 -> $1.00 per unit.
    Negative margins generated. Exact penny reconciliation must hold.
    """
    # T0: 100 units @ $1,000.00 price, $400.00 cost -> Margin = $60,000.00
    canonical_schema_db.execute("""
        INSERT INTO transactions (
            transaction_line_id, invoice_id, account_id, transaction_date,
            extended_list_amt, net_invoiced_amt, cogs_amt,
            reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt,
            product_family, quantity, uom, is_credit_reversal
        ) VALUES (
            'T0-DROP', 'INV-1', 'A1', '2024-02-15',
            100000.0, 100000.0, 40000.0, 100000.0, 40000.0, 0.0,
            'DROP-SKU', 100.0, 'EA', FALSE
        );
    """)

    # T1: 100 units @ $1.00 price, $400.00 cost -> Margin = 100 * (-$399.00) = -$39,900.00
    canonical_schema_db.execute("""
        INSERT INTO transactions (
            transaction_line_id, invoice_id, account_id, transaction_date,
            extended_list_amt, net_invoiced_amt, cogs_amt,
            reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt,
            product_family, quantity, uom, is_credit_reversal
        ) VALUES (
            'T1-DROP', 'INV-2', 'A1', '2025-02-15',
            100.0, 100.0, 40000.0, 100.0, 40000.0, 0.0,
            'DROP-SKU', 100.0, 'EA', FALSE
        );
    """)

    bridge = compute_pvmc_bridge(canonical_schema_db, "2024-H1", "2025-H1")
    assert bridge["status"] == "success"
    assert bridge["reconciliation_certified"] is True
    assert bridge["reconciliation_delta"] == 0.0
    assert abs(bridge["delta_margin"] - (-99900.00)) < 1e-2
    assert abs(bridge["price_effect"] - (-99900.00)) < 1e-2


def test_adversarial_pvmc_heterogeneous_uom_mixture_complex(canonical_schema_db):
    """
    Challenge 2.3: Complex portfolio with 5 disparate Units of Measure ('EA', 'KG', 'MTR', 'LITRE', 'HRS')
    under simultaneous price, cost, volume, and mix shifts.
    Verifies that volume homogeneity segments each UoM cleanly and penny reconciliation holds.
    """
    uom_specs = [
        ("SKU-EA", "EA", 100.0, 150.0, 50.0, 60.0, 20.0, 22.0),
        ("SKU-KG", "KG", 500.0, 450.0, 10.0, 9.0, 4.0, 4.5),
        ("SKU-MTR", "MTR", 1000.0, 1200.0, 2.5, 2.8, 1.0, 1.1),
        ("SKU-LITRE", "LITRE", 250.0, 250.0, 8.0, 8.0, 5.0, 4.0),
        ("SKU-HRS", "HRS", 40.0, 80.0, 150.0, 175.0, 50.0, 50.0),
    ]

    for i, (prod, uom, q0, q1, p0, p1, c0, c1) in enumerate(uom_specs):
        r0 = q0 * p0
        cg0 = q0 * c0
        canonical_schema_db.execute(f"""
            INSERT INTO transactions (
                transaction_line_id, invoice_id, account_id, transaction_date,
                extended_list_amt, net_invoiced_amt, cogs_amt,
                reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt,
                product_family, quantity, uom, is_credit_reversal
            ) VALUES (
                'T0-UOM-{i}', 'INV-{i}', 'A1', '2024-03-01',
                {r0}, {r0}, {cg0}, {r0}, {cg0}, 0.0,
                '{prod}', {q0}, '{uom}', FALSE
            );
        """)

        r1 = q1 * p1
        cg1 = q1 * c1
        canonical_schema_db.execute(f"""
            INSERT INTO transactions (
                transaction_line_id, invoice_id, account_id, transaction_date,
                extended_list_amt, net_invoiced_amt, cogs_amt,
                reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt,
                product_family, quantity, uom, is_credit_reversal
            ) VALUES (
                'T1-UOM-{i}', 'INV-{i}', 'A1', '2025-03-01',
                {r1}, {r1}, {cg1}, {r1}, {cg1}, 0.0,
                '{prod}', {q1}, '{uom}', FALSE
            );
        """)

    bridge = compute_pvmc_bridge(canonical_schema_db, "2024-H1", "2025-H1")
    assert bridge["status"] == "success"
    assert bridge["volume_homogeneity_passed"] is True
    assert len(bridge["uom_segments"]) == 5
    assert bridge["reconciliation_certified"] is True
    assert bridge["reconciliation_delta"] <= 0.01


def test_adversarial_pvmc_credit_note_net_positive_volume(canonical_schema_db):
    """
    Challenge 2.4: Net positive volume with heavy credit reversals and returns.
    Verifies that credit note flags invert quantities and net cleanly with 0.00 delta.
    """
    canonical_schema_db.execute("""
        INSERT INTO transactions (
            transaction_line_id, invoice_id, account_id, transaction_date,
            extended_list_amt, net_invoiced_amt, cogs_amt,
            reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt,
            product_family, quantity, uom, is_credit_reversal
        ) VALUES 
        ('T0-S1', 'INV-1', 'A1', '2024-01-01', 10000.0, 10000.0, 6000.0, 10000.0, 6000.0, 0.0, 'SKU-CR', 100.0, 'EA', FALSE),
        ('T0-R1', 'INV-2', 'A1', '2024-01-05', -2000.0, -2000.0, -1200.0, -2000.0, -1200.0, 0.0, 'SKU-CR', 20.0, 'EA', TRUE),
        ('T1-S1', 'INV-3', 'A1', '2025-01-01', 12000.0, 12000.0, 7200.0, 12000.0, 7200.0, 0.0, 'SKU-CR', 120.0, 'EA', FALSE),
        ('T1-R1', 'INV-4', 'A1', '2025-01-05', -4000.0, -4000.0, -2400.0, -4000.0, -2400.0, 0.0, 'SKU-CR', 40.0, 'EA', TRUE);
    """)

    bridge = compute_pvmc_bridge(canonical_schema_db, "2024-H1", "2025-H1")
    assert bridge["status"] == "success"
    # Net T0 = 80 units @ ($100, $60) -> Margin = 80 * $40 = $3,200
    # Net T1 = 80 units @ ($100, $60) -> Margin = 80 * $40 = $3,200
    assert abs(bridge["delta_margin"] - 0.0) < 1e-2
    assert bridge["reconciliation_delta"] == 0.0
    assert bridge["reconciliation_certified"] is True


def test_adversarial_pvmc_isolated_credit_note_reconciliation_failure(canonical_schema_db):
    """
    Challenge 2.5: EMPIRICAL VULNERABILITY DEMONSTRATION.
    When an item has positive sales in T0, but in T1 has ONLY credit notes/returns (net quantity <= 0),
    or vice versa, the bridge's turnover isolation logic fails to capture the residual margin of the
    inactive/return period, producing an unallocated residual and failing reconciliation certification.
    """
    # T0: Positive sales of 100 units @ $100 price, $50 cost -> Margin = $500.00
    canonical_schema_db.execute("""
        INSERT INTO transactions (
            transaction_line_id, invoice_id, account_id, transaction_date,
            extended_list_amt, net_invoiced_amt, cogs_amt,
            reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt,
            product_family, quantity, uom, is_credit_reversal
        ) VALUES (
            'T0-SALE', 'INV-1', 'A1', '2024-01-01',
            1000.0, 1000.0, 500.0, 1000.0, 500.0, 0.0,
            'SKU-RET-ONLY', 100.0, 'EA', FALSE
        );
    """)

    # T1: ONLY a return of 10 units @ -$100 price, -$50 cost -> Margin = -$50.00
    canonical_schema_db.execute("""
        INSERT INTO transactions (
            transaction_line_id, invoice_id, account_id, transaction_date,
            extended_list_amt, net_invoiced_amt, cogs_amt,
            reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt,
            product_family, quantity, uom, is_credit_reversal
        ) VALUES (
            'T1-RET', 'INV-2', 'A1', '2025-01-01',
            -100.0, -100.0, -50.0, -100.0, -50.0, 0.0,
            'SKU-RET-ONLY', -10.0, 'EA', TRUE
        );
    """)

    bridge = compute_pvmc_bridge(canonical_schema_db, "2024-H1", "2025-H1")

    # True delta margin is: final_margin_t1 (-50) - base_margin_t0 (500) = -550.00
    assert bridge["delta_margin"] == -550.0
    assert bridge["base_margin_t0"] == 500.0
    assert bridge["final_margin_t1"] == -50.0

    # Under resolved turnover isolation logic, both T0 lost margin (-500) and T1 return margin (-50)
    # are accounted for, achieving exact penny reconciliation:
    assert bridge["reconciliation_certified"] is True
    assert bridge["reconciliation_delta"] <= 0.01


def test_adversarial_pvmc_isolated_credit_note_t0_return_t1_sale(canonical_schema_db):
    """
    Challenge 2.6: Symmetrical isolated credit note validation.
    When an item has ONLY credit notes/returns in T0 (q0 <= 0, m0 != 0), and positive sales in T1 (q1 > 0),
    verify that T0 return margin is properly accounted for in discontinued turnover and exact penny reconciliation holds.
    """
    # T0: ONLY a return of 10 units @ -$100 price, -$50 cost -> Margin = -$50.00
    canonical_schema_db.execute("""
        INSERT INTO transactions (
            transaction_line_id, invoice_id, account_id, transaction_date,
            extended_list_amt, net_invoiced_amt, cogs_amt,
            reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt,
            product_family, quantity, uom, is_credit_reversal
        ) VALUES (
            'T0-RET', 'INV-1', 'A1', '2024-01-01',
            -100.0, -100.0, -50.0, -100.0, -50.0, 0.0,
            'SKU-SYM-CR', -10.0, 'EA', TRUE
        );
    """)

    # T1: Positive sales of 100 units @ $100 price, $50 cost -> Margin = $500.00
    canonical_schema_db.execute("""
        INSERT INTO transactions (
            transaction_line_id, invoice_id, account_id, transaction_date,
            extended_list_amt, net_invoiced_amt, cogs_amt,
            reporting_invoiced_amt, reporting_cogs_amt, reporting_rebate_amt,
            product_family, quantity, uom, is_credit_reversal
        ) VALUES (
            'T1-SALE', 'INV-2', 'A1', '2025-01-01',
            1000.0, 1000.0, 500.0, 1000.0, 500.0, 0.0,
            'SKU-SYM-CR', 100.0, 'EA', FALSE
        );
    """)

    bridge = compute_pvmc_bridge(canonical_schema_db, "2024-H1", "2025-H1")

    # True delta margin is: final_margin_t1 (500) - base_margin_t0 (-50) = 550.00
    assert bridge["delta_margin"] == 550.0
    assert bridge["base_margin_t0"] == -50.0
    assert bridge["final_margin_t1"] == 500.0

    assert bridge["reconciliation_certified"] is True
    assert bridge["reconciliation_delta"] <= 0.01

