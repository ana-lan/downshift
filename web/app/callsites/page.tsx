import Link from "next/link";
import { Section } from "@/components/Panel";
import { Table } from "@/components/Table";
import { Disclaimer } from "@/components/Disclaimer";
import { DecisionBadge, FoundByBadge } from "@/components/Badge";
import { summary, callsites } from "@/lib/data";
import { modelStats } from "@/lib/select";
import { formatUsd, formatPct, siteName, siteFile } from "@/lib/format";

export default function CallSitesPage() {
  const { baseline, candidates, threshold, min_pass_rate, sites_total, sites_downgraded } = summary;
  const allModels = [baseline, ...candidates];

  return (
    <>
      <Section
        eyebrow="CALL SITES"
        title={`${sites_total} call sites, ${sites_downgraded} downgraded`}
      >
        <p className="text-muted text-sm mb-6">
          A candidate must reach at least {formatPct(threshold, 0)} of the baseline pass rate and clear an absolute floor of {formatPct(min_pass_rate, 0)}. The cheapest passing model wins. A judge grades at 4 of 5 or higher.
        </p>
        <Table
          headers={[
            "Call site",
            "Found by",
            "Difficulty",
            "Grading",
            "Decision",
            ...allModels.map((m) => m + (m === baseline ? " *" : "")),
            "After/mo",
            "Savings/mo",
          ]}
          minWidth={900}
        >
          {callsites.map((site) => (
            <tr key={site.id} className="hover:bg-card/50 transition-colors">
              <td className="px-3 sm:px-4 py-2 border-b border-line-soft text-heading">
                <Link href={`/callsites/${site.slug}/`} className="hover:text-accent transition-colors font-semibold">
                  {siteName(site.id)}
                </Link>
                <div className="text-xs text-subtle">{siteFile(site.id)}</div>
              </td>
              <td className="px-3 sm:px-4 py-2 border-b border-line-soft text-muted whitespace-nowrap">
                <FoundByBadge foundBy={site.found_by} />
              </td>
              <td className="px-3 sm:px-4 py-2 border-b border-line-soft text-muted whitespace-nowrap">
                {site.difficulty ?? "n/a"}
              </td>
              <td className="px-3 sm:px-4 py-2 border-b border-line-soft text-muted whitespace-nowrap">
                {site.grading ?? "n/a"}
              </td>
              <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap">
                {site.decision ? <DecisionBadge action={site.decision.action} /> : "n/a"}
              </td>
              {allModels.map((model) => {
                const ms = modelStats(site, model);
                const isChosen = ms?.chosen && !ms?.is_baseline;
                return (
                  <td
                    key={model}
                    className={`px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap ${isChosen ? "text-good font-semibold" : "text-muted"}`}
                  >
                    {ms ? formatPct(ms.pass_rate) : "n/a"}
                  </td>
                );
              })}
              <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap text-muted">
                {formatUsd(site.cost?.after_monthly ?? null)}
              </td>
              <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap text-muted">
                {formatUsd(site.cost?.savings ?? null)}
              </td>
            </tr>
          ))}
        </Table>
        <p className="text-xs text-subtle mt-3">* baseline model. Chosen model pass rate shown in green.</p>
        <div className="mt-4">
          <Disclaimer />
        </div>
      </Section>
    </>
  );
}
