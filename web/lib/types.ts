export interface Downgrade { site_id: string; from: string; to: string }
export interface Pricing {
  model: string;
  input_per_mtok: number | null;
  output_per_mtok: number | null;
  tier: string | null;
}
export interface Summary {
  project: string;
  tool_version: string;
  baseline: string;
  candidates: string[];
  judge_models: string[];
  threshold: number;
  min_pass_rate: number;
  calls_per_day: number;
  days_per_month: number;
  sites_total: number;
  sites_downgraded: number;
  downgrades: Downgrade[];
  missing_evals: string[];
  cost: {
    before_monthly: number | null;
    after_monthly: number | null;
    savings: number | null;
    savings_pct: number | null;
  };
  quality: {
    baseline_pass_rate: number | null;
    after_pass_rate: number | null;
    delta: number | null;
  };
  pricing: Pricing[];
  disclaimer: string;
}
export interface PromptMessage { role: string; content: string; resolved: boolean }
export interface Decision {
  action: "keep" | "downgrade";
  model: string;
  baseline: string;
  reason: string;
  baseline_pass_rate: number | null;
  baseline_below_floor: boolean;
}
export interface ModelCheck { ratio: number | null; passed: boolean; reason: string }
export interface ModelStats {
  model: string;
  tier: string | null;
  is_baseline: boolean;
  chosen: boolean;
  cases: number | null;
  scored: number | null;
  passed: number | null;
  errors: number | null;
  pass_rate: number | null;
  mean_score: number | null;
  avg_judge_score: number | null;
  avg_prompt_tokens: number | null;
  avg_completion_tokens: number | null;
  avg_latency_s: number | null;
  cost_per_call: number | null;
  check: ModelCheck | null;
}
export interface SiteCost {
  before_model: string;
  after_model: string;
  calls_per_day: number;
  before_monthly: number | null;
  after_monthly: number | null;
  savings: number | null;
  savings_pct: number | null;
}
export interface CallSite {
  id: string;
  slug: string;
  file: string;
  line: number;
  function: string;
  api: string;
  is_async: boolean;
  found_by: string;
  via: string | null;
  purpose: string | null;
  output_contract: unknown;
  difficulty: string | null;
  grading: string | null;
  output_format: string | null;
  temperature: number | null;
  max_tokens: number | null;
  model_in_code: string | null;
  messages: PromptMessage[] | null;
  eval_cases: number;
  decision: Decision | null;
  models: ModelStats[];
  cost: SiteCost | null;
}
export interface MetricMap { [key: string]: number }
export interface Change { id: string; kind: string; detail: string }
export interface SiteBrief {
  id: string;
  found_by: string;
  via: string | null;
  model: string | null;
  model_source: string | null;
  prompt_resolved: boolean;
}
export interface AuditData {
  labels: { [key: string]: string };
  ast: MetricMap | null;
  audit: MetricMap;
  ast_after: MetricMap | null;
  changes: Change[];
  ast_sites: SiteBrief[];
  audit_sites: SiteBrief[];
}
export interface ModelOutput {
  output: string;
  passed: boolean | null;
  score: number | null;
  judge_score: number | null;
  detail: string;
  error: string | null;
}
export interface EvalExample {
  id: string;
  inputs: { [key: string]: unknown };
  expected: unknown;
  notes: string | null;
  outputs: { [model: string]: ModelOutput | null };
}
export interface EvalGridRow { id: string; passed: { [model: string]: boolean | null } }
export interface SiteEvals {
  site_id: string;
  slug: string;
  grading: string | null;
  cases: number;
  models: string[];
  examples: EvalExample[];
  grid: EvalGridRow[];
}
