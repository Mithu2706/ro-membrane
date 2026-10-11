export type Application = "bwro" | "swro" | "industrial" | "second_pass" | "other";
export type Priority = "quality" | "productivity" | "low_pressure" | "balanced";
export type Oxidant = "none" | "dechlorinated" | "free_chlorine_present" | "chloramine" | "unknown";
export type Status = "suitable" | "conditional" | "insufficient_evidence" | "unsuitable";
export type CheckStatus = "pass" | "warn" | "fail" | "unknown";

export interface Chemistry {
  ph?: number | null;
  alkalinity_mg_l_caco3?: number | null;
  hardness_mg_l_caco3?: number | null;
  calcium_mg_l?: number | null;
  magnesium_mg_l?: number | null;
  sulfate_mg_l?: number | null;
  chloride_mg_l?: number | null;
  sodium_mg_l?: number | null;
  silica_mg_l?: number | null;
  boron_mg_l?: number | null;
  sdi?: number | null;
  turbidity_ntu?: number | null;
  toc_mg_l?: number | null;
  cod_mg_l?: number | null;
  oxidant_exposure: Oxidant;
  free_chlorine_mg_l?: number | null;
  pretreatment: string[];
  pretreatment_notes?: string | null;
}

export interface AssessmentInput {
  application: Application;
  feed_tds_mg_l: number | null;
  feed_temperature_c: number | null;
  available_pressure_bar: number | null;
  permeate_flow_m3d: number | null;
  recovery_pct: number | null;
  target_permeate_tds_mg_l?: number | null;
  target_boron_mg_l?: number | null;
  feed_flow_limit_m3d?: number | null;
  design_flux_lmh?: number | null;
  pressure_loss_allowance_bar?: number | null;
  priority: Priority;
  input_origin?: "client" | "demo";
  chemistry: Chemistry;
  client: { name?: string | null; organization?: string | null; email?: string | null; project_name?: string | null };
}

export interface Check {
  key: string;
  label: string;
  status: CheckStatus;
  message: string;
  detail?: string;
}

export interface RatedParam {
  value: number | null;
  value_min: number | null;
  value_max: number | null;
  value_text: string | null;
  unit: string;
  evidence_type: string;
  verification_status: string;
  source_id: number | null;
  test_conditions: string | null;
}

export interface Candidate {
  membrane_id: number;
  name: string;
  manufacturer: string;
  model: string;
  category: string;
  category_label: string;
  element_size: string | null;
  status: Status;
  status_label: string;
  summary: string;
  positives: string[];
  concerns: string[];
  checks: Check[];
  rated: Record<string, RatedParam | null>;
  rated_test_conditions: string | null;
  conflicts: string[];
  estimates: {
    required_pressure_bar: number | null;
    required_pressure_high_bar: number | null;
    permeate_tds_mg_l: number | null;
    permeate_tds_high_mg_l: number | null;
    permeate_confidence: "rough" | "low" | null;
    boron_permeate_mg_l: number | null;
    elements_required: number | null;
    rated_flux_lmh: number | null;
  };
  evidence: {
    level: string;
    verified_critical_params: number;
    critical_params_total: number;
    condition_match: string;
    observations: { evidence_type: string; feed_description: string | null; performance_text: string | null;
      permeate_concentration_text: string | null; test_method: string | null; source_id: number | null }[];
  };
  source_ids: number[];
  rank: number | null;
  technical?: Record<string, number | string | boolean | null>;
}

export interface Source {
  id: number;
  title: string;
  authors: string | null;
  year: number | null;
  doi: string | null;
  url: string | null;
  source_type: string;
  publisher: string | null;
  page_table: string | null;
  verification_status: string;
  notes: string | null;
}

export interface ChemItem {
  key: string;
  label: string;
  status: "ok" | "caution" | "risk" | "not_assessed" | "missing";
  message: string;
  detail?: string;
}

export interface AssessmentResult {
  engine_version: string;
  generated_at: string;
  outcome: "recommended" | "no_supported_recommendation";
  headline: string;
  summary: string;
  application: Application;
  application_label: string;
  priority_label: string;
  input_origin?: "client" | "demo";
  recommended: Candidate | null;
  alternatives: Candidate[];
  needs_more_data: Candidate[];
  excluded: Candidate[];
  candidates: Candidate[];
  system: {
    flow: { permeate_m3d: number; feed_m3d: number; concentrate_m3d: number; permeate_m3h: number; feed_m3h: number;
      concentrate_m3h: number; recovery_pct: number };
    concentrate_tds_ideal_mg_l: number;
    concentrate_tds_mass_balance_mg_l: number | null;
    concentration_factor: number;
    pressure_status: string | null;
    checks: Check[];
  };
  chemistry: { completeness: string; missing_core: string[]; items: ChemItem[]; concentration_factor: number };
  warnings: { severity: "critical" | "caution" | "info"; title: string; message: string }[];
  assumptions: string[];
  limitations: string[];
  unavailable: string[];
  sources: Source[];
  technical?: Record<string, unknown>;
}

export interface AssessmentRecord {
  reference: string;
  created_at: string;
  inputs: AssessmentInput;
  result: AssessmentResult;
}
