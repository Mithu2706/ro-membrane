import { ArrowLeft, Download, Search } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Alert, Badge, Button, CheckIcon, EmptyState, PageLoader, StatusChip } from "../components/ui";
import { download } from "../lib/api";
import { APPLICATION_LABELS, date, fmt } from "../lib/format";
import type { AssessmentInput, AssessmentResult } from "../lib/types";
import { AdminHeader, useLoad } from "./AdminApp";
import { OutcomeBadge, type SubmissionSummary } from "./Overview";

export default function Submissions() {
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [application, setApplication] = useState("");
  const [outcome, setOutcome] = useState("");
  const [page, setPage] = useState(1);
  const params = new URLSearchParams({ page: String(page), page_size: "25" });
  if (query) params.set("q", query);
  if (application) params.set("application", application);
  if (outcome) params.set("outcome", outcome);
  const { data, error, loading } = useLoad<{ total: number; items: SubmissionSummary[]; page: number; page_size: number }>(`/api/admin/submissions?${params}`);

  return (
    <div>
      <AdminHeader
        eyebrow="Clients"
        title="Submissions"
        actions={<Button variant="secondary" size="sm" onClick={() => download("/api/admin/export/submissions.csv", "submissions.csv")}><Download className="h-3.5 w-3.5" /> Export CSV</Button>}
      >
        Every assessment is stored with its inputs, recommendation, warnings and evidence references.
      </AdminHeader>
      <form
        className="mb-5 flex flex-wrap gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          setPage(1);
          setQuery(q);
        }}
      >
        <div className="relative min-w-[260px] flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-graphite-300" />
          <input className="field-input pl-9" placeholder="Search client, organisation, project or membrane" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <select className="field-input w-auto" value={application} onChange={(e) => { setApplication(e.target.value); setPage(1); }} aria-label="Filter by application">
          <option value="">All applications</option>
          {Object.entries(APPLICATION_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <select className="field-input w-auto" value={outcome} onChange={(e) => { setOutcome(e.target.value); setPage(1); }} aria-label="Filter by outcome">
          <option value="">All outcomes</option>
          <option value="recommended">Recommended</option>
          <option value="no_supported_recommendation">No supported recommendation</option>
        </select>
        <Button type="submit" variant="secondary">Search</Button>
      </form>
      {error && <Alert tone="critical">{error}</Alert>}
      {loading && !data ? (
        <PageLoader />
      ) : data && data.items.length === 0 ? (
        <EmptyState title="No submissions match">Try a different search or filter.</EmptyState>
      ) : data ? (
        <div className="panel overflow-x-auto">
          <table className="table-clean w-full min-w-[860px]">
            <thead>
              <tr><th>#</th><th>Received</th><th>Client / project</th><th>Application</th><th className="text-right">Feed TDS</th><th className="text-right">Production</th><th>Outcome</th><th>Recommended</th></tr>
            </thead>
            <tbody>
              {data.items.map((s) => (
                <tr key={s.id} className="hover:bg-ivory-200/30">
                  <td className="num text-graphite-400"><Link to={`/admin/submissions/${s.id}`}>{s.id}</Link></td>
                  <td className="whitespace-nowrap text-graphite-500">{date(s.created_at)}</td>
                  <td>
                    <Link to={`/admin/submissions/${s.id}`} className="text-midnight hover:text-teal">{s.project_name || "Untitled"}</Link>
                    {s.input_origin === "demo" && <span className="ml-2"><Badge tone="alert">Demo data</Badge></span>}
                    <div className="text-[11.5px] text-graphite-400">{[s.client_name, s.client_organization].filter(Boolean).join(" · ") || "Anonymous"}</div>
                  </td>
                  <td className="text-graphite-500">{APPLICATION_LABELS[s.application]}</td>
                  <td className="num text-right">{fmt(s.feed_tds_mg_l)}</td>
                  <td className="num text-right">{fmt(s.permeate_flow_m3d)} <span className="text-graphite-400">m³/d</span></td>
                  <td><OutcomeBadge outcome={s.outcome} /></td>
                  <td className="text-[12.5px]">{s.recommended_membrane ?? <span className="text-graphite-300">—</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center justify-between border-t border-line px-4 py-3 text-[12.5px] text-graphite-500">
            <span>{data.total} submission(s)</span>
            <div className="flex gap-2">
              <Button size="sm" variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
              <Button size="sm" variant="secondary" disabled={page * data.page_size >= data.total} onClick={() => setPage(page + 1)}>Next</Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

interface SubmissionFull {
  id: number;
  reference: string;
  created_at: string;
  client_name: string | null;
  client_organization: string | null;
  client_email: string | null;
  project_name: string | null;
  application: string;
  inputs: AssessmentInput;
  result: AssessmentResult;
  outcome: string;
  engine_version: string;
}

export function SubmissionDetail() {
  const { id } = useParams();
  const { data: s, error, loading } = useLoad<SubmissionFull>(`/api/admin/submissions/${id}`);
  if (loading && !s) return <PageLoader />;
  if (error || !s) return <Alert tone="critical">{error ?? "Not found"}</Alert>;
  const r = s.result;
  const inputs = s.inputs;
  const chem = inputs.chemistry as unknown as Record<string, unknown>;
  const tech = (r.technical || {}) as Record<string, unknown>;
  return (
    <div>
      <Link to="/admin/submissions" className="mb-4 inline-flex items-center gap-1.5 text-[13px] text-graphite-500 hover:text-midnight"><ArrowLeft className="h-3.5 w-3.5" /> Submissions</Link>
      <AdminHeader
        eyebrow={`Submission #${s.id} · ${date(s.created_at)}`}
        title={s.project_name || "Untitled project"}
        actions={
          <>
            <a href={`/results/${s.reference}`} target="_blank" rel="noreferrer"><Button variant="secondary" size="sm">Client view</Button></a>
            <Button size="sm" onClick={() => download(`/api/admin/submissions/${s.id}/report.pdf`, "report.pdf")}><Download className="h-3.5 w-3.5" /> PDF report</Button>
          </>
        }
      >
        {[s.client_name, s.client_organization, s.client_email].filter(Boolean).join(" · ") || "No client details supplied"} — engine {s.engine_version}
      </AdminHeader>

      <div className="grid gap-6 xl:grid-cols-[1fr_1.4fr]">
        <section className="space-y-6">
          <div className="panel">
            <div className="border-b border-line px-5 py-3 text-[14px] font-medium text-midnight">Client requirements</div>
            <dl className="divide-y divide-line/60 text-[13px]">
              {[
                ["Application", APPLICATION_LABELS[inputs.application]],
                ["Feed TDS", `${fmt(inputs.feed_tds_mg_l)} mg/L`],
                ["Temperature", `${inputs.feed_temperature_c} °C`],
                ["Available pressure", `${inputs.available_pressure_bar} bar`],
                ["Production", `${fmt(inputs.permeate_flow_m3d)} m³/d`],
                ["Recovery", `${inputs.recovery_pct}%`],
                ["Target permeate TDS", inputs.target_permeate_tds_mg_l ?? "—"],
                ["Design flux", inputs.design_flux_lmh ? `${inputs.design_flux_lmh} LMH` : "—"],
                ["Priority", inputs.priority],
              ].map(([k, v]) => (
                <div key={k as string} className="flex justify-between px-5 py-2"><dt className="text-graphite-500">{k}</dt><dd className="num text-midnight">{v as string}</dd></div>
              ))}
            </dl>
          </div>
          <div className="panel">
            <div className="border-b border-line px-5 py-3 text-[14px] font-medium text-midnight">Water analysis (as submitted)</div>
            <dl className="grid grid-cols-2 gap-x-6 px-5 py-3 text-[12.5px]">
              {Object.entries(chem).map(([k, v]) => (
                <div key={k} className="flex justify-between border-b border-line/50 py-1.5">
                  <dt className="text-graphite-500">{k}</dt>
                  <dd className="num text-midnight">{v === null || v === undefined ? <span className="text-graphite-300">null</span> : Array.isArray(v) ? v.join(", ") || "—" : String(v)}</dd>
                </div>
              ))}
            </dl>
          </div>
          <div className="panel">
            <div className="border-b border-line px-5 py-3 text-[14px] font-medium text-midnight">System calculation values</div>
            <pre className="num overflow-x-auto px-5 py-3 text-[11.5px] leading-relaxed text-graphite-700">{JSON.stringify(tech, null, 2)}</pre>
          </div>
        </section>

        <section className="space-y-6">
          <div className="panel p-5">
            <div className="flex items-center gap-3"><OutcomeBadge outcome={r.outcome} /></div>
            <div className="mt-3 font-display text-[22px] text-midnight">{r.headline}</div>
            <p className="mt-1 text-[13.5px] text-graphite-500">{r.summary}</p>
            {r.warnings.length > 0 && (
              <ul className="mt-4 space-y-1.5 text-[12.5px]">
                {r.warnings.map((w, i) => <li key={i}><span className={w.severity === "critical" ? "text-alert" : "text-brass-700"}>{w.severity.toUpperCase()}</span> · <b className="font-medium">{w.title}:</b> {w.message}</li>)}
              </ul>
            )}
          </div>
          <div className="panel">
            <div className="border-b border-line px-5 py-3 text-[14px] font-medium text-midnight">Candidate screening (with technical detail)</div>
            <ul className="divide-y divide-line">
              {r.candidates.map((c) => (
                <li key={c.membrane_id} className="px-5 py-4">
                  <details>
                    <summary className="flex cursor-pointer flex-wrap items-center gap-3">
                      <span className="num w-6 text-[12px] text-graphite-300">{c.rank ?? "—"}</span>
                      <span className="flex-1 text-[13.5px] font-medium text-midnight">{c.name}</span>
                      <StatusChip status={c.status} label={c.status_label} size="sm" />
                    </summary>
                    <div className="mt-3 pl-9">
                      <ul className="space-y-1.5">
                        {c.checks.map((k) => (
                          <li key={k.key} className="flex gap-2 text-[12.5px]">
                            <CheckIcon status={k.status} className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                            <div><b className="font-medium">{k.label}:</b> {k.message}{k.detail && <div className="num text-[11.5px] text-graphite-400">{k.detail}</div>}</div>
                          </li>
                        ))}
                      </ul>
                      {c.technical && Object.keys(c.technical).length > 0 && (
                        <pre className="num mt-3 overflow-x-auto rounded-[3px] bg-ivory-200/50 p-3 text-[11px] text-graphite-700">{JSON.stringify(c.technical, null, 2)}</pre>
                      )}
                    </div>
                  </details>
                </li>
              ))}
            </ul>
          </div>
        </section>
      </div>
    </div>
  );
}
