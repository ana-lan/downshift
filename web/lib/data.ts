import type { Summary, CallSite, AuditData, SiteEvals } from "@/lib/types";
import { findBySlug, sumCases } from "@/lib/select";

import summaryJson from "@/public/data/summary.json";
import callsitesJson from "@/public/data/callsites.json";
import auditJson from "@/public/data/audit.json";
import evalsJson from "@/public/data/evals_summary.json";

export const summary = summaryJson as unknown as Summary;
export const callsites = callsitesJson as unknown as CallSite[];
export const audit = auditJson as unknown as AuditData;
export const evals = evalsJson as unknown as SiteEvals[];

export function getCallsite(slug: string): CallSite | undefined {
  return findBySlug(callsites, slug);
}

export function getSiteEvals(slug: string): SiteEvals | undefined {
  return findBySlug(evals, slug);
}

export function allSlugs(): string[] {
  return callsites.map((s) => s.slug);
}

export function totalEvalCases(): number {
  return sumCases(evals);
}
