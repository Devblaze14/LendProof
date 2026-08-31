import { Icon } from "./DashboardShell";

const LABELS: Record<string, string> = {
  critical: "Critical", high: "High", medium: "Medium", low: "Low",
};

const STYLES: Record<string, { bg: string; text: string; dot: string; border: string; glow: string }> = {
  critical: {
    bg: "bg-red-500/10",
    text: "text-red-400",
    dot: "bg-red-400",
    border: "border-red-500/20",
    glow: "shadow-[0_0_12px_rgba(239,68,68,0.15)]",
  },
  high: {
    bg: "bg-amber-500/10",
    text: "text-amber-400",
    dot: "bg-amber-400",
    border: "border-amber-500/20",
    glow: "shadow-[0_0_12px_rgba(245,158,11,0.15)]",
  },
  medium: {
    bg: "bg-blue-500/10",
    text: "text-blue-400",
    dot: "bg-blue-400",
    border: "border-blue-500/20",
    glow: "shadow-[0_0_12px_rgba(59,130,246,0.15)]",
  },
  low: {
    bg: "bg-slate-500/10",
    text: "text-slate-400",
    dot: "bg-slate-400",
    border: "border-slate-500/20",
    glow: "",
  },
};

const ICONS: Record<string, string> = {
  critical: "error",
  high: "warning",
  medium: "info",
  low: "radio_button_unchecked",
};

/** Severity badge with icon, dot indicator, and glow effect.
 * Never color-only — accessibility compliant. */
export function SeverityBadge({ severity, showIcon = true }: { severity: string; showIcon?: boolean }) {
  const style = STYLES[severity] ?? STYLES.low;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-[11px] font-semibold tracking-wide uppercase ${style.bg} ${style.text} ${style.border} ${style.glow} transition-all`}>
      {showIcon && <Icon name={ICONS[severity] || "circle"} size={14} />}
      <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
      {LABELS[severity] ?? severity}
    </span>
  );
}

/** Compact severity indicator for tight spaces */
export function SeverityDot({ severity }: { severity: string }) {
  const style = STYLES[severity] ?? STYLES.low;
  return (
    <span className={`w-2.5 h-2.5 rounded-full ${style.dot} ${style.glow}`} title={LABELS[severity] ?? severity} />
  );
}
