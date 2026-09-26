import { describe, expect, it } from "vitest";
import {
  allSlugs,
  audit,
  callsites,
  evals,
  getCallsite,
  getSiteEvals,
  summary,
  totalEvalCases,
} from "@/lib/data";

describe("exported data contract", () => {
  it("has one call site per summary site", () => {
    expect(callsites.length).toBe(summary.sites_total);
    const downgraded = callsites.filter((s) => s.decision?.action === "downgrade").length;
    expect(downgraded).toBe(summary.sites_downgraded);
    expect(summary.downgrades.length).toBe(summary.sites_downgraded);
  });

  it("has unique slugs that resolve to call sites and evals", () => {
    const slugs = allSlugs();
    expect(new Set(slugs).size).toBe(slugs.length);
    for (const slug of slugs) {
      expect(getCallsite(slug)?.slug).toBe(slug);
      expect(getSiteEvals(slug)?.slug).toBe(slug);
    }
  });

  it("lists the baseline first and marks exactly one chosen model", () => {
    const models = [summary.baseline, ...summary.candidates];
    for (const site of callsites) {
      expect(site.models.map((m) => m.model)).toEqual(models);
      expect(site.models[0].is_baseline).toBe(true);
      expect(site.models.filter((m) => m.chosen).length).toBe(1);
    }
  });

  it("keeps eval grids consistent with case counts", () => {
    expect(totalEvalCases()).toBe(evals.reduce((n, e) => n + e.cases, 0));
    for (const e of evals) {
      expect(e.grid.length).toBe(e.cases);
      expect(e.examples.length).toBeLessThanOrEqual(e.cases);
    }
  });

  it("has audit metrics for the bob audit", () => {
    expect(Object.keys(audit.labels).length).toBeGreaterThan(0);
    expect(audit.audit_sites.length).toBe(callsites.length);
  });
});
