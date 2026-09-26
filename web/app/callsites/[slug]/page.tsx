import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { Panel, Section } from "@/components/Panel";
import { MiniStat } from "@/components/StatCard";
import { CodeBlock } from "@/components/CodeBlock";
import { Disclaimer } from "@/components/Disclaimer";
import { Badge, DecisionBadge, FoundByBadge } from "@/components/Badge";
import { getCallsite, getSiteEvals, allSlugs } from "@/lib/data";
import { ModelsTable, EvalExamples, EvalGrid } from "./CallSiteDetail";
import {
  formatUsd,
  formatPct,
  formatNumber,
  siteName,
  formatValue,
} from "@/lib/format";

export const dynamicParams = false;

export function generateStaticParams() {
  return allSlugs().map((slug) => ({ slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const site = getCallsite(slug);
  if (!site) return {};
  return { title: `${siteName(site.id)} \u00b7 Downshift` };
}

export default async function CallSiteDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const site = getCallsite(slug);
  if (!site) notFound();

  const siteEvals = getSiteEvals(slug);
  const showJudge = site.grading === "judge";

  return (
    <>
      {/* Header */}
      <Panel>
        <Link href="/callsites/" className="text-xs text-subtle hover:text-heading transition-colors mb-4 inline-block">
          &#8592; All call sites
        </Link>
        <p className="text-xs font-mono text-accent-2 tracking-wider mb-2 uppercase">
          CALL SITE &middot; {site.file}:{site.line}
        </p>
        <h1 className="text-2xl font-bold font-mono text-heading mb-3">
          {siteName(site.id)}
        </h1>
        <div className="flex flex-wrap gap-2 mb-4">
          <FoundByBadge foundBy={site.found_by} />
          {site.via && <Badge tone="accent">via {site.via}</Badge>}
          {site.difficulty && <Badge>{site.difficulty}</Badge>}
          {site.grading && <Badge>{site.grading}</Badge>}
          {site.output_format && <Badge>{site.output_format}</Badge>}
          {site.is_async && <Badge>async</Badge>}
          {site.max_tokens != null && <Badge>max_tokens {site.max_tokens}</Badge>}
          {site.temperature != null && <Badge>temperature {site.temperature}</Badge>}
        </div>
        {site.purpose && <p className="text-muted text-sm mb-4">{site.purpose}</p>}
        {site.output_contract != null && (
          <div className="mt-3">
            <p className="text-xs font-mono text-subtle mb-1">Output contract</p>
            {typeof site.output_contract === "string" ? (
              <p className="text-sm text-muted">{site.output_contract}</p>
            ) : (
              <CodeBlock code={formatValue(site.output_contract)} />
            )}
          </div>
        )}
      </Panel>

      {/* Decision */}
      <Section eyebrow="DECISION" title="">
        {site.decision ? (
          <>
            <div className="flex items-center gap-3 mb-3">
              <DecisionBadge action={site.decision.action} />
              <span className="text-heading font-mono text-sm">
                {site.decision.action === "downgrade"
                  ? `${site.decision.baseline} \u2192 ${site.decision.model}`
                  : `stays on ${site.decision.baseline}`}
              </span>
            </div>
            <p className="text-muted text-sm mb-5">{site.decision.reason}</p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
              <MiniStat value={formatUsd(site.cost?.before_monthly ?? null)} label="Before/mo" />
              <MiniStat value={formatUsd(site.cost?.after_monthly ?? null)} label="After/mo" tone="good" />
              <MiniStat
                value={`${formatUsd(site.cost?.savings ?? null)} (${formatPct(site.cost?.savings_pct ?? null)})`}
                label="Savings/mo"
                tone="good"
              />
              <MiniStat value={formatNumber(site.cost?.calls_per_day ?? null)} label="Calls/day" />
            </div>
            <Disclaimer />
          </>
        ) : (
          <p className="text-muted text-sm">No decision available.</p>
        )}
      </Section>

      {/* Models */}
      <ModelsTable site={site} showJudge={showJudge} />

      {/* Prompt */}
      <Section eyebrow="PROMPT" title="">
        <p className="text-xs text-subtle mb-3">
          Model in code: <span className="font-mono text-muted">{site.model_in_code ?? "unresolved"}</span>
        </p>
        {site.messages ? (
          <div className="space-y-4">
            {site.messages.map((msg, i) => (
              <div key={i}>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-mono text-subtle uppercase">{msg.role}</span>
                  {!msg.resolved && <Badge tone="warn">not resolved statically</Badge>}
                </div>
                <div className="rounded-xl border border-line bg-card p-4 overflow-x-auto text-xs font-mono text-muted whitespace-pre-wrap">
                  {msg.content}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-muted text-sm">Prompt not resolved statically.</p>
        )}
      </Section>

      {/* Eval examples */}
      {siteEvals ? (
        <EvalExamples siteEvals={siteEvals} />
      ) : (
        <Section eyebrow="EVAL EXAMPLES" title="">
          <p className="text-muted text-sm">No evals for this call site.</p>
        </Section>
      )}

      {/* All cases grid */}
      {siteEvals ? (
        <EvalGrid siteEvals={siteEvals} />
      ) : (
        <Section eyebrow="ALL CASES" title="">
          <p className="text-muted text-sm">No evals for this call site.</p>
        </Section>
      )}
    </>
  );
}
