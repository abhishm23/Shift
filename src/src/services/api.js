/**
 * Air-Gapped Loopback API Client for Sift Analytical Engine
 * Strict Origin: http://127.0.0.1:8765
 * Zero external telemetry / Zero third-party network egress.
 */

const API_BASE = 'http://127.0.0.1:8765';

/**
 * Generic fetch wrapper enforcing loopback isolation and consistent error handling
 */
async function apiFetch(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;
  const defaultHeaders = isFormData
    ? { 'Accept': 'application/json' }
    : {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      };

  const config = {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  };

  try {
    const response = await fetch(url, config);
    if (!response.ok) {
      let detail = `HTTP ${response.status}: ${response.statusText}`;
      try {
        const errorJson = await response.json();
        if (errorJson.detail) detail = typeof errorJson.detail === 'string' ? errorJson.detail : JSON.stringify(errorJson.detail);
        else if (errorJson.message) detail = errorJson.message;
      } catch (_) {
        // Non-JSON error body
      }
      const err = new Error(detail);
      err.status = response.status;
      throw err;
    }
    return await response.json();
  } catch (err) {
    // Re-throw with enriched message for UI consumption
    throw err;
  }
}

export const api = {
  // ── Health & Workspace ──────────────────────────────────────────────────
  health: {
    check: () => apiFetch('/api/health'),
  },

  workspace: {
    meta: () => apiFetch('/api/workspace/meta'),
    status: () => apiFetch('/api/workspace/status'),
    open: (path) =>
      apiFetch('/api/workspace/open', {
        method: 'POST',
        body: JSON.stringify({ path }),
      }),
    create: (path, projectName = 'Sift Project', reportingCurrency = 'USD') =>
      apiFetch('/api/workspace/create', {
        method: 'POST',
        body: JSON.stringify({
          path,
          project_name: projectName,
          reporting_currency: reportingCurrency,
        }),
      }),
    checkpoint: () =>
      apiFetch('/api/workspace/checkpoint', {
        method: 'POST',
      }),
    close: () =>
      apiFetch('/api/workspace/close', {
        method: 'POST',
      }),
  },

  // ── Ingestion & Reconciliation ──────────────────────────────────────────
  ingest: {
    upload: (file) => {
      const formData = new FormData();
      formData.append('file', file);
      return apiFetch('/api/ingest/upload', {
        method: 'POST',
        body: formData,
      });
    },
    preview: (filePath, nrows = 1000) =>
      apiFetch('/api/ingest/preview', {
        method: 'POST',
        body: JSON.stringify({ file_path: filePath, nrows }),
      }),
    reconcile: ({ filePath, columnMapping, controlGross, controlNet, reportingCurrency = 'USD', quarantineOverride = false }) =>
      apiFetch('/api/ingest/reconcile', {
        method: 'POST',
        body: JSON.stringify({
          file_path: filePath,
          column_mapping: columnMapping,
          control_gross: Number(controlGross),
          control_net: Number(controlNet),
          reporting_currency: reportingCurrency,
          quarantine_override: Boolean(quarantineOverride),
        }),
      }),
    execute: (params) => api.ingest.reconcile(params),
  },

  // ── Calibration ─────────────────────────────────────────────────────────
  calibrate: {
    loao: ({ controls, thresholdMethod = 'P75', kappa = 0.40, madMultiplier = 1.5, minTransactions = 10, minDistinctAccounts = 5 }) =>
      apiFetch('/api/calibrate/loao', {
        method: 'POST',
        body: JSON.stringify({
          controls,
          threshold_method: thresholdMethod,
          kappa: Number(kappa),
          mad_multiplier: Number(madMultiplier),
          min_transactions: Number(minTransactions),
          min_distinct_accounts: Number(minDistinctAccounts),
        }),
      }),
    freeze: (profileName, controls = [], thresholdMethod = 'P75', kappa = 0.40, madMultiplier = 1.5) =>
      apiFetch('/api/calibrate/freeze', {
        method: 'POST',
        body: JSON.stringify({
          profile_name: profileName,
          controls,
          threshold_method: thresholdMethod,
          kappa: Number(kappa),
          mad_multiplier: Number(madMultiplier),
        }),
      }),
    profiles: () => apiFetch('/api/calibrate/profiles'),
  },

  // ── Triage & Beam Search ────────────────────────────────────────────────
  triage: {
    beamSearch: ({ investigationDims, width = 3, depth = 3, fdrQ = 0.05, minSliceSize = 5 }) =>
      apiFetch('/api/triage/beam-search', {
        method: 'POST',
        body: JSON.stringify({
          investigation_dims: investigationDims,
          width: Number(width),
          depth: Number(depth),
          fdr_q: Number(fdrQ),
          min_slice_size: Number(minSliceSize),
        }),
      }),
    overlapLedger: () => apiFetch('/api/triage/overlap-ledger'),
    findingTransactions: (findingId) =>
      apiFetch(`/api/triage/findings/${findingId}/transactions`),
  },

  // ── Interaction & PVMC Bridge ───────────────────────────────────────────
  interactions: {
    evaluate: (dimA, dimB, minSupportTx = 5, minSupportAccts = 3, fdrQ = 0.05, mode = 'statistical') =>
      apiFetch('/api/interactions/evaluate', {
        method: 'POST',
        body: JSON.stringify({
          dim_a: dimA,
          dim_b: dimB,
          min_support_tx: Number(minSupportTx),
          min_support_accts: Number(minSupportAccts),
          fdr_q: Number(fdrQ),
          mode,
        }),
      }),
  },

  pvmc: {
    bridge: ({ t0Filter = null, t1Filter = null, productCol = null, qtyCol = null, uomCol = null } = {}) =>
      apiFetch('/api/pvmc/bridge', {
        method: 'POST',
        body: JSON.stringify({
          t0_filter: t0Filter,
          t1_filter: t1Filter,
          product_col: productCol,
          qty_col: qtyCol,
          uom_col: uomCol,
        }),
      }),
  },

  // ── Lifecycle & Export ──────────────────────────────────────────────────
  lifecycle: {
    transition: ({ findingFingerprint, newState, dispositionCode = null, dismissalCategory = null, snoozeDate = null, assignedOwner = null, notes = null, user = 'auditor' }) =>
      apiFetch('/api/lifecycle/transition', {
        method: 'POST',
        body: JSON.stringify({
          finding_fingerprint: findingFingerprint,
          new_state: newState,
          disposition_code: dispositionCode,
          dismissal_category: dismissalCategory,
          snooze_date: snoozeDate,
          assigned_owner: assignedOwner,
          notes,
          user,
        }),
      }),
    history: (findingFingerprint) =>
      apiFetch(`/api/lifecycle/history/${findingFingerprint}`),
    diff: (historicalWorkspacePath) =>
      apiFetch('/api/lifecycle/diff', {
        method: 'POST',
        body: JSON.stringify({ historical_workspace_path: historicalWorkspacePath }),
      }),
  },

  export: {
    executiveSummary: (outPath = 'export_executive_summary.html', format = 'html') =>
      apiFetch('/api/export/executive-summary', {
        method: 'POST',
        body: JSON.stringify({ out_path: outPath, format }),
      }),
    actionableFindings: (outPath = 'export_actionable_findings.csv') =>
      apiFetch('/api/export/actionable-findings', {
        method: 'POST',
        body: JSON.stringify({ out_path: outPath }),
      }),
    restrictedDealLedger: (password, outPath = 'export_restricted_deals.zip', userAcknowledged = true) =>
      apiFetch('/api/export/restricted-deal-ledger', {
        method: 'POST',
        body: JSON.stringify({
          out_path: outPath,
          password,
          user_acknowledged: Boolean(userAcknowledged),
        }),
      }),
  },
};

export default api;
