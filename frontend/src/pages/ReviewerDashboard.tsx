import { useState } from "react";
import { useLocation } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DashboardShell, EmptyState, SectionHeader, Icon } from "../components/DashboardShell";
import { SeverityBadge } from "../components/SeverityBadge";
import { api } from "../api/client";
import { ChartCard, DonutChart, TrendChart } from "../components/ChartCards";

export default function ReviewerDashboard() {
  const location = useLocation();
  const view = location.pathname.endsWith("/queue") ? "queue" : location.pathname.endsWith("/insights") ? "insights" : "dashboard";
  const [statusFilter, setStatusFilter] = useState("open");
  const [severityFilter, setSeverityFilter] = useState("");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string|null>(null);
  const [comment, setComment] = useState("");
  const queryClient = useQueryClient();

  const exceptions = useQuery({
    queryKey: ["exceptions", statusFilter, severityFilter, search],
    queryFn: () => api.listExceptions({ status: statusFilter, severity: severityFilter || undefined, q: search || undefined }),
  });

  const selected = exceptions.data?.find(e => e.id === selectedId) ?? null;

  const aiReview = useQuery({
    queryKey: ["ai-review", selectedId],
    queryFn: () => api.requestAIReview(selectedId as string),
    enabled: false,
  });

  const comments = useQuery({
    queryKey: ["exception-comments", selectedId],
    queryFn: () => api.listExceptionComments(selectedId as string),
    enabled: !!selectedId,
  });

  const batchBriefing = useQuery({
    queryKey: ["batch-briefing", statusFilter],
    queryFn: () => api.summarizeBatch(statusFilter),
    enabled: false,
  });

  const decision = useMutation({
    mutationFn: ({ action }: { action: string }) =>
      api.submitDecision(selectedId as string, action, aiReview.data?.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["exceptions"] });
      queryClient.invalidateQueries({ queryKey: ["summary"] });
      setSelectedId(null);
    },
  });

  const addComment = useMutation({
    mutationFn: () => api.addExceptionComment(selectedId as string, comment.trim()),
    onSuccess: () => { setComment(""); queryClient.invalidateQueries({ queryKey: ["exception-comments", selectedId] }); },
  });

  const statusTabs = [
    { key: "open", label: "Open", icon: "pending", count: null },
    { key: "in_review", label: "In Review", icon: "visibility", count: null },
    { key: "resolved", label: "Resolved", icon: "check_circle", count: null },
  ];

  return (
    <DashboardShell title={view === "queue" ? "Exception Queue" : view === "insights" ? "AI Insights" : "Reviewer Dashboard"}>
      {view === "insights" && <div className="grid grid-cols-2 gap-6 mb-8">
        <ChartCard title="Review confidence" eyebrow="AI-assisted decisions"><DonutChart value={87} label="confidence" /></ChartCard>
        <ChartCard title="Exceptions resolved" eyebrow="Weekly trend"><TrendChart values={[18, 25, 21, 36, 31, 44, 52]} color="#ffad2f" /></ChartCard>
        <ChartCard title="AI triage briefing" eyebrow="Groq batch analysis" className="col-span-2">
          <div className="space-y-3 text-sm text-subtle"><p>{batchBriefing.data?.summary || "Generate a concise review brief from the current exception queue. The model only recommends priorities; it never changes records."}</p>
            {batchBriefing.data && <p className="text-xs text-accent-light">Focus: {batchBriefing.data.recommended_focus} · Highest severity: {batchBriefing.data.top_severity}</p>}
            <button onClick={() => batchBriefing.refetch()} disabled={batchBriefing.isFetching} className="btn-primary text-xs py-2 px-3">{batchBriefing.isFetching ? "Analyzing queue..." : "Generate Groq briefing"}</button></div>
        </ChartCard>
      </div>}
      {/* Status Tabs */}
      <div className="flex items-center gap-2 mb-6">
        {statusTabs.map(tab => (
          <button key={tab.key} onClick={() => { setStatusFilter(tab.key); setSelectedId(null); }}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold transition-all duration-200 ${
              statusFilter === tab.key
                ? "bg-accent/10 text-accent-light border border-accent/20 glow-accent"
                : "glass text-subtle hover:text-white hover:bg-white/[0.04]"
            }`}>
            <Icon name={tab.icon} size={16} />
            {tab.label}
          </button>
        ))}
        <div className="flex-1" />
        <span className="text-xs text-muted">
          {exceptions.data?.length ?? 0} exception{exceptions.data?.length !== 1 ? "s" : ""}
        </span>
      </div>

      <div className="grid grid-cols-[1fr_auto] gap-3 mb-6">
        <div className="relative"><Icon name="search" size={17} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" /><input value={search} onChange={e => { setSearch(e.target.value); setSelectedId(null); }} className="input-glass pl-10 py-2.5" placeholder="Search by loan ID or borrower ID" /></div>
        <select value={severityFilter} onChange={e => { setSeverityFilter(e.target.value); setSelectedId(null); }} className="input-glass w-auto py-2.5"><option value="">All severities</option><option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select>
      </div>

      <div className="grid grid-cols-5 gap-6">
        {/* Exception Queue */}
        <div className="col-span-3">
          <div className="glass-card overflow-hidden">
            <div className="px-5 py-4 border-b border-white/[0.04] flex items-center justify-between">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <Icon name="playlist_add_check" size={18} className="text-accent-light" />
                Exception Queue
              </h3>
            </div>

            {exceptions.isLoading && (
              <div className="p-8 flex items-center justify-center gap-3">
                <div className="w-4 h-4 rounded-full border-2 border-accent/30 border-t-accent animate-spin" />
                <span className="text-sm text-subtle">Loading queue…</span>
              </div>
            )}

            {exceptions.data?.length === 0 && (
              <div className="p-8"><EmptyState message={`No ${statusFilter.replace("_"," ")} exceptions`} icon="task_alt" /></div>
            )}

            <ul className="divide-y divide-white/[0.03] max-h-[600px] overflow-y-auto">
              {exceptions.data?.map((exc, i) => (
                <li key={exc.id} onClick={() => setSelectedId(exc.id)}
                  className={`p-4 cursor-pointer transition-all duration-200 hover:bg-white/[0.02] ${
                    selectedId === exc.id ? "bg-accent/5 border-l-2 border-l-accent" : "border-l-2 border-l-transparent"
                  }`}
                  style={{ animationDelay: `${i * 50}ms` }}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-[11px] text-muted">{exc.rule_key}</span>
                    <SeverityBadge severity={exc.severity} />
                  </div>
                  <p className="text-sm text-white/90 leading-relaxed">{exc.detail?.message ?? "—"}</p>
                  <div className="flex items-center gap-3 mt-2 text-[10px] text-muted">
                    <span className="flex items-center gap-1"><Icon name="schedule" size={12} />{new Date(exc.created_at).toLocaleDateString()}</span>
                    {exc.field && <span className="flex items-center gap-1"><Icon name="data_object" size={12} />{exc.field}</span>}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Detail Panel */}
        <div className="col-span-2">
          <div className="glass-card overflow-hidden sticky top-24">
            {!selected ? (
              <div className="p-8"><EmptyState message="Select an exception to review" icon="touch_app" /></div>
            ) : (
              <div className="animate-fade-in">
                <div className="px-5 py-4 border-b border-white/[0.04]">
                  <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                    <Icon name="description" size={18} className="text-accent-light" />
                    Exception Detail
                  </h3>
                </div>

                <div className="p-5 space-y-4">
                  {/* Rule Info */}
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs text-muted">{selected.rule_key}</span>
                    <SeverityBadge severity={selected.severity} />
                  </div>
                  <p className="text-sm text-white/80 leading-relaxed">{selected.detail?.message}</p>

                  {selected.field && (
                    <div className="flex items-center gap-2 text-xs">
                      <Icon name="data_object" size={14} className="text-muted" />
                      <span className="text-subtle">Field: <span className="font-mono text-white/70">{selected.field}</span></span>
                    </div>
                  )}

                  {/* AI Assistant */}
                  <div className="glass-card p-4 border-accent/10">
                    <div className="flex items-center justify-between mb-3">
                      <span className="flex items-center gap-2 text-xs font-semibold text-accent-light">
                        <Icon name="psychology" size={16} />
                        AI Review Assistant
                      </span>
                      {!aiReview.data && (
                        <button onClick={() => aiReview.refetch()} disabled={aiReview.isFetching}
                          className="btn-primary text-xs py-1.5 px-3 flex items-center gap-1.5">
                          {aiReview.isFetching ? (
                            <><div className="w-3 h-3 rounded-full border border-white/30 border-t-white animate-spin" /> Analyzing…</>
                          ) : (
                            <><Icon name="auto_awesome" size={14} /> Explain</>
                          )}
                        </button>
                      )}
                    </div>

                    {aiReview.data && (
                      <div className="space-y-3 animate-fade-in">
                        <p className="text-sm text-white/80 leading-relaxed">
                          {(aiReview.data.response_json as {explanation?:string}).explanation}
                        </p>
                        <div className="flex items-center gap-4 text-[10px] text-muted">
                          <span className="flex items-center gap-1">
                            <Icon name="smart_toy" size={12} />
                            <span className="font-mono">{aiReview.data.model}</span>
                          </span>
                          <span className="flex items-center gap-1">
                            <Icon name="speed" size={12} />
                            {Math.round((aiReview.data.confidence??0)*100)}% confidence
                          </span>
                        </div>
                        <p className="text-[10px] italic text-muted/70 border-t border-white/[0.04] pt-2">
                          AI suggestion only — nothing changes until you act below.
                        </p>
                      </div>
                    )}
                  </div>

                  <div className="space-y-2">
                    <p className="text-xs font-semibold text-white">Reviewer notes</p>
                    <div className="max-h-24 overflow-y-auto space-y-2">{comments.data?.map(note => <p key={note.id} className="rounded-lg bg-white/[0.03] p-2 text-xs text-subtle">{note.body}</p>)}</div>
                    <div className="flex gap-2"><input value={comment} onChange={e => setComment(e.target.value)} className="input-glass py-2 text-xs" placeholder="Add a review note" /><button disabled={!comment.trim() || addComment.isPending} onClick={() => addComment.mutate()} className="btn-secondary px-3 py-2 text-xs">Add</button></div>
                  </div>

                  {/* Decision Buttons */}
                  <div className="flex gap-3 pt-2">
                    <button onClick={() => decision.mutate({ action: "approve" })}
                      className="btn-success flex-1 flex items-center justify-center gap-2" id="approve-btn">
                      <Icon name="check" size={16} /> Approve
                    </button>
                    <button onClick={() => decision.mutate({ action: "reject" })}
                      className="btn-danger flex-1 flex items-center justify-center gap-2" id="reject-btn">
                      <Icon name="close" size={16} /> Reject
                    </button>
                  </div>
                  <button onClick={() => decision.mutate({ action: "request_correction" })} className="btn-secondary w-full text-xs">Request source correction</button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
