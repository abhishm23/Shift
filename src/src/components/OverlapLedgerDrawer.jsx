import React from 'react';
import { X, Layers, AlertCircle, ShieldAlert, Check, Copy, ArrowUpRight } from 'lucide-react';

/**
 * Overlap Ledger Drawer (R4.6, R4.7, AC-4)
 * Slide-over drawer detailing flagged transactions and displaying Deduplicated Net Unique Portfolio Exposure.
 * Highlights intersection of transactions across multi-slice findings to prevent double-counting.
 */
export default function OverlapLedgerDrawer({
  isOpen,
  onClose,
  selectedFinding,
  netUniqueExposure = 0.00,
  grossSumFindings = 0.00,
}) {
  if (!isOpen) return null;

  // Use transactions from selected finding, default to empty array (clean slate)
  const transactions = selectedFinding?.transactions || selectedFinding?.transaction_lines || [];

  const overlapDeduplicationDelta = Math.max(0, grossSumFindings - netUniqueExposure);

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/80 backdrop-blur-sm transition-opacity">
      <div className="absolute inset-0" onClick={onClose} />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-2xl bg-slate-900 border-l border-slate-800 shadow-2xl flex flex-col">
          {/* Drawer Header */}
          <div className="px-6 py-5 bg-slate-950 border-b border-slate-800 flex items-start justify-between">
            <div className="space-y-1">
              <div className="flex items-center space-x-2">
                <Layers className="w-5 h-5 text-cyan-400" />
                <h2 className="text-lg font-bold text-white tracking-wide">
                  Detailed Deal Transactions & Overlap Ledger
                </h2>
              </div>
              <p className="text-xs text-slate-400">
                Selected Deal Exception: <span className="text-cyan-300 font-mono font-semibold">{selectedFinding?.title || selectedFinding?.id || 'No finding selected'}</span>
              </p>
            </div>
            <button
              onClick={onClose}
              className="rounded-lg p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Deduplicated Portfolio Exposure Hero Invariant (R4.7 / AC-4) */}
          <div className="p-6 bg-slate-900/90 border-b border-slate-800 space-y-3">
            <div className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center justify-between">
              <span>Why We Deduplicate Overlapping Deals (Invariant AC-4)</span>
              <span className="text-[11px] font-mono text-cyan-400 font-normal">True Set Union</span>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="bg-slate-950 p-3.5 rounded-lg border border-cyan-800/40">
                <div className="text-[11px] text-slate-400 font-medium">True Non-Overlapping Exposure</div>
                <div className="text-xl font-mono font-black text-cyan-300 mt-1">
                  ${netUniqueExposure.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </div>
                <div className="text-[10px] text-cyan-500/80 mt-1 font-mono">
                  Exact set union of transaction dollars
                </div>
              </div>

              <div className="bg-slate-950 p-3.5 rounded-lg border border-slate-800">
                <div className="text-[11px] text-slate-400 font-medium">Sum of Individual Slices (Pre-Dedup)</div>
                <div className="text-xl font-mono font-bold text-slate-400 line-through mt-1">
                  ${grossSumFindings.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </div>
                <div className="text-[10px] text-amber-400 mt-1 font-mono">
                  -${overlapDeduplicationDelta.toLocaleString('en-US', { minimumFractionDigits: 2 })} double-counted overlap
                </div>
              </div>
            </div>

            <p className="text-[11px] text-slate-400 leading-relaxed">
              <strong>Plain-English Explanation:</strong> If an order has both an unapproved product discount and a sales rep concession, traditional spreadsheets add both slices together and count that money twice. Sift tracks individual invoice lines so each dollar is counted exactly once.
            </p>
          </div>

          {/* Transaction Table */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">
                Flagged Transaction Lines ({transactions.length})
              </h3>
              <span className="text-[11px] font-mono text-slate-500">Line-Grain Record</span>
            </div>

            {transactions.length === 0 ? (
              <div className="p-8 text-center bg-slate-950/60 rounded-xl border border-slate-800 space-y-2">
                <Layers className="w-8 h-8 text-slate-600 mx-auto" />
                <div className="text-xs font-bold text-slate-300">No Transaction Lines Available</div>
                <p className="text-[11px] text-slate-500 max-w-sm mx-auto">
                  Individual line-grain transactions will appear here after scanning your deal dataset.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {transactions.map((tx) => (
                  <div
                    key={tx.line_id || tx.id}
                    className="bg-slate-950 p-4 rounded-xl border border-slate-800 hover:border-slate-700 transition space-y-2.5"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <span className="font-mono text-xs font-bold text-cyan-300">{tx.line_id || tx.id}</span>
                        <span className="text-slate-600">&bull;</span>
                        <span className="font-mono text-xs text-slate-300">{tx.account_id || tx.account}</span>
                      </div>
                      <span className="font-mono text-xs font-bold text-rose-400 bg-rose-950/60 border border-rose-800/60 px-2 py-0.5 rounded">
                        +${(tx.defensible_gap || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })} Gap
                      </span>
                    </div>

                    <div className="grid grid-cols-3 gap-2 text-xs font-mono pt-1">
                      <div>
                        <span className="text-slate-500 text-[10px] block">List Price:</span>
                        <span className="text-slate-300">${(tx.list_price || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
                      </div>
                      <div>
                        <span className="text-slate-500 text-[10px] block">Net Invoiced:</span>
                        <span className="text-slate-300">${(tx.net_invoiced || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
                      </div>
                      <div>
                        <span className="text-slate-500 text-[10px] block">Concession:</span>
                        <span className="text-rose-300 font-bold">{tx.discount_pct || 0}% (P75: {tx.cohort_p75 || 0}%)</span>
                      </div>
                    </div>

                    {/* Multi-slice Overlap Badges */}
                    {tx.other_findings && tx.other_findings.length > 0 && (
                      <div className="pt-2 border-t border-slate-800/60 flex items-center space-x-2 text-[11px]">
                        <span className="text-amber-400 font-semibold flex items-center space-x-1">
                          <AlertCircle className="w-3 h-3" />
                          <span>Shared in other findings:</span>
                        </span>
                        <div className="flex flex-wrap gap-1">
                          {tx.other_findings.map((fId) => (
                            <span key={fId} className="bg-amber-950/60 border border-amber-800/50 text-amber-300 px-1.5 py-0.5 rounded font-mono text-[10px]">
                              {fId}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Drawer Footer */}
          <div className="p-4 bg-slate-950 border-t border-slate-800 flex justify-end">
            <button
              onClick={onClose}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold rounded-lg transition"
            >
              Close Ledger
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
