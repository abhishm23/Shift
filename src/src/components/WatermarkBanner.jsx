import React from 'react';
import { AlertTriangle, ShieldAlert } from 'lucide-react';

/**
 * Permanent, Indelible Quarantine Watermark Banner (R2.9 / AC-8)
 * Rendered conditionally across all views whenever reconciliation residual variance exceeds 1 bp (0.01%).
 * Cannot be dismissed while variance exceeds audit guardrails.
 * Guaranteed to NEVER render on an uninitialized / clean-slate dashboard.
 */
export default function WatermarkBanner({
  residualPct = 0,
  residualDollars = 0,
  certifiedAudit = false,
  hasReconciled = false,
  forceShow = false
}) {
  // 1 bp = 0.01% = 0.0001
  // On clean slate launch (hasReconciled is false or residualPct is 0), varianceExceeded must be false.
  const varianceExceeded = forceShow || (Boolean(hasReconciled) && !certifiedAudit && Math.abs(residualPct) > 0.01);

  if (!varianceExceeded) {
    return null;
  }

  const formattedPct = Math.abs(residualPct).toFixed(2);
  const formattedDollars = Number(residualDollars || 0).toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  return (
    <div
      role="alert"
      aria-label="Quarantine Watermark Banner"
      className="sticky top-0 z-50 w-full bg-gradient-to-r from-amber-950 via-rose-950 to-amber-950 border-y-2 border-rose-500 shadow-2xl px-4 py-2 text-rose-100 flex items-center justify-between animate-pulse"
      style={{
        backgroundImage: 'repeating-linear-gradient(45deg, rgba(225, 29, 72, 0.08), rgba(225, 29, 72, 0.08) 10px, transparent 10px, transparent 20px)'
      }}
    >
      <div className="flex items-center space-x-3 mx-auto">
        <div className="p-1.5 bg-rose-600/30 rounded border border-rose-500 text-rose-400">
          <AlertTriangle className="w-5 h-5 text-rose-400 animate-bounce" />
        </div>
        <div className="flex flex-col sm:flex-row sm:items-center sm:space-x-3">
          <span className="font-mono font-black tracking-wider text-rose-300 text-sm md:text-base uppercase drop-shadow">
            UNRECONCILED RESIDUAL: {formattedPct}% ({formattedDollars}) OUTSIDE AUDIT GUARDRAILS
          </span>
          <span className="text-xs bg-rose-900/80 border border-rose-700/80 text-rose-200 px-2 py-0.5 rounded font-semibold tracking-wide">
            QUARANTINE MODE ACTIVE
          </span>
        </div>
      </div>
      <div className="hidden lg:flex items-center space-x-2 text-xs text-rose-300/80 font-mono">
        <ShieldAlert className="w-4 h-4" />
        <span>TOLERANCE: &le; 1 bp (&plusmn;0.01%)</span>
      </div>
    </div>
  );
}
