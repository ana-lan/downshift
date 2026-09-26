import { describe, expect, it } from "vitest";
import type { AuditData, CallSite, ModelStats, SiteEvals } from "@/lib/types";
import {
  auditRows,
  baselineStats,
  chosenStats,
  findBySlug,
  modelStats,
  sortBySavings,
  sumCases,
} from "@/lib/select";

function stats(model: string, o: Partial<ModelStats> = {}): ModelStats {
  return {
    model,
    tier: null,
    is_baseline: false,
    chosen: false,
    cases: 10,
    scored: 10,
    passed: 5,
    errors: 0,
    pass_rate: 0.5,
    mean_score: 0.5,
    avg_judge_score: null,
    avg_prompt_tokens: 100,
    avg_completion_tokens: 10,
    avg_latency_s: 1,
    cost_per_call: 0.001,
    check: null,
    ...o,
  };
}

function site(slug: string, savings: number | null, models: ModelStats[] = []): CallSite {
  return {
    id: `app/${slug}.py::${slug}`,
    slug,
    file: `app/${slug}.py`,
    line: 1,
    function: slug,
    api: "chat.completions.create",
    is_async: false,
    found_by: "ast",
    via: null,
    purpose: null,
    output_contract: null,
    difficulty: null,
    grading: null,
    output_format: null,
    temperature: null,
    max_tokens: null,
    model_in_code: null,
    messages: null,
    eval_cases: 0,
    decision: null,
    models,
    cost:
      savings === null
        ? null
        : {
            before_model: "big",
            after_model: "small",
            calls_per_day: 100,
            before_monthly: 10,
            after_monthly: 10 - savings,
            savings,
            savings_pct: savings / 10,
          },
  };
}

function siteEvals(slug: string, cases: number): SiteEvals {
  return { site_id: slug, slug, grading: "exact", cases, models: [], examples: [], grid: [] };
}

describe("findBySlug and sumCases", () => {
  const evals = [siteEvals("a", 20), siteEvals("b", 25)];
  it("finds by slug", () => {
    expect(findBySlug(evals, "b")?.cases).toBe(25);
    expect(findBySlug(evals, "missing")).toBeUndefined();
  });
  it("sums cases", () => {
    expect(sumCases(evals)).toBe(45);
    expect(sumCases([])).toBe(0);
  });
});

describe("model lookups", () => {
  const s = site("x", 1, [
    stats("big", { is_baseline: true }),
    stats("small", { chosen: true }),
    stats("tiny"),
  ]);
  it("finds a model, the baseline and the chosen model", () => {
    expect(modelStats(s, "tiny")?.model).toBe("tiny");
    expect(modelStats(s, "nope")).toBeUndefined();
    expect(baselineStats(s)?.model).toBe("big");
    expect(chosenStats(s)?.model).toBe("small");
  });
  it("returns undefined when there are no models", () => {
    expect(baselineStats(site("y", 0))).toBeUndefined();
    expect(chosenStats(site("y", 0))).toBeUndefined();
  });
});

describe("sortBySavings", () => {
  it("sorts descending with nulls last and does not mutate", () => {
    const input = [site("a", 1), site("b", null), site("c", 5), site("d", 0)];
    const sorted = sortBySavings(input);
    expect(sorted.map((s) => s.slug)).toEqual(["c", "a", "d", "b"]);
    expect(input.map((s) => s.slug)).toEqual(["a", "b", "c", "d"]);
  });
});

describe("auditRows", () => {
  const audit: AuditData = {
    labels: { call_sites: "Call sites", models_resolved: "Models resolved" },
    ast: { call_sites: 7, models_resolved: 6 },
    audit: { call_sites: 8, models_resolved: 8 },
    ast_after: { call_sites: 7 },
    changes: [],
    ast_sites: [],
    audit_sites: [],
  };
  it("builds rows in label order", () => {
    expect(auditRows(audit)).toEqual([
      { key: "call_sites", label: "Call sites", ast: 7, audit: 8, astAfter: 7 },
      { key: "models_resolved", label: "Models resolved", ast: 6, audit: 8, astAfter: null },
    ]);
  });
  it("uses null when the ast scans are missing", () => {
    const rows = auditRows({ ...audit, ast: null, ast_after: null });
    expect(rows[0]).toEqual({
      key: "call_sites",
      label: "Call sites",
      ast: null,
      audit: 8,
      astAfter: null,
    });
  });
});
