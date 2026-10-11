import {
  AlertTriangle,
  ArrowLeft,
  BookOpen,
  ChevronDown,
  Download,
  FileWarning,
  FlaskConical,
  Info,
  Plus,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import { ReactNode, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Alert, Badge, Button, CheckIcon, EmptyState, PageLoader, StatusChip, VerificationBadge, cx } from "../components/ui";
import { api, ApiError, download } from "../lib/api";
import { date, EVIDENCE_LABELS, fmt, range } from "../lib/format";
import type { AssessmentRecord, Candidate, ChemItem, Source } from "../lib/types";

const STATUS_COLOR: Record<string, string> = {
  suitable: "#2D7771",
  conditional: "#C29B58",
  insufficient_evidence: "#A3AAA7",
  unsuitable: "#C4552B",
};

export default function Results() {
  const { token } = useParams();
  const location = useLocation();
  const [rec, setRec] = useState<AssessmentRecord | null>((location.state as AssessmentRecord) || null);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    if (rec && rec.reference === token) return;
    api<AssessmentRecord>(`/api/assessments/${token}`)
      .then(setRec)
      .catch((e) => setError(e instanceof ApiError && e.status === 404 ? "This assessment could not be found." : (e as Error).message));
  }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  if (error)
    return (
      <div className="mx-auto max-w-3xl px-5 py-20">
        <EmptyState icon={<FileWarning className="h-8 w-8" />} title="Assessment unavailable">
          {error}{" "}
          <Link to="/assess" className="text-teal underline">Start a new assessment</Link>.
        </EmptyState>
      </div>
    );
  if (!rec) return <PageLoader label="Loading results" />;

  const { result: r, inputs } = rec;
  const sources = new Map(r.sources.map((s) => [s.id, s]));

  async function getReport() {
    setDownloading(true);
    try {
      await download(`/api/assessments/${rec!.reference}/report.pdf`, "RO-recommendation.pdf");
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setDownloading(false);
    }
  }

  const rc = r.recommended;
  return (
    <div className="pb-20">
      {/* Header band */}
      <section className="border-b border-line bg-ivory-200/40">
        <div className="mx-auto max-w-7xl px-5 pb-8 pt-8 lg:px-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <Link to="/assess" className="inline-flex items-center gap-1.5 text-[13px] text-graphite-500 hover:text-midnight">
              <ArrowLeft className="h-3.5 w-3.5" /> Edit inputs
            </Link>
            <div className="flex items-center gap-2">
              <Link to="/assess" onClick={() => { try { localStorage.removeItem("osmora.assessment.draft.v1"); } catch { /* ignore */ } }}>
                <Button variant="secondary" size="md"><Plus className="h-4 w-4" /> New assessment</Button>
              </Link>
              <Button onClick={getReport} loading={downloading}>
                <Download className="h-4 w-4" /> Technical report (PDF)
              </Button>
            </div>
          </div>
          <div className="mt-6 flex flex-wrap items-baseline gap-x-4 gap-y-1 text-[12.5px] text-graphite-500">
            <span className="eyebrow">{r.application_label}</span>
            {(r.input_origin ?? inputs.input_origin) === "demo" && <Badge tone="alert">Demonstration data — not a measured analysis</Badge>}
            <span>{inputs.client?.project_name || "Untitled project"}</span>
            <span className="num">Ref {rec.reference.slice(0, 10).toUpperCase()}</span>
            <span>{date(rec.created_at)}</span>
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-7xl px-5 lg:px-8">
        {/* Verdict */}
        <section className="-mt-px grid gap-6 pt-8 lg:grid-cols-[1.6fr_1fr]">
          <Verdict rec={rec} />
          <FlowCard rec={rec} />
        </section>

        <div className="mt-6">
          <Alert tone="info" title="Preliminary engineering estimate">
            Indicative values derived from manufacturer ratings and published evidence under the assumptions listed below. They
            are not a certified manufacturer projection and will not exactly match a real installation.
          </Alert>
        </div>

        {/* Warnings */}
        {r.warnings.filter((w) => w.severity !== "info").length > 0 && (
          <section className="mt-12">
            <SectionTitle eyebrow="Attention" title="Important considerations" />
            <div className="grid gap-3 md:grid-cols-2">
              {r.warnings.map((w, i) => (
                <Alert key={i} tone={w.severity === "critical" ? "critical" : w.severity === "caution" ? "caution" : "info"} title={w.title}>
                  {w.message}
                </Alert>
              ))}
            </div>
          </section>
        )}

        {/* Recommended */}
        {rc && (
          <section className="mt-12">
            <SectionTitle eyebrow="Recommended candidate" title={rc.name} />
            <CandidateDetail c={rc} sources={sources} defaultOpen />
          </section>
        )}

        {/* Comparison charts */}
        <Comparison rec={rec} />

        {/* Alternatives */}
        <section className="mt-12">
          <SectionTitle eyebrow="Ranked alternatives" title={r.alternatives.length ? "Other candidates to evaluate" : "Alternatives"}>
            Ordered by screening status first, then by your priority ({r.priority_label.toLowerCase()}), then by strength of evidence.
          </SectionTitle>
          {r.alternatives.length === 0 ? (
            <EmptyState title="No alternative passed the screening">Candidates with missing evidence or failed checks are listed below.</EmptyState>
          ) : (
            <div className="space-y-3">
              {r.alternatives.map((c) => (
                <CandidateDetail key={c.membrane_id} c={c} sources={sources} />
              ))}
            </div>
          )}
        </section>

        {/* Needs more data / excluded */}
        <section className="mt-12 grid gap-6 lg:grid-cols-2">
          <ReasonList
            icon={<Info className="h-4 w-4 text-graphite-400" />}
            title="Not enough evidence to assess"
            text="These membranes may be suitable, but the dataset lacks the specifications needed to confirm it."
            items={r.needs_more_data}
          />
          <ReasonList
            icon={<ShieldAlert className="h-4 w-4 text-alert" />}
            title="Excluded"
            text="These membranes fail at least one hard constraint for your conditions."
            items={r.excluded}
          />
        </section>

        {/* Chemistry */}
        <section className="mt-12">
          <SectionTitle eyebrow="Water chemistry" title="Scaling, fouling and feed quality">
            Analysis completeness: <span className="font-medium text-midnight">{r.chemistry.completeness}</span>
            {r.chemistry.missing_core.length > 0 && <> — missing {r.chemistry.missing_core.join(", ")}</>}.
          </SectionTitle>
          <ChemistryPanel items={r.chemistry.items} />
        </section>

        {/* Assumptions */}
        <section className="mt-12 grid gap-6 lg:grid-cols-2">
          <Accordion title="Assumptions behind these estimates" icon={<FlaskConical className="h-4 w-4 text-teal" />} defaultOpen>
            <ul className="space-y-2">
              {r.assumptions.map((a) => <li key={a} className="flex gap-2"><span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-teal" />{a}</li>)}
            </ul>
          </Accordion>
          <Accordion title="Limitations and what is not modelled" icon={<AlertTriangle className="h-4 w-4 text-brass-600" />} defaultOpen>
            <ul className="space-y-2">
              {r.limitations.map((a) => <li key={a} className="flex gap-2"><span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-brass" />{a}</li>)}
            </ul>
            <div className="mt-4 text-[11px] font-semibold uppercase tracking-wider text-graphite-400">Not yet modelled</div>
            <ul className="mt-2 space-y-1.5 text-graphite-500">
              {r.unavailable.map((a) => <li key={a}>— {a}</li>)}
            </ul>
          </Accordion>
        </section>

        {/* Sources */}
        <section className="mt-12">
          <SectionTitle eyebrow="Evidence" title="Sources" />
          <SourcesList sources={r.sources} />
        </section>
      </div>
    </div>
  );
}

function SectionTitle({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return (
    <div className="mb-5">
      <div className="eyebrow">{eyebrow}</div>
      <h2 className="mt-1.5 text-[26px] leading-tight">{title}</h2>
      {children && <p className="mt-1.5 max-w-3xl text-[13.5px] text-graphite-500">{children}</p>}
    </div>
  );
}

function Verdict({ rec }: { rec: AssessmentRecord }) {
  const r = rec.result;
  const c = r.recommended;
  const ok = r.outcome === "recommended";
  return (
    <div className={cx("relative overflow-hidden rounded-[3px] p-7 shadow-lift sm:p-9", ok ? "bg-midnight text-ivory" : "border border-alert/30 bg-ivory-50")}>
      {ok && <div className="grid-lines absolute inset-0 opacity-70" />}
      <div className="relative">
        <div className="flex flex-wrap items-center gap-3">
          {ok ? <ShieldCheck className="h-5 w-5 text-brass" /> : <ShieldAlert className="h-5 w-5 text-alert" />}
          {c ? <StatusChip status={c.status} label={c.status_label} /> : <StatusChip status="unsuitable" label="No supported recommendation" />}
        </div>
        <h1 className={cx("mt-5 text-[30px] leading-[1.1] sm:text-[38px]", ok ? "text-ivory" : "text-midnight")}>{r.headline}</h1>
        <p className={cx("mt-3 max-w-2xl text-[14.5px] leading-relaxed", ok ? "text-ivory/70" : "text-graphite-500")}>{r.summary}</p>
        {c && (
          <>
            <div className="mt-8 grid grid-cols-2 gap-6 border-t border-ivory/10 pt-6 sm:grid-cols-4">
              <Metric dark label="Feed pressure" value={range(c.estimates.required_pressure_bar, c.estimates.required_pressure_high_bar)} unit="bar"
                sub={`of ${fmt(rec.inputs.available_pressure_bar)} bar available`} />
              <Metric dark label="Permeate TDS" value={range(c.estimates.permeate_tds_mg_l, c.estimates.permeate_tds_high_mg_l)} unit="mg/L"
                sub={rec.inputs.target_permeate_tds_mg_l != null ? `target ${fmt(rec.inputs.target_permeate_tds_mg_l)} mg/L` : c.estimates.permeate_confidence === "low" ? "low confidence" : "rough estimate"} />
              <Metric dark label="Elements" value={c.estimates.elements_required != null ? `≈ ${fmt(c.estimates.elements_required)}` : null}
                sub={`membrane-level estimate${c.element_size ? ` · ${c.element_size}` : ""}; not a plant layout`} />
              <Metric dark label="Evidence" value={<span className="font-sans text-[15px] font-medium">{c.evidence.level}</span>}
                sub={`${c.evidence.verified_critical_params}/${c.evidence.critical_params_total} key values verified`} />
            </div>
            {c.positives.length > 0 && (
              <div className="mt-6 flex flex-wrap gap-2">
                {c.positives.map((p) => (
                  <span key={p} className="rounded-full border border-ivory/15 px-3 py-1 text-[12px] text-ivory/75">{p}</span>
                ))}
              </div>
            )}
          </>
        )}
        {!c && (
          <div className="mt-6 rounded-[3px] border border-line bg-white/60 p-4 text-[13.5px] text-graphite-500">
            <div className="font-medium text-midnight">What you can do</div>
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {r.system.checks.some((x) => x.status === "fail") && <li>Review the feed-flow, pressure or recovery targets flagged below.</li>}
              {r.chemistry.completeness !== "complete" && <li>Complete the water analysis (pH, calcium/hardness, alkalinity, SDI or turbidity).</li>}
              {r.needs_more_data.length > 0 && <li>Ask suppliers for full datasheets for the candidates listed as lacking evidence.</li>}
              <li>Consult a membrane supplier for a detailed projection.</li>
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

function Metric({ label, value, unit, sub, dark }: { label: string; value: ReactNode; unit?: string; sub?: string; dark?: boolean }) {
  const empty = value === null || value === undefined;
  return (
    <div className="min-w-0">
      <div className={cx("text-[10.5px] font-semibold uppercase tracking-wider", dark ? "text-ivory/45" : "text-graphite-400")}>{label}</div>
      <div className="mt-1.5 flex items-baseline gap-1">
        <span className={cx("num text-[22px] leading-none", dark ? "text-ivory" : "text-midnight", empty && "text-[14px] opacity-60")}>
          {empty ? "Not estimated" : value}
        </span>
        {!empty && unit && <span className={cx("text-[11.5px]", dark ? "text-ivory/50" : "text-graphite-400")}>{unit}</span>}
      </div>
      {sub && <div className={cx("mt-1 text-[11.5px]", dark ? "text-ivory/45" : "text-graphite-400")}>{sub}</div>}
    </div>
  );
}

function FlowCard({ rec }: { rec: AssessmentRecord }) {
  const f = rec.result.system.flow;
  const pPerm = f.permeate_m3d / f.feed_m3d;
  const W = 300;
  const feedH = 54;
  const permH = Math.max(6, feedH * pPerm);
  const concH = Math.max(6, feedH - permH);
  return (
    <div className="panel flex flex-col p-6 shadow-lift">
      <div className="eyebrow">Flow balance</div>
      <div className="mt-1 text-[13px] text-graphite-500">At {fmt(f.recovery_pct, 0)}% recovery</div>
      <svg viewBox={`0 0 ${W} 150`} className="mt-4 w-full" role="img" aria-label="Feed splits into permeate and concentrate">
        <defs>
          <linearGradient id="perm" x1="0" x2="1"><stop offset="0" stopColor="#1F4646" /><stop offset="1" stopColor="#2D7771" /></linearGradient>
          <linearGradient id="conc" x1="0" x2="1"><stop offset="0" stopColor="#1F4646" /><stop offset="1" stopColor="#C29B58" /></linearGradient>
        </defs>
        <rect x="0" y={75 - feedH / 2} width="110" height={feedH} fill="#1F4646" />
        <rect x="110" y={75 - feedH / 2 - 8} width="34" height={feedH + 16} fill="#102A2A" rx="2" />
        <text x="127" y="79" textAnchor="middle" fontSize="9" fill="#F5F2EA" fontFamily="IBM Plex Mono">RO</text>
        <path d={`M144 ${75 - feedH / 2} C 190 ${75 - feedH / 2}, 200 ${22}, 240 ${22} L ${W} 22 L ${W} ${22 + permH} L 240 ${22 + permH} C 200 ${22 + permH}, 190 ${75 - feedH / 2 + permH}, 144 ${75 - feedH / 2 + permH} Z`} fill="url(#perm)" opacity="0.95" />
        <path d={`M144 ${75 + feedH / 2 - concH} C 190 ${75 + feedH / 2 - concH}, 200 ${128 - concH}, 240 ${128 - concH} L ${W} ${128 - concH} L ${W} 128 L 240 128 C 200 128, 190 ${75 + feedH / 2}, 144 ${75 + feedH / 2} Z`} fill="url(#conc)" opacity="0.9" />
      </svg>
      <dl className="mt-4 grid grid-cols-3 gap-3 border-t border-line pt-4">
        {[
          ["Feed", f.feed_m3d, f.feed_m3h, "text-midnight"],
          ["Permeate", f.permeate_m3d, f.permeate_m3h, "text-teal"],
          ["Concentrate", f.concentrate_m3d, f.concentrate_m3h, "text-brass-600"],
        ].map(([l, d, h, c]) => (
          <div key={l as string}>
            <dt className={cx("text-[10.5px] font-semibold uppercase tracking-wider", c as string)}>{l as string}</dt>
            <dd className="num mt-1 text-[17px] text-midnight">{fmt(d as number)}</dd>
            <dd className="text-[11px] text-graphite-400">m³/day · {fmt(h as number, 1)} m³/h</dd>
          </div>
        ))}
      </dl>
      <div className="mt-4 text-[11.5px] leading-relaxed text-graphite-400">
        Concentrate salinity ≈ <span className="num text-graphite-500">{fmt(rec.result.system.concentrate_tds_ideal_mg_l)}</span> mg/L (idealised,
        assuming full salt rejection and no precipitation).
      </div>
    </div>
  );
}

function Comparison({ rec }: { rec: AssessmentRecord }) {
  const r = rec.result;
  const pData = useMemo(
    () =>
      r.candidates
        .filter((c) => c.estimates.required_pressure_bar != null && c.status !== "unsuitable")
        .slice(0, 8)
        .map((c) => ({
          name: c.model,
          full: c.name,
          low: c.estimates.required_pressure_bar!,
          span: Math.max(0.4, (c.estimates.required_pressure_high_bar ?? c.estimates.required_pressure_bar!) - c.estimates.required_pressure_bar!),
          high: c.estimates.required_pressure_high_bar,
          max: c.rated.max_operating_pressure_bar?.value ?? null,
          status: c.status,
          label: c.status_label,
        })),
    [r],
  );
  const qData = useMemo(
    () =>
      r.candidates
        .filter((c) => c.estimates.permeate_tds_mg_l != null && c.status !== "unsuitable")
        .slice(0, 8)
        .map((c) => ({ name: c.model, full: c.name, cp: c.estimates.permeate_tds_mg_l!, status: c.status, conf: c.estimates.permeate_confidence })),
    [r],
  );
  if (pData.length === 0 && qData.length === 0) return null;
  const avail = rec.inputs.available_pressure_bar ?? 0;
  const target = rec.inputs.target_permeate_tds_mg_l;
  return (
    <section className="mt-12">
      <SectionTitle eyebrow="Comparison" title="How the candidates compare">
        Indicative estimates for candidates that were not excluded. Colour indicates screening status.
      </SectionTitle>
      <div className="grid gap-6 lg:grid-cols-2">
        {pData.length > 0 && (
          <div className="panel p-5">
            <div className="flex items-baseline justify-between">
              <div className="text-[13.5px] font-medium text-midnight">Estimated feed pressure</div>
              <div className="flex items-center gap-1.5 text-[11.5px] text-graphite-400"><span className="h-px w-4 border-t border-dashed border-alert" /> available {fmt(avail)} bar</div>
            </div>
            <div className="mt-3 h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={pData} layout="vertical" margin={{ left: 8, right: 24, top: 4, bottom: 4 }}>
                  <CartesianGrid horizontal={false} stroke="#E5DFD2" />
                  <XAxis type="number" domain={[0, (dataMax: number) => Math.ceil((Math.max(dataMax, avail) * 1.1) / 5) * 5]} allowDecimals={false} tick={{ fontSize: 11, fill: "#5B6663", fontFamily: "IBM Plex Mono" }} unit=" bar" />
                  <YAxis type="category" dataKey="name" width={108} tick={{ fontSize: 11.5, fill: "#202927" }} />
                  <RTooltip cursor={{ fill: "rgba(16,42,42,0.04)" }} content={<PressureTip />} />
                  <ReferenceLine x={avail} stroke="#C4552B" strokeDasharray="4 3" />
                  <Bar dataKey="low" stackId="p" fill="transparent" isAnimationActive={false} />
                  <Bar dataKey="span" stackId="p" radius={[0, 2, 2, 0]} barSize={14}>
                    {pData.map((d) => <Cell key={d.name} fill={STATUS_COLOR[d.status]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-2 text-[11.5px] text-graphite-400">Bars span the estimate for a rated element and one delivering 15% less flow.</div>
          </div>
        )}
        {qData.length > 0 && (
          <div className="panel p-5">
            <div className="flex items-baseline justify-between">
              <div className="text-[13.5px] font-medium text-midnight">Estimated permeate TDS</div>
              {target != null && <div className="flex items-center gap-1.5 text-[11.5px] text-graphite-400"><span className="h-px w-4 border-t border-dashed border-alert" /> target {fmt(target)} mg/L</div>}
            </div>
            <div className="mt-3 h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={qData} layout="vertical" margin={{ left: 8, right: 24, top: 4, bottom: 4 }}>
                  <CartesianGrid horizontal={false} stroke="#E5DFD2" />
                  <XAxis type="number" domain={[0, (dataMax: number) => { const m = Math.max(dataMax, target ?? 0) * 1.15; const step = m > 500 ? 100 : m > 100 ? 50 : 10; return Math.ceil(m / step) * step; }]} allowDecimals={false} tick={{ fontSize: 11, fill: "#5B6663", fontFamily: "IBM Plex Mono" }} />
                  <YAxis type="category" dataKey="name" width={108} tick={{ fontSize: 11.5, fill: "#202927" }} />
                  <RTooltip cursor={{ fill: "rgba(16,42,42,0.04)" }} content={<QualityTip />} />
                  {target != null && <ReferenceLine x={target} stroke="#C4552B" strokeDasharray="4 3" />}
                  <Bar dataKey="cp" radius={[0, 2, 2, 0]} barSize={14}>
                    {qData.map((d) => <Cell key={d.name} fill={STATUS_COLOR[d.status]} fillOpacity={d.conf === "low" ? 0.45 : 1} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-2 text-[11.5px] text-graphite-400">Rough estimate from rated rejection; faded bars are low-confidence extrapolations.</div>
          </div>
        )}
      </div>
    </section>
  );
}

type TipProps = { active?: boolean; payload?: { payload: Record<string, unknown> }[] };
function PressureTip({ active, payload }: TipProps) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload as { full: string; low: number; high: number | null; max: number | null; label: string };
  return (
    <div className="rounded-[3px] bg-midnight px-3 py-2 text-[12px] text-ivory shadow-lift">
      <div className="font-medium">{d.full}</div>
      <div className="num mt-1 text-ivory/80">{range(d.low, d.high, 1)} bar</div>
      <div className="text-ivory/60">Rated maximum: {d.max != null ? `${d.max} bar` : "not documented"}</div>
      <div className="text-ivory/60">{d.label}</div>
    </div>
  );
}
function QualityTip({ active, payload }: TipProps) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload as { full: string; cp: number; conf: string };
  return (
    <div className="rounded-[3px] bg-midnight px-3 py-2 text-[12px] text-ivory shadow-lift">
      <div className="font-medium">{d.full}</div>
      <div className="num mt-1 text-ivory/80">≈ {fmt(d.cp, 0)} mg/L</div>
      <div className="text-ivory/60">{d.conf === "low" ? "Low confidence — tested at a very different salinity" : "Rough estimate"}</div>
    </div>
  );
}

const SPEC_ROWS: [string, string][] = [
  ["active_area_m2", "Active area"],
  ["rated_permeate_flow_m3d", "Rated permeate flow"],
  ["rated_flux_lmh", "Rated flux"],
  ["rated_salt_rejection_pct", "Salt rejection (rated)"],
  ["min_salt_rejection_pct", "Salt rejection (minimum)"],
  ["boron_rejection_pct", "Boron rejection"],
  ["max_operating_pressure_bar", "Maximum pressure"],
  ["max_operating_temperature_c", "Maximum temperature"],
  ["ph_continuous_min", "pH range (continuous)"],
  ["max_free_chlorine_mg_l", "Free chlorine tolerance"],
  ["max_feed_sdi", "Maximum feed SDI"],
  ["max_feed_turbidity_ntu", "Maximum turbidity"],
];

function specValue(c: Candidate, key: string): ReactNode {
  if (key === "ph_continuous_min") {
    const a = c.rated.ph_continuous_min, b = c.rated.ph_continuous_max;
    if (!a || !b) return null;
    return `${a.value}–${b.value}`;
  }
  const p = c.rated[key];
  if (!p) return null;
  if (p.value_text && p.value == null) return p.value_text;
  if (p.value == null) return p.value_min != null ? `${p.value_min}–${p.value_max} ${p.unit}` : p.value_text;
  const v = p.value_text && key.startsWith("max_free") ? p.value_text : `${fmt(p.value, p.value % 1 ? (p.value < 10 ? 2 : 1) : 0)} ${p.unit}`;
  return v;
}

function CandidateDetail({ c, sources, defaultOpen = false }: { c: Candidate; sources: Map<number, Source>; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const passCount = c.checks.filter((x) => x.status === "pass").length;
  return (
    <article className="panel overflow-hidden">
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} className="flex w-full flex-wrap items-center gap-x-6 gap-y-3 px-5 py-4 text-left hover:bg-ivory-200/30">
        <span className="num w-6 text-[13px] text-graphite-300">{c.rank != null ? String(c.rank).padStart(2, "0") : "—"}</span>
        <span className="min-w-[200px] flex-1">
          <span className="block font-display text-[19px] text-midnight">{c.name}</span>
          <span className="text-[12px] text-graphite-400">{c.category_label}{c.element_size ? ` · ${c.element_size}` : ""}</span>
        </span>
        <StatusChip status={c.status} label={c.status_label} size="sm" />
        <span className="hidden w-28 text-right sm:block">
          <span className="block text-[10.5px] uppercase tracking-wider text-graphite-400">Pressure</span>
          <span className="num text-[13.5px] text-midnight">{range(c.estimates.required_pressure_bar, c.estimates.required_pressure_high_bar) ?? "—"}{c.estimates.required_pressure_bar != null && " bar"}</span>
        </span>
        <span className="hidden w-24 text-right md:block">
          <span className="block text-[10.5px] uppercase tracking-wider text-graphite-400">Elements</span>
          <span className="num text-[13.5px] text-midnight">{c.estimates.elements_required != null ? `≈ ${fmt(c.estimates.elements_required)}` : "—"}</span>
        </span>
        <span className="hidden w-28 text-right sm:block">
          <span className="block text-[10.5px] uppercase tracking-wider text-graphite-400">Permeate</span>
          <span className="num text-[13.5px] text-midnight">{c.estimates.permeate_tds_mg_l != null ? `≈ ${fmt(c.estimates.permeate_tds_mg_l)} mg/L` : "—"}</span>
        </span>
        <ChevronDown className={cx("h-4 w-4 text-graphite-400 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="grid gap-8 border-t border-line px-5 py-6 lg:grid-cols-[1.1fr_1fr] animate-rise">
          <div>
            <p className="text-[14px] leading-relaxed text-graphite-700">{c.summary}</p>
            <div className="mt-5 text-[11px] font-semibold uppercase tracking-wider text-graphite-400">
              Screening checks · {passCount}/{c.checks.length} passed
            </div>
            <ul className="mt-2 divide-y divide-line/70">
              {c.checks.map((k) => (
                <li key={k.key} className="flex gap-3 py-2.5">
                  <CheckIcon status={k.status} className="mt-0.5 h-4 w-4 shrink-0" />
                  <div>
                    <div className="text-[13px] font-medium text-midnight">{k.label}</div>
                    <div className="text-[12.5px] leading-snug text-graphite-500">{k.message}</div>
                  </div>
                </li>
              ))}
            </ul>
            {c.concerns.length > 0 && (
              <div className="mt-4 rounded-[3px] border border-brass/30 bg-brass-50/50 px-4 py-3 text-[12.5px] text-graphite-700">
                {c.concerns.map((x) => <div key={x}>• {x}</div>)}
              </div>
            )}
          </div>
          <div>
            <div className="flex items-center justify-between">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-graphite-400">Reported specifications</div>
              {c.conflicts.length > 0 && <Badge tone="alert">Source conflict</Badge>}
            </div>
            <table className="table-clean mt-2 w-full">
              <tbody>
                {SPEC_ROWS.map(([k, label]) => {
                  const v = specValue(c, k);
                  const p = c.rated[k];
                  return (
                    <tr key={k}>
                      <td className="w-[44%] text-graphite-500">{label}</td>
                      <td className={cx("num", v == null && "text-graphite-300")}>{v ?? "Not reported"}</td>
                      <td className="text-right">{p && <VerificationBadge status={p.verification_status} />}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {c.rated_test_conditions && (
              <div className="mt-3 text-[11.5px] leading-relaxed text-graphite-400">
                <span className="font-medium text-graphite-500">Rated at:</span> {c.rated_test_conditions}
              </div>
            )}
            {c.evidence.observations.length > 0 && (
              <div className="mt-5">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-graphite-400">Published observations</div>
                <ul className="mt-2 space-y-2">
                  {c.evidence.observations.map((o, i) => (
                    <li key={i} className="rounded-[3px] border border-line bg-white/50 px-3 py-2 text-[12.5px]">
                      <div className="flex items-center gap-2">
                        <Badge>{EVIDENCE_LABELS[o.evidence_type] ?? o.evidence_type}</Badge>
                        <span className="text-graphite-400">{o.feed_description}</span>
                      </div>
                      <div className="mt-1 text-graphite-700">{o.performance_text}</div>
                      {o.source_id && sources.get(o.source_id) && (
                        <div className="mt-1 text-[11px] text-graphite-400">{sources.get(o.source_id)!.authors?.split(";")[0]} ({sources.get(o.source_id)!.year})</div>
                      )}
                    </li>
                  ))}
                </ul>
                <div className="mt-2 text-[11px] text-graphite-400">Observations are context only and are not used as manufacturer ratings.</div>
              </div>
            )}
          </div>
        </div>
      )}
    </article>
  );
}

function ReasonList({ icon, title, text, items }: { icon: ReactNode; title: string; text: string; items: Candidate[] }) {
  const [all, setAll] = useState(false);
  const shown = all ? items : items.slice(0, 5);
  return (
    <div className="panel p-5">
      <div className="flex items-center gap-2 text-[14px] font-medium text-midnight">{icon}{title}<span className="num ml-auto text-[12px] text-graphite-400">{items.length}</span></div>
      <p className="mt-1 text-[12.5px] text-graphite-500">{text}</p>
      {items.length === 0 ? (
        <div className="mt-4 text-[13px] text-graphite-400">None.</div>
      ) : (
        <ul className="mt-4 divide-y divide-line/70">
          {shown.map((c) => (
            <li key={c.membrane_id} className="py-2.5">
              <div className="text-[13px] font-medium text-midnight">{c.name}</div>
              <div className="text-[12.5px] leading-snug text-graphite-500">{c.summary}</div>
            </li>
          ))}
        </ul>
      )}
      {items.length > 5 && (
        <button className="mt-2 text-[12.5px] text-teal hover:underline" onClick={() => setAll(!all)}>
          {all ? "Show fewer" : `Show all ${items.length}`}
        </button>
      )}
    </div>
  );
}

const CHEM_STYLE: Record<string, { label: string; cls: string }> = {
  ok: { label: "Low concern", cls: "text-teal-700 bg-teal-50 border-teal/25" },
  caution: { label: "Caution", cls: "text-brass-700 bg-brass-50 border-brass/30" },
  risk: { label: "Risk", cls: "text-alert-600 bg-alert-50 border-alert/25" },
  not_assessed: { label: "Unresolved", cls: "text-graphite-500 bg-ivory-200 border-line" },
  missing: { label: "Data missing", cls: "text-graphite-500 bg-ivory-200 border-line" },
};

function ChemistryPanel({ items }: { items: ChemItem[] }) {
  if (!items.length) return <EmptyState title="No chemistry items to report" />;
  return (
    <div className="grid gap-px overflow-hidden border border-line bg-line md:grid-cols-2">
      {items.map((i) => (
        <div key={i.key} className="bg-ivory-50 p-5">
          <div className="flex items-center justify-between gap-3">
            <div className="text-[14px] font-medium text-midnight">{i.label}</div>
            <span className={cx("rounded-[2px] border px-1.5 py-0.5 text-[11px] font-medium", CHEM_STYLE[i.status].cls)}>{CHEM_STYLE[i.status].label}</span>
          </div>
          <p className="mt-1.5 text-[13px] leading-relaxed text-graphite-500">{i.message}</p>
        </div>
      ))}
    </div>
  );
}

function Accordion({ title, icon, children, defaultOpen }: { title: string; icon: ReactNode; children: ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(!!defaultOpen);
  return (
    <div className="panel">
      <button className="flex w-full items-center gap-2 px-5 py-4 text-left text-[14px] font-medium text-midnight" onClick={() => setOpen(!open)} aria-expanded={open}>
        {icon}{title}<ChevronDown className={cx("ml-auto h-4 w-4 text-graphite-400 transition-transform", open && "rotate-180")} />
      </button>
      {open && <div className="border-t border-line px-5 py-4 text-[13px] leading-relaxed text-graphite-700">{children}</div>}
    </div>
  );
}

function SourcesList({ sources }: { sources: Source[] }) {
  return (
    <ol className="divide-y divide-line border-y border-line">
      {sources.map((s) => {
        const link = s.url || (s.doi ? `https://doi.org/${s.doi}` : null);
        return (
          <li key={s.id} className="grid gap-2 py-3.5 sm:grid-cols-[40px_1fr_auto] sm:items-baseline">
            <span className="num text-[12px] text-graphite-300">[{s.id}]</span>
            <div className="text-[13px] leading-snug">
              <span className="text-midnight">{s.title}</span>
              <span className="text-graphite-400">{s.authors ? ` — ${s.authors}` : ""}{s.year ? ` (${s.year})` : ""}{s.publisher ? `. ${s.publisher}` : ""}</span>
              {link && (
                <a href={link} target="_blank" rel="noreferrer noopener" className="ml-2 inline-flex items-center gap-1 text-teal hover:underline">
                  <BookOpen className="h-3 w-3" /> {s.doi ? `doi:${s.doi}` : "link"}
                </a>
              )}
            </div>
            <div className="flex gap-1.5">
              <Badge>{s.source_type.replace(/-/g, " ")}</Badge>
              <VerificationBadge status={s.verification_status} />
            </div>
          </li>
        );
      })}
    </ol>
  );
}
