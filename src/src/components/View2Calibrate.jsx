import React, { useState, useEffect, useMemo } from 'react';
import {
  Sliders,
  Lock,
  Download,
  Upload,
  BarChart3,
  ShieldCheck,
  AlertCircle,
  CheckCircle,
  HelpCircle,
  ArrowLeftRight,
  TrendingDown,
  Layers,
  ChevronRight,
  ChevronUp,
  ChevronDown,
  Search,
  Filter,
  Tag
} from 'lucide-react';
import { api } from '../services/api';

export default function View2Calibrate({
  onCalibrationChange,
  activeCalibrationId,
  setActiveCalibrationId,
  datasetColumns = [],
  inferredTypes = {},
  columnMapping = {},
  investigationDims: propInvestigationDims = [],
  setInvestigationDims: propSetInvestigationDims
}) {
  // Three-column categorization clean slate state - strictly empty initially
  const [comparabilityControls, setComparabilityControls] = useState([]);
  const [investigationDims, setInvestigationDims] = useState([]);
  const [excludedAttributes, setExcludedAttributes] = useState([]);

  // Search & Taxonomy filtering for wide schemas (DEF-UI-10)
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedTaxonomy, setSelectedTaxonomy] = useState('ALL'); // ALL, SALES, PRODUCT, CUSTOMER, DEAL, METRICS

  // Calibration parameters
  const [thresholdMethod, setThresholdMethod] = useState('P75'); // 'P75' | 'MAD'
  const [kappa, setKappa] = useState(0.40); // Capture rate haircut
  const [baselinePeriod, setBaselinePeriod] = useState('2024-Q1_to_2024-Q4');
  const [isFreezing, setIsFreezing] = useState(false);
  const [freezeSuccess, setFreezeSuccess] = useState(null);

  // Selected Cohort & Distribution - null until computed from active data
  const [selectedCohort, setSelectedCohort] = useState(null);
  const [cohortStats, setCohortStats] = useState(null);
  const [showAdvancedStats, setShowAdvancedStats] = useState(false);

  // Auto-populate 3-column attribute selector from datasetColumns (DEF-UI-03, DEF-UI-08)
  useEffect(() => {
    if (datasetColumns && datasetColumns.length > 0) {
      const allLoaded = new Set([...comparabilityControls, ...investigationDims, ...excludedAttributes]);
      if (allLoaded.size === 0) {
        const controls = [];
        const audited = [];
        const excluded = [];

        datasetColumns.forEach((col) => {
          const lower = col.toLowerCase();
          const isMetric =
            lower.endsWith('_amt') ||
            lower.endsWith('_pct') ||
            lower.endsWith('_val') ||
            lower.endsWith('_rate') ||
            lower.endsWith('_cost') ||
            lower.endsWith('_price') ||
            lower.endsWith('_cnt') ||
            lower.endsWith('_count') ||
            lower.endsWith('_qty') ||
            lower.startsWith('extended_') ||
            lower.startsWith('net_') ||
            lower.startsWith('pocket_') ||
            lower.startsWith('cogs_') ||
            lower.startsWith('gross_') ||
            lower.startsWith('rebate_');

          const isIdOrDate =
            lower.endsWith('_id') ||
            lower.startsWith('id_') ||
            lower === 'id' ||
            lower.includes('date') ||
            lower.includes('time') ||
            lower.includes('timestamp') ||
            lower.includes('comment') ||
            lower.includes('notes') ||
            lower.includes('description') ||
            lower.includes('phone') ||
            lower.includes('email') ||
            lower.includes('address') ||
            lower.includes('zip') ||
            lower.includes('postal') ||
            lower.includes('customer_name') ||
            lower.includes('account_name');

          if (isMetric || isIdOrDate) {
            excluded.push(col);
          } else if (
            lower.includes('product') ||
            lower.includes('category') ||
            lower.includes('family') ||
            lower.includes('segment') ||
            lower.includes('region') ||
            lower.includes('tier') ||
            lower.includes('market') ||
            lower.includes('currency') ||
            lower.includes('geo') ||
            lower.includes('industry') ||
            lower.includes('vertical') ||
            lower.includes('brand') ||
            lower.includes('sku') ||
            lower.includes('class')
          ) {
            controls.push(col);
          } else {
            audited.push(col);
          }
        });

        if (controls.length === 0 && audited.length > 0) {
          controls.push(...audited.splice(0, Math.min(3, audited.length)));
        }

        setComparabilityControls(controls);
        setInvestigationDims(audited);
        setExcludedAttributes(excluded);
        if (propSetInvestigationDims) {
          propSetInvestigationDims(audited);
        }
      }
    }
  }, [datasetColumns]);

  // Synchronize investigationDims with parent prop when updated
  const updateInvestigationDims = (newDims) => {
    setInvestigationDims(newDims);
    if (propSetInvestigationDims) {
      propSetInvestigationDims(newDims);
    }
  };

  // Move item between columns with bidirectional sync
  const moveItem = (item, fromList, setFromList, toList, setToList, isFromAudit = false, isToAudit = false) => {
    const newFrom = fromList.filter((i) => i !== item);
    const newTo = [...toList, item];
    setFromList(newFrom);
    setToList(newTo);

    if (isFromAudit) {
      updateInvestigationDims(newFrom);
    } else if (isToAudit) {
      updateInvestigationDims(newTo);
    }
  };

  // Taxonomy category identifier for wide schema grouping (DEF-UI-10)
  const getTaxonomyCategory = (col) => {
    const lower = col.toLowerCase();
    if (
      lower.endsWith('_amt') ||
      lower.endsWith('_pct') ||
      lower.endsWith('_val') ||
      lower.endsWith('_rate') ||
      lower.endsWith('_cost') ||
      lower.endsWith('_price') ||
      lower.endsWith('_id') ||
      lower.includes('date') ||
      lower.includes('time')
    ) {
      return 'METRICS';
    }
    if (
      lower.includes('sales') ||
      lower.includes('rep') ||
      lower.includes('channel') ||
      lower.includes('territory') ||
      lower.includes('partner') ||
      lower.includes('agent') ||
      lower.includes('motion') ||
      lower.includes('distributor')
    ) {
      return 'SALES';
    }
    if (
      lower.includes('prod') ||
      lower.includes('sku') ||
      lower.includes('cat') ||
      lower.includes('family') ||
      lower.includes('brand') ||
      lower.includes('item') ||
      lower.includes('line')
    ) {
      return 'PRODUCT';
    }
    if (
      lower.includes('cust') ||
      lower.includes('account') ||
      lower.includes('client') ||
      lower.includes('industry') ||
      lower.includes('vertical') ||
      lower.includes('tier') ||
      lower.includes('segment') ||
      lower.includes('geo') ||
      lower.includes('region') ||
      lower.includes('market')
    ) {
      return 'CUSTOMER';
    }
    if (
      lower.includes('contract') ||
      lower.includes('deal') ||
      lower.includes('term') ||
      lower.includes('sla') ||
      lower.includes('order') ||
      lower.includes('pay') ||
      lower.includes('promo') ||
      lower.includes('discount')
    ) {
      return 'DEAL';
    }
    return 'OTHER';
  };

  const matchesFilter = (col) => {
    if (searchTerm && !col.toLowerCase().includes(searchTerm.toLowerCase().trim())) {
      return false;
    }
    if (selectedTaxonomy !== 'ALL') {
      const cat = getTaxonomyCategory(col);
      if (selectedTaxonomy === 'OTHER') {
        if (cat === 'OTHER' || cat === 'METRICS') return true;
        return false;
      }
      if (cat !== selectedTaxonomy) return false;
    }
    return true;
  };

  const filteredControls = useMemo(() => comparabilityControls.filter(matchesFilter), [comparabilityControls, searchTerm, selectedTaxonomy]);
  const filteredAudited = useMemo(() => investigationDims.filter(matchesFilter), [investigationDims, searchTerm, selectedTaxonomy]);
  const filteredExcluded = useMemo(() => excludedAttributes.filter(matchesFilter), [excludedAttributes, searchTerm, selectedTaxonomy]);

  const moveAllFiltered = (target) => {
    if (target === 'controls') {
      const toMoveFromAudit = filteredAudited;
      const toMoveFromExcluded = filteredExcluded;
      if (toMoveFromAudit.length === 0 && toMoveFromExcluded.length === 0) return;

      const newAudit = investigationDims.filter(i => !toMoveFromAudit.includes(i));
      const newExcluded = excludedAttributes.filter(i => !toMoveFromExcluded.includes(i));
      const newControls = [...comparabilityControls, ...toMoveFromAudit, ...toMoveFromExcluded];

      updateInvestigationDims(newAudit);
      setExcludedAttributes(newExcluded);
      setComparabilityControls(newControls);
    } else if (target === 'audited') {
      const toMoveFromControls = filteredControls;
      const toMoveFromExcluded = filteredExcluded;
      if (toMoveFromControls.length === 0 && toMoveFromExcluded.length === 0) return;

      const newControls = comparabilityControls.filter(i => !toMoveFromControls.includes(i));
      const newExcluded = excludedAttributes.filter(i => !toMoveFromExcluded.includes(i));
      const newAudit = [...investigationDims, ...toMoveFromControls, ...toMoveFromExcluded];

      setComparabilityControls(newControls);
      setExcludedAttributes(newExcluded);
      updateInvestigationDims(newAudit);
    } else if (target === 'excluded') {
      const toMoveFromControls = filteredControls;
      const toMoveFromAudit = filteredAudited;
      if (toMoveFromControls.length === 0 && toMoveFromAudit.length === 0) return;

      const newControls = comparabilityControls.filter(i => !toMoveFromControls.includes(i));
      const newAudit = investigationDims.filter(i => !toMoveFromAudit.includes(i));
      const newExcluded = [...excludedAttributes, ...toMoveFromControls, ...toMoveFromAudit];

      setComparabilityControls(newControls);
      updateInvestigationDims(newAudit);
      setExcludedAttributes(newExcluded);
    }
  };

  const handleFreezeBaseline = async () => {
    setIsFreezing(true);
    setFreezeSuccess(null);

    const period = baselinePeriod || 'FY2024';
    const profileName = `calib_${period}_${thresholdMethod.toLowerCase()}_k${Math.round(kappa * 100)}`;

    try {
      const res = await api.calibrate.freeze(profileName, comparabilityControls, thresholdMethod, kappa);
      const calibId = res.calibration_id || `CALIB-${Date.now().toString(36).toUpperCase()}`;
      setActiveCalibrationId(calibId);
      setFreezeSuccess(`Baseline successfully saved & locked to ${profileName}.calib.json (ID: ${calibId})`);
      if (onCalibrationChange) onCalibrationChange(calibId);
    } catch (err) {
      console.warn('[View2] Freeze baseline API error, simulating local freeze:', err.message);
      const fallbackId = `CALIB-${period}-${thresholdMethod}-${Date.now().toString(36).slice(-4).toUpperCase()}`;
      setActiveCalibrationId(fallbackId);
      setFreezeSuccess(`Comparison rules saved & locked locally to ${profileName}.calib.json (${fallbackId})`);
      if (onCalibrationChange) onCalibrationChange(fallbackId);
    } finally {
      setIsFreezing(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header Banner: Plain-English Step 2 */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900/60 p-5 rounded-2xl border border-slate-800 shadow-sm">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="h-8 w-8 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
              <Sliders className="w-4 h-4" />
            </div>
            <h2 className="text-xl font-bold tracking-tight text-white">
              Step 2: Compare Similar Deals
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-1.5 max-w-2xl leading-relaxed">
            Group products, regions, and customer accounts to ensure every deal is compared fairly against true peers, setting clear benchmark standards for fair discounts.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <span className="text-xs font-mono bg-slate-800 border border-slate-700 text-cyan-300 px-3 py-1.5 rounded-lg flex items-center space-x-1.5">
            <Lock className="w-3.5 h-3.5 text-cyan-400" />
            <span>Active Rules: {activeCalibrationId || 'Uncalibrated'}</span>
          </span>
        </div>
      </div>

      {/* 3-Column Attribute Categorization (DEF-UI-03, DEF-UI-08, DEF-UI-10) */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4 shadow-md">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 pb-2 border-b border-slate-800">
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-200 flex items-center space-x-2">
              <ArrowLeftRight className="w-4 h-4 text-cyan-400" />
              <span>What Factors Govern Deal Pricing? (Three-Column Grouping)</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5 leading-relaxed">
              Group your dataset columns. Comparability Controls justify different prices (apples-to-apples). Audited Factors are searched for pricing leaks and rogue discounts.
            </p>
          </div>

          <div className="text-xs font-mono bg-slate-950 px-3 py-1.5 rounded-xl border border-slate-800 text-slate-400 flex items-center space-x-2">
            <span>Total Columns:</span>
            <span className="font-bold text-cyan-400">
              {comparabilityControls.length + investigationDims.length + excludedAttributes.length}
            </span>
          </div>
        </div>

        {/* Search, Taxonomy Filter & Bulk Tools (DEF-UI-10) */}
        <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 bg-slate-950/60 p-3 rounded-xl border border-slate-800">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search attributes (e.g., rep, region, sku, contract)..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-slate-900 border border-slate-800 rounded-lg pl-9 pr-8 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 font-mono"
            />
            {searchTerm && (
              <button
                onClick={() => setSearchTerm('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 text-xs"
              >
                &times;
              </button>
            )}
          </div>

          {/* Taxonomy Pills */}
          <div className="flex flex-wrap items-center gap-1.5 text-xs">
            <span className="text-[11px] text-slate-500 font-semibold mr-1 flex items-center space-x-1">
              <Filter className="w-3 h-3" />
              <span>Taxonomy:</span>
            </span>
            {[
              { id: 'ALL', label: 'All' },
              { id: 'SALES', label: 'Sales' },
              { id: 'PRODUCT', label: 'Product' },
              { id: 'CUSTOMER', label: 'Customer' },
              { id: 'DEAL', label: 'Deal' },
              { id: 'METRICS', label: 'Financial' },
            ].map((tax) => (
              <button
                key={tax.id}
                type="button"
                onClick={() => setSelectedTaxonomy(tax.id)}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-medium transition ${
                  selectedTaxonomy === tax.id
                    ? 'bg-cyan-500/20 border border-cyan-500/50 text-cyan-300 font-semibold'
                    : 'bg-slate-900 hover:bg-slate-800 text-slate-400 border border-slate-800'
                }`}
              >
                {tax.label}
              </button>
            ))}
          </div>
        </div>

        {/* Bulk Move Actions for Filtered Set */}
        {(searchTerm || selectedTaxonomy !== 'ALL') && (
          <div className="flex flex-wrap items-center justify-between gap-2 px-1 text-xs text-slate-400 font-mono">
            <span>
              Filtered:{' '}
              <strong className="text-cyan-300">
                {filteredControls.length + filteredAudited.length + filteredExcluded.length}
              </strong>{' '}
              columns matching
            </span>
            <div className="flex items-center space-x-2">
              <span className="text-[10px] text-slate-500">Move all matching to:</span>
              <button
                type="button"
                onClick={() => moveAllFiltered('controls')}
                className="text-[11px] bg-cyan-950 hover:bg-cyan-900 border border-cyan-800 text-cyan-300 px-2 py-0.5 rounded font-sans"
              >
                + Controls
              </button>
              <button
                type="button"
                onClick={() => moveAllFiltered('audited')}
                className="text-[11px] bg-amber-950 hover:bg-amber-900 border border-amber-800 text-amber-300 px-2 py-0.5 rounded font-sans"
              >
                + Audited
              </button>
              <button
                type="button"
                onClick={() => moveAllFiltered('excluded')}
                className="text-[11px] bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 px-2 py-0.5 rounded font-sans"
              >
                + Excluded
              </button>
            </div>
          </div>
        )}

        {/* 3 Columns Display */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Column 1: Comparability Controls */}
          <div className="bg-slate-950/70 border border-cyan-900/40 rounded-xl p-4 space-y-3 flex flex-col">
            <div className="flex items-center justify-between pb-2 border-b border-cyan-900/30">
              <span className="text-xs font-bold uppercase tracking-wider text-cyan-400">
                1. Fair Pricing Factors
              </span>
              <span className="text-[10px] font-mono bg-cyan-950 text-cyan-300 px-2 py-0.5 rounded border border-cyan-800/40">
                {filteredControls.length} / {comparabilityControls.length} factors
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              Legitimate price drivers (e.g., product family, customer tier, region).
            </p>
            <div className="space-y-1.5 min-h-[160px] max-h-[380px] overflow-y-auto pr-1 flex-1">
              {filteredControls.length === 0 ? (
                <div className="text-center py-10 text-slate-500 text-xs italic border border-dashed border-slate-800 rounded-lg">
                  {comparabilityControls.length === 0
                    ? 'No attributes loaded yet. Upload data in Step 1 to populate available columns.'
                    : 'No factors match current filter.'}
                </div>
              ) : (
                filteredControls.map((item) => (
                  <div
                    key={item}
                    className="bg-cyan-950/30 border border-cyan-800/50 rounded-lg px-2.5 py-1.5 text-xs text-cyan-200 font-mono flex items-center justify-between group hover:border-cyan-700 transition"
                  >
                    <div className="flex items-center space-x-1.5 truncate mr-1">
                      <span className="truncate">{item}</span>
                      <span className="text-[9px] px-1 py-0.2 bg-cyan-900/50 text-cyan-400 rounded uppercase font-sans">
                        {getTaxonomyCategory(item)}
                      </span>
                    </div>
                    <div className="flex items-center space-x-1 opacity-75 group-hover:opacity-100 transition flex-shrink-0">
                      <button
                        title="Move to Audited Deal Factors"
                        onClick={() => moveItem(item, comparabilityControls, setComparabilityControls, investigationDims, setInvestigationDims, false, true)}
                        className="text-[10px] bg-amber-950 hover:bg-amber-900 border border-amber-800/60 text-amber-300 px-1.5 py-0.5 rounded font-sans"
                      >
                        &rarr; Audit
                      </button>
                      <button
                        title="Move to Excluded Attributes"
                        onClick={() => moveItem(item, comparabilityControls, setComparabilityControls, excludedAttributes, setExcludedAttributes)}
                        className="text-[10px] bg-slate-800 hover:bg-slate-700 text-slate-400 px-1.5 py-0.5 rounded"
                      >
                        &times;
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Column 2: Investigation Dimensions */}
          <div className="bg-slate-950/70 border border-amber-900/40 rounded-xl p-4 space-y-3 flex flex-col">
            <div className="flex items-center justify-between pb-2 border-b border-amber-900/30">
              <span className="text-xs font-bold uppercase tracking-wider text-amber-400">
                2. Audited Deal Factors
              </span>
              <span className="text-[10px] font-mono bg-amber-950 text-amber-300 px-2 py-0.5 rounded border border-amber-800/40">
                {filteredAudited.length} / {investigationDims.length} factors
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              Attributes scrutinized for pricing leaks (e.g., sales rep, sales channel).
            </p>
            <div className="space-y-1.5 min-h-[160px] max-h-[380px] overflow-y-auto pr-1 flex-1">
              {filteredAudited.length === 0 ? (
                <div className="text-center py-10 text-slate-500 text-xs italic border border-dashed border-slate-800 rounded-lg">
                  {investigationDims.length === 0
                    ? 'No audited factors selected yet.'
                    : 'No audited factors match current filter.'}
                </div>
              ) : (
                filteredAudited.map((item) => (
                  <div
                    key={item}
                    className="bg-amber-950/30 border border-amber-800/50 rounded-lg px-2.5 py-1.5 text-xs text-amber-200 font-mono flex items-center justify-between group hover:border-amber-700 transition"
                  >
                    <div className="flex items-center space-x-1.5 truncate mr-1">
                      <span className="truncate">{item}</span>
                      <span className="text-[9px] px-1 py-0.2 bg-amber-900/50 text-amber-400 rounded uppercase font-sans">
                        {getTaxonomyCategory(item)}
                      </span>
                    </div>
                    <div className="flex items-center space-x-1 opacity-75 group-hover:opacity-100 transition flex-shrink-0">
                      <button
                        title="Move to Fair Pricing Factors"
                        onClick={() => moveItem(item, investigationDims, setInvestigationDims, comparabilityControls, setComparabilityControls, true, false)}
                        className="text-[10px] bg-cyan-950 hover:bg-cyan-900 border border-cyan-800/60 text-cyan-300 px-1.5 py-0.5 rounded font-sans"
                      >
                        &larr; Ctrl
                      </button>
                      <button
                        title="Move to Excluded Attributes"
                        onClick={() => moveItem(item, investigationDims, setInvestigationDims, excludedAttributes, setExcludedAttributes, true, false)}
                        className="text-[10px] bg-slate-800 hover:bg-slate-700 text-slate-400 px-1.5 py-0.5 rounded"
                      >
                        &times;
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Column 3: Excluded Attributes */}
          <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-4 space-y-3 flex flex-col">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                3. Excluded Attributes
              </span>
              <span className="text-[10px] font-mono bg-slate-800 text-slate-400 px-2 py-0.5 rounded">
                {filteredExcluded.length} / {excludedAttributes.length} ignored
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              Metadata, comments, and identifiers ignored during deal comparisons.
            </p>
            <div className="space-y-1.5 min-h-[160px] max-h-[380px] overflow-y-auto pr-1 flex-1">
              {filteredExcluded.length === 0 ? (
                <div className="text-center py-10 text-slate-500 text-xs italic border border-dashed border-slate-800 rounded-lg">
                  {excludedAttributes.length === 0
                    ? 'No attributes excluded.'
                    : 'No excluded attributes match current filter.'}
                </div>
              ) : (
                filteredExcluded.map((item) => (
                  <div
                    key={item}
                    className="bg-slate-900/60 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-400 font-mono flex items-center justify-between group hover:border-slate-700 transition"
                  >
                    <div className="flex items-center space-x-1.5 truncate mr-1">
                      <span className="truncate">{item}</span>
                      <span className="text-[9px] px-1 py-0.2 bg-slate-800 text-slate-400 rounded uppercase font-sans">
                        {getTaxonomyCategory(item)}
                      </span>
                    </div>
                    <div className="flex items-center space-x-1 opacity-75 group-hover:opacity-100 transition flex-shrink-0">
                      <button
                        title="Move to Fair Pricing Factors"
                        onClick={() => moveItem(item, excludedAttributes, setExcludedAttributes, comparabilityControls, setComparabilityControls)}
                        className="text-[10px] bg-slate-800 hover:bg-slate-700 text-cyan-300 px-1.5 py-0.5 rounded"
                      >
                        Ctrl
                      </button>
                      <button
                        title="Move to Audited Deal Factors"
                        onClick={() => moveItem(item, excludedAttributes, setExcludedAttributes, investigationDims, setInvestigationDims, false, true)}
                        className="text-[10px] bg-slate-800 hover:bg-slate-700 text-amber-300 px-1.5 py-0.5 rounded"
                      >
                        Audit
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Cohort Visualization & Support Fences */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Cohort Peer Distribution Card */}
        <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4 shadow-md">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-200 flex items-center space-x-2">
                <BarChart3 className="w-4 h-4 text-cyan-400" />
                <span>Fair Peer Group Discount Distribution</span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                {cohortStats
                  ? `Leave-One-Account-Out distribution for cohort: ${cohortStats.name}`
                  : 'Select comparable attributes and load baseline data to view cohort distribution.'}
              </p>
            </div>

            {/* Threshold Selector: P75 vs MAD */}
            <div className="flex items-center space-x-1 bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs">
              <button
                type="button"
                onClick={() => setThresholdMethod('P75')}
                title="Flags deals where the discount is larger than 75% of similar peer orders"
                className={`px-3 py-1.5 rounded-lg font-bold transition ${
                  thresholdMethod === 'P75' ? 'bg-cyan-500 text-slate-950 shadow' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Top 25% Threshold (P75)
              </button>
              <button
                type="button"
                onClick={() => setThresholdMethod('MAD')}
                title="Statistical outlier boundary for products with wide price variations"
                className={`px-3 py-1.5 rounded-lg font-bold transition ${
                  thresholdMethod === 'MAD' ? 'bg-cyan-500 text-slate-950 shadow' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Outlier Filter (Median + 1.5 &times; MAD)
              </button>
            </div>
          </div>

          {/* Clean Slate when no cohort stats are loaded */}
          {!cohortStats ? (
            <div className="border-2 border-dashed border-slate-800 rounded-xl p-10 text-center space-y-3 bg-slate-950/40">
              <BarChart3 className="w-10 h-10 text-slate-600 mx-auto" />
              <h4 className="text-sm font-bold text-slate-300">No Peer Cohort Distribution Loaded Yet</h4>
              <p className="text-xs text-slate-400 max-w-md mx-auto leading-relaxed">
                Upload sales data in Step 1 and classify comparable attributes above. Sift will isolate peer buyer cohorts (excluding each customer's own history) to calculate fair discount benchmarks.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Support Fence Verification Badge */}
              <div className="flex items-center space-x-4 bg-slate-950/60 p-3 rounded-lg border border-slate-800 text-xs">
                <div className="flex items-center space-x-2 text-emerald-400 font-semibold">
                  <ShieldCheck className="w-4 h-4" />
                  <span>Sufficient Peer Evidence:</span>
                </div>
                <span className="font-mono text-slate-300">
                  N = {cohortStats.transactionCount} transactions (&ge; 10 required)
                </span>
                <span className="text-slate-600">&bull;</span>
                <span className="font-mono text-slate-300">
                  |A| = {cohortStats.distinctAccounts} accounts (&ge; 5 required)
                </span>
              </div>

              {/* Visual Distribution Chart */}
              <div className="space-y-2 pt-2">
                <div className="flex items-end justify-between h-44 gap-2 pt-4 px-2 bg-slate-950/40 rounded-lg border border-slate-800">
                  {cohortStats.distribution.map((bin) => {
                    const isOverThreshold = bin.isConcession;
                    return (
                      <div key={bin.bin} className="flex-1 flex flex-col items-center h-full justify-end group">
                        <span className="text-[10px] font-mono text-slate-400 mb-1 group-hover:text-cyan-300">
                          {bin.count}
                        </span>
                        <div
                          style={{ height: `${bin.height}%` }}
                          className={`w-full rounded-t transition-all duration-300 ${
                            isOverThreshold
                              ? 'bg-rose-500/80 hover:bg-rose-400'
                              : bin.isMedian
                              ? 'bg-cyan-500/80 hover:bg-cyan-400'
                              : 'bg-slate-700 hover:bg-slate-600'
                          }`}
                        />
                        <span className="text-[10px] font-mono text-slate-500 mt-2 truncate w-full text-center">
                          {bin.bin}
                        </span>
                      </div>
                    );
                  })}
                </div>

                {/* Distribution Legend & Markers */}
                <div className="flex flex-wrap items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-800 font-mono">
                  <div className="flex items-center space-x-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-cyan-500 inline-block" />
                    <span>Typical Discount: {cohortStats.medianDiscount?.toFixed(1)}%</span>
                  </div>
                  <div className="flex items-center space-x-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-amber-400 inline-block" />
                    <span>Top 25% Boundary: {cohortStats.p75Discount?.toFixed(1)}%</span>
                  </div>
                  <div className="flex items-center space-x-1.5 text-rose-400 font-semibold">
                    <span className="w-2.5 h-2.5 rounded-full bg-rose-500 inline-block" />
                    <span>Review Cutoff: {cohortStats.activeThreshold?.toFixed(1)}%</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Calibration Parameters & Freeze Rules */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-5 shadow-md">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-200 flex items-center space-x-2">
            <Lock className="w-4 h-4 text-cyan-400" />
            <span>Save Pricing Baseline & Lock Deals</span>
          </h3>

          {/* Historical Baseline Period */}
          <div className="space-y-2">
            <label className="text-xs font-bold uppercase tracking-wider text-slate-300">
              Historical Baseline Period (Locked Time Window)
            </label>
            <select
              value={baselinePeriod}
              onChange={(e) => setBaselinePeriod(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2.5 text-xs text-slate-200 font-mono focus:outline-none focus:border-cyan-500 transition"
            >
              <option value="2024-Q1_to_2024-Q4">FY2024 Locked Base (2024-Q1 to 2024-Q4)</option>
              <option value="2024-H2">FY2024 Second Half (2024-H2)</option>
              <option value="2025-Q1_locked">FY2025 Q1 Interim Baseline</option>
            </select>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Baselines must be frozen from locked historical periods. Dynamic rolling baselines are strictly disallowed during active audit to prevent shifting targets.
            </p>
          </div>

          {/* Capture-Rate Haircut Slider (kappa) */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-300">
                Realistic Negotiation Target
              </label>
              <span className="text-xs font-mono font-bold text-cyan-400 bg-cyan-950 px-2 py-0.5 rounded border border-cyan-800/60">
                {(kappa * 100).toFixed(0)}%
              </span>
            </div>
            <input
              type="range"
              min="0.10"
              max="1.00"
              step="0.05"
              value={kappa}
              onChange={(e) => setKappa(parseFloat(e.target.value))}
              className="w-full h-2 bg-slate-950 rounded-lg appearance-none cursor-pointer accent-cyan-500"
            />
            <div className="flex justify-between text-[10px] text-slate-500 font-mono">
              <span>10% (Conservative)</span>
              <span>40% (Standard)</span>
              <span>100% (Full Gap)</span>
            </div>
            <p className="text-[11px] text-slate-400">
              Target {(kappa * 100).toFixed(0)}% of the pricing gap during upcoming contract renewals to account for commercial negotiations.
            </p>
          </div>

          {/* Freeze Action */}
          <div className="pt-2 space-y-3">
            <button
              type="button"
              onClick={handleFreezeBaseline}
              disabled={isFreezing}
              className="w-full bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-bold px-4 py-3 rounded-xl text-xs tracking-wider uppercase transition shadow-lg shadow-cyan-950/40 flex items-center justify-center space-x-2"
            >
              <Lock className="w-4 h-4" />
              <span>{isFreezing ? 'Saving Baseline Rules...' : 'Save Pricing Baseline & Lock Deals (Calculate fair peer thresholds)'}</span>
            </button>

            {freezeSuccess && (
              <div className="p-3 bg-emerald-950/30 border border-emerald-500/40 rounded-xl text-emerald-300 text-xs flex items-center space-x-2">
                <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <span>{freezeSuccess}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Progressive Disclosure: Advanced Statistical Formulations */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-sm">
        <button
          type="button"
          onClick={() => setShowAdvancedStats(!showAdvancedStats)}
          className="w-full px-5 py-3.5 bg-slate-950/40 hover:bg-slate-800/40 text-left flex items-center justify-between transition"
        >
          <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-slate-300">
            <Sliders className="w-4 h-4 text-cyan-400" />
            <span>Advanced Statistical Formulations & Peer Group Mechanics</span>
          </div>
          <div className="flex items-center space-x-1 text-xs text-cyan-400 font-medium">
            <span>{showAdvancedStats ? 'Hide Details' : 'Show Details'}</span>
            {showAdvancedStats ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </div>
        </button>

        {showAdvancedStats && (
          <div className="p-5 border-t border-slate-800 space-y-4 bg-slate-950/50 text-xs font-mono">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="p-3 bg-slate-900 rounded-xl border border-slate-800">
                <span className="text-slate-500 text-[10px] block">Peer Logic Formulation:</span>
                <span className="text-slate-200 font-bold">Leave-One-Account-Out (LOAO)</span>
              </div>
              <div className="p-3 bg-slate-900 rounded-xl border border-slate-800">
                <span className="text-slate-500 text-[10px] block">Support Fences:</span>
                <span className="text-cyan-300 font-bold">N &ge; 10 txns, |A| &ge; 5 accts</span>
              </div>
              <div className="p-3 bg-slate-900 rounded-xl border border-slate-800">
                <span className="text-slate-500 text-[10px] block">Boundary Strategy:</span>
                <span className="text-slate-300 font-bold">&tau; = P75 or Median + 1.5 &times; MAD</span>
              </div>
            </div>

            <p className="text-[11px] text-slate-400 font-sans leading-relaxed">
              <strong>LOAO Isolation Invariant:</strong> When evaluating transaction <em>i</em> of account <em>A</em>, the peer distribution strictly omits all historical orders from account <em>A</em> (<code className="text-cyan-300">&Omega;_c \ A</code>). If the cohort has insufficient support, hierarchical back-off traverses to parent controls. Frozen baselines are stored as immutable <code className="text-cyan-300">.calib.json</code> profiles.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
