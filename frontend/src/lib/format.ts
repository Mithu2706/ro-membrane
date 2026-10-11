export const fmt = (v: number | null | undefined, digits = 0) =>
  v === null || v === undefined || Number.isNaN(v)
    ? "—"
    : v.toLocaleString("en-GB", { minimumFractionDigits: digits, maximumFractionDigits: digits });

export const range = (lo: number | null | undefined, hi: number | null | undefined, digits = 0) => {
  if (lo === null || lo === undefined) return null;
  if (hi === null || hi === undefined || Math.abs(hi - lo) < Math.pow(10, -digits)) return fmt(lo, digits);
  return `${fmt(lo, digits)}–${fmt(hi, digits)}`;
};

export const date = (iso: string) =>
  new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });

export const APPLICATION_LABELS: Record<string, string> = {
  bwro: "Brackish-water RO",
  swro: "Seawater RO",
  industrial: "Industrial wastewater / reuse",
  second_pass: "Second-pass RO",
  other: "Other / specialised",
};

export const STATUS_LABELS: Record<string, string> = {
  suitable: "Suitable for preliminary evaluation",
  conditional: "Conditional",
  insufficient_evidence: "Insufficient evidence",
  unsuitable: "Unsuitable",
};

export const VERIFICATION_LABELS: Record<string, string> = {
  verified: "Verified",
  "report-extracted": "From review report",
  unverified: "Unverified",
  disputed: "Disputed",
};

export const EVIDENCE_LABELS: Record<string, string> = {
  "manufacturer-rated": "Manufacturer rating",
  "laboratory-experimental": "Laboratory test",
  "pilot-plant": "Pilot / plant data",
  calculated: "Calculated",
  estimated: "Estimated",
};
