import { AlertOctagon, ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis, Cell } from "recharts";
import { Alert, Badge, PageLoader, Stat, VerificationBadge, cx } from "../components/ui";
import { APPLICATION_LABELS, date } from "../lib/format";
import { AdminHeader, useLoad } from "./AdminApp";

interface Stats {
  submissions_total: number;
  submissions_by_outcome: Record<string, number>;
  submissions_by_application: Record<string, number>;
  membranes_active: number;
  membranes_archived: number;
  membranes_verified: number;
  sources_total: number;
  specifications_total: number;
  observations_total: number;
  coverage: { id: number; name: string; category: string; verification_status: string; critical_present: number; critical_total: number; missing: string[]; conflicts: string[]; spec_count: number }[];
  recent_submissions: SubmissionSummary[];
}
export interface SubmissionSummary {
  id: number;
  created_at: string;
  client_name: string | null;
  client_organization: string | null;
  project_name: string | null;
  application: string;
  outcome: string;
  recommended_membrane: string | null;
  feed_tds_mg_l: number | null;
  permeate_flow_m3d: number | null;
  recovery_pct: number | null;
  warning_count: number;
  input_origin?: "client" | "demo";
}

export function OutcomeBadge({ outcome }: { outcome: string }) {
  return outcome === "recommended" ? <Badge tone="teal">Recommended</Badge> : <Badge tone="alert">No supported recommendation</Badge>;
}

export default function Overview() {
  const { data, error, loading } = useLoad<Stats>("/api/admin/stats");
  if (loading && !data) return <PageLoader />;
  if (error || !data) return <Alert tone="critical" title="Could not load statistics">{error}</Alert>;

  const sorted = [...data.coverage].sort((a, b) => a.critical_present / a.critical_total - b.critical_present / b.critical_total);
  const appData = Object.entries(data.submissions_by_application).map(([k, v]) => ({ name: APPLICATION_LABELS[k] ?? k, v }));
  const conflicts = data.coverage.filter((c) => c.conflicts.length);

  return (
    <div>
      <AdminHeader eyebrow="Console" title="Overview">Evidence coverage and client activity at a glance.</AdminHeader>
      <div className="grid grid-cols-2 gap-px overflow-hidden border border-line bg-line md:grid-cols-4">
        <div className="bg-ivory-50 p-5"><Stat label="Submissions" value={data.submissions_total} sub={`${data.submissions_by_outcome.recommended ?? 0} with a recommendation`} /></div>
        <div className="bg-ivory-50 p-5"><Stat label="Active membranes" value={data.membranes_active} sub={`${data.membranes_verified} datasheet-verified · ${data.membranes_archived} archived`} /></div>
        <div className="bg-ivory-50 p-5"><Stat label="Specifications" value={data.specifications_total} sub={`${data.observations_total} experimental observations`} /></div>
        <div className="bg-ivory-50 p-5"><Stat label="Research sources" value={data.sources_total} /></div>
      </div>

      {conflicts.length > 0 && (
        <div className="mt-6">
          <Alert tone="caution" title={`${conflicts.length} membrane(s) with conflicting source values`}>
            {conflicts.map((c) => `${c.name} (${c.conflicts.join(", ")})`).join("; ")}
          </Alert>
        </div>
      )}

      <div className="mt-8 grid gap-6 xl:grid-cols-[1.5fr_1fr]">
        <section className="panel">
          <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
            <div className="text-[14px] font-medium text-midnight">Membrane evidence coverage</div>
            <div className="text-[11.5px] text-graphite-400">Key parameters needed for a full screening</div>
          </div>
          <div className="max-h-[480px] overflow-y-auto">
            <table className="table-clean w-full">
              <thead><tr><th>Membrane</th><th>Coverage</th><th>Missing</th><th>Status</th></tr></thead>
              <tbody>
                {sorted.map((c) => {
                  const pct = c.critical_present / c.critical_total;
                  return (
                    <tr key={c.id}>
                      <td><Link className="text-midnight hover:text-teal" to={`/admin/membranes/${c.id}`}>{c.name}</Link><div className="text-[11.5px] text-graphite-400">{c.category}</div></td>
                      <td className="w-40">
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 flex-1 bg-ivory-200"><div className={cx("h-full", pct === 1 ? "bg-teal" : pct >= 0.5 ? "bg-brass" : "bg-alert")} style={{ width: `${pct * 100}%` }} /></div>
                          <span className="num text-[11.5px] text-graphite-500">{c.critical_present}/{c.critical_total}</span>
                        </div>
                      </td>
                      <td className="text-[12px] text-graphite-500">
                        {c.missing.length ? c.missing.join(", ") : <span className="text-teal">Complete</span>}
                        {c.conflicts.length > 0 && <div className="mt-1 inline-flex items-center gap-1 text-alert"><AlertOctagon className="h-3 w-3" /> conflict</div>}
                      </td>
                      <td><VerificationBadge status={c.verification_status} /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        <div className="space-y-6">
          <section className="panel p-5">
            <div className="text-[14px] font-medium text-midnight">Submissions by application</div>
            {appData.length ? (
              <div className="mt-3 h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={appData} layout="vertical" margin={{ left: 0, right: 16 }}>
                    <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: "#5B6663" }} />
                    <YAxis type="category" dataKey="name" width={150} tick={{ fontSize: 11.5, fill: "#202927" }} />
                    <Tooltip cursor={{ fill: "rgba(16,42,42,0.04)" }} />
                    <Bar dataKey="v" name="Submissions" barSize={12}>
                      {appData.map((d, i) => <Cell key={d.name} fill={i % 2 ? "#C29B58" : "#2D7771"} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="mt-3 text-[13px] text-graphite-400">No submissions yet.</div>
            )}
          </section>
          <section className="panel">
            <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
              <div className="text-[14px] font-medium text-midnight">Recent submissions</div>
              <Link to="/admin/submissions" className="inline-flex items-center gap-1 text-[12.5px] text-teal hover:underline">All <ArrowRight className="h-3 w-3" /></Link>
            </div>
            <ul className="divide-y divide-line/70">
              {data.recent_submissions.length === 0 && <li className="px-5 py-4 text-[13px] text-graphite-400">No submissions yet.</li>}
              {data.recent_submissions.map((s) => (
                <li key={s.id}>
                  <Link to={`/admin/submissions/${s.id}`} className="block px-5 py-3 hover:bg-ivory-200/40">
                    <div className="flex items-center justify-between gap-3">
                      <span className="truncate text-[13px] text-midnight">{s.project_name || s.client_organization || s.client_name || `Submission #${s.id}`}</span>
                      <OutcomeBadge outcome={s.outcome} />
                    </div>
                    <div className="mt-0.5 text-[11.5px] text-graphite-400">{APPLICATION_LABELS[s.application]} · {date(s.created_at)}</div>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>
    </div>
  );
}
