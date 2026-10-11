import { Alert, PageLoader } from "../components/ui";
import { APPLICATION_LABELS, date } from "../lib/format";
import { AdminHeader, useLoad } from "./AdminApp";

interface Method {
  equations: { title: string; equation: string; note: string }[];
  assumptions: string[];
  unavailable: string[];
  policy: Record<string, number | number[]>;
  compatibility: Record<string, Record<string, string>>;
}

const CATEGORIES = ["BWRO", "BWRO-low-energy", "BWRO-fouling-resistant", "BWRO-high-rejection", "SWRO", "SWRO-low-energy", "Industrial"];

export default function Methodology() {
  const { data, error, loading } = useLoad<Method>("/api/admin/methodology");
  if (loading && !data) return <PageLoader />;
  if (error || !data) return <Alert tone="critical">{error}</Alert>;
  return (
    <div>
      <AdminHeader eyebrow="Engine" title="Calculation methodology">
        Internal reference for administrators and reviewers. These details appear in the report appendix but never on the client dashboard.
      </AdminHeader>
      <Alert tone="caution" title="Code correctness is not scientific validation">
        Automated tests confirm the equations are implemented as documented. Agreement with real RO performance has not been established by this software.
      </Alert>
      <div className="mt-6 grid gap-px overflow-hidden border border-line bg-line md:grid-cols-2">
        {data.equations.map((e) => (
          <div key={e.title} className="bg-ivory-50 p-5">
            <div className="text-[13.5px] font-medium text-midnight">{e.title}</div>
            <div className="num mt-2 rounded-[2px] bg-midnight px-3 py-2 text-[12.5px] text-ivory">{e.equation}</div>
            <div className="mt-2 text-[12.5px] text-graphite-500">{e.note}</div>
          </div>
        ))}
      </div>
      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <section className="panel p-5">
          <div className="text-[14px] font-medium text-midnight">Policy constants</div>
          <p className="mt-1 text-[12px] text-graphite-500">Engine choices, not literature values.</p>
          <dl className="mt-3 divide-y divide-line/70 text-[13px]">
            {Object.entries(data.policy).map(([k, v]) => (
              <div key={k} className="flex justify-between py-2"><dt className="text-graphite-500">{k}</dt><dd className="num">{Array.isArray(v) ? v.join(" – ") : v}</dd></div>
            ))}
          </dl>
        </section>
        <section className="panel p-5">
          <div className="text-[14px] font-medium text-midnight">Assumptions</div>
          <ul className="mt-3 space-y-2 text-[13px] text-graphite-700">{data.assumptions.map((a) => <li key={a}>• {a}</li>)}</ul>
        </section>
      </div>
      <section className="panel mt-6 overflow-x-auto">
        <div className="border-b border-line px-5 py-3 text-[14px] font-medium text-midnight">Application × category compatibility</div>
        <table className="table-clean w-full min-w-[800px]">
          <thead><tr><th>Application</th>{CATEGORIES.map((c) => <th key={c}>{c}</th>)}</tr></thead>
          <tbody>
            {Object.entries(data.compatibility).map(([app, row]) => (
              <tr key={app}>
                <td className="font-medium">{APPLICATION_LABELS[app]}</td>
                {CATEGORIES.map((c) => {
                  const v = row[c] ?? "incompatible";
                  return <td key={c} className={v === "compatible" ? "text-teal" : v === "conditional" ? "text-brass-700" : "text-alert"}>{v}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
        <div className="px-5 py-3 text-[12px] text-graphite-500">A “conditional” pairing becomes compatible when a source explicitly documents that membrane for the application.</div>
      </section>
    </div>
  );
}

interface AuditRow { id: number; created_at: string; username: string; action: string; entity: string; entity_id: string | null; details: Record<string, unknown> }

export function AuditLog() {
  const { data, error, loading } = useLoad<AuditRow[]>("/api/admin/audit?limit=300");
  if (loading && !data) return <PageLoader />;
  if (error || !data) return <Alert tone="critical">{error}</Alert>;
  return (
    <div>
      <AdminHeader eyebrow="Governance" title="Audit log">Significant dataset edits, verification changes, imports, backups and sign-ins.</AdminHeader>
      <div className="panel overflow-x-auto">
        <table className="table-clean w-full min-w-[800px]">
          <thead><tr><th>When</th><th>User</th><th>Action</th><th>Entity</th><th>Details</th></tr></thead>
          <tbody>
            {data.map((a) => (
              <tr key={a.id}>
                <td className="whitespace-nowrap text-graphite-500">{date(a.created_at)}</td>
                <td>{a.username}</td>
                <td className="font-medium">{a.action}</td>
                <td>{a.entity}{a.entity_id ? ` #${a.entity_id}` : ""}</td>
                <td className="num max-w-[420px] truncate text-[11px] text-graphite-500" title={JSON.stringify(a.details)}>{JSON.stringify(a.details)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
