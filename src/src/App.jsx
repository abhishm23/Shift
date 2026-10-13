import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  ShieldAlert,
  Database,
  Sliders,
  Layers,
  FolderOpen,
  PlusCircle,
  FileCheck2,
  Lock,
  Activity,
  Server,
  HelpCircle,
  TrendingUp,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import WatermarkBanner from './components/WatermarkBanner';
import View1Reconcile from './components/View1Reconcile';
import View2Calibrate from './components/View2Calibrate';
import View3Triage from './components/View3Triage';
import UseCaseGuide from './components/UseCaseGuide';
import { api } from './services/api';

export default function App() {
  const [activeTab, setActiveTab] = useState('reconcile'); // 'reconcile' | 'calibrate' | 'triage'
  const [isOnline, setIsOnline] = useState(false);
  const [backendHealth, setBackendHealth] = useState(null);
  const [showEngineDetails, setShowEngineDetails] = useState(false);

  // Workspace metadata state (.mxa container) - clean slate on launch
  const [workspaceMeta, setWorkspaceMeta] = useState({
    path: 'No workspace loaded',
    duckdb_status: 'embedded',
    memory_limit: '4GB',
    temp_dir: 'disk_spilling_enabled',
  });

  // Audit Manifest State & 1 bp Reconciliation Gate - clean slate on launch
  const [auditManifest, setAuditManifest] = useState({
    certified: false,
    residualPct: 0.00,
    residualDollars: 0.00,
    watermark: null,
    hasReconciled: false,
    manifestFile: null,
  });

  // Calibration State - null initially until user saves comparison rules
  const [activeCalibrationId, setActiveCalibrationId] = useState(null);

  // Dynamic dataset schema & attribute state passed across views (DEF-UI-03, DEF-UI-04, DEF-UI-08, DEF-UI-09)
  const [datasetColumns, setDatasetColumns] = useState([]);
  const [inferredTypes, setInferredTypes] = useState({});
  const [columnMapping, setColumnMapping] = useState({});
  const [investigationDims, setInvestigationDims] = useState([]);

  // Check loopback backend health periodically
  useEffect(() => {
    let isMounted = true;
    const checkBackend = async () => {
      try {
        const health = await api.health.check();
        if (isMounted) {
          setIsOnline(true);
          setBackendHealth(health);
        }
      } catch (err) {
        if (isMounted) {
          setIsOnline(false);
          setBackendHealth(null);
        }
      }
    };

    checkBackend();
    const interval = setInterval(checkBackend, 5000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-cyan-500 selection:text-white">
      {/* Permanent, Indelible Quarantine Watermark Banner (R2.9 / AC-8) */}
      <WatermarkBanner
        residualPct={auditManifest.residualPct}
        residualDollars={auditManifest.residualDollars}
        certifiedAudit={auditManifest.certified}
        hasReconciled={auditManifest.hasReconciled}
      />

      {/* Main Application Header */}
      <header className="bg-slate-900 border-b border-slate-800 px-6 py-3.5 flex flex-col md:flex-row md:items-center justify-between gap-4 sticky top-0 z-40 backdrop-blur-md bg-slate-900/90">
        {/* Brand & Workspace Title */}
        <div className="flex items-center space-x-3">
          <div className="h-9 w-9 bg-gradient-to-br from-cyan-500 to-cyan-700 rounded-xl flex items-center justify-center shadow-lg shadow-cyan-950/50">
            <Database className="w-5 h-5 text-slate-950 font-black" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-lg font-black tracking-wider text-white">SIFT</h1>
              <span className="text-[10px] font-mono uppercase bg-slate-800 text-cyan-300 px-2 py-0.5 rounded font-semibold tracking-wide border border-slate-700">
                Commercial Audit
              </span>
            </div>
            <div className="flex items-center space-x-2 text-xs font-mono text-slate-400 mt-0.5">
              <FolderOpen className="w-3 h-3 text-slate-500" />
              <span className="truncate max-w-[200px] sm:max-w-xs">{workspaceMeta.path}</span>
            </div>
          </div>
        </div>

        {/* Tab Navigation (Plain-English Outcome Steps: R7.1) */}
        <nav className="flex items-center space-x-1.5 bg-slate-950 p-1.5 rounded-xl border border-slate-800 self-center">
          <button
            onClick={() => setActiveTab('reconcile')}
            title="Upload sales data and verify that totals match accounting records"
            className={`px-4 py-2.5 rounded-lg text-xs font-bold transition flex items-center space-x-2.5 ${
              activeTab === 'reconcile'
                ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-950/40'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
            }`}
          >
            <FileCheck2 className="w-4 h-4 flex-shrink-0" />
            <div className="text-left">
              <div className="font-bold">1. Add & Check Data</div>
              <div className={`text-[10px] hidden xl:block font-normal ${activeTab === 'reconcile' ? 'text-slate-900/80' : 'text-slate-500'}`}>
                Upload & verify with accounting
              </div>
            </div>
          </button>

          <button
            onClick={() => setActiveTab('calibrate')}
            title="Group products and customers to compare pricing like-for-like"
            className={`px-4 py-2.5 rounded-lg text-xs font-bold transition flex items-center space-x-2.5 ${
              activeTab === 'calibrate'
                ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-950/40'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
            }`}
          >
            <Sliders className="w-4 h-4 flex-shrink-0" />
            <div className="text-left">
              <div className="font-bold">2. Compare Similar Deals</div>
              <div className={`text-[10px] hidden xl:block font-normal ${activeTab === 'calibrate' ? 'text-slate-900/80' : 'text-slate-500'}`}>
                Group like-for-like peers
              </div>
            </div>
          </button>

          <button
            onClick={() => setActiveTab('triage')}
            title="Identify pricing exceptions, margin leaks, and recoverable revenue"
            className={`px-4 py-2.5 rounded-lg text-xs font-bold transition flex items-center space-x-2.5 ${
              activeTab === 'triage'
                ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-950/40'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
            }`}
          >
            <TrendingUp className="w-4 h-4 flex-shrink-0" />
            <div className="text-left">
              <div className="font-bold">3. Discover Profit Opportunities</div>
              <div className={`text-[10px] hidden xl:block font-normal ${activeTab === 'triage' ? 'text-slate-900/80' : 'text-slate-500'}`}>
                Find margin leaks & recover revenue
              </div>
            </div>
          </button>
        </nav>

        {/* Status & Harness Indicators (R1.1 - R1.7, AC-6) */}
        <div className="flex items-center space-x-3 text-xs font-mono">
          {/* Air-Gap Badge */}
          <div className="flex items-center space-x-1.5 bg-emerald-950/60 border border-emerald-800/60 text-emerald-300 px-2.5 py-1 rounded-lg">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="font-semibold text-[11px]">AIR-GAPPED (127.0.0.1)</span>
          </div>

          {/* DuckDB Status with Progressive Disclosure Toggle */}
          <button
            onClick={() => setShowEngineDetails(!showEngineDetails)}
            className="hidden lg:flex items-center space-x-1.5 bg-slate-950 hover:bg-slate-800 border border-slate-800 text-slate-300 px-2.5 py-1 rounded-lg transition"
            title="Toggle Engine Diagnostics"
          >
            <Server className="w-3.5 h-3.5 text-cyan-400" />
            <span>DuckDB: {workspaceMeta.memory_limit}</span>
            {showEngineDetails ? <ChevronUp className="w-3 h-3 text-slate-400" /> : <ChevronDown className="w-3 h-3 text-slate-400" />}
          </button>

          {/* Backend Connection Status */}
          <div
            title={isOnline ? 'Analytical Engine Connected (127.0.0.1:8765)' : 'Loopback Engine Offline (Running in Local Preview Mode)'}
            className={`flex items-center space-x-1 px-2.5 py-1 rounded-lg border text-[11px] ${
              isOnline
                ? 'bg-cyan-950/40 border-cyan-800 text-cyan-300'
                : 'bg-slate-950 border-slate-800 text-slate-400'
            }`}
          >
            <Activity className={`w-3.5 h-3.5 ${isOnline ? 'text-cyan-400' : 'text-slate-500'}`} />
            <span>{isOnline ? 'ENGINE READY' : 'PREVIEW MODE'}</span>
          </div>
        </div>
      </header>

      {/* Engine Details Progressive Disclosure Banner */}
      {showEngineDetails && (
        <div className="bg-slate-900 border-b border-slate-800 px-6 py-2.5 text-xs font-mono text-slate-300 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center space-x-4">
            <span><strong>DuckDB:</strong> In-process (Embedded v1.0)</span>
            <span>&bull;</span>
            <span><strong>RAM Budget:</strong> 4 GB limit</span>
            <span>&bull;</span>
            <span><strong>Disk Spilling:</strong> Active (.tmp spill directory enabled)</span>
            <span>&bull;</span>
            <span><strong>IPC:</strong> 127.0.0.1 loopback only</span>
          </div>
          <div className="text-[11px] text-emerald-400 font-semibold">
            ✓ External Network Egress: Prohibited (Strict Air-Gap)
          </div>
        </div>
      )}

      {/* Main Content View Container */}
      <main className="flex-1 p-6 max-w-7xl w-full mx-auto">
        {/* Interactive Real-World Use Case Guide */}
        <UseCaseGuide />
        {activeTab === 'reconcile' && (
          <View1Reconcile
            workspaceMeta={workspaceMeta}
            auditManifest={auditManifest}
            setAuditManifest={setAuditManifest}
            onReconciled={(manifest) => setAuditManifest(manifest)}
            onReconciliationComplete={() => setActiveTab('calibrate')}
            onColumnsDetected={(cols, types, mapping) => {
              setDatasetColumns(cols);
              setInferredTypes(types);
              setColumnMapping(mapping);
            }}
          />
        )}

        {activeTab === 'calibrate' && (
          <View2Calibrate
            activeCalibrationId={activeCalibrationId}
            setActiveCalibrationId={setActiveCalibrationId}
            datasetColumns={datasetColumns}
            inferredTypes={inferredTypes}
            columnMapping={columnMapping}
            investigationDims={investigationDims}
            setInvestigationDims={setInvestigationDims}
            onCalibrationChange={(id) => setActiveCalibrationId(id)}
          />
        )}

        {activeTab === 'triage' && (
          <View3Triage
            activeCalibrationId={activeCalibrationId}
            readinessTier={2}
            residualPct={auditManifest.residualPct}
            investigationDims={investigationDims}
            datasetColumns={datasetColumns}
          />
        )}
      </main>

      {/* App Footer */}
      <footer className="bg-slate-900 border-t border-slate-800 px-6 py-2 text-xs font-mono text-slate-500 flex flex-col sm:flex-row items-center justify-between gap-2">
        <div>
          Sift &bull; Local-First Analytical Engine &bull; Zero Remote Telemetry &bull; Single-file .mxa
        </div>
        <div className="flex items-center space-x-4">
          <span>Tolerance: 1 bp (&plusmn;0.01%)</span>
          <span>&bull;</span>
          <span>FDR q &lt; 0.05</span>
          <span>&bull;</span>
          <span>Beam (w=3, d=3)</span>
        </div>
      </footer>
    </div>
  );
}
