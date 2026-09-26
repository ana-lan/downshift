import type { CallSite, SiteEvals, ModelStats, AuditData } from "@/lib/types";

export function findBySlug<T extends { slug: string }>(
  items: T[],
  slug: string
): T | undefined {
  return items.find((item) => item.slug === slug);
}

export function sumCases(evals: SiteEvals[]): number {
  return evals.reduce((acc, e) => acc + e.cases, 0);
}

export function modelStats(site: CallSite, model: string): ModelStats | undefined {
  return site.models.find((m) => m.model === model);
}

export function chosenStats(site: CallSite): ModelStats | undefined {
  return site.models.find((m) => m.chosen);
}

export function baselineStats(site: CallSite): ModelStats | undefined {
  return site.models.find((m) => m.is_baseline);
}

export function sortBySavings(sites: CallSite[]): CallSite[] {
  return [...sites].sort((a, b) => {
    const sa = a.cost?.savings ?? null;
    const sb = b.cost?.savings ?? null;
    if (sa === null && sb === null) return 0;
    if (sa === null) return 1;
    if (sb === null) return -1;
    return sb - sa;
  });
}

export interface AuditRow {
  key: string;
  label: string;
  ast: number | null;
  audit: number | null;
  astAfter: number | null;
}

export function auditRows(audit: AuditData): AuditRow[] {
  return Object.entries(audit.labels).map(([key, label]) => ({
    key,
    label,
    ast: audit.ast ? (audit.ast[key] ?? null) : null,
    audit: audit.audit[key] ?? null,
    astAfter: audit.ast_after ? (audit.ast_after[key] ?? null) : null,
  }));
}
