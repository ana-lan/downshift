import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { Section } from "@/components/Panel";
import { MiniStat } from "@/components/StatCard";
import { CodeBlock } from "@/components/CodeBlock";
import { Disclaimer } from "@/components/Disclaimer";
import { Badge, DecisionBadge, FoundByBadge } from "@/components/Badge";
import { getCallsite, getSiteEvals, allSlugs } from "@/lib/data";
import { ModelsTable, EvalExamples, EvalGrid } from "./CallSiteDetail";
import { formatUsd, formatPct, formatNumber, siteName, formatValue } from "@/lib/format";

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
  const d = site.decision;
  const c = site.cost;
  const meta = [
    site.difficulty,
    site.grading,
    site.output_format,
    site.is_async ? "async" : null,
    site.max_tokens != null ? `max_tokens ${site.max_tokens}` : null,
    site.temperature != null ? `temperature ${site.temperature}` : null,
  ].filter((x): x is string => Boolean(x));

  return (
    <>
      <section className="pt-10 sm:pt-14 pb-12">
        <Link
          href="/callsites/"
          className="text-xs text-subtle hover:text-heading transition-colors"
        >
          &#8592; All call sites
        </Link>
        <div className="mt-6 grid gap-10 lg:grid-cols-[1.3fr_1fr]">
          <div>
            <p className="text-[11px] font-mono uppercase tracking-[0.18em] text-accent-2">
              {site.file}:{site.line}
            </p>
            <h1 className="mt-2 text-3xl sm:text-4xl font-semibold font-mono tracking-tight text-heading break-all">
              {siteName(site.id)}
            </h1>
            <div className="mt-4 flex flex-wrap gap-2">
              <FoundByBadge foundBy={site.found_by} />
              {site.via && <Badge tone="accent">via {site.via}</Badge>}
              {meta.map((m) => (
                <Badge key={m}>{m}</Badge>
              ))}
            </div>
            {site.purpose && <p className="mt-5 text-muted leading-relaxed">{site.purpose}</p>}
            {site.output_contract != null && (
              <div className="mt-5">
                <p className="text-[11px] font-mono uppercase tracking-wider text-subtle mb-2">
                  Output contract
                </p>
                {typeof site.output_contract === "string" ? (
                  <p className="text-sm text-text leading-relaxed">{site.output_contract}</p>
                ) : (
                  <CodeBlock code={formatValue(site.output_contract)} />
                )}
              </div>
            )}
          </div>

          <div className="rounded-xl border border-line bg-card p-6 self-start">
            {d ? (
              <>
                <div className="flex flex-wrap items-center gap-2">
                  <DecisionBadge action={d.action} />
                  <span className="font-mono text-sm text-heading">
                    {d.action === "downgrade"
                      ? `${d.baseline} \u2192 ${d.model}`
                      : `stays on ${d.baseline}`}
                  </span>
                </div>
                <p className="mt-3 text-sm text-muted leading-relaxed">{d.reason}</p>
                <div className="mt-5 pt-5 border-t border-line grid grid-cols-2 gap-5">
                  <MiniStat value={formatUsd(c?.before_monthly ?? null)} label="Before / month" tone="warn" />
                  <MiniStat value={formatUsd(c?.after_monthly ?? null)} label="After / month" tone="good" />
                  <MiniStat
                    value={formatUsd(c?.savings ?? null)}
                    label={`Savings (${formatPct(c?.savings_pct ?? null)})`}
                    tone="good"
                  />
                  <MiniStat value={formatNumber(c?.calls_per_day ?? null)} label="Calls / day" tone="violet" />
                </div>
              </>
            ) : (
              <p className="text-sm text-muted">No decision available.</p>
            )}
            <div className="mt-5">
              <Disclaimer />
            </div>
          </div>
        </div>
      </section>

      <ModelsTable site={site} showJudge={site.grading === "judge"} />

      <Section eyebrow="Prompt" title="What the call sends">
        <p className="text-xs text-subtle mb-4">
          Model in code:{" "}
          <span className="font-mono text-muted">{site.model_in_code ?? "unresolved"}</span>
        </p>
        {site.messages ? (
          <div className="space-y-4">
            {site.messages.map((msg, i) => (
              <div key={i}>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-[11px] font-mono uppercase tracking-wider text-subtle">
                    {msg.role}
                  </span>
                  {!msg.resolved && <Badge tone="warn">not resolved statically</Badge>}
                </div>
                <div className="rounded-lg border border-line bg-card px-4 py-3.5 text-xs font-mono text-text whitespace-pre-wrap">
                  {msg.content}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-muted text-sm">Prompt not resolved statically.</p>
        )}
      </Section>

      {siteEvals ? (
        <>
          <EvalExamples siteEvals={siteEvals} />
          <EvalGrid siteEvals={siteEvals} />
        </>
      ) : (
        <Section eyebrow="Evals" title="No evals for this call site">
          <p className="text-muted text-sm">Run downshift evalgen or the Bob Eval Writer first.</p>
        </Section>
      )}
    </>
  );
}
