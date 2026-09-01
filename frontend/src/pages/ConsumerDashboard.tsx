import { useState } from "react";
import { useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { DashboardShell, StatCard, SectionHeader, EmptyState, Icon } from "../components/DashboardShell";
import { VerifiedBadge, IntegrityStatus } from "../components/ChainLink";
import { api } from "../api/client";
import { ChartCard, DonutChart, TrendChart } from "../components/ChartCards";

export default function ConsumerDashboard() {
  const location = useLocation();
  const view = location.pathname.endsWith("/records")
    ? "records"
    : location.pathname.endsWith("/integrity")
      ? "integrity"
      : "dashboard";
  const summary = useQuery({ queryKey: ["summary"], queryFn: api.summary });
  const verified = useQuery({ queryKey: ["verified"], queryFn: api.listVerified });
  const [selectedVerified, setSelectedVerified] = useState<string|null>(null);

  const integrityCheck = useQuery({
    queryKey: ["integrity", selectedVerified],
    queryFn: () => api.verifyIntegrity(selectedVerified as string),
    enabled: !!selectedVerified,
  });

  const q = summary.data?.data_quality_score ?? 0;

  return (
    <DashboardShell title={view === "records" ? "Verified Records" : view === "integrity" ? "Chain Integrity" : "Data Consumer Dashboard"}>
      {/* Stats */}
      <div className="grid grid-cols-4 gap-5 mb-8">
        <StatCard label="Data Quality Score" value={`${q}%`} icon="speed" color={q>=80?"success":q>=50?"warning":"danger"} />
        <StatCard label="Verified Records" value={(summary.data?.verified_records??0).toLocaleString()} icon="verified" color="success" />
        <StatCard label="Total Loans" value={(summary.data?.total_loans??0).toLocaleString()} icon="description" color="accent" />
        <StatCard label="Open Exceptions" value={(summary.data?.open_exceptions??0).toLocaleString()} icon="warning" color="warning" />
      </div>

      {view === "dashboard" && <div className="grid grid-cols-2 gap-6 mb-8">
        <ChartCard title="Verification activity" eyebrow="Last 7 days"><TrendChart values={[30, 42, 37, 58, 54, 71, 84]} /></ChartCard>
        <ChartCard title="Data quality" eyebrow="Portfolio health"><DonutChart value={q} label="quality score" /></ChartCard>
      </div>}

      <div className={`grid grid-cols-3 gap-6 ${view === "dashboard" ? "" : "grid-cols-1"}`}>
        {/* Verified Records List */}
        <div className="col-span-2">
          <SectionHeader
            title="Verified Loan Records"
            subtitle="Hash-chain audited, tamper-evident records"
            action={
              <a href={`${import.meta.env.VITE_API_BASE_URL||"http://localhost:8000"}/api/v1/export/verified-dataset`}
                className="btn-secondary flex items-center gap-2 text-xs" id="export-csv-btn">
                <Icon name="download" size={16} /> Export CSV
              </a>
            }
          />
          <div className="glass-card overflow-hidden">
            {verified.isLoading && (
              <div className="p-8 flex items-center justify-center gap-3">
                <div className="w-4 h-4 rounded-full border-2 border-accent/30 border-t-accent animate-spin" />
                <span className="text-sm text-subtle">Loading records…</span>
              </div>
            )}
            {verified.data?.length === 0 && (
              <div className="p-8"><EmptyState message="No records verified yet — they'll appear here once a reviewer approves a loan." icon="hourglass_empty" /></div>
            )}
            <ul className="divide-y divide-white/[0.03] max-h-[500px] overflow-y-auto">
              {verified.data?.map((v, i) => (
                <li key={v.id}
                  onClick={() => setSelectedVerified(selectedVerified === v.id ? null : v.id)}
                  className={`p-4 flex items-center gap-4 cursor-pointer transition-all hover:bg-white/[0.02] ${
                    selectedVerified === v.id ? "bg-accent/5 border-l-2 border-l-emerald-400" : "border-l-2 border-l-transparent"
                  }`}
                  style={{ animationDelay: `${i*30}ms` }}>
                  <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center flex-shrink-0">
                    <Icon name="verified" size={20} className="text-emerald-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-white font-mono truncate">
                      {v.loan_record_id.slice(0,16)}…
                    </p>
                    <p className="text-[10px] text-muted flex items-center gap-2 mt-0.5">
                      <Icon name="schedule" size={12} />
                      {new Date(v.verified_at).toLocaleString()}
                    </p>
                  </div>
                  <VerifiedBadge hash={v.record_hash} />
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Integrity Panel */}
        <div className={view === "records" ? "hidden" : "space-y-6"}>
          <SectionHeader title="Chain Integrity" subtitle="Verify tamper-evidence" />

          {!selectedVerified ? (
            <div className="glass-card p-8">
              <EmptyState message="Select a verified record to check its hash-chain integrity" icon="security" />
            </div>
          ) : integrityCheck.isLoading ? (
            <div className="glass-card p-8 flex items-center justify-center gap-3">
              <div className="w-4 h-4 rounded-full border-2 border-accent/30 border-t-accent animate-spin" />
              <span className="text-sm text-subtle">Verifying chain…</span>
            </div>
          ) : integrityCheck.data ? (
            <div className="animate-fade-in space-y-4">
              <IntegrityStatus valid={integrityCheck.data.valid} chainLength={integrityCheck.data.chain_length} />
              <div className="glass-card p-4 space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted">Chain Length</span>
                  <span className="font-mono text-white">{integrityCheck.data.chain_length}</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted">Status</span>
                  <span className={integrityCheck.data.valid ? "text-emerald-400" : "text-red-400"}>
                    {integrityCheck.data.valid ? "✓ Valid" : "✗ Broken"}
                  </span>
                </div>
                {integrityCheck.data.broken_at_index !== null && (
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted">Broken At</span>
                    <span className="font-mono text-red-400">Index {integrityCheck.data.broken_at_index}</span>
                  </div>
                )}
              </div>
            </div>
          ) : null}

          {/* Quality Overview */}
          <SectionHeader title="Quality Overview" />
          <div className="glass-card p-5 text-center">
            <svg width={90} height={90} className="-rotate-90 mx-auto mb-2">
              <circle cx={45} cy={45} r={38} fill="none" className="progress-ring-bg" strokeWidth={7} />
              <circle cx={45} cy={45} r={38} fill="none" strokeWidth={7}
                strokeDasharray={238.8} strokeDashoffset={238.8-(q/100)*238.8}
                strokeLinecap="round" style={{stroke:q>=80?"#10b981":q>=50?"#f59e0b":"#ef4444",transition:"stroke-dashoffset 1s"}} />
            </svg>
            <p className="text-lg font-bold font-mono text-white">{q}%</p>
            <p className="text-[11px] text-subtle mt-0.5">Data Quality Score</p>
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
