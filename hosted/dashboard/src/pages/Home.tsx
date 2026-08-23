import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowUpRight,
  Bot,
  CheckCircle2,
  Clock3,
  Database,
  Gauge,
  LockKeyhole,
  Radio,
  RefreshCw,
  ShieldCheck,
  TriangleAlert,
  Webhook,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useLocation } from "wouter";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "";

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
  stage_timings_ms: Record<string, number>;
  error_summary?: string | null;
};

const formatter = new Intl.DateTimeFormat("en-GB", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "UTC",
});

function formatUtc(value?: string | null) {
  return value ? `${formatter.format(new Date(value))} UTC` : "Awaiting first run";
}

function StatusDot({ tone }: { tone: "green" | "amber" | "red" | "slate" }) {
  return <span className={`status-dot status-dot-${tone}`} aria-hidden="true" />;
}

function RunStatus({ status }: { status: PipelineRun["status"] }) {
  const styles = {
    running: "border-sky-200 bg-sky-50 text-sky-700",
    succeeded: "border-emerald-200 bg-emerald-50 text-emerald-700",
    failed: "border-rose-200 bg-rose-50 text-rose-700",
    partial: "border-amber-200 bg-amber-50 text-amber-700",
  } as const;
  return <Badge className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] ${styles[status]}`}>{status}</Badge>;
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
      const [healthResponse, readinessResponse, runsResponse] = await Promise.all([
        fetch(`${API_BASE_URL}/health`),
        fetch(`${API_BASE_URL}/api/readiness`),
        fetch(`${API_BASE_URL}/api/pipeline-runs?limit=8`),
      ]);
      if (healthResponse.ok) setHealth(await healthResponse.json());
      if (readinessResponse.ok) setReadiness(await readinessResponse.json());
      if (runsResponse.ok) setRuns(await runsResponse.json());
    } catch {
      // The shell remains useful before Render is connected.
    } finally {
      setLastChecked(new Date());
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const latestRun = runs[0];
  const routeCopy = {
    "/": {
      eyebrow: "Control plane / Overview",
      title: "Hosted anomaly operations.",
      description: "A calm command surface for the crypto detection pipeline—designed for traceability before alert delivery goes live.",
      focus: "Command summary",
    },
    "/runs": {
      eyebrow: "Control plane / Run history",
      title: "Trace every execution.",
      description: "Chronological lifecycle evidence for ingestion, quality, anomaly, and narrative stages across the hosted service.",
      focus: "Execution timeline",
    },
    "/alerts": {
      eyebrow: "Control plane / Alert readiness",
      title: "Make escalation deliberate.",
      description: "A readiness view for the future alert layer—visible, auditable, and intentionally quiet until idempotency is live.",
      focus: "Triage posture",
    },
    "/settings": {
      eyebrow: "Control plane / Configuration",
      title: "Keep the boundary clear.",
      description: "A server-side configuration surface for hosted credentials, persistence, and delivery readiness.",
      focus: "Configuration boundary",
    },
  }[location as "/" | "/runs" | "/alerts" | "/settings"] ?? {
    eyebrow: "Control plane / Overview",
    title: "Hosted anomaly operations.",
    description: "A calm command surface for the crypto detection pipeline—designed for traceability before alert delivery goes live.",
    focus: "Command summary",
  };
  const systemState = health?.status === "ok" ? "Operational" : "Awaiting connection";
  const systemTone = health?.status === "ok" ? "green" : "amber";
  const successfulRuns = useMemo(() => runs.filter((run) => run.status === "succeeded").length, [runs]);

  const metrics = [
    { label: "Latest run", value: latestRun ? latestRun.status : "—", meta: latestRun ? formatUtc(latestRun.started_at) : "Hosted schedule not connected", icon: Activity, tone: "violet" },
    { label: "Anomalies", value: latestRun ? latestRun.anomalies_count : "—", meta: latestRun ? "from latest lifecycle" : "Awaiting first run", icon: TriangleAlert, tone: "amber" },
    { label: "Narratives", value: latestRun ? latestRun.narratives_count : "—", meta: readiness?.groq_narratives ? "AI stage configured" : "Provider readiness pending", icon: Bot, tone: "cyan" },
    { label: "Alerts", value: "Disabled", meta: "Module 5B not live", icon: Webhook, tone: "slate" },
  ] as const;

  return (
    <div className="ops-page">
      <div className="ops-grid" aria-hidden="true" />
      <div className="mx-auto max-w-[1440px] px-5 pb-12 pt-6 sm:px-8 lg:px-10">
        <header className="mb-8 flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
          <div>
            <div className="mb-4 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-violet-600">
              <span className="brand-mark"><span /><span /><span /></span>
              {routeCopy.eyebrow}
            </div>
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-violet-200/80 bg-violet-50/70 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-violet-700"><span className="h-1.5 w-1.5 rounded-full bg-violet-500" />{routeCopy.focus}</div>
            <h1 className="max-w-3xl text-4xl font-semibold tracking-[-0.045em] text-slate-950 sm:text-5xl">{routeCopy.title}</h1>
            <p className="mt-3 max-w-2xl text-base leading-7 text-slate-500">{routeCopy.description}</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden text-right sm:block">
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">Environment</p>
              <p className="mt-1 text-sm font-medium text-slate-700">Hosted foundation · 5A.1</p>
            </div>
            <Button onClick={() => void refresh()} variant="outline" className="h-10 rounded-xl border-slate-200 bg-white/70 px-4 text-slate-700 shadow-sm hover:bg-white" disabled={loading}>
              <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
        </header>

        <section className="mb-6 grid gap-4 lg:grid-cols-[1.45fr_0.55fr]">
          <Card className="hero-card overflow-hidden border-0 text-white shadow-[0_24px_80px_rgba(72,49,137,0.18)]">
            <CardContent className="relative flex min-h-[220px] flex-col justify-between p-7 sm:p-9">
              <div className="hero-orbit hero-orbit-one" />
              <div className="hero-orbit hero-orbit-two" />
              <div className="relative z-10 flex items-start justify-between gap-5">
                <div>
                  <div className="mb-5 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-violet-200"><StatusDot tone={systemTone} /> System posture</div>
                  <div className="flex items-baseline gap-3"><h2 className="text-3xl font-semibold tracking-[-0.035em]">{systemState}</h2><span className="rounded-full bg-white/10 px-2.5 py-1 text-xs text-violet-100">{health?.status === "ok" ? "API reachable" : "Preview shell"}</span></div>
                  <p className="mt-3 max-w-md text-sm leading-6 text-violet-100/80">Run lifecycle, persistence, and readiness are visible. Automatic alert delivery remains intentionally disabled.</p>
                </div>
                <div className="hidden rounded-2xl border border-white/10 bg-white/10 p-3 sm:block"><ShieldCheck className="h-6 w-6 text-violet-100" /></div>
              </div>
              <div className="relative z-10 mt-8 grid grid-cols-3 gap-4 border-t border-white/10 pt-5">
                <div><p className="text-[10px] uppercase tracking-[0.16em] text-violet-200/70">Database</p><p className="mt-1 text-sm font-medium">{health?.database_configured ? "Connected" : "Not connected"}</p></div>
                <div><p className="text-[10px] uppercase tracking-[0.16em] text-violet-200/70">Successful runs</p><p className="mt-1 text-sm font-medium">{runs.length ? successfulRuns : "—"}</p></div>
                <div><p className="text-[10px] uppercase tracking-[0.16em] text-violet-200/70">Last checked</p><p className="mt-1 text-sm font-medium">{lastChecked ? lastChecked.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}</p></div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-slate-200/80 bg-white/80 shadow-[0_16px_50px_rgba(31,25,51,0.06)] backdrop-blur">
            <CardHeader className="flex flex-row items-center justify-between pb-3"><CardTitle className="text-sm font-semibold text-slate-800">Readiness gate</CardTitle><Gauge className="h-4 w-4 text-violet-500" /></CardHeader>
            <CardContent className="space-y-4">
              <ReadinessRow icon={Database} label="Run lifecycle" value={readiness?.pipeline_run_lifecycle === "ready" ? "Ready" : "Pending"} good={readiness?.pipeline_run_lifecycle === "ready"} />
              <ReadinessRow icon={LockKeyhole} label="Server-side secrets" value={health?.database_configured ? "Configured" : "Pending"} good={Boolean(health?.database_configured)} />
              <ReadinessRow icon={Radio} label="Alert delivery" value="Disabled" good={false} />
              <div className="mt-5 rounded-xl border border-amber-200/80 bg-amber-50/80 p-3 text-xs leading-5 text-amber-800">Alert creation and delivery are intentionally held until Module 5B idempotency is implemented.</div>
            </CardContent>
          </Card>
        </section>

        <section className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {metrics.map(({ label, value, meta, icon: Icon, tone }) => <Card key={label} className="metric-card border-slate-200/80 bg-white/75 shadow-[0_12px_40px_rgba(31,25,51,0.045)] backdrop-blur"><CardContent className="p-5"><div className="mb-5 flex items-center justify-between"><span className={`metric-icon metric-icon-${tone}`}><Icon className="h-4 w-4" /></span><ArrowUpRight className="h-4 w-4 text-slate-300" /></div><p className="text-2xl font-semibold tracking-[-0.035em] text-slate-900">{value}</p><p className="mt-1 text-sm font-medium text-slate-700">{label}</p><p className="mt-2 truncate text-xs text-slate-400">{meta}</p></CardContent></Card>)}
        </section>

        <section className="grid gap-6 xl:grid-cols-[1.5fr_0.5fr]">
          <Card className="border-slate-200/80 bg-white/85 shadow-[0_16px_50px_rgba(31,25,51,0.06)] backdrop-blur">
            <CardHeader className="flex flex-row items-center justify-between border-b border-slate-100 px-6 py-5"><div><CardTitle className="text-base font-semibold text-slate-900">{location === "/alerts" ? "Alert readiness" : location === "/settings" ? "Configuration boundary" : "Pipeline runs"}</CardTitle><p className="mt-1 text-xs text-slate-400">{location === "/alerts" ? "Deterministic escalation is held for Module 5B" : location === "/settings" ? "Server-side environment contract" : "UTC lifecycle history from the hosted API"}</p></div><Badge variant="outline" className="rounded-full border-slate-200 bg-slate-50 text-[10px] uppercase tracking-[0.14em] text-slate-500">{runs.length ? `${runs.length} loaded` : "No runs yet"}</Badge></CardHeader>
            <CardContent className="p-0">
              {runs.length ? <div className="divide-y divide-slate-100">{runs.map((run) => <div key={run.run_id} className="flex flex-col gap-3 px-6 py-4 transition-colors hover:bg-slate-50/70 sm:flex-row sm:items-center sm:justify-between"><div className="flex min-w-0 items-center gap-4"><div className="run-icon"><Activity className="h-4 w-4" /></div><div className="min-w-0"><div className="flex items-center gap-3"><p className="truncate font-mono text-xs text-slate-700">{run.run_id.slice(0, 18)}…</p><RunStatus status={run.status} /></div><p className="mt-1 text-xs text-slate-400">Started {formatUtc(run.started_at)}</p></div></div><div className="grid grid-cols-3 gap-6 pl-14 text-right sm:pl-0"><div><p className="text-sm font-semibold text-slate-800">{run.readings_fetched}</p><p className="text-[10px] uppercase tracking-[0.12em] text-slate-400">Readings</p></div><div><p className="text-sm font-semibold text-slate-800">{run.anomalies_count}</p><p className="text-[10px] uppercase tracking-[0.12em] text-slate-400">Anomalies</p></div><div><p className="text-sm font-semibold text-slate-400">{run.alerts_sent}</p><p className="text-[10px] uppercase tracking-[0.12em] text-slate-400">Alerts</p></div></div></div>)}</div> : <div className="flex min-h-[220px] flex-col items-center justify-center px-6 text-center"><div className="mb-4 rounded-2xl bg-slate-100 p-3 text-slate-400"><Clock3 className="h-6 w-6" /></div><p className="font-medium text-slate-700">No hosted runs recorded yet</p><p className="mt-1 max-w-sm text-sm leading-6 text-slate-400">Connect the Render service and run the lifecycle endpoint to populate this view.</p></div>}
            </CardContent>
          </Card>

          <Card className="border-slate-200/80 bg-slate-950 text-white shadow-[0_16px_50px_rgba(31,25,51,0.1)]">
            <CardHeader className="pb-3"><CardTitle className="text-base font-semibold">Deployment contract</CardTitle><p className="mt-1 text-xs leading-5 text-slate-400">The foundation is ready for the next hosted milestone.</p></CardHeader>
            <CardContent className="space-y-4">
              <ContractRow icon={CheckCircle2} label="React / Vite shell" state="Ready" />
              <ContractRow icon={CheckCircle2} label="FastAPI lifecycle API" state="Ready" />
              <ContractRow icon={CheckCircle2} label="Supabase schema" state="Ready" />
              <ContractRow icon={XCircle} label="Automatic alert delivery" state="Not live" muted />
              <div className="mt-6 border-t border-white/10 pt-5"><p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Next gate</p><p className="mt-2 text-sm leading-6 text-slate-300">Deploy the API, connect the dashboard origin, then validate one complete run lifecycle.</p></div>
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  );
}

function ReadinessRow({ icon: Icon, label, value, good }: { icon: typeof Database; label: string; value: string; good: boolean }) { return <div className="flex items-center justify-between"><div className="flex items-center gap-3"><Icon className="h-4 w-4 text-slate-400" /><span className="text-sm text-slate-600">{label}</span></div><div className="flex items-center gap-2 text-xs font-medium text-slate-500"><StatusDot tone={good ? "green" : "amber"} />{value}</div></div>; }
function ContractRow({ icon: Icon, label, state, muted }: { icon: typeof CheckCircle2; label: string; state: string; muted?: boolean }) { return <div className="flex items-center justify-between border-b border-white/10 pb-3 last:border-0 last:pb-0"><div className="flex items-center gap-3"><Icon className={`h-4 w-4 ${muted ? "text-slate-600" : "text-emerald-400"}`} /><span className="text-sm text-slate-300">{label}</span></div><span className={`text-xs font-medium ${muted ? "text-slate-500" : "text-emerald-300"}`}>{state}</span></div>; }
