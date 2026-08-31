/**
 * Signature element: interlocking chain-link glyph representing the
 * tamper-evident hash chain — the product's core differentiator.
 */
export function ChainLink({ className = "", size = 16 }: { className?: string; size?: number }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} className={className} fill="none">
      <path d="M9.5 14.5L14.5 9.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <rect x="3" y="9" width="8" height="6" rx="3" transform="rotate(-45 7 12)" stroke="currentColor" strokeWidth="1.6" />
      <rect x="13" y="9" width="8" height="6" rx="3" transform="rotate(-45 17 12)" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  );
}

export function VerifiedBadge({ hash, showFull = false }: { hash: string; showFull?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 text-xs font-medium text-emerald-400 transition-all hover:bg-emerald-500/15 hover:border-emerald-500/30">
      <span className="w-5 h-5 rounded-lg bg-emerald-500/20 flex items-center justify-center">
        <ChainLink size={12} />
      </span>
      Verified
      <span className="font-mono text-[10px] text-emerald-400/60">
        {showFull ? hash : hash.slice(0, 12)}
      </span>
    </span>
  );
}

export function IntegrityStatus({ valid, chainLength }: { valid: boolean; chainLength: number }) {
  return (
    <div className={`glass-card p-4 flex items-center gap-4 ${valid ? "glow-success" : "glow-danger"}`}>
      <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
        valid ? "bg-emerald-500/10" : "bg-red-500/10"
      }`}>
        <span className={`icon ${valid ? "text-emerald-400" : "text-red-400"}`} style={{ fontSize: 24 }}>
          {valid ? "verified_user" : "gpp_bad"}
        </span>
      </div>
      <div>
        <p className={`text-sm font-semibold ${valid ? "text-emerald-400" : "text-red-400"}`}>
          {valid ? "Chain Integrity Valid" : "Chain Integrity Broken"}
        </p>
        <p className="text-xs text-subtle mt-0.5">
          {chainLength} link{chainLength !== 1 ? "s" : ""} in hash chain
        </p>
      </div>
    </div>
  );
}
