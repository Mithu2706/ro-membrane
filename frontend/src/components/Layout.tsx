import { ArrowUpRight } from "lucide-react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useEffect } from "react";
import { cx } from "./ui";

export function Logo({ light = false }: { light?: boolean }) {
  return (
    <Link to="/" className="group inline-flex items-center gap-2.5" aria-label="Osmora home">
      <svg viewBox="0 0 32 32" className="h-7 w-7" aria-hidden>
        <rect width="32" height="32" rx="4" fill={light ? "#F5F2EA" : "#102A2A"} />
        <circle cx="16" cy="15" r="7" fill="none" stroke="#C29B58" strokeWidth="2.4" />
        <path d="M10.5 25.5h11" stroke="#2D7771" strokeWidth="2.4" />
      </svg>
      <span className={cx("font-display text-[21px] leading-none tracking-tight", light ? "text-ivory" : "text-midnight")}>
        Osmora
      </span>
    </Link>
  );
}

export function PublicLayout() {
  const { pathname } = useLocation();
  const dark = pathname === "/";
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return (
    <div className="flex min-h-screen flex-col">
      <header
        className={cx(
          "sticky top-0 z-40 border-b backdrop-blur",
          dark ? "border-ivory/10 bg-midnight/90" : "border-line bg-ivory/85",
        )}
      >
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 lg:px-8">
          <Logo light={dark} />
          <nav className="flex items-center gap-1 sm:gap-6 text-[13.5px]">
            <NavLink
              to="/assess"
              className={({ isActive }) =>
                cx(
                  "hidden sm:inline transition-colors",
                  dark ? "text-ivory/70 hover:text-ivory" : isActive ? "text-midnight" : "text-graphite-500 hover:text-midnight",
                )
              }
            >
              Assessment
            </NavLink>
            <a
              href="#method"
              onClick={(e) => {
                if (pathname !== "/") {
                  e.preventDefault();
                  window.location.href = "/#method";
                }
              }}
              className={cx("hidden sm:inline transition-colors", dark ? "text-ivory/70 hover:text-ivory" : "text-graphite-500 hover:text-midnight")}
            >
              Method
            </a>
            <Link
              to="/assess"
              className={cx(
                "inline-flex h-9 items-center gap-1.5 rounded-[3px] px-3.5 font-medium transition-colors",
                dark ? "bg-brass text-midnight hover:bg-brass-400" : "bg-midnight text-ivory hover:bg-midnight-700",
              )}
            >
              Start assessment <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
          </nav>
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
      <footer className="border-t border-line bg-ivory-200/60">
        <div className="mx-auto grid max-w-7xl gap-6 px-5 py-10 text-[12.5px] text-graphite-500 lg:grid-cols-[1fr_2fr] lg:px-8">
          <div>
            <Logo />
            <p className="mt-3 max-w-xs">Evidence-based reverse osmosis membrane screening and preliminary system design.</p>
          </div>
          <div className="space-y-2 leading-relaxed lg:text-right">
            <p>
              Results are preliminary design support derived from manufacturer ratings and published research under stated
              assumptions. They are not certified manufacturer projections and do not replace detailed engineering, pilot
              testing or supplier design review.
            </p>
            <p className="text-graphite-400">Runs locally · No client data leaves this installation · No AI service involved in engineering decisions</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
