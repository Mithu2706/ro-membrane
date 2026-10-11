import { AlertTriangle, CheckCircle2, CircleHelp, Info, Loader2, OctagonX, XCircle } from "lucide-react";
import { ButtonHTMLAttributes, ReactNode, useId, useState } from "react";
import type { CheckStatus, Status } from "../lib/types";

export function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

type BtnVariant = "primary" | "secondary" | "ghost" | "dark" | "danger";
export function Button({
  variant = "primary",
  size = "md",
  loading,
  className,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: BtnVariant; size?: "sm" | "md" | "lg"; loading?: boolean }) {
  const v: Record<BtnVariant, string> = {
    primary: "bg-teal text-ivory hover:bg-teal-600 border border-teal-600/40",
    secondary: "bg-transparent text-midnight border border-midnight/25 hover:border-midnight/60 hover:bg-midnight/[0.03]",
    ghost: "bg-transparent text-graphite-500 hover:text-midnight border border-transparent",
    dark: "bg-brass text-midnight hover:bg-brass-400 border border-brass-600/40",
    danger: "bg-transparent text-alert border border-alert/40 hover:bg-alert-50",
  };
  const s = { sm: "h-8 px-3 text-[13px]", md: "h-10 px-4 text-sm", lg: "h-12 px-6 text-[15px]" }[size];
  return (
    <button
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-[3px] font-medium tracking-[0.01em] transition-all duration-150",
        "disabled:opacity-50 disabled:cursor-not-allowed active:translate-y-px",
        v[variant],
        s,
        className,
      )}
      disabled={loading || rest.disabled}
      {...rest}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
}

export function Tooltip({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <span className="relative inline-flex">
      <button
        type="button"
        aria-describedby={id}
        className="text-graphite-300 hover:text-teal transition-colors"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        aria-label="More information"
      >
        <CircleHelp className="h-3.5 w-3.5" />
      </button>
      {open && (
        <span
          role="tooltip"
          id={id}
          className="absolute left-1/2 bottom-full z-30 mb-2 w-64 -translate-x-1/2 rounded-[3px] bg-midnight px-3 py-2 text-[12.5px] leading-snug text-ivory shadow-lift animate-rise"
        >
          {text}
        </span>
      )}
    </span>
  );
}

export function Field({
  label,
  unit,
  hint,
  tooltip,
  error,
  optional,
  children,
}: {
  label: string;
  unit?: string;
  hint?: string;
  tooltip?: string;
  error?: string;
  optional?: boolean;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 flex items-center gap-1.5 text-[13px] font-medium text-midnight">
        {label}
        {tooltip && <Tooltip text={tooltip} />}
        {optional && <span className="ml-auto text-[11px] font-normal uppercase tracking-wider text-graphite-300">Optional</span>}
      </span>
      <span className="relative block">
        {children}
        {unit && (
          <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[12px] text-graphite-400 num">{unit}</span>
        )}
      </span>
      {error ? (
        <span className="mt-1 block text-[12px] text-alert">{error}</span>
      ) : hint ? (
        <span className="mt-1 block text-[12px] text-graphite-400">{hint}</span>
      ) : null}
    </label>
  );
}

export function NumberInput({
  value,
  onChange,
  invalid,
  placeholder,
  step = "any",
  unitPad,
}: {
  value: number | null | undefined;
  onChange: (v: number | null) => void;
  invalid?: boolean;
  placeholder?: string;
  step?: string;
  unitPad?: boolean;
}) {
  return (
    <input
      type="number"
      inputMode="decimal"
      step={step}
      className={cx("field-input num", unitPad && "pr-20")}
      value={value === null || value === undefined ? "" : value}
      placeholder={placeholder ?? "Not measured"}
      aria-invalid={invalid || undefined}
      onChange={(e) => {
        const raw = e.target.value;
        onChange(raw === "" ? null : Number(raw));
      }}
    />
  );
}

const STATUS_STYLE: Record<Status, string> = {
  suitable: "bg-teal-50 text-teal-700 border-teal/30",
  conditional: "bg-brass-50 text-brass-700 border-brass/40",
  insufficient_evidence: "bg-ivory-200 text-graphite-500 border-graphite-300/60",
  unsuitable: "bg-alert-50 text-alert-600 border-alert/30",
};
const STATUS_DOT: Record<Status, string> = {
  suitable: "bg-teal",
  conditional: "bg-brass",
  insufficient_evidence: "bg-graphite-300",
  unsuitable: "bg-alert",
};

export function StatusChip({ status, label, size = "md" }: { status: Status; label: string; size?: "sm" | "md" }) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full border font-medium whitespace-nowrap",
        size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-[12px]",
        STATUS_STYLE[status],
      )}
    >
      <span className={cx("h-1.5 w-1.5 rounded-full", STATUS_DOT[status])} />
      {label}
    </span>
  );
}

export function CheckIcon({ status, className = "h-4 w-4" }: { status: CheckStatus; className?: string }) {
  if (status === "pass") return <CheckCircle2 className={cx(className, "text-teal")} />;
  if (status === "warn") return <AlertTriangle className={cx(className, "text-brass-600")} />;
  if (status === "fail") return <XCircle className={cx(className, "text-alert")} />;
  return <CircleHelp className={cx(className, "text-graphite-300")} />;
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "teal" | "brass" | "alert" | "dark" }) {
  const t = {
    neutral: "bg-ivory-200 text-graphite-500 border-line",
    teal: "bg-teal-50 text-teal-700 border-teal/25",
    brass: "bg-brass-50 text-brass-700 border-brass/30",
    alert: "bg-alert-50 text-alert-600 border-alert/25",
    dark: "bg-midnight text-ivory border-midnight",
  }[tone];
  return <span className={cx("inline-flex items-center rounded-[2px] border px-1.5 py-0.5 text-[11px] font-medium", t)}>{children}</span>;
}

export function VerificationBadge({ status }: { status: string }) {
  if (status === "verified") return <Badge tone="teal">Verified datasheet</Badge>;
  if (status === "report-extracted") return <Badge tone="brass">From literature</Badge>;
  if (status === "disputed") return <Badge tone="alert">Disputed</Badge>;
  return <Badge>Unverified</Badge>;
}

export function Alert({
  tone = "info",
  title,
  children,
}: {
  tone?: "info" | "caution" | "critical" | "success";
  title?: string;
  children?: ReactNode;
}) {
  const conf = {
    info: { c: "border-teal/30 bg-teal-50/60 text-midnight", i: <Info className="h-4 w-4 text-teal" /> },
    caution: { c: "border-brass/40 bg-brass-50/70 text-midnight", i: <AlertTriangle className="h-4 w-4 text-brass-600" /> },
    critical: { c: "border-alert/35 bg-alert-50/70 text-midnight", i: <OctagonX className="h-4 w-4 text-alert" /> },
    success: { c: "border-teal/30 bg-teal-50/60 text-midnight", i: <CheckCircle2 className="h-4 w-4 text-teal" /> },
  }[tone];
  return (
    <div role={tone === "critical" ? "alert" : "status"} className={cx("flex gap-3 rounded-[3px] border px-4 py-3", conf.c)}>
      <span className="mt-0.5 shrink-0">{conf.i}</span>
      <div className="text-[13.5px] leading-relaxed">
        {title && <div className="font-semibold text-midnight">{title}</div>}
        {children}
      </div>
    </div>
  );
}

export function PageLoader({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 text-graphite-400">
      <div className="relative h-[2px] w-48 overflow-hidden bg-line">
        <span className="absolute inset-y-0 w-1/2 bg-teal animate-sweep" />
      </div>
      <span className="text-[12px] uppercase tracking-eyebrow">{label}</span>
    </div>
  );
}

export function EmptyState({ icon, title, children }: { icon?: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 border border-dashed border-line px-6 py-12 text-center">
      {icon && <div className="text-graphite-300">{icon}</div>}
      <div className="font-display text-lg text-midnight">{title}</div>
      {children && <div className="max-w-md text-[13.5px] text-graphite-500">{children}</div>}
    </div>
  );
}

export function SectionHeading({ eyebrow, title, children }: { eyebrow?: string; title: string; children?: ReactNode }) {
  return (
    <div className="mb-5">
      {eyebrow && <div className="eyebrow mb-1.5">{eyebrow}</div>}
      <h2 className="text-[26px] leading-tight">{title}</h2>
      {children && <p className="mt-1.5 max-w-2xl text-[14px] text-graphite-500">{children}</p>}
    </div>
  );
}

export function Stat({ label, value, unit, sub }: { label: string; value: ReactNode; unit?: string; sub?: ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-graphite-400">{label}</div>
      <div className="mt-1 flex items-baseline gap-1.5">
        <span className="num text-[26px] font-medium leading-none text-midnight">{value}</span>
        {unit && <span className="text-[12px] text-graphite-400">{unit}</span>}
      </div>
      {sub && <div className="mt-1 text-[12px] text-graphite-400">{sub}</div>}
    </div>
  );
}
