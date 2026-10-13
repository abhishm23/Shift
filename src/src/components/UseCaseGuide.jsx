import React, { useState } from 'react';
import {
  Sparkles,
  ChevronDown,
  ChevronUp,
  TrendingDown,
  Layers,
  RefreshCw,
  ShieldCheck,
  HelpCircle,
  FileCheck2,
  Sliders,
  TrendingUp,
  ArrowRight
} from 'lucide-react';

export default function UseCaseGuide() {
  const [isOpen, setIsOpen] = useState(false);
  const [activeScenario, setActiveScenario] = useState(0);

  const scenarios = [
    {
      id: 'runaway-discounts',
      icon: TrendingDown,
      badge: 'Scenario 1: Pricing Leak',
      title: 'Identifying Unintended or Runaway Customer Discounts',
      headline: 'Stop temporary deal concessions from quietly becoming permanent discounts.',
      story: 'A sales representative offers a special 35% discount to close an urgent deal at quarter-end. Six months later, the customer continues placing routine re-orders at that same 35% discount, even though standard company policy strictly limits discounts to 15%.',
      howSiftHelps: 'Sift groups orders into like-for-like peer cohorts (same product family, customer tier, and order size). It automatically flags when a specific account receives concessions far deeper than 75% of similar peer customers, calculating the exact excess discount dollars given away.',
      businessOutcome: 'Sales and finance leaders catch runaway discounts immediately instead of discovering them months later during an audit, protecting hundreds of thousands in gross profit margin.'
    },
    {
      id: 'discount-stacking',
      icon: Layers,
      badge: 'Scenario 2: Margin Erosion',
      title: 'Detecting Discount Stacking Where Multiple Promotions Erode Margins',
      headline: 'Prevent separate promotions from compounding into negative-margin deals.',
      story: 'A distributor qualifies for a 10% standard partner discount, an additional 5% regional marketing rebate, and a temporary 12% promotional discount. Separately, each discount was authorized by different managers. Combined, they slash margins by 27%, turning what appeared to be a profitable deal into an outright commercial loss.',
      howSiftHelps: 'Sift runs automated interaction checks across multiple discount programs, partner tiers, and off-invoice rebate accruals. It alerts commercial deal desks whenever compounding concessions breach true pocket margin boundaries.',
      businessOutcome: 'Eliminates hidden promotional overlap and equips finance teams with empirical evidence to establish strict compound concession caps in master contracts.'
    },
    {
      id: 'renewal-negotiations',
      icon: RefreshCw,
      badge: 'Scenario 3: Revenue Recovery',
      title: 'Discovering Pricing Benchmarks to Negotiate Higher Contract Renewal Rates',
      headline: 'Negotiate higher annual contract renewals with objective, peer-tested market data.',
      story: 'An enterprise customer is up for their annual agreement renewal. The commercial sales team wants to raise prices by 8%, but fears aggressive customer pushback without hard, defensible evidence of what comparable companies are actually paying.',
      howSiftHelps: "Sift calculates an unbiased peer benchmark by evaluating all other comparable accounts while strictly excluding this specific customer's historical orders (Leave-One-Account-Out). It demonstrates that 80% of peer accounts with similar order volume pay $120/unit, while this customer pays only $95/unit.",
      businessOutcome: 'Empowers commercial deal desks and account managers to enter renewal discussions equipped with objective, market-validated benchmarks, recovering recurring profit without damaging client goodwill.'
    },
    {
      id: 'audit-reconciliation',
      icon: ShieldCheck,
      badge: 'Scenario 4: Financial Governance',
      title: 'Verifying Sales Records Reconcile Against Accounting Before Executive Audits',
      headline: 'Ensure granular line-item data matches your official general ledger to the penny.',
      story: 'Prior to quarterly executive reviews or external financial audits, controllers must verify that detailed line-item sales spreadsheets reconcile against official General Ledger accounts. Unmatched invoices, currency translation differences, or unbooked adjustments often lead to embarrassing restatements.',
      howSiftHelps: "Sift's built-in 1 basis point (0.01%) reconciliation gate checks raw transaction list and net sales figures against your official General Ledger control totals. If numbers match within 0.01%, Sift certifies the dataset. If unexplained variances exist, residual rows are quarantined and all screens are visibly watermarked.",
      businessOutcome: 'Guarantees 100% financial data integrity before executive presentations and protects leadership from auditing penalties and reporting restatements.'
    }
  ];

  if (!isOpen) {
    return (
      <div
        onClick={() => setIsOpen(true)}
        className="bg-slate-900/80 hover:bg-slate-800/80 border border-slate-800 hover:border-slate-700 rounded-xl px-4 py-2.5 mb-5 flex items-center justify-between cursor-pointer transition select-none shadow-sm"
      >
        <div className="flex items-center space-x-3 text-xs">
          <div className="h-6 w-6 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
            <Sparkles className="w-3.5 h-3.5" />
          </div>
          <span className="font-bold text-slate-200">How Sift Works & Real-World Use Cases</span>
          <span className="text-[10px] bg-slate-950 text-cyan-400 border border-cyan-800/40 px-2 py-0.5 rounded font-mono">
            4 Commercial Scenarios
          </span>
          <span className="text-slate-500 hidden md:inline text-[11px]">
            &bull; Unintended discounts, promotional stacking, renewals, and accounting audit reconciliation
          </span>
        </div>

        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            setIsOpen(true);
          }}
          className="text-xs font-semibold text-cyan-400 hover:text-cyan-300 flex items-center space-x-1.5 bg-slate-950 border border-slate-800 px-3 py-1 rounded-lg transition hover:border-cyan-800/60"
        >
          <span>Explore Scenarios</span>
          <ChevronDown className="w-3.5 h-3.5" />
        </button>
      </div>
    );
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl mb-5 transition-all">
      {/* Collapsible Header Banner */}
      <div
        onClick={() => setIsOpen(false)}
        className="px-5 py-3.5 bg-gradient-to-r from-slate-900 via-cyan-950/20 to-slate-900 border-b border-slate-800/80 flex items-center justify-between cursor-pointer hover:bg-slate-800/50 transition select-none"
      >
        <div className="flex items-center space-x-3">
          <div className="h-8 w-8 rounded-xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 shadow-inner">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-sm font-bold text-white tracking-wide">
                How Sift Works & Real-World Use Cases
              </span>
              <span className="text-[10px] bg-cyan-950 text-cyan-300 border border-cyan-800/60 px-2 py-0.5 rounded-full font-medium">
                Layman Commercial Guide
              </span>
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            setIsOpen(false);
          }}
          className="text-xs font-semibold text-slate-400 hover:text-white flex items-center space-x-1 bg-slate-950 border border-slate-800 px-3 py-1.5 rounded-lg transition hover:border-slate-700"
        >
          <span>Collapse Guide</span>
          <ChevronUp className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Expanded Content Body */}
      {isOpen && (
        <div className="p-6 space-y-6 bg-slate-900/40">
          {/* Quick 1-2-3 Step Overview */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800/80 space-y-1.5 hover:border-cyan-900/50 transition">
              <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-cyan-400">
                <FileCheck2 className="w-4 h-4" />
                <span>1. Add & Check Data</span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                Upload sales transaction spreadsheets (.xlsx, .csv, .parquet). Sift verifies that every dollar matches your official accounting books within 0.01% before auditing.
              </p>
            </div>

            <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800/80 space-y-1.5 hover:border-amber-900/50 transition">
              <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-amber-400">
                <Sliders className="w-4 h-4" />
                <span>2. Compare Similar Deals</span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                Group like products and customer accounts together so you compare apples to apples, establishing fair and defensible discount thresholds across true peers.
              </p>
            </div>

            <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800/80 space-y-1.5 hover:border-emerald-900/50 transition">
              <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-emerald-400">
                <TrendingUp className="w-4 h-4" />
                <span>3. Discover Profit Opportunities</span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                Pinpoint high-priority margin leaks, see deduplicated cash recovery targets without double counting, and export executive-ready reports with formula injection safety.
              </p>
            </div>
          </div>

          {/* Interactive Scenario Selector Tabs */}
          <div className="space-y-4 pt-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                Select a Practical Scenario to See How It Works:
              </span>
              <span className="text-xs font-mono text-cyan-400 bg-slate-950 px-2.5 py-0.5 rounded border border-slate-800">
                Scenario {activeScenario + 1} of 4
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
              {scenarios.map((sc, idx) => {
                const Icon = sc.icon;
                const isActive = activeScenario === idx;
                return (
                  <button
                    key={sc.id}
                    type="button"
                    onClick={() => setActiveScenario(idx)}
                    className={`p-3 rounded-xl border text-left transition flex items-start space-x-2.5 ${
                      isActive
                        ? 'bg-cyan-950/40 border-cyan-500 text-white shadow-md shadow-cyan-950/30'
                        : 'bg-slate-950/40 border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
                    }`}
                  >
                    <Icon className={`w-4 h-4 flex-shrink-0 mt-0.5 ${isActive ? 'text-cyan-400' : 'text-slate-500'}`} />
                    <div className="min-w-0">
                      <div className={`text-[10px] font-bold uppercase tracking-wide ${isActive ? 'text-cyan-400' : 'text-slate-500'}`}>
                        {sc.badge.split(':')[0]}
                      </div>
                      <div className="text-xs font-semibold truncate mt-0.5">
                        {sc.title}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Active Scenario Card */}
            <div className="bg-slate-950 p-6 rounded-xl border border-slate-800 space-y-4">
              <div className="pb-3 border-b border-slate-800">
                <span className="text-xs font-bold font-mono text-cyan-400 uppercase tracking-wide">
                  {scenarios[activeScenario].badge}
                </span>
                <h4 className="text-base font-bold text-white mt-1">
                  {scenarios[activeScenario].title}
                </h4>
                <p className="text-xs text-slate-300 font-medium mt-1">
                  {scenarios[activeScenario].headline}
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-1">
                {/* Commercial Challenge */}
                <div className="space-y-1.5">
                  <div className="text-xs font-bold uppercase tracking-wider text-rose-400">
                    The Commercial Challenge
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    {scenarios[activeScenario].story}
                  </p>
                </div>

                {/* How Sift Solves It */}
                <div className="space-y-1.5">
                  <div className="text-xs font-bold uppercase tracking-wider text-cyan-400">
                    How Sift Solves It
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    {scenarios[activeScenario].howSiftHelps}
                  </p>
                </div>

                {/* Practical Business Impact */}
                <div className="space-y-1.5 bg-emerald-950/20 border border-emerald-900/40 p-4 rounded-xl">
                  <div className="text-xs font-bold uppercase tracking-wider text-emerald-400 flex items-center space-x-1.5">
                    <ShieldCheck className="w-4 h-4" />
                    <span>Tangible Business Impact</span>
                  </div>
                  <p className="text-xs text-emerald-200/90 leading-relaxed mt-1">
                    {scenarios[activeScenario].businessOutcome}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
