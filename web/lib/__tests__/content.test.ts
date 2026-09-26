import { describe, expect, it } from "vitest";
import { BOB_TASKS, CASE_STUDIES } from "@/lib/content";

describe("CASE_STUDIES", () => {
  it("has both case studies with unique slugs", () => {
    const slugs = CASE_STUDIES.map((cs) => cs.slug);
    expect(slugs).toEqual(["orchestrai", "mem0"]);
    expect(new Set(slugs).size).toBe(slugs.length);
  });

  it.each(CASE_STUDIES.map((cs) => [cs.slug, cs] as const))(
    "%s: per-feature monthly costs add up to the total (within a cent)",
    (_slug, cs) => {
      const sum = cs.features.reduce((acc, f) => acc + f.monthly, 0);
      expect(Math.abs(sum - cs.bobMonthly)).toBeLessThanOrEqual(0.011);
    },
  );

  it.each(CASE_STUDIES.map((cs) => [cs.slug, cs] as const))(
    "%s: Bob resolves more than ast on every metric, and costs more than the static view",
    (_slug, cs) => {
      for (const m of cs.metrics) {
        expect(m.bob).toBeGreaterThan(m.ast);
      }
      expect(cs.bobMonthly).toBeGreaterThan(cs.staticMonthly);
    },
  );
});

describe("BOB_TASKS", () => {
  it("lists every Bob task including both case study audits", () => {
    const tasks = BOB_TASKS.map((t) => t.task);
    expect(tasks).toContain("Audit OrchestrAI");
    expect(tasks).toContain("Audit mem0");
    expect(BOB_TASKS.length).toBe(11);
  });
});
