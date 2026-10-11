import { AlertOctagon, Archive, ArchiveRestore, ArrowLeft, Pencil, Plus, Trash2, X } from "lucide-react";
import { FormEvent, ReactNode, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Alert, Badge, Button, EmptyState, Field, PageLoader, VerificationBadge, cx } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { APPLICATION_LABELS, EVIDENCE_LABELS, VERIFICATION_LABELS } from "../lib/format";
import { AdminHeader, useLoad } from "./AdminApp";

export interface Vocab {
  parameters: Record<string, { label: string; unit: string }>;
  evidence_types: string[];
  verification_statuses: string[];
  categories: string[];
  source_types: string[];
  applications: string[];
}

interface MembraneRow {
  id: number;
  manufacturer: string;
  model: string;
  display_name: string;
  category: string;
  intended_applications: string[];
  element_size: string | null;
  verification_status: string;
  archived: boolean;
  spec_count: number;
  observation_count: number;
  conflicts: string[];
  missing_critical: string[];
}

export default function Membranes() {
  const [showArchived, setShowArchived] = useState(false);
  const [creating, setCreating] = useState(false);
  const [filter, setFilter] = useState("");
  const { data, error, loading, reload } = useLoad<MembraneRow[]>("/api/admin/membranes");
  const rows = (data || []).filter((m) => (showArchived || !m.archived) && m.display_name.toLowerCase().includes(filter.toLowerCase()));
  return (
    <div>
      <AdminHeader eyebrow="Research dataset" title="Membranes" actions={<Button size="sm" onClick={() => setCreating(true)}><Plus className="h-3.5 w-3.5" /> Add membrane</Button>}>
        Exact commercial models with their rated specifications and experimental observations. Missing values are never filled in.
      </AdminHeader>
      {creating && (
        <Modal title="Add membrane" onClose={() => setCreating(false)}>
          <MembraneForm onSaved={() => { setCreating(false); reload(); }} />
        </Modal>
      )}
      <div className="mb-4 flex flex-wrap items-center gap-4">
        <input className="field-input max-w-xs" placeholder="Filter by name" value={filter} onChange={(e) => setFilter(e.target.value)} />
        <label className="inline-flex items-center gap-2 text-[13px] text-graphite-500">
          <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} /> Show archived
        </label>
      </div>
      {error && <Alert tone="critical">{error}</Alert>}
      {loading && !data ? <PageLoader /> : (
        <div className="panel overflow-x-auto">
          <table className="table-clean w-full min-w-[820px]">
            <thead><tr><th>Membrane</th><th>Category</th><th>Applications</th><th className="text-right">Specs</th><th className="text-right">Obs.</th><th>Data gaps</th><th>Verification</th></tr></thead>
            <tbody>
              {rows.map((m) => (
                <tr key={m.id} className={cx("hover:bg-ivory-200/30", m.archived && "opacity-50")}>
                  <td><Link className="font-medium text-midnight hover:text-teal" to={`/admin/membranes/${m.id}`}>{m.display_name}</Link>{m.archived && <span className="ml-2"><Badge>Archived</Badge></span>}</td>
                  <td className="text-graphite-500">{m.category}</td>
                  <td className="text-[12px] text-graphite-500">{m.intended_applications.map((a) => APPLICATION_LABELS[a] ?? a).join(", ") || "—"}</td>
                  <td className="num text-right">{m.spec_count}</td>
                  <td className="num text-right">{m.observation_count}</td>
                  <td className="text-[12px]">
                    {m.missing_critical.length ? <span className="text-graphite-500">{m.missing_critical.length} key value(s) missing</span> : <span className="text-teal">Key values present</span>}
                    {m.conflicts.length > 0 && <div className="inline-flex items-center gap-1 text-alert"><AlertOctagon className="h-3 w-3" /> conflict: {m.conflicts.join(", ")}</div>}
                  </td>
                  <td><VerificationBadge status={m.verification_status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function Modal({ title, onClose, children, wide }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-midnight/50 p-4 backdrop-blur-[1px]" role="dialog" aria-modal="true" aria-label={title}>
      <div className={cx("my-10 w-full rounded-[3px] bg-ivory-50 shadow-lift animate-rise", wide ? "max-w-3xl" : "max-w-xl")}>
        <div className="flex items-center justify-between border-b border-line px-6 py-4">
          <h3 className="text-[20px]">{title}</h3>
          <button onClick={onClose} aria-label="Close" className="text-graphite-400 hover:text-midnight"><X className="h-5 w-5" /></button>
        </div>
        <div className="px-6 py-5">{children}</div>
      </div>
    </div>
  );
}

function useVocab() {
  return useLoad<Vocab>("/api/admin/vocabularies").data;
}

interface MembraneFull extends MembraneRow {
  feed_limitations: string | null;
  notes: string | null;
  specifications: Spec[];
  observations: Obs[];
  resolved: Record<string, { value: number | null; spec_id: number }>;
  conflicts: string[] & Record<string, unknown>;
}
interface Spec {
  id: number;
  parameter: string;
  label: string;
  value: number | null;
  value_min: number | null;
  value_max: number | null;
  value_text: string | null;
  unit: string;
  source_id: number | null;
  source_title: string | null;
  evidence_type: string;
  test_conditions: string | null;
  verification_status: string;
  notes: string | null;
}
interface Obs {
  id: number;
  evidence_type: string;
  feed_description: string | null;
  feed_salinity_text: string | null;
  pressure_bar: number | null;
  pressure_text: string | null;
  temperature_c: number | null;
  recovery_text: string | null;
  salt_rejection_pct: number | null;
  performance_text: string | null;
  permeate_concentration_text: string | null;
  test_method: string | null;
  source_title: string | null;
  verification_status: string;
  notes: string | null;
}

function MembraneForm({ initial, onSaved }: { initial?: Partial<MembraneFull>; onSaved: (id: number) => void }) {
  const vocab = useVocab();
  const [f, setF] = useState({
    manufacturer: initial?.manufacturer ?? "",
    model: initial?.model ?? "",
    category: initial?.category ?? "BWRO",
    intended_applications: initial?.intended_applications ?? [],
    element_size: initial?.element_size ?? "",
    feed_limitations: initial?.feed_limitations ?? "",
    verification_status: initial?.verification_status ?? "unverified",
    notes: initial?.notes ?? "",
  });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const body = { ...f, element_size: f.element_size || null, feed_limitations: f.feed_limitations || null, notes: f.notes || null };
      const r = initial?.id
        ? await api<{ id: number }>(`/api/admin/membranes/${initial.id}`, { method: "PUT", json: body })
        : await api<{ id: number }>("/api/admin/membranes", { method: "POST", json: body });
      onSaved(r.id);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }
  if (!vocab) return <PageLoader />;
  return (
    <form onSubmit={save} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Manufacturer"><input className="field-input" required value={f.manufacturer} onChange={(e) => setF({ ...f, manufacturer: e.target.value })} /></Field>
        <Field label="Exact model"><input className="field-input" required value={f.model} onChange={(e) => setF({ ...f, model: e.target.value })} /></Field>
        <Field label="Category">
          <select className="field-input" value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>{vocab.categories.map((c) => <option key={c}>{c}</option>)}</select>
        </Field>
        <Field label="Element size" optional><input className="field-input" value={f.element_size} onChange={(e) => setF({ ...f, element_size: e.target.value })} placeholder="e.g. 8 x 40 in" /></Field>
      </div>
      <div>
        <div className="mb-1.5 text-[13px] font-medium text-midnight">Documented applications</div>
        <div className="flex flex-wrap gap-2">
          {vocab.applications.map((a) => {
            const on = f.intended_applications.includes(a);
            return (
              <button type="button" key={a} onClick={() => setF({ ...f, intended_applications: on ? f.intended_applications.filter((x) => x !== a) : [...f.intended_applications, a] })}
                className={cx("rounded-full border px-3 py-1 text-[12px]", on ? "border-teal bg-teal-50 text-teal-700" : "border-line text-graphite-500")}>{APPLICATION_LABELS[a]}</button>
            );
          })}
        </div>
        <div className="mt-1 text-[11.5px] text-graphite-400">Only list applications stated by a source.</div>
      </div>
      <Field label="Feed-water limitations" optional><textarea className="field-input min-h-[64px]" value={f.feed_limitations} onChange={(e) => setF({ ...f, feed_limitations: e.target.value })} /></Field>
      <Field label="Notes and uncertainty" optional><textarea className="field-input min-h-[64px]" value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} /></Field>
      <Field label="Verification status">
        <select className="field-input" value={f.verification_status} onChange={(e) => setF({ ...f, verification_status: e.target.value })}>{vocab.verification_statuses.map((v) => <option key={v} value={v}>{VERIFICATION_LABELS[v]}</option>)}</select>
      </Field>
      {err && <Alert tone="critical">{err}</Alert>}
      <div className="flex justify-end"><Button type="submit" loading={busy}>Save membrane</Button></div>
    </form>
  );
}

export function MembraneDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { data: m, error, loading, reload } = useLoad<MembraneFull>(`/api/admin/membranes/${id}`);
  const vocab = useVocab();
  const sources = useLoad<{ id: number; title: string }[]>("/api/admin/sources").data;
  const [editing, setEditing] = useState(false);
  const [specForm, setSpecForm] = useState<Partial<Spec> | null>(null);
  const [obsForm, setObsForm] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  if (loading && !m) return <PageLoader />;
  if (error || !m) return <Alert tone="critical">{error ?? "Not found"}</Alert>;

  const act = async (fn: () => Promise<unknown>, ok: string) => {
    try {
      await fn();
      setMsg(ok);
      reload();
    } catch (e) {
      setMsg((e as Error).message);
    }
  };
  const conflictKeys = Object.keys(m.conflicts || {});

  return (
    <div>
      <Link to="/admin/membranes" className="mb-4 inline-flex items-center gap-1.5 text-[13px] text-graphite-500 hover:text-midnight"><ArrowLeft className="h-3.5 w-3.5" /> Membranes</Link>
      <AdminHeader
        eyebrow={`${m.category}${m.element_size ? ` · ${m.element_size}` : ""}`}
        title={m.display_name}
        actions={
          <>
            <select
              aria-label="Membrane verification status"
              className="field-input h-8 w-auto !py-0 text-[12.5px]"
              value={m.verification_status}
              onChange={(e) => act(() => api(`/api/admin/membranes/${m.id}/verify`, { method: "POST", json: { verification_status: e.target.value } }), "Verification status updated")}
            >
              {vocab?.verification_statuses.map((v) => <option key={v} value={v}>{VERIFICATION_LABELS[v]}</option>)}
            </select>
            <Button size="sm" variant="secondary" onClick={() => setEditing(true)}><Pencil className="h-3.5 w-3.5" /> Edit</Button>
            <Button size="sm" variant={m.archived ? "secondary" : "danger"} onClick={() => act(() => api(`/api/admin/membranes/${m.id}/archive`, { method: "POST", json: { archived: !m.archived } }), m.archived ? "Restored" : "Archived")}>
              {m.archived ? <><ArchiveRestore className="h-3.5 w-3.5" /> Restore</> : <><Archive className="h-3.5 w-3.5" /> Archive</>}
            </Button>
          </>
        }
      >
        {m.notes}
      </AdminHeader>
      {msg && <div className="mb-4"><Alert tone="info">{msg}</Alert></div>}
      {m.archived && <div className="mb-4"><Alert tone="caution" title="Archived">This membrane is excluded from client recommendations.</Alert></div>}
      {m.missing_critical.length > 0 && (
        <div className="mb-4"><Alert tone="caution" title="Missing key specifications">{m.missing_critical.join(", ")}. The engine will report "insufficient evidence" for checks that need these values.</Alert></div>
      )}
      {conflictKeys.length > 0 && (
        <div className="mb-4"><Alert tone="critical" title="Source conflict">Different manufacturer-rated values are recorded for: {conflictKeys.join(", ")}. The verified value is used; review the records below.</Alert></div>
      )}
      {editing && (
        <Modal title="Edit membrane" onClose={() => setEditing(false)}>
          <MembraneForm initial={m} onSaved={() => { setEditing(false); reload(); }} />
        </Modal>
      )}
      {specForm && vocab && (
        <Modal title={specForm.id ? "Edit specification" : "Add specification"} onClose={() => setSpecForm(null)} wide>
          <SpecForm membraneId={m.id} initial={specForm} vocab={vocab} sources={sources || []} onSaved={() => { setSpecForm(null); reload(); }} />
        </Modal>
      )}
      {obsForm && vocab && (
        <Modal title="Add experimental observation" onClose={() => setObsForm(false)} wide>
          <ObsForm membraneId={m.id} vocab={vocab} sources={sources || []} onSaved={() => { setObsForm(false); reload(); }} />
        </Modal>
      )}

      <section className="panel">
        <div className="flex items-center justify-between border-b border-line px-5 py-3">
          <div>
            <div className="text-[14px] font-medium text-midnight">Rated and calculated specifications</div>
            <div className="text-[11.5px] text-graphite-400">Manufacturer ratings only. Experimental results belong in observations.</div>
          </div>
          <Button size="sm" onClick={() => setSpecForm({})}><Plus className="h-3.5 w-3.5" /> Add value</Button>
        </div>
        {m.specifications.length === 0 ? (
          <div className="p-5"><EmptyState title="No specifications recorded">All values will show as “Not reported” to clients.</EmptyState></div>
        ) : (
          <div className="overflow-x-auto">
            <table className="table-clean w-full min-w-[980px]">
              <thead><tr><th>Parameter</th><th>Value</th><th>Evidence</th><th>Test conditions</th><th>Source</th><th>Verification</th><th></th></tr></thead>
              <tbody>
                {m.specifications.map((s) => {
                  const used = m.resolved[s.parameter]?.spec_id === s.id;
                  return (
                    <tr key={s.id} className={cx(conflictKeys.includes(s.parameter) && "bg-alert-50/40")}>
                      <td>{s.label}{used && <div className="text-[10.5px] uppercase tracking-wider text-teal">used by engine</div>}</td>
                      <td className="num whitespace-nowrap">{s.value ?? (s.value_min != null ? `${s.value_min}–${s.value_max}` : "—")} {s.unit}{s.value_text && <div className="font-sans text-[11px] text-graphite-400">“{s.value_text}”</div>}</td>
                      <td className="text-[12px]">{EVIDENCE_LABELS[s.evidence_type] ?? s.evidence_type}</td>
                      <td className="max-w-[220px] text-[11.5px] text-graphite-500">{s.test_conditions ?? "—"}</td>
                      <td className="max-w-[220px] text-[11.5px] text-graphite-500">{s.source_title ?? <span className="text-alert">No source</span>}</td>
                      <td>
                        <select aria-label="Specification verification" className="rounded-[2px] border border-line bg-white px-1.5 py-1 text-[11.5px]" value={s.verification_status}
                          onChange={(e) => act(() => api(`/api/admin/specifications/${s.id}/verify`, { method: "POST", json: { verification_status: e.target.value } }), "Specification verification updated")}>
                          {vocab?.verification_statuses.map((v) => <option key={v} value={v}>{VERIFICATION_LABELS[v]}</option>)}
                        </select>
                      </td>
                      <td className="whitespace-nowrap text-right">
                        <button className="p-1 text-graphite-400 hover:text-teal" aria-label="Edit" onClick={() => setSpecForm(s)}><Pencil className="h-3.5 w-3.5" /></button>
                        <button className="p-1 text-graphite-400 hover:text-alert" aria-label="Delete"
                          onClick={() => confirm(`Delete ${s.label}?`) && act(() => api(`/api/admin/specifications/${s.id}`, { method: "DELETE" }), "Specification deleted")}><Trash2 className="h-3.5 w-3.5" /></button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="panel mt-6">
        <div className="flex items-center justify-between border-b border-line px-5 py-3">
          <div className="text-[14px] font-medium text-midnight">Experimental, pilot and plant observations</div>
          <Button size="sm" variant="secondary" onClick={() => setObsForm(true)}><Plus className="h-3.5 w-3.5" /> Add observation</Button>
        </div>
        {m.observations.length === 0 ? (
          <div className="px-5 py-4 text-[13px] text-graphite-400">No observations recorded.</div>
        ) : (
          <ul className="divide-y divide-line">
            {m.observations.map((o) => (
              <li key={o.id} className="grid gap-3 px-5 py-4 md:grid-cols-[1fr_auto]">
                <div className="text-[13px]">
                  <div className="flex flex-wrap items-center gap-2"><Badge>{EVIDENCE_LABELS[o.evidence_type]}</Badge><span className="text-graphite-500">{o.feed_description}</span><VerificationBadge status={o.verification_status} /></div>
                  <div className="mt-1.5 text-midnight">{o.performance_text}</div>
                  <div className="mt-1 text-[12px] text-graphite-500">
                    {[o.feed_salinity_text && `Feed ${o.feed_salinity_text}`, (o.pressure_text || o.pressure_bar) && `Pressure ${o.pressure_text ?? o.pressure_bar + " bar"}`,
                      o.temperature_c != null && `${o.temperature_c} °C`, o.recovery_text && `Recovery ${o.recovery_text}`, o.permeate_concentration_text && `Permeate ${o.permeate_concentration_text}`, o.test_method]
                      .filter(Boolean).join(" · ")}
                  </div>
                  <div className="mt-1 text-[11.5px] text-graphite-400">{o.source_title}</div>
                </div>
                <button className="self-start p-1 text-graphite-400 hover:text-alert" aria-label="Delete observation"
                  onClick={() => confirm("Delete this observation?") && act(() => api(`/api/admin/observations/${o.id}`, { method: "DELETE" }), "Observation deleted")}><Trash2 className="h-3.5 w-3.5" /></button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="mt-6 text-right">
        <button className="text-[12px] text-graphite-400 hover:text-midnight" onClick={() => nav("/admin/membranes")}>Back to list</button>
      </div>
    </div>
  );
}

const num = (s: string) => (s.trim() === "" ? null : Number(s));

function SpecForm({ membraneId, initial, vocab, sources, onSaved }: { membraneId: number; initial: Partial<Spec>; vocab: Vocab; sources: { id: number; title: string }[]; onSaved: () => void }) {
  const [f, setF] = useState({
    parameter: initial.parameter ?? Object.keys(vocab.parameters)[0],
    value: initial.value?.toString() ?? "",
    value_min: initial.value_min?.toString() ?? "",
    value_max: initial.value_max?.toString() ?? "",
    value_text: initial.value_text ?? "",
    source_id: initial.source_id?.toString() ?? "",
    evidence_type: initial.evidence_type ?? "manufacturer-rated",
    test_conditions: initial.test_conditions ?? "",
    verification_status: initial.verification_status ?? "unverified",
    notes: initial.notes ?? "",
  });
  const [err, setErr] = useState<string | null>(null);
  const unit = vocab.parameters[f.parameter]?.unit;
  async function save(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    const body = {
      parameter: f.parameter, value: num(f.value), value_min: num(f.value_min), value_max: num(f.value_max), value_text: f.value_text || null,
      unit, source_id: f.source_id ? Number(f.source_id) : null, evidence_type: f.evidence_type, test_conditions: f.test_conditions || null,
      verification_status: f.verification_status, notes: f.notes || null,
    };
    try {
      if (initial.id) await api(`/api/admin/specifications/${initial.id}`, { method: "PUT", json: body });
      else await api(`/api/admin/membranes/${membraneId}/specifications`, { method: "POST", json: body });
      onSaved();
    } catch (e) {
      setErr((e as Error).message);
    }
  }
  return (
    <form onSubmit={save} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Parameter">
          <select className="field-input" value={f.parameter} onChange={(e) => setF({ ...f, parameter: e.target.value })}>
            {Object.entries(vocab.parameters).map(([k, v]) => <option key={k} value={k}>{v.label} ({v.unit})</option>)}
          </select>
        </Field>
        <Field label="Evidence type" tooltip="Manufacturer ratings and calculated values belong here. Experimental results should be recorded as observations.">
          <select className="field-input" value={f.evidence_type} onChange={(e) => setF({ ...f, evidence_type: e.target.value })}>
            {vocab.evidence_types.map((v) => <option key={v} value={v}>{EVIDENCE_LABELS[v] ?? v}</option>)}
          </select>
        </Field>
        <Field label="Value" unit={unit} hint="Leave empty if only a range or text is reported"><input className="field-input num pr-16" type="number" step="any" value={f.value} onChange={(e) => setF({ ...f, value: e.target.value })} /></Field>
        <Field label="Verbatim source text" optional><input className="field-input" value={f.value_text} onChange={(e) => setF({ ...f, value_text: e.target.value })} placeholder='e.g. "600 psig (41 bar)"' /></Field>
        <Field label="Range minimum" unit={unit} optional><input className="field-input num pr-16" type="number" step="any" value={f.value_min} onChange={(e) => setF({ ...f, value_min: e.target.value })} /></Field>
        <Field label="Range maximum" unit={unit} optional><input className="field-input num pr-16" type="number" step="any" value={f.value_max} onChange={(e) => setF({ ...f, value_max: e.target.value })} /></Field>
      </div>
      <Field label="Source">
        <select className="field-input" value={f.source_id} onChange={(e) => setF({ ...f, source_id: e.target.value })}>
          <option value="">— No source (not recommended) —</option>
          {sources.map((s) => <option key={s.id} value={s.id}>[{s.id}] {s.title.slice(0, 110)}</option>)}
        </select>
      </Field>
      <Field label="Original test conditions" optional><textarea className="field-input min-h-[56px]" value={f.test_conditions} onChange={(e) => setF({ ...f, test_conditions: e.target.value })} /></Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Verification status">
          <select className="field-input" value={f.verification_status} onChange={(e) => setF({ ...f, verification_status: e.target.value })}>
            {vocab.verification_statuses.map((v) => <option key={v} value={v}>{VERIFICATION_LABELS[v]}</option>)}
          </select>
        </Field>
        <Field label="Notes / uncertainty" optional><input className="field-input" value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} /></Field>
      </div>
      {err && <Alert tone="critical">{err}</Alert>}
      <div className="flex justify-end"><Button type="submit">Save specification</Button></div>
    </form>
  );
}

function ObsForm({ membraneId, vocab, sources, onSaved }: { membraneId: number; vocab: Vocab; sources: { id: number; title: string }[]; onSaved: () => void }) {
  const [f, setF] = useState<Record<string, string>>({ evidence_type: "laboratory-experimental", verification_status: "unverified" });
  const [err, setErr] = useState<string | null>(null);
  const set = (k: string) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  async function save(e: FormEvent) {
    e.preventDefault();
    const nums = ["feed_salinity_mg_l", "pressure_bar", "temperature_c", "salt_rejection_pct"];
    const body: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(f)) body[k] = v === "" ? null : nums.includes(k) ? Number(v) : k === "source_id" ? Number(v) : v;
    try {
      await api(`/api/admin/membranes/${membraneId}/observations`, { method: "POST", json: body });
      onSaved();
    } catch (e) {
      setErr((e as Error).message);
    }
  }
  return (
    <form onSubmit={save} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Evidence type">
          <select className="field-input" value={f.evidence_type} onChange={set("evidence_type")}>
            <option value="laboratory-experimental">Laboratory test</option><option value="pilot-plant">Pilot / plant data</option>
          </select>
        </Field>
        <Field label="Feed description"><input className="field-input" value={f.feed_description ?? ""} onChange={set("feed_description")} /></Field>
        <Field label="Feed salinity" unit="mg/L" optional><input className="field-input num pr-16" type="number" step="any" value={f.feed_salinity_mg_l ?? ""} onChange={set("feed_salinity_mg_l")} /></Field>
        <Field label="Pressure" unit="bar" optional><input className="field-input num pr-14" type="number" step="any" value={f.pressure_bar ?? ""} onChange={set("pressure_bar")} /></Field>
        <Field label="Temperature" unit="°C" optional><input className="field-input num pr-12" type="number" step="any" value={f.temperature_c ?? ""} onChange={set("temperature_c")} /></Field>
        <Field label="Salt rejection" unit="%" optional><input className="field-input num pr-12" type="number" step="any" value={f.salt_rejection_pct ?? ""} onChange={set("salt_rejection_pct")} /></Field>
        <Field label="Recovery (as reported)" optional><input className="field-input" value={f.recovery_text ?? ""} onChange={set("recovery_text")} /></Field>
        <Field label="Permeate concentration (as reported)" optional><input className="field-input" value={f.permeate_concentration_text ?? ""} onChange={set("permeate_concentration_text")} /></Field>
      </div>
      <Field label="Performance result"><textarea className="field-input min-h-[56px]" value={f.performance_text ?? ""} onChange={set("performance_text")} /></Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Test method" optional><input className="field-input" value={f.test_method ?? ""} onChange={set("test_method")} /></Field>
        <Field label="Verification status">
          <select className="field-input" value={f.verification_status} onChange={set("verification_status")}>{vocab.verification_statuses.map((v) => <option key={v} value={v}>{VERIFICATION_LABELS[v]}</option>)}</select>
        </Field>
      </div>
      <Field label="Source">
        <select className="field-input" value={f.source_id ?? ""} onChange={set("source_id")}>
          <option value="">— Select —</option>
          {sources.map((s) => <option key={s.id} value={s.id}>[{s.id}] {s.title.slice(0, 110)}</option>)}
        </select>
      </Field>
      {err && <Alert tone="critical">{err}</Alert>}
      <div className="flex justify-end"><Button type="submit">Save observation</Button></div>
    </form>
  );
}
