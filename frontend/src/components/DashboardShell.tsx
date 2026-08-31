import { ReactNode, useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { getSession, clearSession, Role } from "../api/client";

/* ─── Icon helper using Material Symbols ─── */
export function Icon({ name, className = "", size = 20 }: { name: string; className?: string; size?: number }) {
  return (
    <span className={`icon ${className}`} style={{ fontSize: size }}>
      {name}
    </span>
  );
}

/* ─── Navigation Items ─── */
const NAV_ITEMS: Record<Role, Array<{ label: string; path: string; icon: string }>> = {
  operator: [
    { label: "Dashboard", path: "/operator", icon: "dashboard" },
    { label: "Upload", path: "/operator/upload", icon: "upload_file" },
    { label: "Analytics", path: "/operator/analytics", icon: "analytics" },
  ],
  reviewer: [
    { label: "Dashboard", path: "/reviewer", icon: "dashboard" },
    { label: "Queue", path: "/reviewer/queue", icon: "playlist_add_check" },
    { label: "AI Insights", path: "/reviewer/insights", icon: "psychology" },
  ],
  consumer: [
    { label: "Dashboard", path: "/consumer", icon: "dashboard" },
    { label: "Records", path: "/consumer/records", icon: "verified" },
    { label: "Integrity", path: "/consumer/integrity", icon: "security" },
  ],
};

/* ─── Sidebar ─── */
function Sidebar({ role }: { role: Role }) {
  const location = useLocation();
  const navigate = useNavigate();
  const items = NAV_ITEMS[role] || [];

  return (
    <aside className="hidden lg:flex fixed top-0 left-0 h-screen w-[240px] glass-strong flex-col z-40">
      {/* Logo */}
      <div className="px-6 py-6 flex items-center gap-3 border-b border-white/[0.06]">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-accent to-accent-dark flex items-center justify-center glow-accent">
          <Icon name="link" className="text-white" size={18} />
        </div>
        <div>
          <h1 className="text-sm font-bold text-white tracking-tight">LendProof</h1>
          <p className="text-[10px] text-subtle tracking-widest uppercase">Verification Copilot</p>
        </div>
      </div>

      {/* Nav Links */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {items.map((item) => {
          const isActive = location.pathname === item.path ||
            (item.path !== "/" && location.pathname.startsWith(item.path) && item.label !== "Dashboard") ||
            (item.label === "Dashboard" && location.pathname === item.path);

          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200
                ${isActive
                  ? "bg-accent/10 text-accent-light border border-accent/20 glow-accent"
                  : "text-subtle hover:text-white hover:bg-white/[0.04] border border-transparent"
                }`}
            >
              <Icon name={item.icon} size={20} className={isActive ? "text-accent-light" : ""} />
              {item.label}
            </button>
          );
        })}
      </nav>

      {/* Bottom Section */}
      <div className="px-3 pb-4 space-y-2">
        <div className="glass-card p-3 rounded-xl">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-accent/30 to-accent/10 flex items-center justify-center">
              <Icon name="person" size={16} className="text-accent-light" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-white truncate">{getSession()?.name || "User"}</p>
              <p className="text-[10px] text-subtle capitalize">{role}</p>
            </div>
          </div>
        </div>
        <button
          onClick={() => { clearSession(); navigate("/"); }}
          className="w-full flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-medium text-subtle hover:text-white hover:bg-white/[0.04] transition-all"
        >
          <Icon name="logout" size={16} />
          Sign out
        </button>
      </div>
    </aside>
  );
}

/* ─── Top Bar ─── */
function TopBar({ title }: { title: string }) {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className="h-16 flex items-center justify-between px-4 sm:px-8 glass-strong border-b border-white/[0.06] sticky top-0 z-30">
      <div className="flex items-center gap-4">
        <h2 className="text-lg font-semibold text-white">{title}</h2>
      </div>
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 text-xs text-subtle">
          <Icon name="schedule" size={16} />
          <span className="font-mono">{time.toLocaleTimeString()}</span>
        </div>
        <div className="relative tooltip" data-tooltip="Notifications">
          <button className="w-9 h-9 rounded-xl glass flex items-center justify-center hover:bg-white/[0.06] transition-all">
            <Icon name="notifications" size={18} className="text-subtle" />
          </button>
          <span className="notification-dot" />
        </div>
        <button className="w-9 h-9 rounded-xl glass flex items-center justify-center hover:bg-white/[0.06] transition-all tooltip" data-tooltip="Settings">
          <Icon name="settings" size={18} className="text-subtle" />
        </button>
      </div>
    </header>
  );
}

/* ─── Main Shell ─── */
export function DashboardShell({ title, children }: { title: string; children: ReactNode }) {
  const session = getSession();
  const role = session?.role || "operator";

  return (
    <div className="min-h-screen bg-mesh">
      <Sidebar role={role} />
      <div className="ml-0 lg:ml-[240px]">
        <TopBar title={title} />
        <main className="p-4 sm:p-6 lg:p-8 animate-fade-in-up">
          {children}
        </main>
      </div>
    </div>
  );
}

/* ─── Stat Card ─── */
export function StatCard({
  label,
  value,
  icon,
  trend,
  trendUp,
  color = "accent",
}: {
  label: string;
  value: string | number;
  icon?: string;
  trend?: string;
  trendUp?: boolean;
  color?: "accent" | "success" | "danger" | "warning" | "info";
}) {
  const colorMap = {
    accent: { bg: "from-accent/20 to-accent/5", icon: "text-accent-light", ring: "ring-accent/20" },
    success: { bg: "from-emerald-500/20 to-emerald-500/5", icon: "text-emerald-400", ring: "ring-emerald-500/20" },
    danger: { bg: "from-red-500/20 to-red-500/5", icon: "text-red-400", ring: "ring-red-500/20" },
    warning: { bg: "from-amber-500/20 to-amber-500/5", icon: "text-amber-400", ring: "ring-amber-500/20" },
    info: { bg: "from-blue-500/20 to-blue-500/5", icon: "text-blue-400", ring: "ring-blue-500/20" },
  };
  const c = colorMap[color];

  return (
    <div className="glass-card stat-card p-5 group">
      <div className="flex items-start justify-between mb-3">
        <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${c.bg} ring-1 ${c.ring} flex items-center justify-center group-hover:scale-110 transition-transform duration-300`}>
          <Icon name={icon || "bar_chart"} size={20} className={c.icon} />
        </div>
        {trend && (
          <span className={`flex items-center gap-0.5 text-xs font-medium px-2 py-1 rounded-lg ${
            trendUp ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"
          }`}>
            <Icon name={trendUp ? "trending_up" : "trending_down"} size={14} />
            {trend}
          </span>
        )}
      </div>
      <p className="text-2xl font-bold text-white font-mono tracking-tight">{value}</p>
      <p className="text-xs text-subtle mt-1">{label}</p>
    </div>
  );
}

/* ─── Empty State ─── */
export function EmptyState({ message, icon = "inbox" }: { message: string; icon?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center animate-fade-in">
      <div className="w-16 h-16 rounded-2xl bg-white/[0.03] flex items-center justify-center mb-4 animate-float">
        <Icon name={icon} size={32} className="text-muted" />
      </div>
      <p className="text-sm text-subtle max-w-[300px]">{message}</p>
    </div>
  );
}

/* ─── Loading Spinner ─── */
export function LoadingSpinner({ message = "Loading..." }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12">
      <div className="w-10 h-10 rounded-full border-2 border-accent/20 border-t-accent animate-spin mb-4" />
      <p className="text-sm text-subtle">{message}</p>
    </div>
  );
}

/* ─── Section Header ─── */
export function SectionHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="flex items-center justify-between mb-6">
      <div>
        <h3 className="text-base font-semibold text-white">{title}</h3>
        {subtitle && <p className="text-xs text-subtle mt-0.5">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

/* ─── Progress Ring ─── */
export function ProgressRing({ value, size = 80, strokeWidth = 6 }: { value: number; size?: number; strokeWidth?: number }) {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (value / 100) * circumference;

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" className="progress-ring-bg" strokeWidth={strokeWidth} />
        <circle
          cx={size / 2} cy={size / 2} r={radius} fill="none"
          className="progress-ring-fill"
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <span className="absolute text-lg font-bold font-mono text-white">{Math.round(value)}%</span>
    </div>
  );
}
