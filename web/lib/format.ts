export function formatUsd(n: number | null): string {
  if (n === null) return "n/a";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n);
}

export function formatUsdPerCall(n: number | null): string {
  if (n === null) return "n/a";
  return "$" + n.toFixed(6);
}

export function formatPct(rate: number | null, digits = 1): string {
  if (rate === null) return "n/a";
  return (rate * 100).toFixed(digits) + "%";
}

export function formatPts(delta: number | null): string {
  if (delta === null) return "n/a";
  const pts = (delta * 100).toFixed(1);
  return (delta >= 0 ? "+" : "") + pts + " pts";
}

export function formatNumber(n: number | null, digits = 0): string {
  if (n === null) return "n/a";
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(n);
}

export function formatSeconds(s: number | null): string {
  if (s === null) return "n/a";
  return s.toFixed(2) + " s";
}

export function siteName(id: string): string {
  const idx = id.indexOf("::");
  if (idx === -1) return id;
  return id.slice(idx + 2);
}

export function siteFile(id: string): string {
  const idx = id.indexOf("::");
  if (idx === -1) return id;
  return id.slice(0, idx);
}

export function formatValue(v: unknown): string {
  if (v === null || v === undefined) return "n/a";
  if (typeof v === "string") return v;
  return JSON.stringify(v, null, 2);
}
