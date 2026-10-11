import { ExternalLink, Pencil, Plus } from "lucide-react";
import { FormEvent, useState } from "react";
import { Alert, Badge, Button, Field, PageLoader } from "../components/ui";
import { api } from "../lib/api";
import { VERIFICATION_LABELS } from "../lib/format";
import type { Source } from "../lib/types";
import { AdminHeader, useLoad } from "./AdminApp";
import { Modal, type Vocab } from "./Membranes";

type SourceRow = Source & { spec_count: number; observation_count: number };

export default function Sources() {
  const { data, error, loading, reload } = useLoad<SourceRow[]>("/api/admin/sources");
  const vocab = useLoad<Vocab>("/api/admin/vocabularies").data;
  const [form, setForm] = useState<Partial<Source> | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  return (
    <div>
      <AdminHeader eyebrow="Research dataset" title="Sources" actions={<Button size="sm" onClick={() => setForm({})}><Plus className="h-3.5 w-3.5" /> Add source</Button>}>
        Datasheets, papers and reports behind every stored value.
      </AdminHeader>
      {msg && <div className="mb-4"><Alert tone="info">{msg}</Alert></div>}
      {form && vocab && (
        <Modal title={form.id ? "Edit source" : "Add source"} onClose={() => setForm(null)} wide>
          <SourceForm initial={form} vocab={vocab} onSaved={() => { setForm(null); reload(); }} />
        </Modal>
      )}
      {error && <Alert tone="critical">{error}</Alert>}
      {loading && !data ? <PageLoader /> : (
        <div className="panel overflow-x-auto">
          <table className="table-clean w-full min-w-[900px]">
            <thead><tr><th>#</th><th>Source</th><th>Type</th><th className="text-right">Used by</th><th>Verification</th><th></th></tr></thead>
            <tbody>
              {(data || []).map((s) => {
                const link = s.url || (s.doi ? `https://doi.org/${s.doi}` : null);
                return (
                  <tr key={s.id}>
                    <td className="num text-graphite-400">{s.id}</td>
                    <td className="max-w-[520px]">
                      <div className="text-midnight">{s.title}</div>
                      <div className="text-[11.5px] text-graphite-400">{[s.authors, s.year, s.publisher, s.page_table].filter(Boolean).join(" · ")}</div>
                      {link && <a className="mt-0.5 inline-flex items-center gap-1 text-[11.5px] text-teal hover:underline" href={link} target="_blank" rel="noreferrer noopener">{s.doi ? `doi:${s.doi}` : link.slice(0, 60)} <ExternalLink className="h-3 w-3" /></a>}
                      {s.notes && <div className="mt-1 text-[11.5px] text-graphite-500">{s.notes}</div>}
                    </td>
                    <td><Badge>{s.source_type.replace(/-/g, " ")}</Badge></td>
                    <td className="num whitespace-nowrap text-right text-[12px]">{s.spec_count} spec · {s.observation_count} obs</td>
                    <td>
                      <select aria-label="Source verification" className="rounded-[2px] border border-line bg-white px-1.5 py-1 text-[11.5px]" value={s.verification_status}
                        onChange={async (e) => { await api(`/api/admin/sources/${s.id}/verify`, { method: "POST", json: { verification_status: e.target.value } }); setMsg("Source verification updated"); reload(); }}>
                        {vocab?.verification_statuses.map((v) => <option key={v} value={v}>{VERIFICATION_LABELS[v]}</option>)}
                      </select>
                    </td>
                    <td><button aria-label="Edit source" className="p-1 text-graphite-400 hover:text-teal" onClick={() => setForm(s)}><Pencil className="h-3.5 w-3.5" /></button></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function SourceForm({ initial, vocab, onSaved }: { initial: Partial<Source>; vocab: Vocab; onSaved: () => void }) {
  const [f, setF] = useState<Record<string, string>>({
    title: initial.title ?? "", authors: initial.authors ?? "", year: initial.year?.toString() ?? "", doi: initial.doi ?? "", url: initial.url ?? "",
    source_type: initial.source_type ?? "peer-reviewed", publisher: initial.publisher ?? "", page_table: initial.page_table ?? "",
    verification_status: initial.verification_status ?? "unverified", notes: initial.notes ?? "",
  });
  const [err, setErr] = useState<string | null>(null);
  const set = (k: string) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  async function save(e: FormEvent) {
    e.preventDefault();
    const body: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(f)) body[k] = v === "" ? null : k === "year" ? Number(v) : v;
    try {
      if (initial.id) await api(`/api/admin/sources/${initial.id}`, { method: "PUT", json: body });
      else await api("/api/admin/sources", { method: "POST", json: body });
      onSaved();
    } catch (e) {
      setErr((e as Error).message);
    }
  }
  return (
    <form onSubmit={save} className="space-y-4">
      <Field label="Title"><input className="field-input" required value={f.title} onChange={set("title")} /></Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Authors" optional><input className="field-input" value={f.authors} onChange={set("authors")} /></Field>
        <Field label="Year" optional><input className="field-input num" type="number" value={f.year} onChange={set("year")} /></Field>
        <Field label="DOI" optional><input className="field-input" value={f.doi} onChange={set("doi")} placeholder="10.xxxx/..." /></Field>
        <Field label="URL" optional><input className="field-input" value={f.url} onChange={set("url")} placeholder="https://" /></Field>
        <Field label="Source type"><select className="field-input" value={f.source_type} onChange={set("source_type")}>{vocab.source_types.map((t) => <option key={t}>{t}</option>)}</select></Field>
        <Field label="Publication / manufacturer" optional><input className="field-input" value={f.publisher} onChange={set("publisher")} /></Field>
        <Field label="Relevant page / table" optional><input className="field-input" value={f.page_table} onChange={set("page_table")} /></Field>
        <Field label="Verification status"><select className="field-input" value={f.verification_status} onChange={set("verification_status")}>{vocab.verification_statuses.map((v) => <option key={v} value={v}>{VERIFICATION_LABELS[v]}</option>)}</select></Field>
      </div>
      <Field label="Notes" optional><textarea className="field-input min-h-[56px]" value={f.notes} onChange={set("notes")} /></Field>
      {err && <Alert tone="critical">{err}</Alert>}
      <div className="flex justify-end"><Button type="submit">Save source</Button></div>
    </form>
  );
}
