import { Section } from "@/components/Panel";
import { Table } from "@/components/Table";
import { Badge, FoundByBadge } from "@/components/Badge";
import { audit } from "@/lib/data";
import { auditRows } from "@/lib/select";
import { AUDIT_INTRO, AUDIT_AFTER_NOTE } from "@/lib/content";

const td = "px-3 py-3 border-b border-line-soft whitespace-nowrap";

export default function AuditPage() {
  const rows = auditRows(audit);

  return (
    <>
      <Section eyebrow="Static analysis vs Bob" title="Config-driven code blinds static analysis">
        <div className="grid gap-8 lg:grid-cols-[1fr_1.2fr]">
          <div className="space-y-3">
            {AUDIT_INTRO.map((p, i) => (
              <p key={i} className="text-muted text-sm leading-relaxed">
                {p}
              </p>
            ))}
            <p className="text-sm text-subtle leading-relaxed border-l border-accent-2 pl-3">
              {AUDIT_AFTER_NOTE}
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

      <Section eyebrow="Changes" title="What the auditor changed">
        <ul className="divide-y divide-line-soft">
          {audit.changes.map((change) => (
            <li
              key={change.id + change.kind}
              className="grid gap-2 py-3 sm:grid-cols-[7rem_1fr] sm:items-baseline"
            >
              <span>
                <Badge tone="accent">{change.kind}</Badge>
              </span>
              <span>
                <span className="font-mono text-sm text-heading break-all">{change.id}</span>
                <span className="block text-sm text-muted mt-0.5">{change.detail}</span>
              </span>
            </li>
          ))}
        </ul>
      </Section>

      <Section eyebrow="Call sites" title="Side by side">
        <div className="grid gap-6 md:grid-cols-2">
          <div className="rounded-xl border border-line bg-card p-5">
            <p className="text-[11px] font-mono uppercase tracking-wider text-subtle mb-4">
              ast scan &middot; {audit.ast_sites.length} sites
            </p>
            <ul className="space-y-3">
              {audit.ast_sites.map((site) => (
                <li key={site.id}>
                  <span className="font-mono text-sm text-heading break-all">{site.id}</span>
                  <div className="text-xs text-muted mt-0.5">
                    {site.model ? (
                      <span className="font-mono">{site.model}</span>
                    ) : (
                      <span className="text-warn">model unresolved</span>
                    )}{" "}
                    &middot; prompt {site.prompt_resolved ? "resolved" : "not resolved"}
                  </div>
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-xl border border-line bg-card p-5">
            <p className="text-[11px] font-mono uppercase tracking-wider text-subtle mb-4">
              Bob audit &middot; {audit.audit_sites.length} sites
            </p>
            <ul className="space-y-3">
              {audit.audit_sites.map((site) => (
                <li
                  key={site.id}
                  className={site.found_by === "bob" ? "border-l-2 border-accent-2 pl-3" : ""}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-sm text-heading break-all">{site.id}</span>
                    {site.found_by === "bob" && <FoundByBadge foundBy="bob" />}
                  </div>
                  <div className="text-xs text-muted mt-0.5">
                    {site.via && (
                      <>
                        via <span className="font-mono">{site.via}</span> &middot;{" "}
                      </>
                    )}
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
