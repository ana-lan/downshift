import Link from "next/link";
import { Section } from "@/components/Panel";
import { Table } from "@/components/Table";
import { Disclaimer } from "@/components/Disclaimer";
import { DecisionBadge, FoundByBadge } from "@/components/Badge";
import { summary, callsites } from "@/lib/data";
import { modelStats } from "@/lib/select";
import { formatUsd, formatPct, siteName, siteFile, shortModel } from "@/lib/format";

const td = "px-3 py-3 border-b border-line-soft whitespace-nowrap align-top";

export default function CallSitesPage() {
  const { baseline, candidates, threshold, min_pass_rate, sites_total, sites_downgraded } = summary;
  const models = [baseline, ...candidates];

  return (
    <Section eyebrow="Call sites" title={`${sites_total} call sites, ${sites_downgraded} downgraded`}>
      <p className="text-muted text-sm leading-relaxed max-w-3xl mb-8">
        Every call site was evaluated on the baseline and each cheaper model. A candidate must
        reach at least {formatPct(threshold, 0)} of the baseline pass rate and clear a floor of{" "}
        {formatPct(min_pass_rate, 0)}. The cheapest passing model wins. Judge-graded cases pass at
        4 of 5 or higher.
      </p>
      <Table
        headers={[
          "Call site",
          "Decision",
          ...models.map((m) => (m === baseline ? `${shortModel(m)} (base)` : shortModel(m))),
          "Savings/mo",
        ]}
      >
        {callsites.map((site) => {
          const meta = [siteFile(site.id), site.difficulty, site.grading].filter(Boolean);
          const down = site.decision?.action === "downgrade";
          return (
            <tr key={site.id} className="hover:bg-card/60 transition-colors">
              <td className={td}>
                <div className="flex items-center gap-2">
                  <Link
                    href={`/callsites/${site.slug}/`}
                    className="text-heading hover:text-accent transition-colors"
                  >
                    {siteName(site.id)}
                  </Link>
                  {site.found_by === "bob" && <FoundByBadge foundBy="bob" />}
                </div>
                <div className="text-[11px] text-subtle mt-0.5">{meta.join(" \u00b7 ")}</div>
              </td>
              <td className={td}>
                {site.decision ? <DecisionBadge action={site.decision.action} /> : "n/a"}
              </td>
              {models.map((model) => {
                const ms = modelStats(site, model);
                const picked = Boolean(ms?.chosen && !ms?.is_baseline);
                const color = picked
                  ? "text-good font-semibold"
                  : model === baseline
                    ? "text-heading"
                    : "text-muted";
                return (
                  <td key={model} className={`${td} tabular-nums ${color}`}>
                    {ms ? formatPct(ms.pass_rate) : "n/a"}
                  </td>
                );
              })}
              <td className={`${td} tabular-nums ${down ? "text-good" : "text-subtle"}`}>
                {formatUsd(site.cost?.savings ?? null)}
              </td>
            </tr>
          );
        })}
      </Table>
      <p className="mt-4 text-xs text-subtle">
        Pass rate per qwen2.5 model on each call site&apos;s evals. Teal is the model Downshift
        picked.
      </p>
      <div className="mt-3">
        <Disclaimer />
      </div>
    </Section>
  );
}
