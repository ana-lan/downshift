import { Section } from "@/components/Panel";
import { Table } from "@/components/Table";
import { Badge, FoundByBadge } from "@/components/Badge";
import { audit } from "@/lib/data";
import { auditRows } from "@/lib/select";
import { AUDIT_INTRO, AUDIT_AFTER_NOTE } from "@/lib/content";

export default function AuditPage() {
  const rows = auditRows(audit);

  return (
    <>
      <Section
        eyebrow="STATIC ANALYSIS VS BOB"
        title="Config-driven code blinds static analysis"
      >
        {AUDIT_INTRO.map((p, i) => (
          <p key={i} className="text-muted text-sm mb-3">{p}</p>
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
              <td className={`px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap ${(row.audit ?? 0) > (row.ast ?? 0) ? "text-good" : "text-muted"}`}>
                {row.audit ?? "n/a"}
              </td>
              <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap text-muted">
                {row.astAfter ?? "n/a"}
              </td>
            </tr>
          ))}
        </Table>
        <p className="text-xs text-subtle mt-4">{AUDIT_AFTER_NOTE}</p>
      </Section>

      <Section eyebrow="WHAT BOB CHANGED" title="">
        <ul className="space-y-2">
          {audit.changes.map((change) => (
            <li key={change.id + change.kind} className="flex flex-wrap items-start gap-2 text-sm">
              <Badge tone="accent">{change.kind}</Badge>
              <span className="font-mono text-heading">{change.id}</span>
              <span className="text-muted">{change.detail}</span>
            </li>
          ))}
        </ul>
      </Section>

      <Section eyebrow="CALL SITES" title="">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <p className="text-xs font-mono text-subtle uppercase mb-3">
              ast scan ({audit.ast_sites.length})
            </p>
            <ul className="space-y-2">
              {audit.ast_sites.map((site) => (
                <li key={site.id} className="text-sm">
                  <span className="font-mono text-heading">{site.id}</span>
                  <div className="text-xs text-muted mt-0.5">
                    {site.model ? (
                      <span className="font-mono">{site.model}</span>
                    ) : (
                      <span className="text-warn">unresolved</span>
                    )}
                    {" "}&middot;{" "}
                    prompt {site.prompt_resolved ? "resolved" : "not resolved"}
                  </div>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <p className="text-xs font-mono text-subtle uppercase mb-3">
              Bob audit ({audit.audit_sites.length})
            </p>
            <ul className="space-y-2">
              {audit.audit_sites.map((site) => (
                <li
                  key={site.id}
                  className={`text-sm ${site.found_by === "bob" ? "border-l-2 border-accent pl-3" : ""}`}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-heading">{site.id}</span>
                    <FoundByBadge foundBy={site.found_by} />
                  </div>
                  <div className="text-xs text-muted mt-0.5">
                    {site.via && <span>via <span className="font-mono">{site.via}</span> &middot; </span>}
                    <span className="font-mono">{site.model ?? "unresolved"}</span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </Section>
    </>
  );
}
