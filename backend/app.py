"""
Sift Analytical Engine Backend & IPC Gateway
FastAPI bootstrap binding strictly to 127.0.0.1:8765 with air-gap defenses,
Host header validation, loopback CORS, workspace lifecycle management, and static SPA serving.
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any, List, Union

from fastapi import FastAPI, Request, HTTPException, status, UploadFile, File
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Ensure project root is in sys.path
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    REPO_ROOT = Path(sys._MEIPASS)
else:
    REPO_ROOT = Path(__file__).resolve().parent.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.config import DuckDBConfig
from backend.storage import (
    open_workspace,
    create_workspace,
    init_schema,
    get_workspace_meta,
    checkpoint_workspace,
    close_workspace,
)
from backend.ingestion import preview_source, execute_ingestion
from backend.loao import (
    compute_loao_baselines,
    freeze_calibration,
    load_calibration_profile,
    get_active_calibration_profile,
    validate_three_column_classification,
    classify_attributes,
    DEFAULT_CONTROLS,
    DEFAULT_INVESTIGATION_DIMS,
)
from backend.beam_search import (
    run_beam_search,
    get_overlap_ledger,
    get_finding_transactions,
)
from backend.interactions import (
    evaluate_interactions,
    evaluate_contractual_cap_stacking,
    ToneGuard,
    ToneGuardViolationError,
)
from backend.pvmc_bridge import (
    compute_pvmc_bridge,
)
from backend.lifecycle import (
    compute_finding_fingerprint,
    validate_finding_transition,
    transition_finding,
    get_finding_history,
    diff_audit_runs,
)
from backend.export import (
    sanitize_csv_cell,
    export_actionable_findings,
    export_executive_summary,
    export_restricted_deal_ledger,
)



class WorkspaceState:
    """Runtime container managing the active DuckDB workspace connection."""
    def __init__(self):
        self.active_path: Optional[str] = None
        self.connection: Optional[Any] = None
        self.config: DuckDBConfig = DuckDBConfig()

    def is_open(self) -> bool:
        return self.connection is not None


state = WorkspaceState()

app = FastAPI(
    title="Sift Commercial Audit Analytical Engine",
    description="Air-Gapped, Local-First Commercial Audit & Margin Triage Backend",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
)

# ---------------------------------------------------------------------------
# 1. Security Middleware: Host Header Validation (DNS Rebinding Defense)
# ---------------------------------------------------------------------------
ALLOWED_HOSTS = {
    "127.0.0.1:8765",
    "localhost:8765",
    "127.0.0.1",
    "localhost",
    "testserver",  # Used by pytest TestClient
}


@app.middleware("http")
async def host_header_validation_middleware(request: Request, call_next):
    raw_host = request.headers.get("host", "").lower()
    # Normalize host without port if matching host-only
    host = raw_host.split(":")[0] if raw_host else ""
    if raw_host not in ALLOWED_HOSTS and host not in ALLOWED_HOSTS:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": "Forbidden: Invalid Host Header",
                "detail": f"Host '{raw_host}' is barred by Sift air-gap security guardrails.",
            },
        )
    return await call_next(request)


# ---------------------------------------------------------------------------
# 2. Security Middleware: Loopback CORS Enforcement
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8765",
        "http://localhost:8765",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "tauri://localhost",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# 3. Security Middleware: Content Security Policy & Protective Headers
# ---------------------------------------------------------------------------
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self' http://127.0.0.1:* http://localhost:*; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self' http://127.0.0.1:* http://localhost:*; "
        "font-src 'self'; object-src 'none'; media-src 'none'; frame-src 'none';"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


# ---------------------------------------------------------------------------
# 4. Request / Response Pydantic Models
# ---------------------------------------------------------------------------
class WorkspaceOpenRequest(BaseModel):
    path: Optional[str] = Field(None, description="Absolute or relative path to .mxa workspace file")


class WorkspaceCreateRequest(BaseModel):
    path: str = Field(..., description="Path where .mxa workspace file will be created")
    project_name: str = Field("Sift Project", description="Commercial audit project name")
    reporting_currency: str = Field("USD", description="Reporting currency ISO code")


class IngestPreviewRequest(BaseModel):
    file_path: str = Field(..., description="Path to CSV or Parquet source transaction file")
    nrows: Optional[int] = Field(1000, description="Maximum sample rows to inspect in Pass 1 preview")


class IngestReconcileRequest(BaseModel):
    file_path: str = Field(..., description="Path to CSV or Parquet source transaction file")
    column_mapping: Dict[str, str] = Field(..., description="Mapping between canonical schema fields and source columns")
    control_gross: float = Field(..., description="User-confirmed General Ledger Total Gross List Revenue")
    control_net: float = Field(..., description="User-confirmed General Ledger Total Net Invoiced Revenue")
    reporting_currency: Optional[str] = Field("USD", description="Project reporting currency ISO code")
    quarantine_override: Optional[bool] = Field(False, description="Whether user explicitly overrides quarantine")


class CalibrateLOAORequest(BaseModel):
    controls: Optional[List[str]] = Field(default=["product_family", "sales_region"], description="Comparability control dimensions")
    threshold_method: Optional[str] = Field("P75", description="Boundary threshold algorithm: P75 or MAD")
    kappa: Optional[float] = Field(0.40, description="Actionable opportunity capture rate haircut factor")
    mad_multiplier: Optional[float] = Field(1.5, description="MAD multiplier when threshold_method is MAD")
    min_transactions: Optional[int] = Field(10, description="Support fence minimum peer transactions")
    min_distinct_accounts: Optional[int] = Field(5, description="Support fence minimum distinct peer accounts")


class CalibrateFreezeRequest(BaseModel):
    profile_name: str = Field(..., description="Name for the calibration profile snapshot")
    controls: Optional[List[str]] = Field(default=["product_family", "sales_region"], description="Comparability control dimensions")
    threshold_method: Optional[str] = Field("P75", description="Boundary threshold algorithm: P75 or MAD")
    kappa: Optional[float] = Field(0.40, description="Actionable opportunity capture rate haircut factor")
    mad_multiplier: Optional[float] = Field(1.5, description="MAD multiplier when threshold_method is MAD")
    min_transactions: Optional[int] = Field(10, description="Support fence minimum peer transactions")
    min_distinct_accounts: Optional[int] = Field(5, description="Support fence minimum distinct peer accounts")
    historical_start_date: Optional[str] = Field(None, description="Historical baseline start date (YYYY-MM-DD)")
    historical_end_date: Optional[str] = Field(None, description="Historical baseline end date (YYYY-MM-DD)")
    investigation_dimensions: Optional[List[str]] = Field(None, description="Investigation dimension columns")
    export_dir: Optional[str] = Field(None, description="Directory path where .calib.json profile will be exported")



# ---------------------------------------------------------------------------
# 5. Core API Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/health")
def get_health() -> Dict[str, Any]:
    """
    Health check endpoint providing engine status, version, and air-gap mode.
    Returns status: ok, app: sift, version: 0.1.0, air_gapped: True.
    """
    return {
        "status": "ok",
        "healthy": True,
        "app": "sift",
        "version": "0.1.0",
        "air_gapped": True,
        "mode": "air_gapped_desktop",
        "backend_host": "127.0.0.1:8765",
        "duckdb_version": "1.0.0",
        "workspace_open": state.is_open(),
    }


@app.get("/api/workspace/meta")
def get_workspace_metadata() -> Dict[str, Any]:
    """Returns project metadata and audit state for the active workspace."""
    if not state.is_open():
        return {
            "status": "no_workspace_open",
            "open": False,
            "active_path": None,
        }

    meta = get_workspace_meta(state.connection)
    meta["status"] = "open"
    meta["open"] = True
    meta["active_path"] = state.active_path
    return meta


@app.get("/api/workspace/status")
def get_workspace_status() -> Dict[str, Any]:
    """Returns status of active workspace including row counts and config."""
    if not state.is_open():
        return {
            "status": "no_workspace_open",
            "open": False,
            "active_path": None,
            "max_memory": state.config.max_memory,
            "temp_directory": state.config.get_spill_directory(),
        }

    try:
        meta = get_workspace_meta(state.connection)
        tx_count = state.connection.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        finding_count = state.connection.execute("SELECT COUNT(*) FROM finding_records").fetchone()[0]
        return {
            "status": "open",
            "open": True,
            "active_path": state.active_path,
            "project_name": meta.get("project_name", "Untitled"),
            "schema_version": meta.get("schema_version", "1.0.0"),
            "audit_status": meta.get("audit_status", "Unreconciled"),
            "active_calibration_id": meta.get("active_calibration_id"),
            "transaction_count": tx_count,
            "finding_count": finding_count,
            "max_memory": state.config.max_memory,
            "temp_directory": state.config.get_spill_directory(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query workspace status: {str(e)}",
        )


@app.post("/api/workspace/open")
def post_workspace_open(req: WorkspaceOpenRequest) -> Dict[str, Any]:
    """Opens or connects to an existing single-file .mxa project workspace."""
    ws_path = req.path or os.path.join(str(REPO_ROOT), "sift_workspace.mxa")
    try:
        if state.is_open():
            close_workspace(state.connection)
            state.connection = None
            state.active_path = None

        con = open_workspace(ws_path, state.config)
        state.connection = con
        state.active_path = ws_path
        meta = get_workspace_meta(con)
        return {
            "status": "opened",
            "path": ws_path,
            "project_name": meta.get("project_name", "Untitled"),
            "schema_version": meta.get("schema_version", "1.0.0"),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to open workspace at '{ws_path}': {str(e)}",
        )


@app.post("/api/workspace/create")
def post_workspace_create(req: WorkspaceCreateRequest) -> Dict[str, Any]:
    """Creates a new single-file .mxa workspace and initializes the 8-table schema."""
    try:
        if state.is_open():
            close_workspace(state.connection)
            state.connection = None
            state.active_path = None

        con = create_workspace(
            path=req.path,
            project_name=req.project_name,
            reporting_currency=req.reporting_currency,
            config=state.config,
        )

        state.connection = con
        state.active_path = req.path
        return {
            "status": "created",
            "path": req.path,
            "project_name": req.project_name,
            "tables_initialized": 8,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create workspace at '{req.path}': {str(e)}",
        )


@app.post("/api/workspace/checkpoint")
def post_workspace_checkpoint() -> Dict[str, Any]:
    """Checkpoints active workspace, flushing WAL to single-file .mxa container."""
    if not state.is_open():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active workspace is currently open.",
        )
    try:
        checkpoint_workspace(state.connection)
        return {
            "status": "checkpointed",
            "path": state.active_path,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to checkpoint workspace: {str(e)}",
        )


@app.post("/api/workspace/close")
def post_workspace_close() -> Dict[str, Any]:
    """Checkpoints and cleanly closes active .mxa workspace connection."""
    if not state.is_open():
        return {"status": "already_closed"}

    closed_path = state.active_path
    try:
        close_workspace(state.connection)
    finally:
        state.connection = None
        state.active_path = None

    return {"status": "closed", "path": closed_path}


# ---------------------------------------------------------------------------
# Ingestion & Reconciliation Endpoints (Milestone 2)
# ---------------------------------------------------------------------------
@app.post("/api/ingest/upload")
async def post_ingest_upload(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Receives an uploaded sales dataset file (.xlsx, .csv, .parquet),
    saves it to the workspace uploads directory, and returns its absolute path.
    """
    try:
        upload_dir = os.path.join(str(REPO_ROOT), "uploads")
        os.makedirs(upload_dir, exist_ok=True)

        safe_filename = os.path.basename(file.filename or "uploaded_dataset.csv")
        file_path = os.path.join(upload_dir, safe_filename)

        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        file_size = len(content)
        return {
            "status": "success",
            "filename": safe_filename,
            "file_path": os.path.abspath(file_path),
            "size_bytes": file_size,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded file: {str(e)}",
        )


@app.post("/api/ingest/preview")
def post_ingest_preview(req: IngestPreviewRequest) -> Dict[str, Any]:
    """
    Pass 1 streaming preview endpoint.
    Returns detected columns, inferred types, preview records, and proposed canonical mapping.
    """
    try:
        return preview_source(file_path=req.file_path, nrows=req.nrows or 1000)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to preview source file: {str(e)}",
        )


@app.post("/api/ingest/reconcile")
def post_ingest_reconcile(req: IngestReconcileRequest) -> Dict[str, Any]:
    """
    Pass 2 vectorized ingestion and 1 bp reconciliation gate endpoint.
    Loads source into active workspace DuckDB database, evaluates variance,
    issues Certified Audit or Quarantine watermark, and updates workspace state.
    """
    if not state.is_open():
        state.connection = open_workspace(":memory:")
        state.active_path = ":memory:"

    try:
        result = execute_ingestion(
            con=state.connection,
            file_path=req.file_path,
            column_mapping=req.column_mapping,
            control_gross=req.control_gross,
            control_net=req.control_net,
            reporting_currency=req.reporting_currency or "USD",
            quarantine_override=req.quarantine_override or False,
        )
        return result
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to execute ingestion & reconciliation: {str(e)}",
        )


# ---------------------------------------------------------------------------
# LOAO Calibration & Freezing Endpoints (Milestone 3)
# ---------------------------------------------------------------------------
@app.post("/api/calibrate/loao")
def post_calibrate_loao(req: CalibrateLOAORequest) -> Dict[str, Any]:
    """
    Computes LOAO peer cohort statistics and baseline metrics across transactions in the active workspace.
    Enforces support fences (N >= 10, |A| >= 5) with hierarchical back-off, evaluates P75 or MAD boundary,
    and returns comprehensive calibration summary statistics.
    """
    if not state.is_open():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active workspace is open. Please open or create a workspace first.",
        )
    try:
        result = compute_loao_baselines(
            con=state.connection,
            controls=req.controls,
            threshold_method=req.threshold_method or "P75",
            kappa=req.kappa if req.kappa is not None else 0.40,
            mad_multiplier=req.mad_multiplier if req.mad_multiplier is not None else 1.5,
            min_transactions=req.min_transactions if req.min_transactions is not None else 10,
            min_distinct_accounts=req.min_distinct_accounts if req.min_distinct_accounts is not None else 5,
        )
        return result.to_dict()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LOAO calibration failed: {str(e)}",
        )


@app.post("/api/calibrate/freeze")
def post_calibrate_freeze(req: CalibrateFreezeRequest) -> Dict[str, Any]:
    """
    Freezes active LOAO calibration into an immutable snapshot.
    Exports versioned .calib.json manifest file and records snapshot into meta_calibration_profiles.
    """
    if not state.is_open():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active workspace is open. Please open or create a workspace first.",
        )
    try:
        calib_id = freeze_calibration(
            con=state.connection,
            profile_name=req.profile_name,
            controls=req.controls,
            threshold_method=req.threshold_method or "P75",
            kappa=req.kappa if req.kappa is not None else 0.40,
            mad_multiplier=req.mad_multiplier if req.mad_multiplier is not None else 1.5,
            min_transactions=req.min_transactions if req.min_transactions is not None else 10,
            min_distinct_accounts=req.min_distinct_accounts if req.min_distinct_accounts is not None else 5,
            historical_start_date=req.historical_start_date,
            historical_end_date=req.historical_end_date,
            investigation_dimensions=req.investigation_dimensions,
            export_dir=req.export_dir,
        )
        active_profile = get_active_calibration_profile(state.connection)
        return {
            "status": "frozen",
            "calibration_id": calib_id,
            "profile_name": req.profile_name,
            "manifest": active_profile,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to freeze calibration profile: {str(e)}",
        )


@app.get("/api/calibrate/profiles")
def get_calibrate_profiles() -> Dict[str, Any]:
    """Lists all saved/frozen calibration profiles in the active workspace."""
    if not state.is_open():
        return {"profiles": []}
    try:
        rows = state.connection.execute("""
            SELECT calibration_id, name, created_at, threshold_strategy, haircut_kappa, comparability_controls, calibration_json, is_locked
            FROM meta_calibration_profiles
            ORDER BY created_at DESC;
        """).fetchall()
        profiles = []
        for r in rows:
            profiles.append({
                "calibration_id": r[0],
                "name": r[1],
                "created_at": str(r[2]),
                "threshold_strategy": r[3],
                "haircut_kappa": float(r[4]),
                "comparability_controls": r[5],
                "manifest": json.loads(r[6]) if isinstance(r[6], str) else r[6],
                "is_locked": bool(r[7]),
            })
        return {"profiles": profiles}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query calibration profiles: {str(e)}",
        )


# ---------------------------------------------------------------------------
# 5. Triage, Diagnostic Beam Search & Overlap Ledger Endpoints (Milestone 4)
# ---------------------------------------------------------------------------

class BeamSearchRequest(BaseModel):
    investigation_dims: Optional[List[str]] = Field(
        default=["sales_rep", "discount_reason", "channel"],
        description="Investigation dimension columns to traverse",
    )
    width: Optional[int] = Field(3, description="Beam search width")
    depth: Optional[int] = Field(3, description="Maximum beam search depth")
    fdr_q: Optional[float] = Field(0.05, description="Benjamini-Hochberg FDR significance threshold")
    min_slice_size: Optional[int] = Field(5, description="Minimum transactions per slice")


@app.post("/api/triage/beam_search")
@app.post("/api/triage/beam-search")
def api_run_beam_search(payload: BeamSearchRequest):
    if not state.is_open():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No workspace currently open. Open or create a workspace first.",
        )
    try:
        findings = run_beam_search(
            con=state.connection,
            investigation_dims=payload.investigation_dims,
            width=payload.width or 3,
            depth=payload.depth or 3,
            fdr_q=payload.fdr_q or 0.05,
            min_slice_size=payload.min_slice_size or 5,
        )
        ledger = get_overlap_ledger(state.connection)
        return {
            "status": "success",
            "findings_count": len(findings),
            "findings": findings,
            "net_unique_portfolio_exposure": ledger["net_unique_portfolio_exposure"],
            "net_unique_transactions": ledger["net_unique_transactions"],
            "gross_unshrunk_gap_sum": ledger["gross_unshrunk_gap_sum"],
            "gross_shrunk_gap_sum": ledger.get("gross_shrunk_gap_sum", 0.0),
            "overlap_double_counted_dollars": ledger["overlap_double_counted_dollars"],
            "overlap_pct": ledger.get("overlap_pct", 0.0),
            "overlap_ratio_pct": ledger.get("overlap_ratio_pct", 0.0),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Beam search traversal failed: {str(e)}",
        )


@app.get("/api/triage/overlap_ledger")
@app.get("/api/triage/overlap-ledger")
def api_get_overlap_ledger():
    if not state.is_open():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No workspace currently open. Open or create a workspace first.",
        )
    try:
        return get_overlap_ledger(state.connection)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query overlap ledger: {str(e)}",
        )


@app.get("/api/triage/findings/{finding_id}/transactions")
def api_get_finding_transactions(finding_id: str):
    if not state.is_open():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No workspace currently open. Open or create a workspace first.",
        )
    try:
        return get_finding_transactions(state.connection, finding_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query finding transactions: {str(e)}",
        )


# ---------------------------------------------------------------------------
# 5. Milestone 5: Interactions & Decoupled PVMC Bridge Endpoints
# ---------------------------------------------------------------------------

class InteractionEvaluateRequest(BaseModel):
    dim_a: str = Field(..., description="First interaction dimension, e.g. 'sales_rep'")
    dim_b: str = Field(..., description="Second interaction dimension, e.g. 'discount_reason'")
    min_support_tx: Optional[int] = Field(5, description="Minimum transactions per cell")
    min_support_accts: Optional[int] = Field(3, description="Minimum distinct accounts per cell")
    fdr_q: Optional[float] = Field(0.05, description="Benjamini-Hochberg FDR threshold")
    mode: Optional[str] = Field("statistical", description="Audit mode: 'statistical' or 'rule_based'")


class PVMCBridgeRequest(BaseModel):
    t0_filter: Optional[Union[str, Dict[str, Any]]] = Field("2024-H1", description="Base period filter")
    t1_filter: Optional[Union[str, Dict[str, Any]]] = Field("2025-H1", description="Target period filter")
    product_col: Optional[str] = Field(None, description="Product / SKU column")
    qty_col: Optional[str] = Field(None, description="Quantity column")
    uom_col: Optional[str] = Field(None, description="Unit of measure column")


@app.post("/api/interactions/evaluate")
def api_evaluate_interactions(payload: InteractionEvaluateRequest):
    if not state.is_open():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No workspace currently open. Open or create a workspace first.",
        )
    try:
        results = evaluate_interactions(
            con=state.connection,
            dim_a=payload.dim_a,
            dim_b=payload.dim_b,
            min_support_tx=payload.min_support_tx or 5,
            min_support_accts=payload.min_support_accts or 3,
            fdr_q=payload.fdr_q or 0.05,
            mode=payload.mode or "statistical",
        )
        return {
            "status": "success",
            "interactions_count": len(results),
            "interactions": results,
        }
    except ToneGuardViolationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Interaction evaluation failed: {str(e)}",
        )


@app.post("/api/pvmc/bridge")
def api_compute_pvmc_bridge(payload: PVMCBridgeRequest):
    if not state.is_open():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No workspace currently open. Open or create a workspace first.",
        )
    try:
        t0 = payload.t0_filter if payload.t0_filter is not None else "2024-H1"
        t1 = payload.t1_filter if payload.t1_filter is not None else "2025-H1"
        return compute_pvmc_bridge(
            con=state.connection,
            t0_filter=t0,
            t1_filter=t1,
            product_col=payload.product_col,
            qty_col=payload.qty_col,
            uom_col=payload.uom_col,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PVMC bridge calculation failed: {str(e)}",
        )


# ---------------------------------------------------------------------------
# 5b. Milestone 6: Lifecycle State Machine & Safe Exports
# ---------------------------------------------------------------------------

class TransitionFindingRequest(BaseModel):
    finding_fingerprint: str
    new_state: str
    disposition_code: Optional[str] = None
    dismissal_category: Optional[str] = None
    snooze_date: Optional[str] = None
    assigned_owner: Optional[str] = None
    notes: Optional[str] = None
    user: Optional[str] = "auditor"


@app.post("/api/lifecycle/transition")
def api_transition_finding(payload: TransitionFindingRequest):
    if not state.is_open():
        raise HTTPException(status_code=400, detail="No workspace currently open.")
    try:
        return transition_finding(
            con=state.connection,
            finding_fingerprint=payload.finding_fingerprint,
            new_state=payload.new_state,
            disposition_code=payload.disposition_code,
            dismissal_category=payload.dismissal_category,
            snooze_date=payload.snooze_date,
            assigned_owner=payload.assigned_owner,
            notes=payload.notes,
            user=payload.user or "auditor",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transition failed: {str(e)}")


@app.get("/api/lifecycle/history/{finding_fingerprint}")
def api_get_finding_history(finding_fingerprint: str):
    if not state.is_open():
        raise HTTPException(status_code=400, detail="No workspace currently open.")
    try:
        return {"history": get_finding_history(state.connection, finding_fingerprint)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch finding history: {str(e)}")


class DiffRunsRequest(BaseModel):
    historical_workspace_path: str


@app.post("/api/lifecycle/diff")
def api_diff_runs(payload: DiffRunsRequest):
    if not state.is_open():
        raise HTTPException(status_code=400, detail="No workspace currently open.")
    try:
        hist_con = open_workspace(payload.historical_workspace_path)
        try:
            return diff_audit_runs(hist_con, state.connection)
        finally:
            close_workspace(hist_con)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Diff runs failed: {str(e)}")


class ExportExecutiveSummaryRequest(BaseModel):
    out_path: str
    format: Optional[str] = "html"


@app.post("/api/export/executive-summary")
def api_export_executive_summary(payload: ExportExecutiveSummaryRequest):
    if not state.is_open():
        raise HTTPException(status_code=400, detail="No workspace currently open.")
    try:
        path = export_executive_summary(state.connection, payload.out_path, payload.format or "html")
        return {"status": "success", "file_path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


class ExportActionableFindingsRequest(BaseModel):
    out_path: str


@app.post("/api/export/actionable-findings")
def api_export_actionable_findings(payload: ExportActionableFindingsRequest):
    if not state.is_open():
        raise HTTPException(status_code=400, detail="No workspace currently open.")
    try:
        path = export_actionable_findings(state.connection, payload.out_path)
        return {"status": "success", "file_path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


class ExportRestrictedDealLedgerRequest(BaseModel):
    out_path: str
    password: str
    user_acknowledged: bool = False


@app.post("/api/export/restricted-deal-ledger")
def api_export_restricted_deal_ledger(payload: ExportRestrictedDealLedgerRequest):
    if not state.is_open():
        raise HTTPException(status_code=400, detail="No workspace currently open.")
    try:
        path = export_restricted_deal_ledger(
            con=state.connection,
            out_path=payload.out_path,
            password=payload.password,
            user_acknowledged=payload.user_acknowledged,
        )
        return {"status": "success", "file_path": path}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


# ---------------------------------------------------------------------------
# 6. Static SPA Asset Mounting & Informative Fallback
# ---------------------------------------------------------------------------
dist_candidates = [
    REPO_ROOT / "src" / "dist",
    REPO_ROOT / "dist",
]

mounted_dist: Optional[Path] = None
for candidate in dist_candidates:
    if candidate.is_dir() and (candidate / "index.html").is_file():
        mounted_dist = candidate
        break

if mounted_dist:
    app.mount("/", StaticFiles(directory=str(mounted_dist), html=True), name="static_spa")
else:
    @app.get("/", response_class=HTMLResponse)
    def fallback_landing():
        return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Sift — Analytical Engine Active</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 36px; max-width: 640px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5); }
    h1 { margin-top: 0; font-size: 24px; color: #38bdf8; display: flex; align-items: center; gap: 10px; }
    .status-badge { background: #064e3b; color: #34d399; border: 1px solid #059669; padding: 4px 10px; border-radius: 9999px; font-size: 12px; font-weight: 600; text-transform: uppercase; }
    p { color: #94a3b8; line-height: 1.6; }
    ul { list-style: none; padding-left: 0; }
    li { padding: 8px 0; border-bottom: 1px solid #334155; font-size: 14px; }
    a { color: #38bdf8; text-decoration: none; }
    a:hover { text-decoration: underline; }
    code { background: #0f172a; padding: 2px 6px; border-radius: 4px; font-family: monospace; color: #e2e8f0; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Sift Analytical Engine <span class="status-badge">Air-Gapped Localhost</span></h1>
    <p>The Sift analytical engine and in-process DuckDB instance are operational on <code>127.0.0.1:8765</code>.</p>
    <ul>
      <li>API Documentation: <a href="/docs">/docs (Interactive Swagger UI)</a></li>
      <li>System Health: <a href="/api/health">/api/health</a></li>
      <li>Workspace Metadata: <a href="/api/workspace/meta">/api/workspace/meta</a></li>
      <li>Workspace Status: <a href="/api/workspace/status">/api/workspace/status</a></li>
      <li>DuckDB Analytical Engine: <code>DuckDB 1.0.0 (4GB Limit, Disk-Spilling Enabled)</code></li>
    </ul>
    <p><small style="color: #64748b;">Frontend React assets are mounted from <code>dist/</code> when built. Run <code>npm run build</code> to compile the reactive UI.</small></p>
  </div>
</body>
</html>"""
