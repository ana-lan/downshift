import { describe, expect, it } from "vitest";
import { BOB_TASKS, CASE_STUDY } from "@/lib/content";

describe("CASE_STUDY", () => {
  it("per-feature monthly costs add up to the total", () => {
    const sum = CASE_STUDY.features.reduce((acc, f) => acc + f.monthly, 0);
    expect(sum).toBeCloseTo(CASE_STUDY.bobMonthly, 2);
  });

  it("metrics show Bob resolving what ast could not", () => {
    for (const m of CASE_STUDY.metrics) {
      expect(m.bob).toBeGreaterThan(m.ast);
    }
  });

  it("features match the audited call site count", () => {
    const sites = CASE_STUDY.metrics.find((m) => m.label === "Call sites");
    expect(CASE_STUDY.features.length).toBe(sites?.bob);
  });
});

describe("BOB_TASKS", () => {
  it("lists every Bob task including the case study audit", () => {
    expect(BOB_TASKS.map((t) => t.task)).toContain("Audit a real repo");
    expect(BOB_TASKS.length).toBe(10);
  });
});
