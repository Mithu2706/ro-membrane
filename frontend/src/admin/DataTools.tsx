import { DatabaseBackup, Download, FileSpreadsheet, Upload } from "lucide-react";
import { useState } from "react";
import { Alert, Button } from "../components/ui";
import { api, download } from "../lib/api";
import { AdminHeader } from "./AdminApp";

const DATASETS = [
  ["submissions", "Client submissions"],
  ["membranes", "Membranes"],
  ["specifications", "Specifications"],
  ["observations", "Experimental observations"],
  ["sources", "Research sources"],
] as const;

interface ImportResult {
  dry_run: boolean;
  valid_rows: number;
  errors: { row: number; error: string }[];
  imported: number;
}

export default function DataTools() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ tone: "success" | "critical"; text: string } | null>(null);

  const run = async (key: string, fn: () => Promise<void>) => {
    setBusy(key);
    setMsg(null);
    try {
      await fn();
    } catch (e) {
      setMsg({ tone: "critical", text: (e as Error).message });
    } finally {
      setBusy(null);
    }
  };

  async function upload(dryRun: boolean) {
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    const r = await api<ImportResult>(`/api/admin/import/specifications?dry_run=${dryRun}`, { method: "POST", body: fd });
    setResult(r);
    if (!dryRun && r.imported) setMsg({ tone: "success", text: `${r.imported} specification row(s) imported.` });
  }

  return (
    <div>
      <AdminHeader eyebrow="Data management" title="Import, export and backup" />
      {msg && <div className="mb-5"><Alert tone={msg.tone}>{msg.text}</Alert></div>}
      <div className="grid gap-6 lg:grid-cols-2">
        <section className="panel p-6">
          <div className="flex items-center gap-2 text-[15px] font-medium text-midnight"><Download className="h-4 w-4 text-teal" /> Export</div>
          <p className="mt-1 text-[13px] text-graphite-500">Download records as CSV, or everything as a single Excel workbook.</p>
          <ul className="mt-4 divide-y divide-line border-y border-line">
            {DATASETS.map(([k, label]) => (
              <li key={k} className="flex items-center justify-between py-2.5 text-[13.5px]">
                <span>{label}</span>
                <Button size="sm" variant="secondary" loading={busy === k} onClick={() => run(k, () => download(`/api/admin/export/${k}.csv`, `${k}.csv`))}>CSV</Button>
              </li>
            ))}
          </ul>
          <Button className="mt-4" loading={busy === "xlsx"} onClick={() => run("xlsx", () => download("/api/admin/export/workbook.xlsx", "export.xlsx"))}>
            <FileSpreadsheet className="h-4 w-4" /> Excel workbook (all datasets)
          </Button>
        </section>

        <section className="panel p-6">
          <div className="flex items-center gap-2 text-[15px] font-medium text-midnight"><Upload className="h-4 w-4 text-teal" /> Import specifications (CSV)</div>
          <p className="mt-1 text-[13px] text-graphite-500">
            Each row adds one specification to an existing membrane. Values must be in canonical units; every row is validated and nothing is
            imported if any row fails.
          </p>
          <button className="mt-2 text-[12.5px] text-teal hover:underline" onClick={() => run("tpl", () => download("/api/admin/import/specifications/template.csv", "template.csv"))}>Download template</button>
          <input type="file" accept=".csv,text/csv" className="mt-4 block w-full text-[13px] file:mr-3 file:rounded-[3px] file:border file:border-line file:bg-ivory-200 file:px-3 file:py-1.5 file:text-[13px]"
            onChange={(e) => { setFile(e.target.files?.[0] ?? null); setResult(null); }} />
          <div className="mt-4 flex gap-2">
            <Button variant="secondary" disabled={!file} loading={busy === "dry"} onClick={() => run("dry", () => upload(true))}>Validate</Button>
            <Button disabled={!file || !result || result.errors.length > 0 || !result.dry_run} loading={busy === "imp"} onClick={() => run("imp", () => upload(false))}>Import</Button>
          </div>
          {result && (
            <div className="mt-4">
              {result.errors.length === 0 ? (
                <Alert tone="success" title={result.dry_run ? "Validation passed" : "Import complete"}>{result.valid_rows} valid row(s){result.dry_run ? " ready to import." : "."}</Alert>
              ) : (
                <Alert tone="critical" title={`${result.errors.length} row(s) failed validation`}>
                  <ul className="mt-1 max-h-40 overflow-y-auto text-[12px]">{result.errors.map((e) => <li key={e.row}>Row {e.row}: {e.error}</li>)}</ul>
                </Alert>
              )}
            </div>
          )}
        </section>

        <section className="panel p-6 lg:col-span-2">
          <div className="flex items-center gap-2 text-[15px] font-medium text-midnight"><DatabaseBackup className="h-4 w-4 text-teal" /> Database backup</div>
          <p className="mt-1 max-w-3xl text-[13px] text-graphite-500">
            Creates a consistent snapshot of the SQLite database in <code className="num">backend/backups/</code> and downloads a copy. To restore,
            stop the server and replace <code className="num">backend/data/ro_membrane.db</code> with a backup file (see README).
          </p>
          <Button className="mt-4" loading={busy === "bk"} onClick={() => run("bk", async () => { await download("/api/admin/backup", "backup.db", { method: "POST" }); setMsg({ tone: "success", text: "Backup created and downloaded." }); })}>
            <DatabaseBackup className="h-4 w-4" /> Create backup
          </Button>
        </section>
      </div>
    </div>
  );
}
