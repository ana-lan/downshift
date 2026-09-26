import Link from "next/link";
import { Panel, Section } from "@/components/Panel";
import { StatCard, MiniStat } from "@/components/StatCard";
import { Table } from "@/components/Table";
import { CodeBlock } from "@/components/CodeBlock";
import { Disclaimer } from "@/components/Disclaimer";
import { LinkButton } from "@/components/Button";
import { DecisionBadge } from "@/components/Badge";
import { summary, callsites, totalEvalCases } from "@/lib/data";
import { auditRows, sortBySavings, chosenStats, baselineStats } from "@/lib/select";
import { audit } from "@/lib/data";
import {
  formatUsd,
  formatPct,
  formatPts,
  siteName,
  siteFile,
} from "@/lib/format";
import {
  REPO_URL,
  RESULT_NOTES,
  AUDIT_INTRO,
  CI_DEMO,
  ACTION_SNIPPET,
  PIPELINE_ASCII,
} from "@/lib/content";

function numberWord(n: number): string {
  const words = ["zero","one","two","three","four","five","six","seven","eight","nine","ten"];
  if (n >= 0 && n <= 10) return words[n];
  return String(n);
}

export default function HomePage() {
  const { cost, quality, sites_total, sites_downgraded, threshold, min_pass_rate, judge_models, project } = summary;
  const sorted = sortBySavings(callsites);
  const rows = auditRows(audit);

  const allModels = [summary.baseline, ...summary.candidates];

  return (
    <>
      {/* Hero */}
      <Panel>
        <div className="flex items-center gap-2 mb-5">
          <span className="w-2 h-2 rounded-full bg-accent inline-block" />
          <span className="text-xs font-mono text-muted">Open source &middot; pip install downshift</span>
        </div>
        <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold text-heading mb-4 leading-tight">
          Which{" "}
          <span className="text-accent-2">LLM calls</span>{" "}
          are you{" "}
          <span className="text-accent">overpaying</span>{" "}
          for?
        </h1>
        <p className="text-muted max-w-2xl mb-6">
          Downshift finds every LLM call site in a Python repo, writes evals for each one, tests cheaper models against the one you use today, and shows the cost impact of every pull request. Downshift is the toolkit, IBM Bob is the brain.
        </p>
        <div className="flex flex-wrap gap-3 mb-8">
          <LinkButton href="/docs/" variant="primary">Read the docs</LinkButton>
          <LinkButton href={REPO_URL} variant="secondary">View on GitHub &#8599;</LinkButton>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
          <StatCard
            value={`${formatUsd(cost.savings)}/mo`}
            label="Projected savings"
            sub={`${formatPct(cost.savings_pct)} of ${formatUsd(cost.before_monthly)} per month`}
            tone="good"
          />
          <StatCard
            value={`${sites_downgraded} of ${sites_total}`}
            label="Call sites downgraded"
            sub={`each one passed its evals at >= ${formatPct(threshold, 0)} of baseline quality`}
          />
          <StatCard
            value={`${formatPct(quality.baseline_pass_rate)} \u2192 ${formatPct(quality.after_pass_rate)}`}
            label="Mean eval pass rate"
            sub={`${formatPts(quality.delta)} after downgrading`}
          />
          <StatCard
            value={String(totalEvalCases())}
            label="Eval cases"
            sub={`graded by ${judge_models[0]}`}
          />
        </div>
        <Disclaimer />
      </Panel>

      {/* Results */}
      <Section
        eyebrow={`RESULTS \u00b7 ${project.toUpperCase()}`}
        title={`${numberWord(sites_downgraded).charAt(0).toUpperCase() + numberWord(sites_downgraded).slice(1)} of ${numberWord(sites_total)} call sites can run on a smaller model`}
      >
        <div className="grid grid-cols-3 gap-3 mb-6">
          <MiniStat value={`${formatUsd(cost.before_monthly)}/mo`} label="Before" />
          <MiniStat value={`${formatUsd(cost.after_monthly)}/mo`} label="After" tone="good" />
          <MiniStat value={`${formatUsd(cost.savings)}/mo`} label="Savings" tone="good" />
        </div>
        <Table
          headers={["Call site", "Decision", "Model", "Baseline pass", "Chosen pass", "Savings/mo"]}
          minWidth={700}
        >
          {sorted.map((site) => {
            const base = baselineStats(site);
            const chosen = chosenStats(site);
            const modelLabel =
              site.decision?.action === "downgrade"
                ? `${site.decision.baseline} \u2192 ${site.decision.model}`
                : site.decision?.baseline ?? site.models[0]?.model ?? "";
            return (
              <tr key={site.id} className="hover:bg-card/50 transition-colors">
                <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap text-heading">
                  <Link href={`/callsites/${site.slug}/`} className="hover:text-accent transition-colors">
                    {siteName(site.id)}
                  </Link>
                  <div className="text-xs text-subtle">{siteFile(site.id)}</div>
                </td>
                <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap text-muted">
                  {site.decision ? <DecisionBadge action={site.decision.action} /> : "n/a"}
                </td>
                <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap text-muted">
                  {modelLabel}
                </td>
                <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap text-muted">
                  {formatPct(base?.pass_rate ?? null)}
                </td>
                <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap text-muted">
                  {formatPct(chosen?.pass_rate ?? null)}
                </td>
                <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap text-muted">
                  {formatUsd(site.cost?.savings ?? null)}
                </td>
              </tr>
            );
          })}
        </Table>
        <ul className="mt-4 space-y-1">
          {RESULT_NOTES.map((note, i) => (
            <li key={i} className="text-xs text-subtle flex gap-2">
              <span>&bull;</span>
              <span>{note}</span>
            </li>
          ))}
        </ul>
      </Section>

      {/* Audit comparison */}
      <Section
        eyebrow="STATIC ANALYSIS VS BOB"
        title="Config-driven code blinds static analysis"
      >
        {AUDIT_INTRO.map((p, i) => (
          <p key={i} className="text-muted mb-3 text-sm">{p}</p>
        ))}
        <Table headers={["Metric", "ast scan", "Bob audit", "ast after refactor"]}>
          {rows.map((row) => (
            <tr key={row.key} className="hover:bg-card/50 transition-colors">
              <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap text-heading">
                {row.label}
              </td>
              <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap text-muted">
                {row.ast ?? "n/a"}
              </td>
              <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap text-muted">
                {row.audit ?? "n/a"}
              </td>
              <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap text-muted">
                {row.astAfter ?? "n/a"}
              </td>
            </tr>
          ))}
        </Table>
        <p className="mt-4 text-sm">
          <Link href="/audit/" className="text-accent hover:underline">See the full audit &#8594;</Link>
        </p>
      </Section>

      {/* CI guardrail */}
      <Section eyebrow="CI GUARDRAIL" title="Every PR gets a cost diff">
        <div className="grid grid-cols-3 gap-3 mb-5">
          <MiniStat value={CI_DEMO.delta} label="Monthly increase" tone="warn" />
          <MiniStat value={CI_DEMO.pct} label="Percent increase" tone="warn" />
          <MiniStat value={CI_DEMO.range} label="Cost range" tone="warn" />
        </div>
        <p className="text-muted text-sm mb-5">{CI_DEMO.text}</p>
        <CodeBlock code={ACTION_SNIPPET} label="GitHub Actions usage" />
      </Section>

      {/* Architecture */}
      <Section eyebrow="ARCHITECTURE &amp; STACK" title="How the pieces fit">
        <CodeBlock code={PIPELINE_ASCII} />
        <div className="flex flex-wrap gap-2 mt-5">
          {["Python", "Typer", "Ollama", "Qwen 2.5", "IBM Bob", "GitHub Actions", "PyPI", "Next.js 15", "TypeScript", "Tailwind"].map((chip) => (
            <span key={chip} className="text-xs px-2.5 py-1 rounded-md border border-line text-muted font-mono">
              {chip}
            </span>
          ))}
        </div>
      </Section>

      {/* Closing CTA */}
      <Panel className="text-center">
        <h2 className="text-2xl font-bold text-heading mb-3">Cut your LLM bill one PR at a time</h2>
        <p className="text-muted text-sm mb-6 max-w-lg mx-auto">
          Downshift is open source, built by Anagha for the IBM Bob 2.0 Hackathon.
        </p>
        <div className="flex flex-wrap justify-center gap-3 mb-5">
          <LinkButton href={REPO_URL} variant="secondary">GitHub</LinkButton>
          <LinkButton href="https://www.linkedin.com/in/anagha-langhe/" variant="primary">LinkedIn</LinkButton>
        </div>
        <code className="text-xs font-mono text-accent-fg bg-accent-bg border border-accent-line rounded-lg px-4 py-2 inline-block">
          pip install downshift
        </code>
      </Panel>

      {/* suppress unused var warning */}
      <div className="hidden">{allModels.join(",")}{min_pass_rate}</div>
    </>
  );
}
