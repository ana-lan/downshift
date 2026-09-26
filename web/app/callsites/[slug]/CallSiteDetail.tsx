import type { CallSite, SiteEvals } from "@/lib/types";
import { Section } from "@/components/Panel";
import { Table } from "@/components/Table";
import { CodeBlock } from "@/components/CodeBlock";
import { Badge, PassBadge } from "@/components/Badge";
import {
  formatPct,
  formatNumber,
  formatSeconds,
  formatUsdPerCall,
  formatValue,
  shortModel,
} from "@/lib/format";

const td = "px-3 py-3 border-b border-line-soft whitespace-nowrap";

function dotClass(passed: boolean | null | undefined): string {
  if (passed === true) return "bg-good";
  if (passed === false) return "bg-bad/70";
  return "bg-line";
}

export function ModelsTable({ site, showJudge }: { site: CallSite; showJudge: boolean }) {
  const reasons = site.models.filter((m) => !m.is_baseline && m.check);
  return (
    <Section eyebrow="Models" title="How each model did">
      <Table
        headers={[
          "Model",
          "Pass rate",
          ...(showJudge ? ["Judge avg"] : []),
          "Tokens in / out",
          "Latency",
          "Cost / call",
          "vs baseline",
          "Check",
        ]}
      >
        {site.models.map((m) => (
          <tr key={m.model} className="hover:bg-card/60 transition-colors">
            <td className={`${td} text-heading`}>
              <div className="flex items-center gap-2">
                <span>{m.model}</span>
                {m.is_baseline && <Badge>baseline</Badge>}
                {m.chosen && !m.is_baseline && <Badge tone="good">chosen</Badge>}
              </div>
              {m.tier && <div className="text-[11px] text-subtle mt-0.5">{m.tier} tier</div>}
            </td>
            <td className={`${td} tabular-nums ${m.chosen ? "text-good" : "text-muted"}`}>
              {formatPct(m.pass_rate)}
              {m.passed != null && m.cases != null && (
                <span className="text-subtle">
                  {" "}
                  ({m.passed}/{m.cases})
                </span>
              )}
            </td>
            {showJudge && (
              <td className={`${td} tabular-nums text-muted`}>
                {m.avg_judge_score != null ? `${m.avg_judge_score.toFixed(2)} / 5` : "n/a"}
              </td>
            )}
            <td className={`${td} tabular-nums text-muted`}>
              {formatNumber(m.avg_prompt_tokens)} / {formatNumber(m.avg_completion_tokens)}
            </td>
            <td className={`${td} tabular-nums text-muted`}>{formatSeconds(m.avg_latency_s)}</td>
            <td className={`${td} tabular-nums text-muted`}>{formatUsdPerCall(m.cost_per_call)}</td>
            <td className={`${td} tabular-nums text-muted`}>
              {m.check?.ratio != null ? formatPct(m.check.ratio) : "n/a"}
            </td>
            <td className={td}>
              {m.is_baseline ? (
                <span className="text-xs text-subtle">n/a</span>
              ) : (
                <PassBadge passed={m.check?.passed ?? null} />
              )}
            </td>
          </tr>
        ))}
      </Table>
      {reasons.length > 0 && (
        <ul className="mt-6 grid gap-2 sm:grid-cols-2">
          {reasons.map((m) => (
            <li key={m.model} className="text-sm text-muted border-l border-line pl-3">
              <span className="font-mono text-heading">{shortModel(m.model)}</span>{" "}
              {m.check?.reason}
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

export function EvalExamples({ siteEvals }: { siteEvals: SiteEvals }) {
  return (
    <Section
      eyebrow="Eval examples"
      title={`${siteEvals.examples.length} of ${siteEvals.cases} cases, every model side by side`}
    >
      <div className="space-y-3">
        {siteEvals.examples.map((ex, i) => (
          <details
            key={ex.id}
            open={i === 0}
            className="group rounded-lg border border-line bg-card"
          >
            <summary className="px-4 py-3 cursor-pointer list-none flex flex-wrap items-center gap-x-4 gap-y-2">
              <span className="text-subtle transition-transform group-open:rotate-90">&#8250;</span>
              <span className="font-mono text-sm text-heading">{ex.id}</span>
              <span className="flex flex-wrap gap-3">
                {siteEvals.models.map((model) => (
                  <span
                    key={model}
                    className="inline-flex items-center gap-1.5 text-[11px] font-mono text-muted"
                  >
                    <span className={`h-2 w-2 rounded-full ${dotClass(ex.outputs[model]?.passed)}`} />
                    {shortModel(model)}
                  </span>
                ))}
              </span>
            </summary>
            <div className="border-t border-line px-4 pb-5">
              <div className="mt-4 grid gap-6 lg:grid-cols-2">
                <div>
                  <p className="text-[11px] font-mono uppercase tracking-wider text-subtle mb-2">
                    Inputs
                  </p>
                  <dl className="space-y-3">
                    {Object.entries(ex.inputs).map(([k, v]) => (
                      <div key={k}>
                        <dt className="text-[11px] font-mono text-accent">{k}</dt>
                        <dd className="mt-0.5 text-sm text-text whitespace-pre-wrap">
                          {formatValue(v)}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </div>
                <div>
                  <CodeBlock code={formatValue(ex.expected)} label="Expected" />
                  {ex.notes && <p className="mt-3 text-xs text-subtle leading-relaxed">{ex.notes}</p>}
                </div>
              </div>
              <p className="mt-6 text-[11px] font-mono uppercase tracking-wider text-subtle mb-2">
                Outputs
              </p>
              <div className="grid gap-3 md:grid-cols-2">
                {siteEvals.models.map((model) => {
                  const out = ex.outputs[model];
                  return (
                    <div key={model} className="rounded-lg border border-line bg-panel p-3.5">
                      <div className="flex flex-wrap items-center gap-2 mb-2">
                        <span className="font-mono text-xs text-heading">{model}</span>
                        <PassBadge passed={out?.passed ?? null} />
                        {out?.judge_score != null && (
                          <span className="text-[11px] text-subtle">judge {out.judge_score}/5</span>
                        )}
                      </div>
                      {out ? (
                        <>
                          <div className="text-xs font-mono text-text whitespace-pre-wrap">
                            {out.output}
                          </div>
                          {out.detail && (
                            <p className="mt-2 text-[11px] text-subtle leading-relaxed">{out.detail}</p>
                          )}
                          {out.error && <p className="mt-2 text-[11px] text-bad">{out.error}</p>}
                        </>
                      ) : (
                        <p className="text-xs text-subtle">No output</p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </details>
        ))}
      </div>
    </Section>
  );
}

export function EvalGrid({ siteEvals }: { siteEvals: SiteEvals }) {
  const total = siteEvals.grid.length;
  return (
    <Section eyebrow="All cases" title={`Pass and fail across all ${total} cases`}>
      <div className="space-y-4">
        {siteEvals.models.map((model) => {
          const passed = siteEvals.grid.filter((r) => r.passed[model] === true).length;
          return (
            <div key={model} className="grid gap-2 sm:grid-cols-[9rem_1fr_4rem] sm:items-center">
              <span className="font-mono text-sm text-heading">{model}</span>
              <div className="flex flex-wrap gap-1">
                {siteEvals.grid.map((row) => {
                  const p = row.passed[model];
                  const label = p === true ? "pass" : p === false ? "fail" : "n/a";
                  return (
                    <span
                      key={row.id}
                      title={`${row.id} \u00b7 ${model} \u00b7 ${label}`}
                      className={`h-4 w-4 rounded-[3px] ${dotClass(p)}`}
                    />
                  );
                })}
              </div>
              <span className="font-mono text-xs text-muted tabular-nums sm:text-right">
                {passed}/{total}
              </span>
            </div>
          );
        })}
      </div>
      <div className="mt-5 flex items-center gap-4 text-xs text-subtle">
        <span className="flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-[3px] bg-good" /> pass
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-[3px] bg-bad/70" /> fail
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-[3px] bg-line" /> no result
        </span>
        <span>Hover a square for the case id.</span>
      </div>
    </Section>
  );
}
