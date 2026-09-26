import Link from "next/link";
import { Section } from "@/components/Panel";
import { StatCard, MiniStat } from "@/components/StatCard";
import { Table } from "@/components/Table";
import { Disclaimer } from "@/components/Disclaimer";
import { LinkButton } from "@/components/Button";
import { DecisionBadge } from "@/components/Badge";
import { summary, callsites, audit, totalEvalCases } from "@/lib/data";
import { auditRows, sortBySavings, chosenStats, baselineStats } from "@/lib/select";
import { formatUsd, formatPct, formatPts, siteName, siteFile } from "@/lib/format";
import { REPO_URL, RESULT_NOTES, AUDIT_INTRO, CI_DEMO } from "@/lib/content";

const WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];

function numberWord(n: number, capital = false): string {
  const w = n >= 0 && n < WORDS.length ? WORDS[n] : String(n);
  return capital ? w.charAt(0).toUpperCase() + w.slice(1) : w;
}

const td = "px-3 py-3 border-b border-line-soft whitespace-nowrap";

function CostBars() {
  const { before_monthly, after_monthly, savings, savings_pct } = summary.cost;
  const afterPct =
    before_monthly && after_monthly !== null
      ? Math.max(4, (after_monthly / before_monthly) * 100)
      : 100;
  return (
    <div className="rounded-xl border border-line bg-card p-6 sm:p-7">
      <p className="text-[11px] font-mono uppercase tracking-wider text-subtle">
        Projected monthly cost &middot; {summary.project}
      </p>
      <div className="mt-6 space-y-5">
        <div>
          <div className="flex justify-between text-sm">
            <span className="text-muted">Before</span>
            <span className="font-mono tabular-nums text-heading">{formatUsd(before_monthly)}</span>
          </div>
          <div className="mt-2 h-2.5 rounded-full bg-blue/70" />
        </div>
        <div>
          <div className="flex justify-between text-sm">
            <span className="text-muted">After Downshift</span>
            <span className="font-mono tabular-nums text-heading">{formatUsd(after_monthly)}</span>
          </div>
          <div className="mt-2 h-2.5 rounded-full bg-line-soft">
            <div className="h-full rounded-full bg-teal" style={{ width: `${afterPct}%` }} />
          </div>
        </div>
      </div>
      <div className="mt-7 pt-5 border-t border-line flex items-baseline justify-between gap-4">
        <span className="text-sm text-muted">Savings</span>
        <span className="text-2xl sm:text-3xl font-semibold tabular-nums text-good">
          {formatUsd(savings)}
          <span className="text-sm font-normal text-subtle">
            /mo &middot; {formatPct(savings_pct)}
          </span>
        </span>
      </div>
    </div>
  );
}

export default function HomePage() {
  const { quality, sites_total, sites_downgraded, threshold, project } = summary;
  const sorted = sortBySavings(callsites);
  const rows = auditRows(audit);
  const astSites = audit.ast?.call_sites;
  const astResolved = audit.ast?.models_resolved;

  return (
    <>
      <section className="pt-12 sm:pt-20 pb-12">
        <div className="grid gap-10 lg:grid-cols-[1.15fr_1fr] lg:items-center">
          <div>
            <h1 className="text-4xl sm:text-5xl font-semibold tracking-tight text-heading leading-[1.1]">
              Which LLM calls are you <span className="text-brand">overpaying</span> for?
            </h1>
            <p className="mt-5 text-base sm:text-lg text-muted max-w-xl leading-relaxed">
              Downshift finds every LLM call site in a Python repo, writes evals for each one,
              tests cheaper models against the one you use today, and shows the cost impact of
              every pull request.
            </p>
            <p className="mt-3 text-sm text-subtle">Downshift is the toolkit, IBM Bob is the brain.</p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <LinkButton href="/docs/">Get started</LinkButton>
              <LinkButton href={REPO_URL} variant="secondary">
                GitHub &#8599;
              </LinkButton>
              <code className="ml-1 text-xs font-mono text-subtle">pip install downshift</code>
            </div>
          </div>
          <div>
            <CostBars />
            <div className="mt-4">
              <Disclaimer />
            </div>
          </div>
        </div>

        <div className="mt-14 grid grid-cols-2 lg:grid-cols-4 gap-y-8">
          <StatCard
            value={`${sites_downgraded} of ${sites_total}`}
            label="Call sites downgraded"
            sub={`each kept at least ${formatPct(threshold, 0)} of baseline quality`}
            tone="good"
          />
          <StatCard
            value={formatPct(quality.after_pass_rate)}
            label="Mean eval pass rate"
            sub={`${formatPct(quality.baseline_pass_rate)} before, ${formatPts(quality.delta)}`}
          />
          <StatCard
            value={String(totalEvalCases())}
            label="Eval cases"
            sub={`graded by ${summary.judge_models[0] ?? "n/a"}`}
            tone="warn"
          />
          <StatCard
            value={`${audit.audit.models_resolved ?? 0} of ${audit.audit.call_sites ?? 0}`}
            label="Models resolved with Bob"
            sub={
              astSites !== undefined
                ? `static analysis alone: ${astResolved ?? 0} of ${astSites}`
                : undefined
            }
            tone="violet"
          />
        </div>
      </section>

      <Section
        eyebrow={`01 \u00b7 Results \u00b7 ${project}`}
        title={`${numberWord(sites_downgraded, true)} of ${numberWord(sites_total)} call sites can run on a smaller model`}
      >
        <Table headers={["Call site", "Decision", "Model", "Pass rate", "Savings/mo"]}>
          {sorted.map((site) => {
            const base = baselineStats(site);
            const chosen = chosenStats(site);
            const down = site.decision?.action === "downgrade";
            return (
              <tr key={site.id} className="hover:bg-card/60 transition-colors">
                <td className={`${td} text-heading`}>
                  <Link href={`/callsites/${site.slug}/`} className="hover:text-accent">
                    {siteName(site.id)}
                  </Link>
                  <div className="text-[11px] text-subtle">{siteFile(site.id)}</div>
                </td>
                <td className={td}>
                  {site.decision ? <DecisionBadge action={site.decision.action} /> : "n/a"}
                </td>
                <td className={`${td} text-muted`}>
                  {down
                    ? `${site.decision?.baseline} \u2192 ${site.decision?.model}`
                    : site.decision?.baseline ?? "n/a"}
                </td>
                <td className={`${td} text-muted tabular-nums`}>
                  {down
                    ? `${formatPct(base?.pass_rate ?? null)} \u2192 ${formatPct(chosen?.pass_rate ?? null)}`
                    : formatPct(base?.pass_rate ?? null)}
                </td>
                <td className={`${td} tabular-nums ${down ? "text-good" : "text-subtle"}`}>
                  {formatUsd(site.cost?.savings ?? null)}
                </td>
              </tr>
            );
          })}
        </Table>
        <ul className="mt-6 grid gap-2 sm:grid-cols-2">
          {RESULT_NOTES.map((note, i) => (
            <li key={i} className="text-sm text-muted border-l border-line pl-3">
              {note}
            </li>
          ))}
        </ul>
      </Section>

      <Section eyebrow="02 · Static analysis vs Bob" title="Config-driven code blinds static analysis">
        <div className="grid gap-8 lg:grid-cols-[1fr_1.2fr]">
          <div className="space-y-3">
            {AUDIT_INTRO.map((p, i) => (
              <p key={i} className="text-muted text-sm leading-relaxed">
                {p}
              </p>
            ))}
            <p className="pt-2 text-sm">
              <Link href="/audit/" className="text-accent hover:underline">
                See the full audit &#8594;
              </Link>
            </p>
          </div>
          <Table headers={["Metric", "ast", "Bob", "ast after refactor"]}>
            {rows.map((row) => (
              <tr key={row.key}>
                <td className={`${td} text-heading`}>{row.label}</td>
                <td className={`${td} text-muted`}>{row.ast ?? "n/a"}</td>
                <td
                  className={`${td} ${
                    (row.audit ?? 0) > (row.ast ?? 0) ? "text-accent-2" : "text-muted"
                  }`}
                >
                  {row.audit ?? "n/a"}
                </td>
                <td className={`${td} text-muted`}>{row.astAfter ?? "n/a"}</td>
              </tr>
            ))}
          </Table>
        </div>
      </Section>

      <Section eyebrow="03 · CI guardrail" title="Every PR gets a cost diff">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mb-6">
          <MiniStat value={CI_DEMO.delta} label="Projected monthly increase" tone="bad" />
          <MiniStat value={CI_DEMO.pct} label="Percent increase" tone="bad" />
          <MiniStat value={CI_DEMO.range} label="Monthly cost, before and after" tone="warn" />
        </div>
        <p className="text-muted text-sm leading-relaxed max-w-3xl">{CI_DEMO.text}</p>
        <p className="mt-5 text-sm">
          <Link href="/docs/" className="text-accent hover:underline">
            Set up the GitHub Action &#8594;
          </Link>
        </p>
      </Section>
    </>
  );
}
