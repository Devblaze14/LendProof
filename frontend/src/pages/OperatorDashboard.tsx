import { useState } from "react";
import { useLocation } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DashboardShell, StatCard, SectionHeader, EmptyState, Icon } from "../components/DashboardShell";
import { api, ApiError } from "../api/client";
import { BarChart, ChartCard, TrendChart } from "../components/ChartCards";

export default function OperatorDashboard() {
  const location = useLocation();
  const view = location.pathname.endsWith("/upload") ? "upload" : location.pathname.endsWith("/analytics") ? "analytics" : "dashboard";
  const [sourceType, setSourceType] = useState("loan_tape");
  const [message, setMessage] = useState<{text:string;type:string}|null>(null);
  const [dragActive, setDragActive] = useState(false);
  const queryClient = useQueryClient();
  const summary = useQuery({ queryKey: ["summary"], queryFn: api.summary, refetchInterval: 5000 });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => api.uploadFile(file, sourceType),
    onSuccess: (res) => {
      setMessage({ text: `Batch ${res.id.slice(0,8)}… accepted. ${res.row_count||""} rows.`, type: "success" });
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ["summary"] }), 4000);
    },
    onError: (err) => setMessage({ text: err instanceof ApiError ? err.message : "Upload failed.", type: "error" }),
  });

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDragActive(false);
    const f = e.dataTransfer.files?.[0];
    if (f?.name.endsWith(".csv")) uploadMutation.mutate(f);
    else setMessage({ text: "Please drop a .csv file", type: "error" });
  };

  const q = summary.data?.data_quality_score ?? 0;

  return (
    <DashboardShell title={view === "upload" ? "Upload Center" : view === "analytics" ? "Operations Analytics" : "Operator Dashboard"}>
      <div className="grid grid-cols-4 gap-5 mb-8">
        <StatCard label="Total Loans" value={(summary.data?.total_loans??0).toLocaleString()} icon="description" color="accent" />
        <StatCard label="Open Exceptions" value={(summary.data?.open_exceptions??0).toLocaleString()} icon="warning" color="warning" />
        <StatCard label="Resolved" value={(summary.data?.resolved_exceptions??0).toLocaleString()} icon="check_circle" color="success" />
        <StatCard label="Verified Records" value={(summary.data?.verified_records??0).toLocaleString()} icon="verified" color="info" />
      </div>

      {view === "analytics" && <div className="grid grid-cols-2 gap-6 mb-8">
        <ChartCard title="Validation throughput" eyebrow="Last 7 days"><TrendChart values={[42, 58, 51, 74, 68, 89, 96]} /></ChartCard>
        <ChartCard title="Pipeline activity" eyebrow="Current period"><BarChart values={[82, 64, 91, 48]} /></ChartCard>
      </div>}

      <div className={`grid grid-cols-3 gap-6 ${view === "analytics" ? "hidden" : ""}`}>
        <div className="col-span-2">
          <SectionHeader title="Upload Loan File" subtitle="Drag & drop or select a CSV" />
          <div className={`glass-card p-8 transition-all ${dragActive?"border-accent bg-accent/5 glow-accent":""}`}
            onDragOver={e=>{e.preventDefault();setDragActive(true)}} onDragLeave={()=>setDragActive(false)} onDrop={handleDrop}>
            <div className="text-center">
              <div className={`w-16 h-16 rounded-2xl mx-auto mb-4 flex items-center justify-center ${dragActive?"bg-accent/20 scale-110":"bg-white/[0.03]"} transition-all`}>
                <Icon name={dragActive?"cloud_upload":"upload_file"} size={32} className={dragActive?"text-accent-light":"text-subtle"} />
              </div>
              <p className="text-sm font-medium text-white mb-1">{dragActive?"Drop here":"Drag & drop CSV file"}</p>
              <p className="text-xs text-muted mb-5">Duplicate uploads rejected automatically (hash-based)</p>
              <div className="flex items-center justify-center gap-3">
                <select value={sourceType} onChange={e=>setSourceType(e.target.value)} className="input-glass w-auto" id="source-type-select">
                  <option value="loan_tape">loan_tape.csv</option>
                  <option value="servicer_update">servicer_update.csv</option>
                  <option value="document_manifest">document_manifest.csv</option>
                </select>
                <label className="btn-primary cursor-pointer flex items-center gap-2" id="file-upload-button">
                  <Icon name="folder_open" size={16} /> Choose File
                  <input type="file" accept=".csv" className="hidden"
                    onChange={e=>{const f=e.target.files?.[0];if(f)uploadMutation.mutate(f);}} />
                </label>
              </div>
              {uploadMutation.isPending && (
                <div className="mt-5 flex items-center justify-center gap-3 animate-fade-in">
                  <div className="w-4 h-4 rounded-full border-2 border-accent/30 border-t-accent animate-spin" />
                  <span className="text-sm text-accent-light">Processing…</span>
                </div>
              )}
            </div>
          </div>
          {message && (
            <div className={`mt-4 flex items-center gap-3 p-4 rounded-xl border animate-fade-in-up ${
              message.type==="success"?"bg-emerald-500/10 border-emerald-500/20 text-emerald-400":"bg-red-500/10 border-red-500/20 text-red-400"}`}>
              <Icon name={message.type==="success"?"check_circle":"error"} size={20} />
              <p className="text-sm flex-1">{message.text}</p>
              <button onClick={()=>setMessage(null)} className="opacity-50 hover:opacity-100"><Icon name="close" size={16} /></button>
            </div>
          )}
        </div>

        <div>
          <SectionHeader title="Data Quality" />
          <div className="glass-card p-6 text-center">
            <svg width={100} height={100} className="-rotate-90 mx-auto mb-3">
              <circle cx={50} cy={50} r={42} fill="none" className="progress-ring-bg" strokeWidth={8} />
              <circle cx={50} cy={50} r={42} fill="none" strokeWidth={8} strokeDasharray={263.9}
                strokeDashoffset={263.9-(q/100)*263.9} strokeLinecap="round"
                style={{stroke:q>=80?"#10b981":q>=50?"#f59e0b":"#ef4444",transition:"stroke-dashoffset 1s"}} />
            </svg>
            <span className="text-xl font-bold font-mono text-white">{q}%</span>
            <p className="text-xs text-subtle mt-1">Quality Score</p>
          </div>
        </div>
      </div>

      <div className="mt-8 glass-card p-6">
        <SectionHeader title="Ingestion Pipeline" />
        <div className="grid grid-cols-4 gap-4">
          {[{s:1,l:"Upload",d:"Hash-check for duplicates",i:"upload_file"},
            {s:2,l:"Parse",d:"Normalize & map to schema",i:"transform"},
            {s:3,l:"Validate",d:"Run configurable rules",i:"rule"},
            {s:4,l:"Route",d:"Queue exceptions or pass",i:"fork_right"}
          ].map(x=>(
            <div key={x.s} className="glass-card p-5 hover:border-accent/20 transition-all group">
              <div className="flex items-center gap-3 mb-3">
                <span className="w-7 h-7 rounded-lg bg-accent/10 flex items-center justify-center text-xs font-bold font-mono text-accent-light">{x.s}</span>
                <Icon name={x.i} size={20} className="text-subtle group-hover:text-accent-light transition-colors" />
              </div>
              <p className="text-sm font-semibold text-white mb-1">{x.l}</p>
              <p className="text-[11px] text-muted">{x.d}</p>
            </div>
          ))}
        </div>
      </div>
    </DashboardShell>
  );
}
