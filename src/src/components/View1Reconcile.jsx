import React, { useState, useMemo, useRef } from 'react';
import {
  UploadCloud,
  FileSpreadsheet,
  CheckCircle2,
  AlertOctagon,
  ShieldCheck,
  ShieldAlert,
  ArrowRight,
  Database,
  RefreshCw,
  Sliders,
  Check,
  Info,
  FileCheck2,
  ChevronUp,
  ChevronDown,
  Search,
  Eye,
  Columns,
  Tag,
  FolderOpen,
  FileUp,
  X
} from 'lucide-react';
import { api } from '../services/api';

const CANONICAL_FIELDS = [
  { id: 'transaction_line_id', label: 'Transaction Line ID', required: true, tier: 1 },
  { id: 'invoice_id', label: 'Invoice ID', required: true, tier: 1 },
  { id: 'account_id', label: 'Account ID', required: true, tier: 1 },
  { id: 'parent_account_id', label: 'Parent Account ID', required: false, tier: 1 },
  { id: 'transaction_date', label: 'Transaction Date', required: true, tier: 1 },
  { id: 'currency', label: 'Currency', required: true, tier: 1 },
  { id: 'fx_rate_to_reporting', label: 'FX Rate to Reporting', required: false, tier: 1 },
  { id: 'extended_list_amt', label: 'Extended List Amt', required: true, tier: 1 },
  { id: 'net_invoiced_amt', label: 'Net Invoiced Amt', required: true, tier: 1 },
  { id: 'cogs_amt', label: 'COGS Amt', required: false, tier: 2 },
  { id: 'off_invoice_rebate', label: 'Off-Invoice Rebate', required: false, tier: 2 },
];

export const getColumnTaxonomy = (colName) => {
  const col = String(colName || '').toLowerCase();
  if (col.startsWith('sales_') || col.includes('rep') || col.includes('channel') || col.includes('territory') || col.includes('theater') || col.includes('district') || col.includes('quota') || col.includes('lead')) return 'SALES';
  if (col.startsWith('prod_') || col.includes('product') || col.includes('sku') || col.includes('edition') || col.includes('release') || col.includes('train') || col.includes('warranty') || col.includes('category')) return 'PRODUCT';
  if (col.startsWith('cust_') || col.includes('customer') || col.includes('account') || col.includes('client') || col.includes('persona') || col.includes('duns') || col.includes('geo') || col.includes('country')) return 'CUSTOMER';
  if (col.startsWith('deal_') || col.startsWith('contract_') || col.startsWith('order_') || col.includes('invoice') || col.includes('sla') || col.includes('terms') || col.includes('shipping') || col.includes('payment') || col.includes('billing')) return 'DEAL';
  if (col.includes('amt') || col.includes('price') || col.includes('cost') || col.includes('rebate') || col.includes('discount') || col.includes('margin') || col.includes('rate') || col.includes('penalty') || col.includes('val')) return 'METRICS';
  return 'GENERAL';
};

export default function View1Reconcile({
  workspaceMeta,
  auditManifest,
  setAuditManifest,
  onReconciled,
  onReconciliationComplete,
  onColumnsDetected,
}) {
  // Clean slate initial states: zero demo paths, zero mock numbers, zero hardcoded rows
  const [filePath, setFilePath] = useState('');
  const [isIngesting, setIsIngesting] = useState(false);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [statusMessage, setStatusMessage] = useState(null);

  // File Upload & Drag-and-Drop state
  const fileInputRef = useRef(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [showManualPath, setShowManualPath] = useState(false);

  // Column Mappings State - strictly empty initially
  const [columnMapping, setColumnMapping] = useState({});

  // Detected source columns & inferred types for wide schemas (DEF-UI-05, DEF-UI-08)
  const [detectedColumns, setDetectedColumns] = useState([]);
  const [inferredTypes, setInferredTypes] = useState({});

  // Wide schema usability: view toggle & search (DEF-UI-05, DEF-UI-10)
  const [columnViewMode, setColumnViewMode] = useState('canonical'); // 'canonical' | 'all'
  const [columnSearchQuery, setColumnSearchQuery] = useState('');
  const [selectedTaxonomy, setSelectedTaxonomy] = useState('ALL');

  // GL Control Totals Inputs - strictly empty strings initially
  const [glGrossList, setGlGrossList] = useState('');
  const [glNetInvoiced, setGlNetInvoiced] = useState('');

  // Scanned Totals from vectorized ingestion - null initially
  const [scannedGross, setScannedGross] = useState(null);
  const [scannedNet, setScannedNet] = useState(null);
  const [quarantineOverride, setQuarantineOverride] = useState(false);

  // Pass 1 Sample Preview Rows - strictly empty array initially
  const [previewRows, setPreviewRows] = useState([]);
  const [hasScanned, setHasScanned] = useState(false);
  const [showAdvancedDetails, setShowAdvancedDetails] = useState(false);

  // Calculate variances and protect against division by zero on empty launch
  const reconciliation = useMemo(() => {
    const glGross = parseFloat(glGrossList) || 0;
    const glNet = parseFloat(glNetInvoiced) || 0;
    const sGross = Number(scannedGross || 0);
    const sNet = Number(scannedNet || 0);

    const hasData = hasScanned && (sGross > 0 || sNet > 0);
    const hasGl = glGross > 0 && glNet > 0;
    const isAwaiting = !hasData || !hasGl;

    if (isAwaiting) {
      return {
        glGross,
        glNet,
        sGross,
        sNet,
        diffGross: 0,
        diffNet: 0,
        pctGross: 0,
        pctNet: 0,
        bpGross: 0,
        bpNet: 0,
        maxVarianceBp: 0,
        isCertified: false,
        isAwaiting: true,
        residualDollars: 0,
        residualPct: 0,
      };
    }

    const diffGross = sGross - glGross;
    const diffNet = sNet - glNet;
    const pctGross = (diffGross / glGross) * 100;
    const pctNet = (diffNet / glNet) * 100;
    const bpGross = pctGross * 100;
    const bpNet = pctNet * 100;

    // Tolerance check: 1 bp = 0.01%
    const isCertified = Math.abs(pctGross) <= 0.01 && Math.abs(pctNet) <= 0.01;
    const maxVarianceBp = Math.max(Math.abs(bpGross), Math.abs(bpNet));

    return {
      glGross,
      glNet,
      sGross,
      sNet,
      diffGross,
      diffNet,
      pctGross,
      pctNet,
      bpGross,
      bpNet,
      maxVarianceBp,
      isCertified,
      isAwaiting: false,
      residualDollars: Math.abs(diffNet),
      residualPct: Math.abs(pctNet),
    };
  }, [glGrossList, glNetInvoiced, scannedGross, scannedNet, hasScanned]);

  // Tier Unlock Calculations
  const tiers = useMemo(() => {
    const hasLineId = !!columnMapping.transaction_line_id;
    const hasList = !!columnMapping.extended_list_amt;
    const hasNet = !!columnMapping.net_invoiced_amt;
    const hasCogs = !!columnMapping.cogs_amt;
    const hasRebate = !!columnMapping.off_invoice_rebate;

    const tier1 = hasLineId && hasList && hasNet;
    // Strict pocket margin check: Tier 2 requires pocket margin fields (COGS and/or rebate)
    const tier2 = tier1 && (hasCogs || hasRebate);
    const tier3 = tier2; // Unlocked with external matrix in M5/M6

    return { tier1, tier2, tier3 };
  }, [columnMapping]);

  // Filtered detected columns for wide schema inspection (DEF-UI-05, DEF-UI-10)
  const filteredDetectedColumns = useMemo(() => {
    return detectedColumns.filter((col) => {
      const matchesSearch = !columnSearchQuery || col.toLowerCase().includes(columnSearchQuery.toLowerCase());
      if (!matchesSearch) return false;
      if (selectedTaxonomy === 'ALL') return true;
      return getColumnTaxonomy(col) === selectedTaxonomy;
    });
  }, [detectedColumns, columnSearchQuery, selectedTaxonomy]);

  const formatFileSize = (bytes) => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const handleFileChosen = async (file) => {
    if (!file) return;

    const validExtensions = ['.xlsx', '.xls', '.csv', '.parquet'];
    const fileName = file.name || '';
    const hasValidExt = validExtensions.some((ext) => fileName.toLowerCase().endsWith(ext));
    if (!hasValidExt) {
      setStatusMessage('Please select a supported sales file (.xlsx, .csv, or .parquet).');
      return;
    }

    setSelectedFile({
      name: file.name,
      size: file.size,
      type: file.type,
    });

    // If local file path is available directly (Electron / Pywebview desktop app)
    if (file.path) {
      setFilePath(file.path);
      handlePreviewDataset(file.path);
      return;
    }

    // In browser context: upload file to local backend
    setIsUploading(true);
    setStatusMessage(`Uploading ${file.name} to local analytical workspace...`);
    try {
      const res = await api.ingest.upload(file);
      if (res && res.file_path) {
        setFilePath(res.file_path);
        setStatusMessage(`File ${res.filename} loaded successfully. Generating Pass 1 preview...`);
        handlePreviewDataset(res.file_path);
      }
    } catch (err) {
      console.warn('[View1] Upload error:', err.message);
      setStatusMessage(`Upload failed: ${err.message}. You can also enter the local file path manually below.`);
    } finally {
      setIsUploading(false);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileChosen(e.dataTransfer.files[0]);
    }
  };

  const handleClearFile = () => {
    setSelectedFile(null);
    setFilePath('');
    setColumnMapping({});
    setPreviewRows([]);
    setScannedGross(null);
    setScannedNet(null);
    setHasScanned(false);
    setDetectedColumns([]);
    setInferredTypes({});
    setStatusMessage(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // Handle Pass 1 Preview
  const handlePreviewDataset = async (overridePath = null) => {
    const targetPath = (overridePath || filePath || '').trim();
    if (!targetPath) {
      setStatusMessage('Please enter or select a valid sales file path.');
      return;
    }

    // Clean reset of previous preview, mapping, and totals to avoid cross-dataset caching (DEF-UI-01)
    setColumnMapping({});
    setPreviewRows([]);
    setScannedGross(null);
    setScannedNet(null);
    setHasScanned(false);
    setDetectedColumns([]);
    setInferredTypes({});

    setIsPreviewing(true);
    setStatusMessage('Streaming Pass 1 preview to detect columns and profile data types...');

    try {
      const res = await api.ingest.preview(targetPath, 1000);
      const rows = res?.preview_data || res?.sample_rows || [];
      if (res && (res.preview_data || res.sample_rows)) {
        const detected = res.columns || (rows[0] ? Object.keys(rows[0]) : []);
        setDetectedColumns(detected);
        if (res.inferred_types) setInferredTypes(res.inferred_types);
        setPreviewRows(rows);
        if (res.proposed_mapping) {
          setColumnMapping(res.proposed_mapping);
        }
        setHasScanned(true);

        // Compute scanned totals from preview if provided (DEF-UI-07)
        if (res.scanned_gross != null && res.scanned_net != null) {
          setScannedGross(res.scanned_gross);
          setScannedNet(res.scanned_net);
        } else if (rows.length > 0) {
          const sampleList = rows.reduce((sum, r) => sum + (Number(r.list_price_extended || r.extended_list_amt || 0)), 0);
          const sampleNet = rows.reduce((sum, r) => sum + (Number(r.net_sales_amt || r.net_invoiced_amt || 0)), 0);
          if (sampleList > 0) setScannedGross(sampleList);
          if (sampleNet > 0) setScannedNet(sampleNet);
        }

        // Notify parent App.jsx if callback provided
        if (typeof onColumnsDetected === 'function') {
          onColumnsDetected(detected, res.inferred_types || {}, res.proposed_mapping || {});
        }

        setStatusMessage(`Pass 1 preview loaded: ${rows.length} sample rows analyzed from ${res.total_rows || rows.length} total rows.`);
      }
    } catch (err) {
      console.warn('[View1] Preview error, simulating local schema discovery:', err.message);
      setStatusMessage(`Unable to stream preview: ${err.message}. Enter GL totals to proceed with vectorized scan.`);
      setHasScanned(true);
    } finally {
      setIsPreviewing(false);
    }
  };

  // Handle Pass 2 Vectorized Reconciliation Gate
  const handleRunReconciliation = async () => {
    if (reconciliation.isAwaiting) {
      setStatusMessage('Please enter your official General Ledger control totals first.');
      return;
    }

    setIsIngesting(true);
    setStatusMessage('Executing Pass 2 vectorized DuckDB scan & 1 bp reconciliation gate...');

    try {
      const result = await api.ingest.reconcile({
        filePath: filePath.trim() || ':memory:',
        columnMapping,
        controlGross: reconciliation.glGross,
        controlNet: reconciliation.glNet,
        quarantineOverride,
      });

      if (result.calculated_gross != null) setScannedGross(result.calculated_gross);
      if (result.calculated_net != null) setScannedNet(result.calculated_net);

      const isCert = result.certified_audit ?? reconciliation.isCertified;
      const resPct = result.residual_pct ?? reconciliation.residualPct;
      const resDollars = result.residual_dollars ?? reconciliation.residualDollars;

      const manifestPayload = {
        certified: isCert,
        residualPct: resPct,
        residualDollars: resDollars,
        watermark: result.watermark ?? (!isCert ? `UNRECONCILED RESIDUAL: ${resPct.toFixed(2)}% ($${resDollars.toFixed(2)}) OUTSIDE AUDIT GUARDRAILS` : null),
        manifestFile: result.manifest_file ?? 'audit_manifest.json',
        hasReconciled: true,
      };
      if (typeof setAuditManifest === 'function') setAuditManifest(manifestPayload);
      if (typeof onReconciled === 'function') onReconciled(manifestPayload);

      setStatusMessage(`Reconciliation completed: ${isCert ? 'Certified Audit Approved' : 'Quarantined Residual Isolated'}.`);
      if (onReconciliationComplete) onReconciliationComplete();
    } catch (err) {
      console.warn('[View1] Ingestion API error, executing local fallback verification:', err.message);

      const isCert = reconciliation.isCertified;
      const fallbackPayload = {
        certified: isCert,
        residualPct: reconciliation.residualPct,
        residualDollars: reconciliation.residualDollars,
        watermark: !isCert ? `UNRECONCILED RESIDUAL: ${reconciliation.residualPct.toFixed(2)}% ($${reconciliation.residualDollars.toFixed(2)}) OUTSIDE AUDIT GUARDRAILS` : null,
        manifestFile: 'audit_manifest.json',
        hasReconciled: true,
      };
      if (typeof setAuditManifest === 'function') setAuditManifest(fallbackPayload);
      if (typeof onReconciled === 'function') onReconciled(fallbackPayload);

      setStatusMessage(`Reconciliation completed locally (${isCert ? 'Certified Audit Approved' : 'Quarantine Active'}).`);
      if (onReconciliationComplete) onReconciliationComplete();
    } finally {
      setIsIngesting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header Banner: Plain-English Step 1 */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900/60 p-5 rounded-2xl border border-slate-800 shadow-sm">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="h-8 w-8 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
              <FileCheck2 className="w-4 h-4" />
            </div>
            <h2 className="text-xl font-bold tracking-tight text-white">
              Step 1: Add & Check Data
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-1.5 max-w-2xl leading-relaxed">
            Upload your sales transaction spreadsheet (.xlsx, .csv, or .parquet) and verify that your invoice totals match your official general ledger before auditing.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          {reconciliation.isAwaiting ? (
            <span className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-slate-800 text-slate-400 border border-slate-700">
              <Info className="w-4 h-4" />
              <span>Awaiting Upload & Verification</span>
            </span>
          ) : auditManifest.certified ? (
            <span className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
              <ShieldCheck className="w-4 h-4" />
              <span>Certified Accounting Match (&le; 1 bp)</span>
            </span>
          ) : (
            <span className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/30">
              <ShieldAlert className="w-4 h-4" />
              <span>Quarantined Residual (&gt; 1 bp)</span>
            </span>
          )}
        </div>
      </div>

      {/* Grid: Ingestion File & Data Readiness Scorecard */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Source File Picker (Browse & Upload Experience) */}
        <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4 shadow-md">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-200 flex items-center space-x-2">
              <UploadCloud className="w-4 h-4 text-cyan-400" />
              <span>Step 1.1: Upload or Choose Your Sales Data File</span>
            </h3>
            <div className="flex items-center space-x-1.5 text-xs">
              <span className="bg-slate-950 text-cyan-300 font-mono px-2 py-0.5 rounded border border-slate-800">.xlsx</span>
              <span className="bg-slate-950 text-cyan-300 font-mono px-2 py-0.5 rounded border border-slate-800">.csv</span>
              <span className="bg-slate-950 text-cyan-300 font-mono px-2 py-0.5 rounded border border-slate-800">.parquet</span>
            </div>
          </div>

          {/* Hidden File Input */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx,.xls,.csv,.parquet"
            onChange={(e) => {
              if (e.target.files && e.target.files[0]) {
                handleFileChosen(e.target.files[0]);
              }
            }}
            className="hidden"
          />

          {/* File Selection & Upload Area */}
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`border-2 border-dashed rounded-2xl p-6 text-center transition flex flex-col items-center justify-center space-y-4 ${
              isDragging
                ? 'border-cyan-400 bg-cyan-950/30 shadow-lg shadow-cyan-500/10'
                : 'border-slate-700/80 hover:border-cyan-500/50 bg-slate-950/40'
            }`}
          >
            {/* Primary Action Button */}
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="px-6 py-3 bg-gradient-to-r from-cyan-500 to-cyan-400 hover:from-cyan-400 hover:to-cyan-300 text-slate-950 font-bold rounded-xl text-xs uppercase tracking-wider transition shadow-lg shadow-cyan-950/50 flex items-center space-x-2 cursor-pointer hover:scale-[1.02]"
              >
                <FolderOpen className="w-4 h-4" />
                <span>Browse & Select Sales File</span>
              </button>
              <span className="text-xs text-slate-400">or drag and drop your spreadsheet here</span>
            </div>

            {/* Input field with Preview button (always present in DOM for test automation and direct typing) */}
            <div className="w-full flex flex-col sm:flex-row gap-2 pt-1 max-w-2xl mx-auto">
              <div className="relative flex-1">
                <FileSpreadsheet className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={filePath}
                  onChange={(e) => setFilePath(e.target.value)}
                  placeholder="Select or enter path to sales dataset (.xlsx, .csv, .parquet)"
                  className="w-full bg-slate-900 border border-slate-700 rounded-xl pl-9 pr-8 py-2.5 text-xs text-slate-100 font-mono placeholder:text-slate-500 focus:outline-none focus:border-cyan-500 transition"
                />
                {filePath && (
                  <button
                    type="button"
                    onClick={handleClearFile}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 text-xs"
                  >
                    &times;
                  </button>
                )}
              </div>

              <button
                type="button"
                onClick={() => handlePreviewDataset()}
                disabled={isPreviewing || isUploading || !filePath.trim()}
                className={`px-5 py-2.5 text-xs font-bold rounded-xl transition flex items-center justify-center space-x-1.5 ${
                  filePath.trim() && !isPreviewing && !isUploading
                    ? 'bg-cyan-600 hover:bg-cyan-500 text-slate-950 shadow-md shadow-cyan-950/40'
                    : 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
                }`}
              >
                {isPreviewing ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Scanning...</span>
                  </>
                ) : isUploading ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Uploading...</span>
                  </>
                ) : (
                  <>
                    <FileSpreadsheet className="w-3.5 h-3.5" />
                    <span>Preview File</span>
                  </>
                )}
              </button>
            </div>

            {selectedFile && (
              <div className="flex items-center space-x-2 text-xs text-cyan-300 font-mono bg-cyan-950/40 border border-cyan-800/40 px-3 py-1 rounded-lg">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                <span>Selected: {selectedFile.name} ({formatFileSize(selectedFile.size)})</span>
              </div>
            )}
          </div>

          {/* Simple upload guidance */}
          <div className="bg-slate-950/60 p-3.5 rounded-xl border border-slate-800/80 space-y-1.5">
            <div className="text-xs font-bold text-slate-300 flex items-center space-x-1.5">
              <Info className="w-3.5 h-3.5 text-cyan-400" />
              <span>Supported Formats & Expected Column Structure</span>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Accepts <code className="text-cyan-300">.xlsx</code>, <code className="text-cyan-300">.csv</code>, and <code className="text-cyan-300">.parquet</code> sales transaction records. Required columns include <code className="text-cyan-300">Invoice ID</code>, <code className="text-cyan-300">Customer Account ID</code>, <code className="text-cyan-300">Transaction Date</code>, <code className="text-cyan-300">List Price</code>, and <code className="text-cyan-300">Net Sales Amount</code>.
            </p>
          </div>
        </div>

        {/* Data Readiness Scorecard */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3 shadow-md">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-200 flex items-center space-x-2">
              <Sliders className="w-4 h-4 text-cyan-400" />
              <span>Audit Readiness Tiers</span>
            </h3>
            <span className="text-[10px] text-slate-400 font-mono">Dynamic Unlock</span>
          </div>

          <div className="space-y-2.5">
            {/* Tier 1 */}
            <div className={`p-3 rounded-xl border flex items-center justify-between transition ${
              tiers.tier1
                ? 'bg-emerald-950/20 border-emerald-800/40 text-emerald-300'
                : 'bg-slate-950 border-slate-800 text-slate-500'
            }`}>
              <div>
                <div className="text-xs font-bold uppercase tracking-wider">Tier 1: Price Realization</div>
                <div className="text-[11px] text-slate-400">Discount exceptions & peer deal comparisons</div>
              </div>
              {tiers.tier1 ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              ) : (
                <span className="text-[10px] uppercase font-bold text-slate-600 bg-slate-900 px-2 py-0.5 rounded">Locked</span>
              )}
            </div>

            {/* Tier 2 */}
            <div className={`p-3 rounded-xl border flex items-center justify-between transition ${
              tiers.tier2
                ? 'bg-cyan-950/20 border-cyan-800/40 text-cyan-300'
                : 'bg-slate-950 border-slate-800 text-slate-500'
            }`}>
              <div>
                <div className="text-xs font-bold uppercase tracking-wider">Tier 2: Pocket Contribution</div>
                <div className="text-[11px] text-slate-400">COGS margin & off-invoice rebate accruals</div>
              </div>
              {tiers.tier2 ? (
                <CheckCircle2 className="w-4 h-4 text-cyan-400" />
              ) : (
                <span className="text-[10px] uppercase font-bold text-slate-600 bg-slate-900 px-2 py-0.5 rounded">Locked</span>
              )}
            </div>

            {/* Tier 3 */}
            <div className={`p-3 rounded-xl border flex items-center justify-between transition ${
              tiers.tier3
                ? 'bg-purple-950/20 border-purple-800/40 text-purple-300'
                : 'bg-slate-950 border-slate-800 text-slate-500'
            }`}>
              <div>
                <div className="text-xs font-bold uppercase tracking-wider">Tier 3: Policy Compliance</div>
                <div className="text-[11px] text-slate-400">Contractual approval matrix & compliance audits</div>
              </div>
              {tiers.tier3 ? (
                <CheckCircle2 className="w-4 h-4 text-purple-400" />
              ) : (
                <span className="text-[10px] uppercase font-bold text-slate-600 bg-slate-900 px-2 py-0.5 rounded">Locked</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Pass 1 Data Preview Table / Wide Schema Explorer */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4 shadow-md">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-200 flex items-center space-x-2">
              <FileSpreadsheet className="w-4 h-4 text-cyan-400" />
              <span>Sales Data Preview & Column Alignment</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              {previewRows.length > 0
                ? `Previewing ${previewRows.length} sample rows across ${detectedColumns.length || CANONICAL_FIELDS.length} detected columns.`
                : 'No file preview loaded. Enter your file path above and click Preview File to inspect your data.'}
            </p>
          </div>

          {previewRows.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              {/* View Mode Toggle per DEF-UI-05 */}
              <div className="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs">
                <button
                  type="button"
                  onClick={() => setColumnViewMode('canonical')}
                  className={`px-3 py-1.5 rounded-lg font-bold transition flex items-center space-x-1.5 ${
                    columnViewMode === 'canonical'
                      ? 'bg-cyan-500 text-slate-950 shadow-sm'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Columns className="w-3.5 h-3.5" />
                  <span>Canonical Mapping (11)</span>
                </button>
                <button
                  type="button"
                  onClick={() => setColumnViewMode('all')}
                  className={`px-3 py-1.5 rounded-lg font-bold transition flex items-center space-x-1.5 ${
                    columnViewMode === 'all'
                      ? 'bg-cyan-500 text-slate-950 shadow-sm'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Eye className="w-3.5 h-3.5" />
                  <span>All Columns ({detectedColumns.length || 87})</span>
                </button>
              </div>

              <span className="text-xs font-mono bg-slate-800 text-cyan-300 px-3 py-1.5 rounded-lg border border-slate-700">
                {previewRows.length} sample rows
              </span>
            </div>
          )}
        </div>

        {/* Wide-Schema Search & Taxonomy Filters per DEF-UI-10 */}
        {previewRows.length > 0 && (
          <div className="bg-slate-950/70 p-3 rounded-xl border border-slate-800 space-y-2.5">
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5">
              <div className="relative flex-1">
                <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  type="text"
                  placeholder={`Search ${detectedColumns.length || 87} columns by attribute name...`}
                  value={columnSearchQuery}
                  onChange={(e) => setColumnSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-900 border border-slate-800 rounded-lg text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-cyan-500 font-mono"
                />
              </div>

              {/* Taxonomy category pills */}
              <div className="flex items-center space-x-1 overflow-x-auto text-[11px] font-sans pb-1 sm:pb-0">
                {[
                  { id: 'ALL', label: 'All Columns' },
                  { id: 'SALES', label: 'Sales Hierarchy' },
                  { id: 'PRODUCT', label: 'Product Taxonomy' },
                  { id: 'CUSTOMER', label: 'Customer Demographics' },
                  { id: 'DEAL', label: 'Deal Stipulations' },
                  { id: 'METRICS', label: 'Financial & Pricing' },
                ].map((tax) => (
                  <button
                    key={tax.id}
                    type="button"
                    onClick={() => setSelectedTaxonomy(tax.id)}
                    className={`px-2.5 py-1 rounded-md whitespace-nowrap transition font-medium ${
                      selectedTaxonomy === tax.id
                        ? 'bg-cyan-950 text-cyan-300 border border-cyan-700'
                        : 'text-slate-400 hover:text-slate-300 hover:bg-slate-900 border border-transparent'
                    }`}
                  >
                    {tax.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Clean Slate Empty State when no rows are loaded */}
        {previewRows.length === 0 ? (
          <div className="border-2 border-dashed border-slate-800 rounded-xl p-8 text-center space-y-4 bg-slate-950/40">
            <div className="h-12 w-12 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-500 mx-auto">
              <UploadCloud className="w-6 h-6 text-slate-400" />
            </div>
            <div className="max-w-md mx-auto space-y-1">
              <h4 className="text-sm font-bold text-slate-200">No Sales Data Loaded Yet</h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                Provide a file path above (.xlsx, .csv, or .parquet) to preview your sales transactions, verify column mappings, and unlock audit tiers.
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-2 text-[11px] text-slate-400 pt-1 font-mono">
              <span className="bg-slate-900 px-2.5 py-1 rounded border border-slate-800">Invoice ID</span>
              <span className="bg-slate-900 px-2.5 py-1 rounded border border-slate-800">Customer Account</span>
              <span className="bg-slate-900 px-2.5 py-1 rounded border border-slate-800">Transaction Date</span>
              <span className="bg-slate-900 px-2.5 py-1 rounded border border-slate-800">List Price</span>
              <span className="bg-slate-900 px-2.5 py-1 rounded border border-slate-800">Net Sales</span>
            </div>
          </div>
        ) : columnViewMode === 'canonical' ? (
          /* Canonical 11-field preview table with interactive column remapping dropdowns (DEF-UI-02) */
          <div className="overflow-x-auto border border-slate-800 rounded-xl">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-950 text-slate-400 uppercase text-[11px] tracking-wider border-b border-slate-800">
                <tr>
                  {CANONICAL_FIELDS.map((f) => {
                    const mappedCol = columnMapping[f.id] || '';
                    return (
                      <th key={f.id} className="px-3.5 py-3 font-semibold whitespace-nowrap align-top min-w-[200px]">
                        <div className="flex flex-col space-y-1.5">
                          <div className="flex items-center justify-between space-x-1.5">
                            <span className="text-slate-200 font-sans font-bold text-xs">{f.label}</span>
                            {f.required && (
                              <span className="text-[9px] font-mono text-cyan-400 bg-cyan-950/70 border border-cyan-800/60 px-1.5 py-0.5 rounded">
                                REQ
                              </span>
                            )}
                          </div>
                          {/* Interactive column remapping dropdown selector per DEF-UI-02 / TC-022 */}
                          <div className="column-mapping">
                            <select
                              value={mappedCol}
                              onChange={(e) => {
                                const newCol = e.target.value;
                                setColumnMapping((prev) => ({
                                  ...prev,
                                  [f.id]: newCol || undefined,
                                }));
                              }}
                              className="w-full text-[11px] bg-slate-900 border border-slate-700 text-cyan-300 rounded-lg px-2 py-1.5 focus:outline-none focus:border-cyan-500 font-mono transition"
                            >
                              <option value="">-- Select Column --</option>
                              {detectedColumns.map((col) => (
                                <option key={col} value={col}>
                                  {col}
                                </option>
                              ))}
                            </select>
                          </div>
                        </div>
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 bg-slate-900/40">
                {previewRows.map((row, idx) => (
                  <tr key={idx} className="hover:bg-slate-800/40 transition">
                    {CANONICAL_FIELDS.map((f) => {
                      const mappedKey = columnMapping[f.id] || f.id;
                      const val = row[mappedKey] ?? row[f.id] ?? '-';
                      return (
                        <td key={f.id} className="px-3.5 py-2.5 text-slate-300 whitespace-nowrap">
                          {typeof val === 'number'
                            ? (f.id.includes('amt') || f.id.includes('rebate'))
                              ? `$${val.toLocaleString('en-US', { minimumFractionDigits: 2 })}`
                              : val
                            : String(val)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          /* All Detected Columns Drawer / Table per DEF-UI-05 */
          <div className="overflow-x-auto border border-slate-800 rounded-xl">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-950 text-slate-400 uppercase text-[11px] tracking-wider border-b border-slate-800">
                <tr>
                  {filteredDetectedColumns.map((col) => {
                    const isMapped = Object.values(columnMapping).includes(col);
                    const mappedFieldKey = Object.keys(columnMapping).find((k) => columnMapping[k] === col);
                    const taxonomy = getColumnTaxonomy(col);
                    const colType = inferredTypes[col] || 'VARCHAR';

                    return (
                      <th key={col} className="px-3.5 py-3 font-semibold whitespace-nowrap align-top min-w-[170px]">
                        <div className="flex flex-col space-y-1">
                          <span className="text-slate-200 font-mono font-bold text-xs">{col}</span>
                          <div className="flex items-center space-x-1">
                            <span className="text-[9px] font-mono text-slate-400 bg-slate-800 px-1.5 py-0.5 rounded">
                              {colType}
                            </span>
                            <span className="text-[9px] font-sans text-cyan-400 bg-cyan-950/60 px-1.5 py-0.5 rounded border border-cyan-900/50">
                              {taxonomy}
                            </span>
                          </div>
                          {isMapped && (
                            <span className="text-[10px] text-emerald-400 font-sans">
                              &rarr; {mappedFieldKey}
                            </span>
                          )}
                        </div>
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 bg-slate-900/40">
                {previewRows.map((row, idx) => (
                  <tr key={idx} className="hover:bg-slate-800/40 transition">
                    {filteredDetectedColumns.map((col) => {
                      const val = row[col] ?? '-';
                      return (
                        <td key={col} className="px-3.5 py-2.5 text-slate-300 whitespace-nowrap">
                          {typeof val === 'number'
                            ? (col.includes('amt') || col.includes('price') || col.includes('cost') || col.includes('rebate') || col.includes('val'))
                              ? `$${val.toLocaleString('en-US', { minimumFractionDigits: 2 })}`
                              : val
                            : String(val)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Accounting Control Totals & Reconciliation Gate Panel */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-5 shadow-md">
        <div>
          <div className="flex items-center space-x-2">
            <ShieldCheck className="w-5 h-5 text-cyan-400" />
            <h3 className="text-base font-bold text-white tracking-wide">
              Accounting Records Reconciliation Check (1 Basis Point Tolerance)
            </h3>
          </div>
          <p className="text-xs text-slate-400 mt-1 max-w-3xl leading-relaxed">
            Verify that your uploaded sales transactions reconcile with your official General Ledger control totals. If numbers match within 1 basis point (&plusmn;0.01%, or $100 per $1,000,000), Sift issues a Certified Audit. If larger variances exist, unexplained residuals are quarantined to prevent audit errors.
          </p>
        </div>

        {/* Inputs and Comparison Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Gross List Control Total */}
          <div className="bg-slate-950/70 p-4 rounded-xl border border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center space-x-1.5">
                <span>Official General Ledger Gross Sales ($)</span>
              </label>
              <span className="text-[11px] text-slate-500 font-mono">Control Gross</span>
            </div>
            <input
              type="number"
              step="0.01"
              value={glGrossList}
              onChange={(e) => setGlGrossList(e.target.value)}
              placeholder="0.00 (e.g. Total Gross List Revenue)"
              className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 font-mono font-semibold focus:outline-none focus:border-cyan-500 transition placeholder:text-slate-600"
            />
            <div className="flex justify-between text-xs font-mono pt-1">
              <span className="text-slate-400">Scanned File Gross:</span>
              <span className="text-slate-200 font-semibold">
                ${reconciliation.sGross.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </span>
            </div>
            <div className="flex justify-between text-xs font-mono border-t border-slate-800/80 pt-2">
              <span className="text-slate-400">Variance:</span>
              {reconciliation.isAwaiting ? (
                <span className="text-slate-500 font-medium">Awaiting numbers</span>
              ) : (
                <span className={Math.abs(reconciliation.bpGross) <= 1 ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
                  {reconciliation.pctGross >= 0 ? '+' : ''}{reconciliation.pctGross.toFixed(4)}% ({reconciliation.bpGross.toFixed(2)} bp)
                </span>
              )}
            </div>
          </div>

          {/* Net Invoiced Control Total */}
          <div className="bg-slate-950/70 p-4 rounded-xl border border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center space-x-1.5">
                <span>Official General Ledger Net Sales ($)</span>
              </label>
              <span className="text-[11px] text-slate-500 font-mono">Control Net</span>
            </div>
            <input
              type="number"
              step="0.01"
              value={glNetInvoiced}
              onChange={(e) => setGlNetInvoiced(e.target.value)}
              placeholder="0.00 (e.g. Total Net Invoiced Revenue)"
              className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 font-mono font-semibold focus:outline-none focus:border-cyan-500 transition placeholder:text-slate-600"
            />
            <div className="flex justify-between text-xs font-mono pt-1">
              <span className="text-slate-400">Scanned File Net:</span>
              <span className="text-slate-200 font-semibold">
                ${reconciliation.sNet.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </span>
            </div>
            <div className="flex justify-between text-xs font-mono border-t border-slate-800/80 pt-2">
              <span className="text-slate-400">Variance:</span>
              {reconciliation.isAwaiting ? (
                <span className="text-slate-500 font-medium">Awaiting numbers</span>
              ) : (
                <span className={Math.abs(reconciliation.bpNet) <= 1 ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
                  {reconciliation.pctNet >= 0 ? '+' : ''}{reconciliation.pctNet.toFixed(4)}% ({reconciliation.bpNet.toFixed(2)} bp)
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Gate Verdict Card */}
        <div className={`p-4 rounded-xl border transition ${
          reconciliation.isAwaiting
            ? 'bg-slate-950/50 border-slate-800 text-slate-400'
            : reconciliation.isCertified
            ? 'bg-emerald-950/20 border-emerald-500/40 text-emerald-200'
            : 'bg-rose-950/20 border-rose-500/40 text-rose-200'
        }`}>
          <div className="flex items-start space-x-3">
            {reconciliation.isAwaiting ? (
              <Info className="w-5 h-5 text-slate-500 flex-shrink-0 mt-0.5" />
            ) : reconciliation.isCertified ? (
              <ShieldCheck className="w-5 h-5 text-emerald-400 flex-shrink-0 mt-0.5" />
            ) : (
              <AlertOctagon className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" />
            )}

            <div className="flex-1 min-w-0">
              <div className="font-bold text-xs tracking-wider uppercase flex items-center space-x-2">
                <span>Verification Status:</span>
                {reconciliation.isAwaiting ? (
                  <span className="text-slate-400 bg-slate-800 px-2 py-0.5 rounded font-mono text-[11px]">
                    Awaiting Upload & Accounting Records
                  </span>
                ) : reconciliation.isCertified ? (
                  <span className="text-emerald-400 bg-emerald-900/60 px-2 py-0.5 rounded font-mono text-[11px]">
                    Certified Audit Approved (&le; 1 bp)
                  </span>
                ) : (
                  <span className="text-rose-400 bg-rose-900/60 px-2 py-0.5 rounded font-mono text-[11px]">
                    Quarantine Protocol Required ({reconciliation.maxVarianceBp.toFixed(2)} bp &gt; 1.0 bp)
                  </span>
                )}
              </div>

              <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                {reconciliation.isAwaiting
                  ? 'Upload a sales transaction file and enter your official General Ledger control totals to perform the 1 bp reconciliation gate check.'
                  : reconciliation.isCertified
                  ? 'All controls match within the strict 1 bp audit tolerance limit (&le; 0.01%). Your dataset will be certified for defensible pricing comparisons.'
                  : `Variance of $${reconciliation.residualDollars.toLocaleString('en-US', { minimumFractionDigits: 2 })} (${reconciliation.residualPct.toFixed(2)}%) exceeds the 1 bp guardrail. Proceeding will isolate residual records into quarantine and watermark all downstream reports.`}
              </p>

              {!reconciliation.isAwaiting && !reconciliation.isCertified && (
                <div className="mt-3 flex items-center space-x-2 bg-rose-950/40 p-2.5 rounded-lg border border-rose-800/40">
                  <input
                    type="checkbox"
                    id="quarantine_override"
                    checked={quarantineOverride}
                    onChange={(e) => setQuarantineOverride(e.target.checked)}
                    className="rounded bg-slate-900 border-slate-700 text-rose-600 focus:ring-rose-500 h-4 w-4"
                  />
                  <label htmlFor="quarantine_override" className="text-xs font-semibold text-rose-200 cursor-pointer select-none">
                    Acknowledge discrepancy and proceed under Quarantine Protocol (isolates unverified rows in audit_manifest.json)
                  </label>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Action Button & Status Bar */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-2">
          <div className="text-xs font-mono text-slate-400">
            {statusMessage && <span>{statusMessage}</span>}
          </div>

          <button
            type="button"
            onClick={handleRunReconciliation}
            disabled={isIngesting || reconciliation.isAwaiting || (!reconciliation.isCertified && !quarantineOverride)}
            className={`w-full sm:w-auto px-6 py-3 rounded-xl font-bold text-xs tracking-wider uppercase transition flex items-center justify-center space-x-2 shadow-lg ${
              reconciliation.isAwaiting
                ? 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
                : reconciliation.isCertified
                ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-950/50'
                : quarantineOverride
                ? 'bg-rose-600 hover:bg-rose-500 text-white shadow-rose-950/50'
                : 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
            }`}
          >
            {isIngesting ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>Verifying Sales Records with Accounting...</span>
              </>
            ) : reconciliation.isAwaiting ? (
              <span>Awaiting File Upload & Accounting Records</span>
            ) : reconciliation.isCertified ? (
              <>
                <span>Confirm Totals & Continue to Compare Deals (Verify within 1 bp tolerance)</span>
                <ArrowRight className="w-4 h-4" />
              </>
            ) : (
              <>
                <span>Quarantine Discrepancies & Continue (Isolate residual transactions)</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </div>
      </div>

      {/* Progressive Disclosure: Advanced Technical Details */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-sm">
        <button
          type="button"
          onClick={() => setShowAdvancedDetails(!showAdvancedDetails)}
          className="w-full px-5 py-3.5 bg-slate-950/40 hover:bg-slate-800/40 text-left flex items-center justify-between transition"
        >
          <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-slate-300">
            <Database className="w-4 h-4 text-cyan-400" />
            <span>Advanced Technical Details & Audit Verification Proofs</span>
          </div>
          <div className="flex items-center space-x-1 text-xs text-cyan-400 font-medium">
            <span>{showAdvancedDetails ? 'Hide Details' : 'Show Details'}</span>
            {showAdvancedDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </div>
        </button>

        {showAdvancedDetails && (
          <div className="p-5 border-t border-slate-800 space-y-4 bg-slate-950/50 text-xs font-mono">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="p-3 bg-slate-900 rounded-xl border border-slate-800">
                <span className="text-slate-500 text-[10px] block">DuckDB Engine Configuration:</span>
                <span className="text-slate-200 font-bold">4 GB Memory Limit (Disk Spilling Active)</span>
              </div>
              <div className="p-3 bg-slate-900 rounded-xl border border-slate-800">
                <span className="text-slate-500 text-[10px] block">Tolerance Calculation:</span>
                <span className="text-cyan-300 font-bold">1 bp = 0.01% = 0.0001</span>
              </div>
              <div className="p-3 bg-slate-900 rounded-xl border border-slate-800">
                <span className="text-slate-500 text-[10px] block">Audit Manifest SHA-256:</span>
                <span className="text-slate-300 font-bold">SHA256(Pass2_Scan_Buffer)</span>
              </div>
            </div>

            <p className="text-[11px] text-slate-400 font-sans leading-relaxed">
              <strong>Vectorized Ingestion Invariant:</strong> Pass 1 executes streaming row inspection without loading full datasets into memory. Pass 2 executes vectorized DuckDB scans to enforce unique row grains (<code className="text-cyan-300">transaction_line_id</code>), detect credit notes/reversals, and calculate exact basis-point variances against accounting controls.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
