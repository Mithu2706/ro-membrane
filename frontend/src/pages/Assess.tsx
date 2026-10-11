import { ArrowLeft, ArrowRight, Beaker, Building2, Check, Droplets, Factory, FlaskRound, Layers2, RotateCcw, Sparkles, Waves } from "lucide-react";
import { ReactNode, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Alert, Button, Field, NumberInput, Tooltip, cx } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { APPLICATION_LABELS } from "../lib/format";
import type { Application, AssessmentInput, AssessmentRecord, Chemistry, Priority } from "../lib/types";

const DRAFT_KEY = "osmora.assessment.draft.v1";

const EMPTY: AssessmentInput = {
  application: "bwro",
  feed_tds_mg_l: null,
  feed_temperature_c: null,
  available_pressure_bar: null,
  permeate_flow_m3d: null,
  recovery_pct: null,
  target_permeate_tds_mg_l: null,
  target_boron_mg_l: null,
  feed_flow_limit_m3d: null,
  design_flux_lmh: null,
  pressure_loss_allowance_bar: null,
  priority: "balanced",
  input_origin: "client",
  chemistry: { oxidant_exposure: "unknown", pretreatment: [] },
  client: {},
};

const STEPS = [
  { key: "application", label: "Application", hint: "Service type" },
  { key: "feed", label: "Feed water", hint: "Salinity & conditions" },
  { key: "chemistry", label: "Water chemistry", hint: "Analysis (optional)" },
  { key: "requirements", label: "Requirements", hint: "Production & quality" },
  { key: "review", label: "Review", hint: "Confirm & run" },
] as const;

const APPS: { key: Application; icon: typeof Waves; title: string; text: string }[] = [
  { key: "bwro", icon: Droplets, title: "Brackish water", text: "Groundwater or surface water with moderate salinity." },
  { key: "swro", icon: Waves, title: "Seawater", text: "Open-sea or beach-well intakes at seawater salinity." },
  { key: "industrial", icon: Factory, title: "Industrial / reuse", text: "Process water, wastewater recovery or effluent reuse." },
  { key: "second_pass", icon: Layers2, title: "Second pass", text: "Polishing the permeate of a first RO pass." },
  { key: "other", icon: FlaskRound, title: "Other / specialised", text: "High-salinity brines or unusual duties — expert review." },
];

const PRIORITIES: { key: Priority; title: string; text: string }[] = [
  { key: "balanced", title: "Balanced", text: "No preference beyond the screening rules." },
  { key: "quality", title: "Permeate quality", text: "Prefer the lowest estimated permeate salinity." },
  { key: "productivity", title: "Productivity", text: "Prefer higher rated output per element." },
  { key: "low_pressure", title: "Lower pressure", text: "Prefer the lowest estimated operating pressure." },
];

const PRETREATMENT = ["Media filtration", "Cartridge filtration", "Ultrafiltration", "Coagulation", "Softening", "Antiscalant", "Acid dosing", "Dechlorination"];

type Errors = Record<string, string>;

function validateStep(step: number, d: AssessmentInput): Errors {
  const e: Errors = {};
  const req = (k: keyof AssessmentInput, label: string) => {
    if (d[k] === null || d[k] === undefined || d[k] === ("" as unknown)) e[k as string] = `${label} is required`;
  };
  if (step === 1) {
    req("feed_tds_mg_l", "Feed TDS");
    req("feed_temperature_c", "Feed temperature");
    req("available_pressure_bar", "Available pressure");
    if (d.feed_tds_mg_l != null && (d.feed_tds_mg_l <= 0 || d.feed_tds_mg_l > 100000)) e.feed_tds_mg_l = "Enter a value between 0 and 100,000 mg/L";
    if (d.feed_temperature_c != null && (d.feed_temperature_c <= 0 || d.feed_temperature_c > 60)) e.feed_temperature_c = "Enter a temperature between 0 and 60 °C";
    if (d.available_pressure_bar != null && (d.available_pressure_bar <= 0 || d.available_pressure_bar > 120)) e.available_pressure_bar = "Enter a pressure between 0 and 120 bar";
    if (d.feed_flow_limit_m3d != null && d.feed_flow_limit_m3d <= 0) e.feed_flow_limit_m3d = "Must be greater than zero";
  }
  if (step === 2) {
    const c = d.chemistry;
    if (c.ph != null && (c.ph < 0 || c.ph > 14)) e.ph = "pH must be between 0 and 14";
    if (c.sdi != null && (c.sdi < 0 || c.sdi > 20)) e.sdi = "SDI must be between 0 and 20";
    for (const [k, v] of Object.entries(c)) if (typeof v === "number" && v < 0) e[k] = "Cannot be negative";
  }
  if (step === 3) {
    req("permeate_flow_m3d", "Permeate flow");
    req("recovery_pct", "Recovery");
    if (d.permeate_flow_m3d != null && d.permeate_flow_m3d <= 0) e.permeate_flow_m3d = "Must be greater than zero";
    if (d.recovery_pct != null && (d.recovery_pct <= 0 || d.recovery_pct >= 100)) e.recovery_pct = "Recovery must be above 0% and below 100%";
    if (d.design_flux_lmh != null && (d.design_flux_lmh <= 0 || d.design_flux_lmh > 60)) e.design_flux_lmh = "Enter a flux between 0 and 60 LMH";
    if (d.target_permeate_tds_mg_l != null && d.target_permeate_tds_mg_l < 0) e.target_permeate_tds_mg_l = "Cannot be negative";
    if (d.pressure_loss_allowance_bar != null && (d.pressure_loss_allowance_bar < 0 || d.pressure_loss_allowance_bar > 30)) e.pressure_loss_allowance_bar = "Enter 0–30 bar";
  }
  return e;
}

function clean(d: AssessmentInput): AssessmentInput {
  const chem: Chemistry = { ...d.chemistry };
  if (chem.oxidant_exposure !== "free_chlorine_present" && chem.free_chlorine_mg_l == null) delete chem.free_chlorine_mg_l;
  const client = Object.fromEntries(Object.entries(d.client).filter(([, v]) => v && String(v).trim() !== ""));
  return { ...d, chemistry: chem, client };
}

export default function Assess() {
  const navigate = useNavigate();
  const [data, setData] = useState<AssessmentInput>(() => {
    try {
      const raw = localStorage.getItem(DRAFT_KEY);
      if (raw) return { ...EMPTY, ...JSON.parse(raw) };
    } catch {
      /* storage unavailable */
    }
    return EMPTY;
  });
  const [step, setStep] = useState(0);
  const [errors, setErrors] = useState<Errors>({});
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [examples, setExamples] = useState<{ key: string; title: string; description: string; inputs: Partial<AssessmentInput> }[]>([]);
  const [loadedExample, setLoadedExample] = useState<string | null>(null);

  useEffect(() => {
    api<typeof examples>("/api/demo-examples").then(setExamples).catch(() => setExamples([]));
  }, []);
  useEffect(() => {
    try {
      localStorage.setItem(DRAFT_KEY, JSON.stringify(data));
    } catch {
      /* ignore */
    }
  }, [data]);

  const set = <K extends keyof AssessmentInput>(k: K, v: AssessmentInput[K]) => setData((d) => ({ ...d, [k]: v }));
  const setChem = <K extends keyof Chemistry>(k: K, v: Chemistry[K]) => setData((d) => ({ ...d, chemistry: { ...d.chemistry, [k]: v } }));

  const chemCount = useMemo(() => {
    const keys: (keyof Chemistry)[] = ["ph", "alkalinity_mg_l_caco3", "hardness_mg_l_caco3", "calcium_mg_l", "magnesium_mg_l", "sulfate_mg_l",
      "chloride_mg_l", "sodium_mg_l", "silica_mg_l", "boron_mg_l", "sdi", "turbidity_ntu", "toc_mg_l", "cod_mg_l"];
    return { filled: keys.filter((k) => data.chemistry[k] != null).length, total: keys.length };
  }, [data.chemistry]);

  const coreMissing = useMemo(() => {
    const c = data.chemistry;
    const m: string[] = [];
    if (c.ph == null) m.push("pH");
    if (c.calcium_mg_l == null && c.hardness_mg_l_caco3 == null) m.push("calcium or hardness");
    if (c.alkalinity_mg_l_caco3 == null) m.push("alkalinity");
    if (c.sdi == null && c.turbidity_ntu == null) m.push("SDI or turbidity");
    return m;
  }, [data.chemistry]);

  function go(next: number) {
    if (next > step) {
      for (let s = step; s < next; s++) {
        const e = validateStep(s, data);
        if (Object.keys(e).length) {
          setErrors(e);
          setStep(s);
          return;
        }
      }
    }
    setErrors({});
    setStep(next);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function loadExample(key: string) {
    const ex = examples.find((x) => x.key === key);
    if (!ex) return;
    setData({ ...EMPTY, ...ex.inputs, chemistry: { ...EMPTY.chemistry, ...(ex.inputs.chemistry || {}) }, client: { project_name: `Demo — ${ex.title}` }, input_origin: "demo" } as AssessmentInput);
    setLoadedExample(ex.title);
    setErrors({});
    setStep(4);
  }

  function reset() {
    setData(EMPTY);
    setLoadedExample(null);
    setErrors({});
    setStep(0);
  }

  async function submit() {
    for (let s = 0; s < 4; s++) {
      const e = validateStep(s, data);
      if (Object.keys(e).length) {
        setErrors(e);
        setStep(s);
        return;
      }
    }
    setSubmitting(true);
    setServerError(null);
    try {
      const rec = await api<AssessmentRecord>("/api/assessments", { method: "POST", json: clean(data) });
      navigate(`/results/${rec.reference}`, { state: rec });
    } catch (e) {
      setServerError(e instanceof ApiError ? e.message : "Something went wrong.");
      setSubmitting(false);
    }
  }

  return (
    <div className="grid-lines-light min-h-[calc(100vh-4rem)]">
      <div className="mx-auto max-w-7xl px-5 py-10 lg:px-8 lg:py-14">
        <div className="mb-10 flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="eyebrow">New assessment</div>
            <h1 className="mt-2 text-[38px] leading-tight">Describe your water and requirements</h1>
            <p className="mt-2 max-w-2xl text-[14.5px] text-graphite-500">
              Only feed salinity, temperature, pressure, production and recovery are required. Every additional measurement
              sharpens the screening — leave a field empty if it has not been measured; a zero means a measured zero.
            </p>
          </div>
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            {examples.length > 0 && (
              <div className="relative">
                <select
                  aria-label="Load a demonstration example"
                  className="field-input h-10 !py-0 pr-8 text-[13px]"
                  value=""
                  onChange={(e) => loadExample(e.target.value)}
                >
                  <option value="">Load a demonstration example…</option>
                  {examples.map((x) => (
                    <option key={x.key} value={x.key}>{x.title}</option>
                  ))}
                </select>
              </div>
            )}
            <Button variant="ghost" size="md" onClick={reset} title="Clear all fields">
              <RotateCcw className="h-4 w-4" /> Reset
            </Button>
          </div>
        </div>

        <div className="grid gap-10 lg:grid-cols-[240px_1fr]">
          {/* Progress rail */}
          <nav aria-label="Assessment steps" className="min-w-0 lg:sticky lg:top-24 lg:self-start">
            <ol className="flex gap-2 overflow-x-auto lg:flex-col lg:gap-0">
              {STEPS.map((s, i) => {
                const done = i < step;
                const active = i === step;
                return (
                  <li key={s.key} className="relative shrink-0">
                    <button
                      type="button"
                      onClick={() => go(i)}
                      className={cx("group flex w-full items-center gap-3 py-2.5 pr-3 text-left lg:py-3.5", active ? "" : "opacity-80 hover:opacity-100")}
                    >
                      <span
                        className={cx(
                          "num flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-[12px] transition-colors",
                          active ? "border-midnight bg-midnight text-ivory" : done ? "border-teal bg-teal text-ivory" : "border-line bg-ivory-50 text-graphite-400",
                        )}
                      >
                        {done ? <Check className="h-3.5 w-3.5" /> : i + 1}
                      </span>
                      <span>
                        <span className={cx("block text-[13.5px] font-medium", active ? "text-midnight" : "text-graphite-500")}>{s.label}</span>
                        <span className="hidden text-[11.5px] text-graphite-400 lg:block">{s.hint}</span>
                      </span>
                    </button>
                    {i < STEPS.length - 1 && <span className="absolute left-[13px] top-[46px] hidden h-[calc(100%-38px)] w-px bg-line lg:block" />}
                  </li>
                );
              })}
            </ol>
            <div className="mt-8 hidden border-t border-line pt-5 text-[12px] leading-relaxed text-graphite-400 lg:block">
              Your draft is kept in this browser until you submit or reset.
            </div>
          </nav>

          {/* Step body */}
          <div className="panel relative min-h-[520px] min-w-0 p-5 shadow-lift sm:p-9">
            {loadedExample && step === 4 && (
              <div className="mb-6">
                <Alert tone="info" title={`Demonstration example loaded: ${loadedExample}`}>
                  Values are illustrative defaults for demonstration only. Edit any step before running the assessment.
                </Alert>
              </div>
            )}

            <div key={step} className="animate-rise">
              {step === 0 && (
                <StepBlock eyebrow="Step 1 of 5" title="What is the RO system for?" text="The application determines which membrane families are considered. It is never inferred from salinity alone.">
                  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    {APPS.map((a) => (
                      <button
                        key={a.key}
                        type="button"
                        onClick={() => set("application", a.key)}
                        aria-pressed={data.application === a.key}
                        className={cx(
                          "group relative rounded-[3px] border p-5 text-left transition-all",
                          data.application === a.key ? "border-midnight bg-midnight text-ivory shadow-lift" : "border-line bg-white/60 hover:border-midnight/40",
                        )}
                      >
                        <a.icon className={cx("h-5 w-5", data.application === a.key ? "text-brass" : "text-teal")} strokeWidth={1.6} />
                        <div className={cx("mt-5 font-display text-[19px]", data.application === a.key ? "text-ivory" : "text-midnight")}>{a.title}</div>
                        <div className={cx("mt-1 text-[12.5px] leading-snug", data.application === a.key ? "text-ivory/65" : "text-graphite-500")}>{a.text}</div>
                        {data.application === a.key && <Check className="absolute right-4 top-4 h-4 w-4 text-brass" />}
                      </button>
                    ))}
                  </div>
                  <div className="mt-10">
                    <div className="mb-3 flex items-center gap-2 text-[13px] font-medium text-midnight">
                      <Building2 className="h-4 w-4 text-graphite-400" /> Project details <span className="text-[11px] font-normal uppercase tracking-wider text-graphite-300">Optional</span>
                    </div>
                    <div className="grid gap-4 sm:grid-cols-2">
                      {([["project_name", "Project name"], ["name", "Contact name"], ["organization", "Organisation"], ["email", "Email"]] as const).map(([k, l]) => (
                        <Field key={k} label={l}>
                          <input
                            className="field-input"
                            value={data.client[k] ?? ""}
                            maxLength={200}
                            type={k === "email" ? "email" : "text"}
                            onChange={(e) => set("client", { ...data.client, [k]: e.target.value })}
                          />
                        </Field>
                      ))}
                    </div>
                  </div>
                </StepBlock>
              )}

              {step === 1 && (
                <StepBlock eyebrow="Step 2 of 5" title="Feed water and site conditions" text="These values drive osmotic pressure, pressure feasibility and operating-limit checks.">
                  <div className="grid gap-5 sm:grid-cols-2">
                    <Field label="Feed TDS / salinity" unit="mg/L" error={errors.feed_tds_mg_l} tooltip="Total dissolved solids of the RO feed. Seawater is typically around 35,000 mg/L; brackish waters range widely.">
                      <NumberInput unitPad value={data.feed_tds_mg_l} onChange={(v) => set("feed_tds_mg_l", v)} invalid={!!errors.feed_tds_mg_l} placeholder="e.g. 2500" />
                    </Field>
                    <Field label="Feed temperature" unit="°C" error={errors.feed_temperature_c} tooltip="Design feed temperature. Colder water needs more pressure; warmer water passes more salt.">
                      <NumberInput unitPad value={data.feed_temperature_c} onChange={(v) => set("feed_temperature_c", v)} invalid={!!errors.feed_temperature_c} placeholder="e.g. 22" />
                    </Field>
                    <Field
                      label="Available operating pressure"
                      unit="bar"
                      error={errors.available_pressure_bar}
                      tooltip="Maximum feed pressure your high-pressure pump can deliver. This is not the same as the net pressure across the membrane — osmotic pressure and losses are deducted in the screening."
                    >
                      <NumberInput unitPad value={data.available_pressure_bar} onChange={(v) => set("available_pressure_bar", v)} invalid={!!errors.available_pressure_bar} placeholder="e.g. 16" />
                    </Field>
                    <Field label="Available feed-flow limit" unit="m³/day" optional error={errors.feed_flow_limit_m3d} tooltip="If the water source can only supply a limited volume, enter it to check the flow balance.">
                      <NumberInput unitPad value={data.feed_flow_limit_m3d} onChange={(v) => set("feed_flow_limit_m3d", v)} invalid={!!errors.feed_flow_limit_m3d} placeholder="No limit" />
                    </Field>
                  </div>
                </StepBlock>
              )}

              {step === 2 && (
                <StepBlock eyebrow="Step 3 of 5" title="Water chemistry" text="Optional, but scaling and fouling risks can only be screened from measured values. Leave unknown values blank.">
                  <div className="mb-6 flex flex-wrap items-center gap-4 rounded-[3px] border border-line bg-ivory-200/40 px-4 py-3">
                    <Beaker className="h-4 w-4 text-teal" />
                    <div className="text-[13px] text-graphite-500">
                      <span className="num font-medium text-midnight">{chemCount.filled}</span> of {chemCount.total} parameters entered.
                      {coreMissing.length > 0 ? (
                        <> Key values still missing for scaling screening: <span className="text-midnight">{coreMissing.join(", ")}</span>.</>
                      ) : (
                        <> Core screening set complete.</>
                      )}
                    </div>
                  </div>
                  <Group title="General">
                    <ChemField k="ph" label="pH" data={data} setChem={setChem} errors={errors} />
                    <ChemField k="alkalinity_mg_l_caco3" label="Alkalinity" unit="mg/L CaCO₃" data={data} setChem={setChem} errors={errors} tip="Total (M) alkalinity, expressed as CaCO₃. Used with calcium and pH for carbonate scaling." />
                    <ChemField k="hardness_mg_l_caco3" label="Total hardness" unit="mg/L CaCO₃" data={data} setChem={setChem} errors={errors} />
                  </Group>
                  <Group title="Ions">
                    <ChemField k="calcium_mg_l" label="Calcium" unit="mg/L" data={data} setChem={setChem} errors={errors} />
                    <ChemField k="magnesium_mg_l" label="Magnesium" unit="mg/L" data={data} setChem={setChem} errors={errors} />
                    <ChemField k="sodium_mg_l" label="Sodium" unit="mg/L" data={data} setChem={setChem} errors={errors} />
                    <ChemField k="chloride_mg_l" label="Chloride" unit="mg/L" data={data} setChem={setChem} errors={errors} />
                    <ChemField k="sulfate_mg_l" label="Sulfate" unit="mg/L" data={data} setChem={setChem} errors={errors} />
                    <ChemField k="silica_mg_l" label="Silica (SiO₂)" unit="mg/L" data={data} setChem={setChem} errors={errors} />
                    <ChemField k="boron_mg_l" label="Boron" unit="mg/L" data={data} setChem={setChem} errors={errors} tip="Relevant mainly for seawater and drinking-water targets." />
                  </Group>
                  <Group title="Fouling indicators">
                    <ChemField k="sdi" label="SDI (15 min)" data={data} setChem={setChem} errors={errors} tip="Silt density index. Most datasheets limit RO feed to SDI 5 or lower." />
                    <ChemField k="turbidity_ntu" label="Turbidity" unit="NTU" data={data} setChem={setChem} errors={errors} />
                    <ChemField k="toc_mg_l" label="TOC" unit="mg/L" data={data} setChem={setChem} errors={errors} />
                    <ChemField k="cod_mg_l" label="COD" unit="mg/L" data={data} setChem={setChem} errors={errors} />
                  </Group>
                  <Group title="Oxidants & pretreatment">
                    <Field label="Chlorine / oxidant exposure" tooltip="Polyamide RO membranes are damaged by free chlorine. Indicate what reaches the RO feed.">
                      <select className="field-input" value={data.chemistry.oxidant_exposure} onChange={(e) => setChem("oxidant_exposure", e.target.value as Chemistry["oxidant_exposure"])}>
                        <option value="unknown">Not known</option>
                        <option value="none">No oxidant used</option>
                        <option value="dechlorinated">Chlorinated, then dechlorinated</option>
                        <option value="chloramine">Chloramine present</option>
                        <option value="free_chlorine_present">Free chlorine present at RO feed</option>
                      </select>
                    </Field>
                    {data.chemistry.oxidant_exposure === "free_chlorine_present" && (
                      <ChemField k="free_chlorine_mg_l" label="Free chlorine" unit="mg/L" data={data} setChem={setChem} errors={errors} />
                    )}
                  </Group>
                  <div className="mt-2">
                    <div className="mb-2 text-[13px] font-medium text-midnight">Existing pretreatment</div>
                    <div className="flex flex-wrap gap-2">
                      {PRETREATMENT.map((p) => {
                        const on = data.chemistry.pretreatment.includes(p);
                        return (
                          <button
                            key={p}
                            type="button"
                            aria-pressed={on}
                            onClick={() => setChem("pretreatment", on ? data.chemistry.pretreatment.filter((x) => x !== p) : [...data.chemistry.pretreatment, p])}
                            className={cx("rounded-full border px-3 py-1.5 text-[12.5px] transition-colors", on ? "border-teal bg-teal-50 text-teal-700" : "border-line bg-white/60 text-graphite-500 hover:border-graphite-300")}
                          >
                            {on && <Check className="mr-1 inline h-3 w-3" />}
                            {p}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </StepBlock>
              )}

              {step === 3 && (
                <StepBlock eyebrow="Step 4 of 5" title="Treatment requirements" text="Production and quality targets. Your priority only orders candidates that already pass every safety and evidence check — it never overrides them.">
                  <div className="grid gap-5 sm:grid-cols-2">
                    <Field label="Required permeate production" unit="m³/day" error={errors.permeate_flow_m3d}>
                      <NumberInput unitPad value={data.permeate_flow_m3d} onChange={(v) => set("permeate_flow_m3d", v)} invalid={!!errors.permeate_flow_m3d} placeholder="e.g. 1000" />
                    </Field>
                    <Field label="Target recovery" unit="%" error={errors.recovery_pct} tooltip="Share of feed water converted to permeate. Higher recovery concentrates salts and raises scaling risk and osmotic pressure.">
                      <NumberInput unitPad value={data.recovery_pct} onChange={(v) => set("recovery_pct", v)} invalid={!!errors.recovery_pct} placeholder="e.g. 70" />
                    </Field>
                    <Field label="Target permeate TDS" unit="mg/L" optional error={errors.target_permeate_tds_mg_l}>
                      <NumberInput unitPad value={data.target_permeate_tds_mg_l} onChange={(v) => set("target_permeate_tds_mg_l", v)} placeholder="Not specified" />
                    </Field>
                    <Field label="Target permeate boron" unit="mg/L" optional>
                      <NumberInput unitPad value={data.target_boron_mg_l} onChange={(v) => set("target_boron_mg_l", v)} placeholder="Not specified" />
                    </Field>
                  </div>

                  <div className="mt-8">
                    <div className="mb-3 flex items-center gap-2 text-[13px] font-medium text-midnight">
                      Selection priority <Tooltip text="A preference used to order candidates of equal standing. Safety limits and evidence requirements always come first." />
                    </div>
                    <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                      {PRIORITIES.map((p) => (
                        <button
                          key={p.key}
                          type="button"
                          aria-pressed={data.priority === p.key}
                          onClick={() => set("priority", p.key)}
                          className={cx("rounded-[3px] border px-4 py-3 text-left transition-colors", data.priority === p.key ? "border-teal bg-teal-50" : "border-line bg-white/60 hover:border-graphite-300")}
                        >
                          <div className="text-[13.5px] font-medium text-midnight">{p.title}</div>
                          <div className="mt-0.5 text-[12px] leading-snug text-graphite-500">{p.text}</div>
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="mt-8 border-t border-line pt-6">
                    <div className="mb-1 flex items-center gap-2 text-[13px] font-medium text-midnight">
                      <Sparkles className="h-4 w-4 text-brass-600" /> Design assumptions
                    </div>
                    <p className="mb-4 text-[12.5px] text-graphite-500">
                      Needed to estimate operating pressure and element count. If you are unsure, consult your membrane supplier's
                      design guidelines for your feed source — leave blank to skip these estimates.
                    </p>
                    <div className="grid gap-5 sm:grid-cols-2">
                      <Field label="Design average flux" unit="LMH" optional error={errors.design_flux_lmh} tooltip="Average permeate flux across the system, in litres per m² per hour. Typically lower for seawater and high-fouling feeds.">
                        <NumberInput unitPad value={data.design_flux_lmh} onChange={(v) => set("design_flux_lmh", v)} invalid={!!errors.design_flux_lmh} placeholder="Not specified" />
                      </Field>
                      <Field label="Pressure-loss allowance" unit="bar" optional error={errors.pressure_loss_allowance_bar} tooltip="Expected pressure losses through vessels, piping and permeate back-pressure. If blank, losses are not included and a warning is shown.">
                        <NumberInput unitPad value={data.pressure_loss_allowance_bar} onChange={(v) => set("pressure_loss_allowance_bar", v)} placeholder="Not included" />
                      </Field>
                    </div>
                  </div>
                </StepBlock>
              )}

              {step === 4 && (
                <StepBlock eyebrow="Step 5 of 5" title="Review and run the screening" text="Check the values below. The screening runs locally against the research dataset.">
                  <ReviewTable data={data} onEdit={(s) => go(s)} />
                  {serverError && (
                    <div className="mt-5">
                      <Alert tone="critical" title="The assessment could not be completed">{serverError}</Alert>
                    </div>
                  )}
                </StepBlock>
              )}
            </div>

            <div className="mt-10 flex items-center justify-between border-t border-line pt-6">
              <Button variant="secondary" onClick={() => go(Math.max(0, step - 1))} disabled={step === 0}>
                <ArrowLeft className="h-4 w-4" /> Back
              </Button>
              {step < 4 ? (
                <Button onClick={() => go(step + 1)}>
                  Continue <ArrowRight className="h-4 w-4" />
                </Button>
              ) : (
                <Button size="lg" onClick={submit} loading={submitting}>
                  {submitting ? "Screening membranes…" : "Run assessment"} {!submitting && <ArrowRight className="h-4 w-4" />}
                </Button>
              )}
            </div>

            {submitting && (
              <div className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-4 bg-ivory-50/85 backdrop-blur-[2px]">
                <div className="relative h-[2px] w-56 overflow-hidden bg-line">
                  <span className="absolute inset-y-0 w-1/2 bg-teal animate-sweep" />
                </div>
                <div className="text-[12px] uppercase tracking-eyebrow text-graphite-500">Checking limits, chemistry and evidence</div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function StepBlock({ eyebrow, title, text, children }: { eyebrow: string; title: string; text: string; children: ReactNode }) {
  return (
    <section>
      <div className="eyebrow">{eyebrow}</div>
      <h2 className="mt-2 text-[28px] leading-tight">{title}</h2>
      <p className="mb-8 mt-2 max-w-2xl text-[14px] text-graphite-500">{text}</p>
      {children}
    </section>
  );
}

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="mb-7">
      <legend className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-graphite-400">{title}</legend>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{children}</div>
    </fieldset>
  );
}

function ChemField({
  k,
  label,
  unit,
  tip,
  data,
  setChem,
  errors,
}: {
  k: keyof Chemistry;
  label: string;
  unit?: string;
  tip?: string;
  data: AssessmentInput;
  setChem: <K extends keyof Chemistry>(k: K, v: Chemistry[K]) => void;
  errors: Errors;
}) {
  return (
    <Field label={label} unit={unit} tooltip={tip} error={errors[k as string]}>
      <NumberInput unitPad={!!unit} value={data.chemistry[k] as number | null | undefined} onChange={(v) => setChem(k, v as never)} invalid={!!errors[k as string]} />
    </Field>
  );
}

function ReviewTable({ data, onEdit }: { data: AssessmentInput; onEdit: (step: number) => void }) {
  const v = (x: number | null | undefined, unit = "") => (x === null || x === undefined ? <span className="text-graphite-300">Not provided</span> : <span className="num">{x.toLocaleString("en-GB")} {unit}</span>);
  const c = data.chemistry;
  const sections: { title: string; step: number; rows: [string, ReactNode][] }[] = [
    { title: "Application", step: 0, rows: [["Service", APPLICATION_LABELS[data.application]], ["Project", data.client.project_name || <span className="text-graphite-300">—</span>]] },
    { title: "Feed water", step: 1, rows: [["Feed TDS", v(data.feed_tds_mg_l, "mg/L")], ["Temperature", v(data.feed_temperature_c, "°C")], ["Available pressure", v(data.available_pressure_bar, "bar")], ["Feed-flow limit", v(data.feed_flow_limit_m3d, "m³/day")]] },
    {
      title: "Water chemistry",
      step: 2,
      rows: [["pH", v(c.ph)], ["Alkalinity", v(c.alkalinity_mg_l_caco3, "mg/L CaCO₃")], ["Calcium", v(c.calcium_mg_l, "mg/L")], ["Silica", v(c.silica_mg_l, "mg/L")], ["Boron", v(c.boron_mg_l, "mg/L")], ["SDI", v(c.sdi)], ["Turbidity", v(c.turbidity_ntu, "NTU")],
        ["Oxidant exposure", c.oxidant_exposure.replace(/_/g, " ")], ["Pretreatment", c.pretreatment.length ? c.pretreatment.join(", ") : <span className="text-graphite-300">None listed</span>]],
    },
    { title: "Requirements", step: 3, rows: [["Production", v(data.permeate_flow_m3d, "m³/day")], ["Recovery", v(data.recovery_pct, "%")], ["Target permeate TDS", v(data.target_permeate_tds_mg_l, "mg/L")], ["Target boron", v(data.target_boron_mg_l, "mg/L")], ["Priority", PRIORITIES.find((p) => p.key === data.priority)?.title], ["Design flux", v(data.design_flux_lmh, "LMH")], ["Pressure-loss allowance", v(data.pressure_loss_allowance_bar, "bar")]] },
  ];
  return (
    <div className="grid gap-5 md:grid-cols-2">
      {sections.map((s) => (
        <div key={s.title} className="rounded-[3px] border border-line bg-white/50">
          <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
            <span className="text-[12px] font-semibold uppercase tracking-wider text-graphite-500">{s.title}</span>
            <button type="button" className="text-[12px] text-teal hover:underline" onClick={() => onEdit(s.step)}>Edit</button>
          </div>
          <dl className="divide-y divide-line/60">
            {s.rows.map(([k, val]) => (
              <div key={k} className="flex justify-between gap-4 px-4 py-2 text-[13px]">
                <dt className="text-graphite-500">{k}</dt>
                <dd className="text-right text-midnight">{val}</dd>
              </div>
            ))}
          </dl>
        </div>
      ))}
    </div>
  );
}
