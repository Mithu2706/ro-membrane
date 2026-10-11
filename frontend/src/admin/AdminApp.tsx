import { BookMarked, Database, FileClock, FlaskConical, LayoutDashboard, LogOut, Lock, ScrollText, Users } from "lucide-react";
import { createContext, FormEvent, useContext, useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { Logo } from "../components/Layout";
import { Alert, Button, Field, PageLoader, cx } from "../components/ui";
import { api, ApiError, setCsrf } from "../lib/api";
import Overview from "./Overview";
import Submissions, { SubmissionDetail } from "./Submissions";
import Membranes, { MembraneDetail } from "./Membranes";
import Sources from "./Sources";
import DataTools from "./DataTools";
import Methodology, { AuditLog } from "./Methodology";

interface Me {
  authenticated: boolean;
  username?: string;
  csrf_token?: string;
  configured?: boolean;
}

const AuthCtx = createContext<{ username: string; logout: () => void }>({ username: "", logout: () => {} });
export const useAuth = () => useContext(AuthCtx);

export default function AdminApp() {
  const [me, setMe] = useState<Me | null>(null);

  const refresh = () =>
    api<Me>("/api/admin/me")
      .then((m) => {
        setCsrf(m.csrf_token ?? null);
        setMe(m);
      })
      .catch(() => setMe({ authenticated: false }));

  useEffect(() => {
    document.title = "Osmora — Admin console";
    refresh();
  }, []);

  if (!me) return <PageLoader label="Checking session" />;
  if (!me.authenticated) return <Login configured={me.configured !== false} onDone={refresh} />;

  const logout = async () => {
    try {
      await api("/api/admin/logout", { method: "POST" });
    } finally {
      setCsrf(null);
      setMe({ authenticated: false, configured: true });
    }
  };

  const nav = [
    { to: "/admin", label: "Overview", icon: LayoutDashboard, end: true },
    { to: "/admin/submissions", label: "Submissions", icon: Users },
    { to: "/admin/membranes", label: "Membranes", icon: FlaskConical },
    { to: "/admin/sources", label: "Sources", icon: BookMarked },
    { to: "/admin/data", label: "Import / export", icon: Database },
    { to: "/admin/methodology", label: "Methodology", icon: ScrollText },
    { to: "/admin/audit", label: "Audit log", icon: FileClock },
  ];

  return (
    <AuthCtx.Provider value={{ username: me.username!, logout }}>
      <div className="flex min-h-screen bg-ivory">
        <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col bg-midnight text-ivory lg:flex">
          <div className="border-b border-ivory/10 px-5 py-5">
            <Logo light />
            <div className="mt-2 text-[10.5px] uppercase tracking-eyebrow text-brass">Research console</div>
          </div>
          <nav className="flex-1 space-y-0.5 px-3 py-4">
            {nav.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                className={({ isActive }) =>
                  cx("flex items-center gap-3 rounded-[3px] px-3 py-2 text-[13.5px] transition-colors", isActive ? "bg-ivory/10 text-ivory" : "text-ivory/60 hover:bg-ivory/5 hover:text-ivory")
                }
              >
                <n.icon className="h-4 w-4" strokeWidth={1.7} />
                {n.label}
              </NavLink>
            ))}
          </nav>
          <div className="border-t border-ivory/10 px-5 py-4 text-[12.5px]">
            <div className="text-ivory/50">Signed in as</div>
            <div className="text-ivory">{me.username}</div>
            <button onClick={logout} className="mt-3 inline-flex items-center gap-1.5 text-ivory/60 hover:text-ivory">
              <LogOut className="h-3.5 w-3.5" /> Sign out
            </button>
          </div>
        </aside>
        <div className="min-w-0 flex-1">
          {/* Mobile nav */}
          <div className="flex items-center gap-3 overflow-x-auto border-b border-line bg-midnight px-4 py-3 lg:hidden">
            {nav.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => cx("whitespace-nowrap text-[12.5px]", isActive ? "text-ivory" : "text-ivory/60")}>
                {n.label}
              </NavLink>
            ))}
            <button onClick={logout} className="ml-auto text-[12.5px] text-ivory/60">Sign out</button>
          </div>
          <main className="mx-auto max-w-[1280px] px-5 py-8 lg:px-10">
            <Routes>
              <Route index element={<Overview />} />
              <Route path="submissions" element={<Submissions />} />
              <Route path="submissions/:id" element={<SubmissionDetail />} />
              <Route path="membranes" element={<Membranes />} />
              <Route path="membranes/:id" element={<MembraneDetail />} />
              <Route path="sources" element={<Sources />} />
              <Route path="data" element={<DataTools />} />
              <Route path="methodology" element={<Methodology />} />
              <Route path="audit" element={<AuditLog />} />
              <Route path="*" element={<Navigate to="/admin" replace />} />
            </Routes>
          </main>
        </div>
      </div>
    </AuthCtx.Provider>
  );
}

function Login({ configured, onDone }: { configured: boolean; onDone: () => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ csrf_token: string }>("/api/admin/login", { method: "POST", json: { username, password } });
      setCsrf(r.csrf_token);
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sign-in failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="relative hidden overflow-hidden bg-midnight lg:block">
        <div className="grid-lines absolute inset-0" />
        <div className="relative flex h-full flex-col justify-between p-12 text-ivory">
          <Logo light />
          <div>
            <div className="eyebrow !text-brass">Restricted</div>
            <h1 className="mt-3 max-w-md font-display text-[40px] leading-tight text-ivory">Research &amp; submissions console</h1>
            <p className="mt-4 max-w-md text-[14.5px] text-ivory/60">
              Manage the membrane evidence base, review client submissions and export records. Access is limited to authorised administrators.
            </p>
          </div>
          <div className="text-[12px] text-ivory/40">Local installation · sessions expire automatically</div>
        </div>
      </div>
      <div className="flex items-center justify-center px-6 py-12">
        <form onSubmit={submit} className="w-full max-w-sm">
          <div className="mb-8 lg:hidden"><Logo /></div>
          <Lock className="h-5 w-5 text-teal" />
          <h2 className="mt-4 text-[28px]">Administrator sign-in</h2>
          <p className="mt-1 text-[13.5px] text-graphite-500">Credentials are configured on the server through environment variables.</p>
          {!configured && (
            <div className="mt-5">
              <Alert tone="caution" title="Admin console not configured">
                Set <code className="num">RO_ADMIN_PASSWORD</code> (or a bcrypt <code className="num">RO_ADMIN_PASSWORD_HASH</code>) in <code className="num">backend/.env</code> and restart the server.
              </Alert>
            </div>
          )}
          <div className="mt-6 space-y-4">
            <Field label="Username">
              <input className="field-input" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required />
            </Field>
            <Field label="Password">
              <input className="field-input" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </Field>
          </div>
          {error && <div className="mt-4"><Alert tone="critical">{error}</Alert></div>}
          <Button type="submit" className="mt-6 w-full" size="lg" loading={busy} disabled={!configured}>Sign in</Button>
        </form>
      </div>
    </div>
  );
}

export function AdminHeader({ eyebrow, title, children, actions }: { eyebrow?: string; title: string; children?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <div className="mb-7 flex flex-wrap items-end justify-between gap-4 border-b border-line pb-5">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1 className="mt-1 text-[30px] leading-tight">{title}</h1>
        {children && <p className="mt-1 max-w-3xl text-[13.5px] text-graphite-500">{children}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function useLoad<T>(path: string | null, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const reload = () => {
    if (!path) return;
    setLoading(true);
    api<T>(path)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  };
  useEffect(reload, [path, ...deps]); // eslint-disable-line react-hooks/exhaustive-deps
  return { data, error, loading, reload, setData };
}
