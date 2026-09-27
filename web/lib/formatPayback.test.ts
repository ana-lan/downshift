import { describe, expect, it } from "vitest";
import { formatPayback } from "./format";

describe("formatPayback", () => {
  it("handles null", () => expect(formatPayback(null)).toBe("n/a"));
  it("rounds minutes up", () => expect(formatPayback(0.84)).toBe("51 minutes"));
  it("has a one minute floor", () => expect(formatPayback(0.001)).toBe("1 minutes"));
  it("shows hours under 48", () => expect(formatPayback(1.04)).toBe("1.0 hours"));
  it("shows days from 48 hours", () => expect(formatPayback(50)).toBe("3 days"));
});
