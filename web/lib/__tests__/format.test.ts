import { describe, expect, it } from "vitest";
import {
  formatNumber,
  formatPct,
  formatPts,
  formatSeconds,
  formatUsd,
  formatUsdPerCall,
  formatValue,
  shortModel,
  siteFile,
  siteName,
} from "@/lib/format";

describe("formatUsd", () => {
  it("formats dollars with separators and 2 decimals", () => {
    expect(formatUsd(3137.26)).toBe("$3,137.26");
    expect(formatUsd(0)).toBe("$0.00");
    expect(formatUsd(564.649)).toBe("$564.65");
  });
  it("returns n/a for null", () => {
    expect(formatUsd(null)).toBe("n/a");
  });
});

describe("formatUsdPerCall", () => {
  it("uses 6 decimals", () => {
    expect(formatUsdPerCall(0.000412)).toBe("$0.000412");
    expect(formatUsdPerCall(null)).toBe("n/a");
  });
});

describe("formatPct", () => {
  it("formats a rate as a percent", () => {
    expect(formatPct(0.18)).toBe("18.0%");
    expect(formatPct(0.95, 0)).toBe("95%");
    expect(formatPct(1)).toBe("100.0%");
    expect(formatPct(null)).toBe("n/a");
  });
});

describe("formatPts", () => {
  it("signs the delta in percentage points", () => {
    expect(formatPts(0.006)).toBe("+0.6 pts");
    expect(formatPts(-0.02)).toBe("-2.0 pts");
    expect(formatPts(0)).toBe("+0.0 pts");
    expect(formatPts(null)).toBe("n/a");
  });
});

describe("formatNumber and formatSeconds", () => {
  it("formats numbers", () => {
    expect(formatNumber(20000)).toBe("20,000");
    expect(formatNumber(181.456, 1)).toBe("181.5");
    expect(formatNumber(null)).toBe("n/a");
  });
  it("formats seconds", () => {
    expect(formatSeconds(1.234)).toBe("1.23 s");
    expect(formatSeconds(null)).toBe("n/a");
  });
});

describe("site ids", () => {
  it("splits file and function", () => {
    const id = "supportdesk/triage.py::detect_sentiment";
    expect(siteName(id)).toBe("detect_sentiment");
    expect(siteFile(id)).toBe("supportdesk/triage.py");
  });
  it("returns the id unchanged without ::", () => {
    expect(siteName("plain")).toBe("plain");
    expect(siteFile("plain")).toBe("plain");
  });
});

describe("formatValue and shortModel", () => {
  it("formats any value", () => {
    expect(formatValue("text")).toBe("text");
    expect(formatValue({ a: 1 })).toBe('{\n  "a": 1\n}');
    expect(formatValue(null)).toBe("n/a");
    expect(formatValue(undefined)).toBe("n/a");
  });
  it("shortens model names", () => {
    expect(shortModel("qwen2.5:7b")).toBe("7b");
    expect(shortModel("gpt-4o-mini")).toBe("gpt-4o-mini");
  });
});
