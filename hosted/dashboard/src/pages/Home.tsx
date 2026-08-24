import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  BellRing,
  Bot,
  Check,
  CheckCircle2,
  Clock3,
  Database,
  FileText,
  Gauge,
  Info,
  KeyRound,
  RefreshCw,
  RotateCcw,
  Send,
  Settings2,
  ShieldCheck,
  TimerReset,
  Webhook,
  XCircle,
} from "lucide-react";
import { useLocation } from "wouter";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";

type Health = {
  status?: string;
  database_configured?: boolean;
  alert_delivery_enabled?: boolean;
  alert_delivery_status?: string;
};

type Readiness = {
  pipeline_run_lifecycle?: string;
  supabase_persistence?: string;
  groq_narratives?: boolean;
  openrouter_fallback?: boolean;
  automatic_alert_delivery?: string;
};

type PipelineRun = {
  run_id: string;
  started_at: string;
  completed_at?: string | null;
  status: "running" | "succeeded" | "failed" | "partial";
  readings_fetched: number;
  anomalies_count: number;
  narratives_count: number;
  alerts_created: number;
  alerts_sent: number;
  alerts_failed: number;
  stage_timings_ms?: Record<string, number>;
  error_summary?: string | null;
};

type AlertRecord = {
  alert_id: string; anomaly_id?: number | null; narrative_id?: number | null; alert_type?: string; severity?: string; channel?: string; status?: string; attempt_count?: number; last_error?: string | null; sent_at?: string | null; idempotency_key?: string;
};
type AnomalyRecord = { id: number; run_id?: string | null; recorded_at?: string | null; asset_id?: string | null; anomaly_type?: string | null; observed_value?: number | null; reference_value?: number | null; score?: number | null; threshold_used?: number | null; detail?: string | null; created_at?: string | null };
type NarrativeRecord = { anomaly_id: number; severity?: string | null; likely_cause?: string | null; recommended_action?: string | null; narrative?: string | null; provider_used?: string | null; model_used?: string | null; latency_ms?: number | null; fallback_used?: boolean | null; created_at?: string | null; updated_at?: string | null };
type DeliveryAttempt = { attempt_id: string; alert_id: string; attempt_number: number; status: string; provider?: string | null; response_code?: number | null; error_summary?: string | null; started_at?: string | null; finished_at?: string | null; anomaly_id?: number | null; narrative_id?: number | null; alert_type?: string | null; severity?: string | null; channel?: string | null; idempotency_key?: string | null; sent_at?: string | null; acknowledged_at?: string | null };

const formatter = new Intl.DateTimeFormat("en-GB", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "UTC",
});

function formatUtc(value?: string | null) {
  return value ? `${formatter.format(new Date(value))} UTC` : "Awaiting first cycle";
}

function StatusDot({ tone }: { tone: "green" | "amber" | "red" | "slate" }) {
  return <span className={`status-dot status-dot-${tone}`} aria-hidden="true" />;
}

function ToneIcon({ tone, children }: { tone: "blue" | "amber" | "mint" | "violet"; children: React.ReactNode }) {
  return <span className={`veyra-icon veyra-icon-${tone}`}>{children}</span>;
}

function RunStatus({ status }: { status: PipelineRun["status"] }) {
  const tone = status === "succeeded" ? "mint" : status === "failed" ? "amber" : "blue";
  return (
    <span className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.14em] ${tone === "mint" ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-300" : tone === "amber" ? "border-amber-400/30 bg-amber-400/10 text-amber-300" : "border-blue-400/30 bg-blue-400/10 text-blue-300"
      }`}>
      <StatusDot tone={tone === "mint" ? "green" : tone === "amber" ? "amber" : "slate"} />{status}
    </span>
  );
}

function PageHeader({ eyebrow, title, description, focus, loading, refresh }: { eyebrow: string; title: string; description: string; focus: string; loading: boolean; refresh: () => void }) {
  return (
    <header className="relative z-10 mb-7 flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
      <div>
        <div className="mb-4 flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.24em] text-blue-400"><span className="brand-mark"><span /><span /><span /></span>{eyebrow}</div>
        <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-blue-400/25 bg-blue-400/5 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.16em] text-blue-300"><span className="h-1.5 w-1.5 rounded-full bg-blue-400" />{focus}</div>
        <h1 className="max-w-4xl text-4xl font-semibold tracking-[-0.05em] text-slate-100 sm:text-5xl">{title}</h1>
        <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-400">{description}</p>
      </div>
      <div className="flex items-center gap-3">
        <div className="hidden text-right sm:block"><p className="veyra-label">UTC observation</p><p className="mt-1 font-mono text-xs text-slate-400">{new Date().toISOString().replace("T", " ").slice(0, 19)} UTC</p><p className="mt-1 text-[10px] text-slate-600">{new Intl.DateTimeFormat("en-IN", { timeStyle: "short", timeZone: "Asia/Kolkata" }).format(new Date())} IST local context</p></div>
        <Button onClick={refresh} variant="outline" className="h-10 rounded-xl border-slate-700 bg-slate-950/70 px-4 text-slate-200 hover:bg-slate-800" disabled={loading}><RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />Refresh</Button>
      </div>
    </header>
  );
}

function Row({ icon: Icon, label, value, good, muted = false }: { icon: typeof Database; label: string; value: string; good?: boolean; muted?: boolean }) {
  return <div className="flex items-center justify-between border-b border-slate-800/80 py-3 last:border-0"><div className="flex items-center gap-3"><Icon className="h-4 w-4 text-slate-500" /><span className="text-sm text-slate-300">{label}</span></div><span className={`flex items-center gap-2 text-xs font-semibold ${muted ? "text-slate-500" : good ? "text-emerald-300" : "text-amber-300"}`}><StatusDot tone={muted ? "slate" : good ? "green" : "amber"} />{value}</span></div>;
}

export default function Home() {
  const [location] = useLocation();
  const [health, setHealth] = useState<Health | null>(null);
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [anomalies, setAnomalies] = useState<AnomalyRecord[]>([]);
  const [narratives, setNarratives] = useState<NarrativeRecord[]>([]);
  const [attempts, setAttempts] = useState<DeliveryAttempt[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  const refresh = async () => {
    setLoading(true); setError(null);
    try {
      const responses = await Promise.all([
        apiFetch("/health"), apiFetch("/api/readiness"), apiFetch("/api/pipeline-runs?limit=8"),
        apiFetch("/api/anomalies?limit=50"), apiFetch("/api/narratives?limit=50"),
        apiFetch("/api/alerts?limit=20"), apiFetch("/api/alert-delivery-attempts?limit=100"),
      ]);
      if (responses.some((response) => !response.ok)) throw new Error("One or more control-plane reads failed");
      const [nextHealth, nextReadiness, nextRuns, nextAnomalies, nextNarratives, nextAlerts, nextAttempts] = await Promise.all(responses.map((response) => response.json()));
      setHealth(nextHealth); setReadiness(nextReadiness);
      setRuns(Array.isArray(nextRuns) ? nextRuns : nextRuns.runs ?? []);
      setAnomalies(Array.isArray(nextAnomalies) ? nextAnomalies : nextAnomalies.anomalies ?? []);
      setNarratives(Array.isArray(nextNarratives) ? nextNarratives : nextNarratives.narratives ?? []);
      setAlerts(Array.isArray(nextAlerts) ? nextAlerts : nextAlerts.alerts ?? []);
      setAttempts(Array.isArray(nextAttempts) ? nextAttempts : nextAttempts.attempts ?? []);
    } catch (err) { setError(err instanceof Error ? err.message : "Control-plane data unavailable"); }
    finally { setLastChecked(new Date()); setLoading(false); }
  };

  useEffect(() => { void refresh(); }, [location]);

  const latestRun = runs[0];
  const successfulRuns = useMemo(() => runs.filter((run) => run.status === "succeeded").length, [runs]);
  const isOperational = health?.status === "ok" && Boolean(health.database_configured);
  const deliveryLive = Boolean(health?.alert_delivery_enabled);
  const route = location === "/runs" ? "runs" : location === "/anomalies" ? "anomalies" : location === "/narratives" ? "narratives" : location === "/alerts" ? "alerts" : location === "/settings" || location === "/configuration" ? "configuration" : "overview";
  const routeCopy = {
    overview: ["Veyra / Overview", "Market intelligence, with evidence.", "A decision-grade control plane for digital-asset anomalies, explanations, and accountable escalation.", "Command summary"],
    runs: ["Veyra / Pipeline runs", "Follow every monitoring cycle.", "Trace ingestion, validation, detection, explanation, and persistence across each execution.", "Execution timeline"],
    anomalies: ["Veyra / Anomaly review", "Interrogate the signal.", "Review detector findings with asset, reference, score, threshold, and observation context.", "Historical evidence"],
    narratives: ["Veyra / Narrative evidence", "Make findings legible.", "Examine analyst-readable explanations linked to persisted detector evidence.", "Explanation layer"],
    alerts: ["Veyra / Alert delivery", "Escalate with control.", "Follow each alert from idempotent intent to provider response and audit record.", "Delivery audit"],
    configuration: ["Veyra / Runtime policy", "Keep the boundary explicit.", "Verify readiness, persistence, provider configuration, and server-side secret isolation.", "Trust boundary"],
  }[route] as [string, string, string, string];

  return <div className="veyra-shell"><div className="veyra-grid" aria-hidden="true" /><div className="relative mx-auto max-w-[1500px] px-5 pb-14 pt-7 sm:px-8 lg:px-10">
    <PageHeader eyebrow={routeCopy[0]} title={routeCopy[1]} description={routeCopy[2]} focus={routeCopy[3]} loading={loading} refresh={() => void refresh()} />
    {error && <div className="veyra-callout mb-6 border-amber-400/30 bg-amber-400/5 text-amber-200"><XCircle className="mt-0.5 h-5 w-5 shrink-0" /><div><p className="font-semibold">Control-plane data unavailable</p><p className="mt-1 text-sm text-amber-200/70">{error}. The page is showing a truthful empty state rather than inventing operational metrics.</p></div></div>}
    {route === "overview" && <Overview health={health} readiness={readiness} latestRun={latestRun} runs={runs} anomalies={anomalies} narratives={narratives} alerts={alerts} successfulRuns={successfulRuns} deliveryLive={deliveryLive} isOperational={isOperational} lastChecked={lastChecked} />}
    {route === "runs" && <RunsPage runs={runs} />}
    {route === "anomalies" && <AnomaliesPage anomalies={anomalies} />}
    {route === "narratives" && <NarrativesPage narratives={narratives} readiness={readiness} />}
    {route === "alerts" && <AlertsPage alerts={alerts} attempts={attempts} deliveryLive={deliveryLive} />}
    {route === "configuration" && <ConfigurationPage health={health} readiness={readiness} deliveryLive={deliveryLive} />}
  </div></div>;
}

function Overview({ health, readiness, latestRun, runs, anomalies, narratives, alerts, successfulRuns, deliveryLive, isOperational, lastChecked }: { health: Health | null; readiness: Readiness | null; latestRun?: PipelineRun; runs: PipelineRun[]; anomalies: AnomalyRecord[]; narratives: NarrativeRecord[]; alerts: AlertRecord[]; successfulRuns: number; deliveryLive: boolean; isOperational: boolean; lastChecked: Date | null }) {
  const metrics = [
    { label: "Latest cycle", value: latestRun?.status ?? "—", meta: latestRun ? formatUtc(latestRun.started_at) : "Awaiting first cycle", icon: Activity, tone: "blue" as const },
    { label: "Observations", value: latestRun ? latestRun.readings_fetched : "—", meta: "Evaluated in latest cycle", icon: Gauge, tone: "mint" as const },
    { label: "Anomalies", value: latestRun ? latestRun.anomalies_count : "—", meta: latestRun ? "Threshold breaches in cycle" : "Awaiting cycle", icon: AlertTriangle, tone: "amber" as const },
    { label: "Narratives", value: latestRun ? latestRun.narratives_count : "—", meta: latestRun?.narratives_count ? "Generated for findings" : "None required in clean cycle", icon: Bot, tone: "violet" as const },
    { label: "Alerts", value: latestRun ? latestRun.alerts_sent : "—", meta: deliveryLive ? "Delivered through live channel" : "Delivery not configured", icon: BellRing, tone: "blue" as const },
  ];
  return <>
    <section className="mb-6 grid gap-5 lg:grid-cols-[1.55fr_0.75fr]">
      <Card className="veyra-posture overflow-hidden rounded-2xl"><CardContent className="relative p-7 sm:p-9"><div className="veyra-orbit veyra-orbit-one" /><div className="veyra-orbit veyra-orbit-two" /><div className="relative z-10"><div className="mb-5 flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400"><StatusDot tone={isOperational ? "green" : "amber"} /> Production posture <span className={isOperational ? "text-emerald-300" : "text-amber-300"}>— {isOperational ? "Operational" : "Unavailable"}</span></div><div className="flex items-center gap-3"><h2 className="text-3xl font-semibold tracking-[-0.04em] text-slate-100">{isOperational ? "Operational" : "Check service"}</h2><span className="rounded-full bg-slate-950/50 px-2.5 py-1 text-xs text-slate-300">{health?.status === "ok" ? "API reachable" : "Awaiting API"}</span></div><p className="mt-3 max-w-xl text-sm leading-6 text-slate-400">A hosted evidence layer for unusual digital-asset behavior: evaluate the cycle, persist the decision context, and deliver only controlled, auditable alerts.</p></div><div className="relative z-10 mt-8 grid grid-cols-3 gap-4 border-t border-slate-700/70 pt-5"><div><p className="veyra-label">Persistence</p><p className="mt-1 text-sm font-semibold text-slate-200">{health?.database_configured ? "Connected" : "Pending"}</p></div><div><p className="veyra-label">Successful cycles</p><p className="mt-1 text-sm font-semibold text-slate-200">{runs.length ? successfulRuns : "—"}</p></div><div><p className="veyra-label">Last checked</p><p className="mt-1 text-sm font-semibold text-slate-200">{lastChecked ? lastChecked.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}</p></div></div></CardContent></Card>
      <Card className="veyra-card rounded-2xl"><CardHeader className="flex flex-row items-center justify-between pb-3"><CardTitle className="text-sm font-semibold text-slate-200">Production posture</CardTitle><ShieldCheck className="h-4 w-4 text-emerald-300" /></CardHeader><CardContent><Row icon={Activity} label="Run lifecycle" value={readiness?.pipeline_run_lifecycle === "ready" ? "Ready" : "Pending"} good={readiness?.pipeline_run_lifecycle === "ready"} /><Row icon={Database} label="Persistence" value={health?.database_configured ? "Connected" : "Pending"} good={health?.database_configured} /><Row icon={Webhook} label="Slack delivery" value={deliveryLive ? "Live" : "Paused"} good={deliveryLive} /><Row icon={KeyRound} label="Audit and idempotency" value={deliveryLive ? "Enabled" : "Standby"} good={deliveryLive} /></CardContent></Card>
    </section>
    <section className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">{metrics.map(({ label, value, meta, icon: Icon, tone }) => <Card key={label} className="veyra-card rounded-2xl"><CardContent className="p-5"><div className="mb-6 flex items-center justify-between"><ToneIcon tone={tone}><Icon className="h-4 w-4" /></ToneIcon><ArrowUpRight className="h-4 w-4 text-slate-600" /></div><p className="text-3xl font-semibold tracking-[-0.04em] text-slate-100">{value}</p><p className="mt-2 text-sm font-semibold text-slate-300">{label}</p><p className="mt-2 min-h-8 text-xs leading-4 text-slate-500">{meta}</p></CardContent></Card>)}</section>
    <section className="mb-6 grid gap-5 lg:grid-cols-[1.15fr_0.85fr]">
      <Card className="veyra-card rounded-2xl"><CardHeader><CardTitle className="text-base text-slate-100">Historical evidence</CardTitle><p className="mt-1 text-xs text-slate-500">Persisted findings and escalation records from earlier cycles.</p></CardHeader><CardContent><div className="grid grid-cols-3 gap-4"><div><p className="text-2xl font-semibold text-amber-300">{anomalies.length}</p><p className="veyra-label">Findings</p></div><div><p className="text-2xl font-semibold text-violet-300">{narratives.length}</p><p className="veyra-label">Narratives</p></div><div><p className="text-2xl font-semibold text-blue-300">{alerts.length}</p><p className="veyra-label">Alert intents</p></div></div></CardContent></Card>
      <Card className="veyra-card rounded-2xl"><CardHeader><CardTitle className="text-base text-slate-100">Reading the evidence</CardTitle></CardHeader><CardContent><p className="text-sm leading-6 text-slate-400">The cards above summarize the latest completed cycle. Historical evidence reflects findings, narratives, and alert intents preserved from earlier cycles. A clean latest cycle can therefore show zero new anomalies while historical evidence remains available for investigation.</p></CardContent></Card>
    </section>
    <div className="veyra-callout mb-6"><Info className="mt-0.5 h-5 w-5 shrink-0 text-blue-300" /><p className="text-sm text-blue-200">{latestRun ? latestRun.anomalies_count === 0 ? "Clean cycle: detection completed normally; no threshold breach required a narrative or alert." : `${latestRun.anomalies_count} anomaly finding(s) were recorded in the latest cycle and are available for review.` : "Waiting for a persisted lifecycle cycle to interpret."}</p></div>
    <section className="grid gap-5 xl:grid-cols-[1.45fr_0.75fr]"><EvidenceCard runs={runs} /><Card className="veyra-card rounded-2xl"><CardHeader><CardTitle className="flex items-center gap-3 text-base text-slate-100"><ToneIcon tone="blue"><Send className="h-4 w-4" /></ToneIcon>Alert delivery</CardTitle></CardHeader><CardContent><p className={`text-3xl font-semibold ${deliveryLive ? "text-emerald-300" : "text-amber-300"}`}>{deliveryLive ? "Live" : "Paused"}</p><div className="mt-5 space-y-3 text-sm text-slate-400"><p className="flex items-center gap-3"><CheckCircle2 className="h-4 w-4 text-emerald-300" /> Idempotency enforced</p><p className="flex items-center gap-3"><CheckCircle2 className="h-4 w-4 text-emerald-300" /> Delivery attempts audited</p><p className="flex items-center gap-3"><CheckCircle2 className="h-4 w-4 text-emerald-300" /> Secrets remain server-side</p></div><div className="mt-6 border-t border-slate-800 pt-5 text-xs text-slate-500">A clean cycle can legitimately produce zero alerts. Live delivery describes the capability; the cycle count describes what happened in that specific run.</div></CardContent></Card></section>
  </>;
}

function EvidenceCard({ runs }: { runs: PipelineRun[] }) { return <Card className="veyra-card rounded-2xl"><CardHeader className="flex flex-row items-center justify-between border-b border-slate-800"><div><CardTitle className="text-base text-slate-100">Historical evidence — persisted findings</CardTitle><p className="mt-1 text-xs text-slate-500">Lifecycle history from the hosted API</p></div><Badge variant="outline" className="border-slate-700 bg-slate-950/50 text-[10px] uppercase tracking-[0.14em] text-slate-400">{runs.reduce((sum, run) => sum + run.anomalies_count, 0)} total in loaded runs</Badge></CardHeader><CardContent className="p-0">{runs.length ? <div className="divide-y divide-slate-800/80">{runs.slice(0, 6).map((run) => <div key={run.run_id} className="flex flex-col gap-3 px-6 py-4 sm:flex-row sm:items-center sm:justify-between"><div className="flex min-w-0 items-center gap-4"><span className="veyra-row-icon"><Activity className="h-4 w-4" /></span><div className="min-w-0"><div className="flex flex-wrap items-center gap-3"><p className="truncate font-mono text-xs text-slate-300">{run.run_id.slice(0, 18)}…</p><RunStatus status={run.status} /></div><p className="mt-1 text-xs text-slate-500">Started {formatUtc(run.started_at)}</p></div></div><div className="grid grid-cols-3 gap-5 pl-14 text-right sm:pl-0"><div><p className="text-sm font-semibold text-slate-200">{run.readings_fetched}</p><p className="veyra-label">Readings</p></div><div><p className="text-sm font-semibold text-slate-200">{run.anomalies_count}</p><p className="veyra-label">Anomalies</p></div><div><p className="text-sm font-semibold text-slate-400">{run.alerts_sent}</p><p className="veyra-label">Alerts</p></div></div></div>)}</div> : <EmptyState icon={Clock3} title="No persisted cycles yet" description="The API is reachable, but no lifecycle rows are available to interpret." />}</CardContent></Card> }

function RunsPage({ runs }: { runs: PipelineRun[] }) { return <Card className="veyra-card relative z-10 rounded-2xl"><CardHeader className="border-b border-slate-800"><CardTitle className="text-xl text-slate-100">Execution timeline</CardTitle><p className="mt-1 text-sm text-slate-500">Each cycle is durable evidence of what the detector evaluated.</p></CardHeader><CardContent className="p-0">{runs.length ? <div className="divide-y divide-slate-800/80">{runs.map((run) => <div key={run.run_id} className="grid gap-4 px-6 py-5 md:grid-cols-[1.6fr_repeat(4,0.6fr)] md:items-center"><div><div className="flex items-center gap-3"><p className="font-mono text-xs text-slate-300">{run.run_id}</p><RunStatus status={run.status} /></div><p className="mt-2 text-xs text-slate-500">Started {formatUtc(run.started_at)}{run.completed_at ? ` · Completed ${formatUtc(run.completed_at)}` : ""}</p></div><Stat label="Readings" value={run.readings_fetched} /><Stat label="Anomalies" value={run.anomalies_count} /><Stat label="Narratives" value={run.narratives_count} /><Stat label="Alerts" value={run.alerts_sent} /></div>)}</div> : <EmptyState icon={Clock3} title="No pipeline cycles recorded" description="The control plane is connected, but no persisted lifecycle rows are available yet." />}</CardContent></Card> }

function AnomaliesPage({ anomalies }: { anomalies: AnomalyRecord[] }) { return <PagePanel title="Persisted anomaly findings" subtitle="Real detector output from Supabase, with the observation that produced each finding."><div className="grid gap-4 sm:grid-cols-3"><SummaryCard icon={AlertTriangle} label="Persisted findings" value={anomalies.length} tone="amber" /><SummaryCard icon={Activity} label="Distinct assets" value={new Set(anomalies.map((item) => item.asset_id).filter(Boolean)).size} tone="blue" /><SummaryCard icon={ShieldCheck} label="Evidence status" value={anomalies.length ? "Persisted" : "Awaiting"} tone="mint" /></div><div className="mt-5 overflow-x-auto rounded-2xl border border-slate-800"><table className="w-full min-w-[900px] text-left text-xs"><thead className="bg-slate-950/60 text-[10px] uppercase tracking-[0.14em] text-slate-500"><tr><th className="px-4 py-3">Asset</th><th className="px-4 py-3">Detector</th><th className="px-4 py-3">Observed</th><th className="px-4 py-3">Reference</th><th className="px-4 py-3">Score</th><th className="px-4 py-3">Observed at</th></tr></thead><tbody className="divide-y divide-slate-800/80">{anomalies.map((item) => <tr key={item.id} className="text-slate-300"><td className="px-4 py-3 font-medium text-slate-200">{item.asset_id ?? "—"}</td><td className="px-4 py-3">{item.anomaly_type ?? "—"}</td><td className="px-4 py-3 font-mono">{item.observed_value ?? "—"}</td><td className="px-4 py-3 font-mono">{item.reference_value ?? "—"}</td><td className="px-4 py-3 font-mono text-amber-300">{item.score ?? "—"}</td><td className="px-4 py-3 text-slate-500">{formatUtc(item.recorded_at ?? item.created_at)}</td></tr>)}</tbody></table>{!anomalies.length && <EmptyState icon={AlertTriangle} title="No persisted anomaly findings" description="The API is reachable, but no detector findings are available yet." />}</div></PagePanel> }

function NarrativesPage({ narratives, readiness }: { narratives: NarrativeRecord[]; readiness: Readiness | null }) { return <PagePanel title="Narrative evidence" subtitle="The explanation layer attached to real anomaly findings."><div className="grid gap-4 sm:grid-cols-3"><SummaryCard icon={Bot} label="Persisted narratives" value={narratives.length} tone="violet" /><SummaryCard icon={CheckCircle2} label="Primary provider" value={readiness?.groq_narratives ? "Configured" : "Pending"} tone="mint" /><SummaryCard icon={RotateCcw} label="Fallback provider" value={readiness?.openrouter_fallback ? "Available" : "Pending"} tone="blue" /></div><div className="mt-5 space-y-3">{narratives.map((item) => <Card key={`${item.anomaly_id}-${item.created_at}`} className="veyra-card rounded-2xl"><CardContent className="p-5"><div className="flex flex-wrap items-center justify-between gap-3"><p className="font-mono text-xs text-slate-300">Anomaly #{item.anomaly_id}</p><Badge variant="outline" className="border-violet-400/30 text-violet-300">{item.provider_used ?? "provider recorded"}</Badge></div><p className="mt-3 text-sm leading-6 text-slate-300">{item.narrative ?? "Narrative text not returned by the API."}</p><p className="mt-3 text-xs text-slate-500">Cause: {item.likely_cause ?? "—"} · Action: {item.recommended_action ?? "—"} · {formatUtc(item.created_at)}</p></CardContent></Card>)}{!narratives.length && <EmptyState icon={Bot} title="No narratives available" description="A clean cycle may legitimately produce no narratives." />}</div></PagePanel> }

function AlertsPage({ alerts, attempts, deliveryLive }: { alerts: AlertRecord[]; attempts: DeliveryAttempt[]; deliveryLive: boolean }) { return <div className="relative z-10 space-y-5"><div className="grid gap-5 xl:grid-cols-[0.8fr_1.2fr]"><Card className="veyra-card rounded-2xl"><CardHeader><CardTitle className="text-xl text-slate-100">Delivery state machine</CardTitle><p className="mt-1 text-sm text-slate-500">Alert intent and provider delivery are tracked separately.</p></CardHeader><CardContent><Row icon={Send} label="Pending" value="Supported" good /><Row icon={CheckCircle2} label="Sent" value={deliveryLive ? "Live" : "Standby"} good={deliveryLive} /><Row icon={RotateCcw} label="Retry" value="Audited" good /><Row icon={ShieldCheck} label="Acknowledged" value="Supported" good /></CardContent></Card><Card className="veyra-card rounded-2xl"><CardHeader><CardTitle className="text-xl text-slate-100">Alert intents</CardTitle><p className="mt-1 text-sm text-slate-500">Idempotent alert records persisted by anomaly, type, and channel.</p></CardHeader><CardContent>{alerts.length ? <div className="divide-y divide-slate-800/80">{alerts.map((alert) => <div key={alert.alert_id} className="py-4"><div className="flex flex-wrap items-center justify-between gap-3"><p className="font-mono text-xs text-slate-300">{alert.alert_id}</p><Badge variant="outline" className="border-emerald-400/30 text-emerald-300">{alert.status ?? "recorded"}</Badge></div><p className="mt-2 text-xs text-slate-500">Anomaly #{alert.anomaly_id ?? "—"} · {alert.channel ?? "webhook"} · {alert.severity ?? "unclassified"} · attempts {alert.attempt_count ?? 0}</p><p className="mt-2 truncate font-mono text-[10px] text-slate-600">{alert.idempotency_key ?? "Idempotency key recorded server-side"}</p></div>)}</div> : <EmptyState icon={Send} title="No alert intents" description="A clean cycle can legitimately create no new alert intent." />}</CardContent></Card></div><Card className="veyra-card rounded-2xl"><CardHeader><CardTitle className="text-xl text-slate-100">Delivery attempt audit</CardTitle><p className="mt-1 text-sm text-slate-500">Historical Slack canary and subsequent provider responses.</p></CardHeader><CardContent>{attempts.length ? <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-xs"><thead className="text-[10px] uppercase tracking-[0.14em] text-slate-500"><tr><th className="px-3 py-3">Alert</th><th className="px-3 py-3">Attempt</th><th className="px-3 py-3">Status</th><th className="px-3 py-3">Provider</th><th className="px-3 py-3">Response</th><th className="px-3 py-3">Started</th></tr></thead><tbody className="divide-y divide-slate-800/80">{attempts.map((item) => <tr key={item.attempt_id} className="text-slate-300"><td className="px-3 py-3 font-mono">{item.alert_id.slice(0, 8)}…</td><td className="px-3 py-3">#{item.attempt_number}</td><td className="px-3 py-3 font-semibold text-emerald-300">{item.status}</td><td className="px-3 py-3">{item.provider ?? "—"}</td><td className="px-3 py-3 font-mono">{item.response_code ?? "—"}</td><td className="px-3 py-3 text-slate-500">{formatUtc(item.started_at)}</td></tr>)}</tbody></table></div> : <EmptyState icon={Send} title="No delivery attempts" description="No provider attempt records are available yet." />}</CardContent></Card></div> }

function ConfigurationPage({ health, readiness, deliveryLive }: { health: Health | null; readiness: Readiness | null; deliveryLive: boolean }) { return <div className="relative z-10 grid gap-5 xl:grid-cols-[1fr_1fr]"><PagePanel title="Runtime policy" subtitle="Operational boundaries are visible without exposing secrets."><Row icon={Database} label="Supabase persistence" value={health?.database_configured ? "Connected" : "Pending"} good={health?.database_configured} /><Row icon={ShieldCheck} label="Authenticated API" value={health?.status === "ok" ? "Reachable" : "Unavailable"} good={health?.status === "ok"} /><Row icon={Bot} label="AI providers" value={readiness?.groq_narratives ? "Configured" : "Pending"} good={readiness?.groq_narratives} /><Row icon={KeyRound} label="Secrets" value="Server-side" good /></PagePanel><PagePanel title="Boundary principle" subtitle="What the browser is allowed to know."><p className="text-sm leading-7 text-slate-400">The dashboard reports readiness and evidence. Provider keys, database credentials, and webhook URLs never cross into the client.</p><div className="mt-6 border-t border-slate-800 pt-5 text-xs leading-6 text-slate-500">Current delivery posture: <span className={deliveryLive ? "text-emerald-300" : "text-amber-300"}>{deliveryLive ? "live and audited" : "paused"}</span>.</div></PagePanel></div> }

function PagePanel({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) { return <Card className="veyra-card relative z-10 rounded-2xl"><CardHeader><CardTitle className="text-xl text-slate-100">{title}</CardTitle><p className="mt-1 text-sm text-slate-500">{subtitle}</p></CardHeader><CardContent>{children}</CardContent></Card> }
function SummaryCard({ icon: Icon, label, value, tone }: { icon: typeof Activity; label: string; value: string | number; tone: "blue" | "amber" | "mint" | "violet" }) { return <Card className="veyra-card rounded-2xl"><CardContent className="p-5"><ToneIcon tone={tone}><Icon className="h-4 w-4" /></ToneIcon><p className="mt-6 text-3xl font-semibold text-slate-100">{value}</p><p className="mt-2 text-sm text-slate-400">{label}</p></CardContent></Card> }
function Stat({ label, value }: { label: string; value: string | number }) { return <div><p className="text-lg font-semibold text-slate-100">{value}</p><p className="veyra-label">{label}</p></div> }
function EmptyState({ icon: Icon, title, description }: { icon: typeof Activity; title: string; description: string }) { return <div className="flex min-h-[260px] flex-col items-center justify-center px-6 text-center"><Icon className="mb-4 h-8 w-8 text-slate-600" /><p className="font-semibold text-slate-300">{title}</p><p className="mt-2 max-w-md text-sm leading-6 text-slate-500">{description}</p></div> }
