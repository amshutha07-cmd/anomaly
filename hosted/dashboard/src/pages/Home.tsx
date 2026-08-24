import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Bot,
  CheckCircle2,
  Clock3,
  Database,
  FileText,
  Gauge,
  KeyRound,
  RefreshCw,
  Send,
  Settings2,
  ShieldCheck,
  Timer,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useLocation } from "wouter";
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

const formatter = new Intl.DateTimeFormat("en-GB", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "UTC",
});

function formatUtc(value?: string | null) {
  return value ? `${formatter.format(new Date(value))} UTC` : "Not available";
}

function StatusDot({ good = true }: { good?: boolean }) {
  return <span className={`status-dot ${good ? "status-dot-green" : "status-dot-amber"}`} aria-hidden="true" />;
}

function RunStatus({ status }: { status: PipelineRun["status"] }) {
  const styles = {
    running: "border-sky-400/30 bg-sky-400/10 text-sky-200",
    succeeded: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
    failed: "border-rose-400/30 bg-rose-400/10 text-rose-300",
    partial: "border-amber-400/30 bg-amber-400/10 text-amber-300",
  } as const;
  return <Badge className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${styles[status]}`}>{status}</Badge>;
}

function MetricCard({ icon: Icon, label, value, meta, tone = "blue" }: { icon: typeof Activity; label: string; value: string | number; meta: string; tone?: "blue" | "amber" | "mint" | "violet" }) {
  return (
    <Card className="veyra-card">
      <CardContent className="p-5">
        <div className="mb-6 flex items-center justify-between">
          <span className={`veyra-icon veyra-icon-${tone}`}><Icon className="h-4 w-4" /></span>
          <ArrowRight className="h-4 w-4 text-slate-600" />
        </div>
        <p className="text-3xl font-semibold tracking-[-0.04em] text-slate-100">{value}</p>
        <p className="mt-2 text-sm font-medium text-slate-300">{label}</p>
        <p className="mt-2 text-xs text-slate-500">{meta}</p>
      </CardContent>
    </Card>
  );
}

function StatusRow({ icon: Icon, label, value, good = true }: { icon: typeof Database; label: string; value: string; good?: boolean }) {
  return (
    <div className="flex items-center justify-between border-b border-white/[0.07] py-3 last:border-0">
      <div className="flex items-center gap-3"><Icon className="h-4 w-4 text-slate-500" /><span className="text-sm text-slate-300">{label}</span></div>
      <div className={`flex items-center gap-2 text-xs font-semibold ${good ? "text-emerald-300" : "text-amber-300"}`}><StatusDot good={good} />{value}</div>
    </div>
  );
}

function RunTable({ runs }: { runs: PipelineRun[] }) {
  if (!runs.length) return <EmptyState title="No pipeline cycles recorded" body="The control plane is connected, but no persisted lifecycle rows are available yet." />;
  return <div className="divide-y divide-white/[0.07]">{runs.map((run) => (
    <div key={run.run_id} className="flex flex-col gap-3 px-5 py-4 transition-colors hover:bg-white/[0.03] sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 items-center gap-4"><div className="veyra-row-icon"><Activity className="h-4 w-4" /></div><div className="min-w-0"><div className="flex flex-wrap items-center gap-3"><p className="truncate font-mono text-xs text-slate-300">{run.run_id.slice(0, 18)}…</p><RunStatus status={run.status} /></div><p className="mt-1 text-xs text-slate-500">Started {formatUtc(run.started_at)}</p></div></div>
      <div className="grid grid-cols-4 gap-5 text-right"><div><p className="text-sm font-semibold text-slate-200">{run.readings_fetched}</p><p className="text-[9px] uppercase tracking-[0.14em] text-slate-500">Readings</p></div><div><p className="text-sm font-semibold text-slate-200">{run.anomalies_count}</p><p className="text-[9px] uppercase tracking-[0.14em] text-slate-500">Anomalies</p></div><div><p className="text-sm font-semibold text-slate-200">{run.narratives_count}</p><p className="text-[9px] uppercase tracking-[0.14em] text-slate-500">Narratives</p></div><div><p className="text-sm font-semibold text-slate-200">{run.alerts_sent}</p><p className="text-[9px] uppercase tracking-[0.14em] text-slate-500">Sent</p></div></div>
    </div>
  ))}</div>;
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return <div className="flex min-h-[210px] flex-col items-center justify-center px-6 text-center"><Clock3 className="mb-4 h-7 w-7 text-slate-600" /><p className="font-medium text-slate-300">{title}</p><p className="mt-2 max-w-md text-sm leading-6 text-slate-500">{body}</p></div>;
}

export default function Home() {
  const [location] = useLocation();
  const [health, setHealth] = useState<Health | null>(null);
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  const refresh = async () => {
    setLoading(true);
    try {
      const [healthResponse, readinessResponse, runsResponse] = await Promise.all([apiFetch("/health"), apiFetch("/api/readiness"), apiFetch("/api/pipeline-runs?limit=8")]);
      if (healthResponse.ok) setHealth(await healthResponse.json());
      if (readinessResponse.ok) setReadiness(await readinessResponse.json());
      if (runsResponse.ok) setRuns(await runsResponse.json());
    } finally {
      setLastChecked(new Date());
      setLoading(false);
    }
  };

  useEffect(() => { void refresh(); }, []);

  const latestRun = runs[0];
  const successfulRuns = useMemo(() => runs.filter((run) => run.status === "succeeded").length, [runs]);
  const operational = health?.status === "ok";
  const deliveryLive = Boolean(health?.alert_delivery_enabled);
  const route = location === "/" ? "overview" : location.replace("/", "");
  const routeData: Record<string, { eyebrow: string; title: string; description: string }> = {
    overview: { eyebrow: "Veyra / Overview", title: "Market intelligence, with evidence.", description: "Detect unusual digital-asset behavior, preserve the context, and deliver controlled alerts." },
    runs: { eyebrow: "Veyra / Pipeline runs", title: "Trace every execution.", description: "A chronological record of ingestion, validation, detection, narrative, and persistence stages." },
    anomalies: { eyebrow: "Veyra / Anomaly review", title: "Review the evidence, not just the score.", description: "Historical findings are preserved with asset, detector, severity, and lifecycle context." },
    narratives: { eyebrow: "Veyra / Narrative evidence", title: "Explain why the signal mattered.", description: "AI narratives are conditional evidence generated for anomalies that need interpretation." },
    alerts: { eyebrow: "Veyra / Alert delivery", title: "Make escalation deliberate.", description: "Track the path from alert intent to Slack delivery with retries and idempotency." },
    settings: { eyebrow: "Veyra / Runtime policy", title: "Keep the boundary clear.", description: "View operational readiness without exposing provider credentials or delivery secrets." },
    configuration: { eyebrow: "Veyra / Runtime policy", title: "Keep the boundary clear.", description: "View operational readiness without exposing provider credentials or delivery secrets." },
  };
  const copy = routeData[route] ?? routeData.overview;

  const overview = (
    <>
      <section className="mb-6 grid gap-4 xl:grid-cols-[1.4fr_0.6fr]">
        <Card className="veyra-posture overflow-hidden"><CardContent className="relative flex min-h-[220px] flex-col justify-between p-7 sm:p-9"><div className="veyra-orbit veyra-orbit-one" /><div className="veyra-orbit veyra-orbit-two" /><div className="relative z-10"><div className="mb-5 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400"><StatusDot good={operational} /> Production posture</div><div className="flex flex-wrap items-baseline gap-3"><h2 className="text-3xl font-semibold tracking-[-0.04em] text-slate-100">{operational ? "Operational" : "Unavailable"}</h2><Badge className="border border-white/10 bg-white/[0.06] text-xs text-slate-300">{operational ? "API reachable" : "Check service"}</Badge></div><p className="mt-3 max-w-xl text-sm leading-6 text-slate-400">The monitoring lifecycle is connected, persisted, and ready to turn statistically unusual market behavior into an auditable alert decision.</p></div><div className="relative z-10 mt-8 grid grid-cols-3 gap-4 border-t border-white/10 pt-5"><div><p className="veyra-label">Persistence</p><p className="mt-1 text-sm font-medium text-slate-200">{health?.database_configured ? "Connected" : "Pending"}</p></div><div><p className="veyra-label">Successful cycles</p><p className="mt-1 text-sm font-medium text-slate-200">{runs.length ? successfulRuns : "—"}</p></div><div><p className="veyra-label">Last checked</p><p className="mt-1 text-sm font-medium text-slate-200">{lastChecked ? lastChecked.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}</p></div></div></CardContent></Card>
        <Card className="veyra-card"><CardHeader className="flex flex-row items-center justify-between pb-2"><CardTitle className="text-sm font-semibold text-slate-200">Readiness gate</CardTitle><Gauge className="h-4 w-4 text-blue-400" /></CardHeader><CardContent><StatusRow icon={Database} label="Run lifecycle" value={readiness?.pipeline_run_lifecycle === "ready" ? "Ready" : "Pending"} good={readiness?.pipeline_run_lifecycle === "ready"} /><StatusRow icon={ShieldCheck} label="Persistence" value={health?.database_configured ? "Connected" : "Pending"} good={Boolean(health?.database_configured)} /><StatusRow icon={Send} label="Slack delivery" value={deliveryLive ? "Live" : "Paused"} good={deliveryLive} /><StatusRow icon={KeyRound} label="Audit and idempotency" value={deliveryLive ? "Enabled" : "Standby"} good={deliveryLive} /></CardContent></Card>
      </section>
      <section className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-5"><MetricCard icon={Activity} label="Latest cycle" value={latestRun?.status ?? "—"} meta={latestRun ? formatUtc(latestRun.started_at) : "Awaiting cycle"} /><MetricCard icon={Database} label="Observations" value={latestRun?.readings_fetched ?? "—"} meta="Evaluated in latest cycle" tone="mint" /><MetricCard icon={AlertTriangle} label="Anomalies detected" value={latestRun?.anomalies_count ?? "—"} meta={latestRun ? "Threshold breaches" : "Awaiting cycle"} tone="amber" /><MetricCard icon={Bot} label="Narratives generated" value={latestRun?.narratives_count ?? "—"} meta={latestRun?.anomalies_count ? "Explanations produced" : "None required in clean cycle"} tone="violet" /><MetricCard icon={Send} label="Alerts delivered" value={latestRun?.alerts_sent ?? "—"} meta={deliveryLive ? "Slack delivery live" : "Delivery paused"} tone="blue" /></section>
      {latestRun && latestRun.anomalies_count === 0 ? <div className="veyra-callout mb-6"><CheckCircle2 className="h-5 w-5 text-emerald-300" /><div><p className="font-medium text-emerald-200">Clean cycle</p><p className="mt-1 text-sm text-slate-400">Detection completed normally. No threshold breach required a narrative or alert.</p></div></div> : null}
      <section className="grid gap-6 xl:grid-cols-[1.35fr_0.65fr]"><Card className="veyra-card"><CardHeader className="flex flex-row items-center justify-between border-b border-white/[0.07] px-6 py-5"><div><CardTitle className="text-base text-slate-100">Recent pipeline cycles</CardTitle><p className="mt-1 text-xs text-slate-500">Persisted lifecycle evidence from the hosted API</p></div><Badge className="border border-blue-400/20 bg-blue-400/10 text-[10px] uppercase tracking-[0.14em] text-blue-200">{runs.length} loaded</Badge></CardHeader><CardContent className="p-0"><RunTable runs={runs} /></CardContent></Card><Card className="veyra-card"><CardHeader><CardTitle className="text-base text-slate-100">Alert delivery</CardTitle><p className="mt-1 text-xs text-slate-500">Provider-neutral delivery control</p></CardHeader><CardContent><div className="mb-5 flex items-center gap-3"><StatusDot good={deliveryLive} /><span className={`text-2xl font-semibold ${deliveryLive ? "text-emerald-300" : "text-amber-300"}`}>{deliveryLive ? "Live" : "Paused"}</span></div><StatusRow icon={KeyRound} label="Idempotency" value={deliveryLive ? "Enforced" : "Standby"} good={deliveryLive} /><StatusRow icon={RefreshCw} label="Retries" value="Audited" good={deliveryLive} /><StatusRow icon={CheckCircle2} label="Canary" value={deliveryLive ? "Sent" : "Not run"} good={deliveryLive} /></CardContent></Card></section>
    </>
  );

  const page = route === "overview" ? overview : route === "runs" ? <section className="grid gap-6"><Card className="veyra-card"><CardHeader><CardTitle className="text-xl text-slate-100">Execution timeline</CardTitle><p className="text-sm text-slate-500">Each cycle is durable evidence of what the detector evaluated.</p></CardHeader><CardContent className="p-0"><RunTable runs={runs} /></CardContent></Card></section> : route === "anomalies" ? <section className="grid gap-6"><Card className="veyra-card"><CardHeader><CardTitle className="text-xl text-slate-100">Historical anomaly evidence</CardTitle><p className="text-sm text-slate-500">The latest clean cycle is shown alongside historical persisted findings.</p></CardHeader><CardContent><div className="grid gap-4 sm:grid-cols-3"><MetricCard icon={AlertTriangle} label="Historical findings" value={runs.reduce((sum, run) => sum + run.anomalies_count, 0)} meta="Across loaded cycles" tone="amber" /><MetricCard icon={Timer} label="Detection stage" value="Ready" meta="Statistical checks active" tone="blue" /><MetricCard icon={Database} label="Evidence store" value={health?.database_configured ? "Connected" : "Pending"} meta="Supabase persistence" tone="mint" /></div></CardContent></Card></section> : route === "narratives" ? <section className="grid gap-6"><Card className="veyra-card"><CardHeader><CardTitle className="text-xl text-slate-100">Narrative evidence</CardTitle><p className="text-sm text-slate-500">Narratives are conditional explanations, generated only when anomaly evidence requires context.</p></CardHeader><CardContent><StatusRow icon={Bot} label="Primary narrative provider" value={readiness?.groq_narratives ? "Configured" : "Pending"} good={Boolean(readiness?.groq_narratives)} /><StatusRow icon={RefreshCw} label="Fallback provider" value={readiness?.openrouter_fallback ? "Configured" : "Pending"} good={Boolean(readiness?.openrouter_fallback)} /><div className="veyra-callout mt-5"><FileText className="h-5 w-5 text-blue-300" /><p className="text-sm text-slate-400">A clean run with zero narratives is an expected outcome: there was no anomaly requiring an explanation.</p></div></CardContent></Card></section> : route === "alerts" ? <section className="grid gap-6 md:grid-cols-2"><Card className="veyra-card"><CardHeader><CardTitle className="text-xl text-slate-100">Delivery state machine</CardTitle><p className="text-sm text-slate-500">Alert intent and provider delivery are tracked separately.</p></CardHeader><CardContent><StatusRow icon={Send} label="Pending" value="Supported" /><StatusRow icon={CheckCircle2} label="Sent" value={deliveryLive ? "Live" : "Standby"} good={deliveryLive} /><StatusRow icon={RefreshCw} label="Retry" value="Audited" good={deliveryLive} /><StatusRow icon={ShieldCheck} label="Acknowledged" value="Supported" /></CardContent></Card><Card className="veyra-card"><CardHeader><CardTitle className="text-xl text-slate-100">Delivery evidence</CardTitle></CardHeader><CardContent><p className="text-4xl font-semibold text-emerald-300">{deliveryLive ? "Live" : "Paused"}</p><p className="mt-2 text-sm text-slate-500">Slack webhook delivery is governed server-side. Credentials remain outside the browser.</p></CardContent></Card></section> : <section className="grid gap-6 md:grid-cols-2"><Card className="veyra-card"><CardHeader><CardTitle className="text-xl text-slate-100">Runtime policy</CardTitle><p className="text-sm text-slate-500">Operational boundaries visible without exposing secrets.</p></CardHeader><CardContent><StatusRow icon={Database} label="Supabase persistence" value={health?.database_configured ? "Connected" : "Pending"} good={Boolean(health?.database_configured)} /><StatusRow icon={ShieldCheck} label="Authenticated API" value={operational ? "Reachable" : "Unavailable"} good={operational} /><StatusRow icon={Settings2} label="AI providers" value={readiness?.groq_narratives ? "Configured" : "Pending"} good={Boolean(readiness?.groq_narratives)} /><StatusRow icon={KeyRound} label="Secrets" value="Server-side" /></CardContent></Card><Card className="veyra-card"><CardHeader><CardTitle className="text-xl text-slate-100">Boundary principle</CardTitle></CardHeader><CardContent><p className="text-sm leading-7 text-slate-400">The dashboard reports readiness and evidence. Provider keys, database credentials, and webhook URLs never cross into the client.</p></CardContent></Card></section>;

  return <div className="veyra-shell"><div className="veyra-grid" /><div className="mx-auto max-w-[1500px] px-5 pb-14 pt-7 sm:px-8 lg:px-10"><header className="mb-8 flex flex-col justify-between gap-5 lg:flex-row lg:items-end"><div><p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.25em] text-blue-300">{copy.eyebrow}</p><h1 className="max-w-4xl text-4xl font-semibold tracking-[-0.055em] text-slate-100 sm:text-5xl">{copy.title}</h1><p className="mt-3 max-w-2xl text-base leading-7 text-slate-400">{copy.description}</p></div><div className="flex items-center gap-3"><div className="hidden text-right sm:block"><p className="veyra-label">UTC observation</p><p className="mt-1 font-mono text-xs text-slate-400">{lastChecked ? formatUtc(lastChecked.toISOString()) : "Waiting"}</p></div><Button onClick={() => void refresh()} variant="outline" className="border-white/10 bg-white/[0.04] text-slate-200 hover:bg-white/[0.08]" disabled={loading}><RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />Refresh</Button></div></header>{page}</div></div>;
}
