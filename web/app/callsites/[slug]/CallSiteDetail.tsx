import type { CallSite, SiteEvals } from "@/lib/types";
import { Section } from "@/components/Panel";
import { Table } from "@/components/Table";
import { CodeBlock } from "@/components/CodeBlock";
import { PassBadge } from "@/components/Badge";
import {
  formatPct,
  formatNumber,
  formatSeconds,
  formatUsdPerCall,
  formatValue,
} from "@/lib/format";

interface ModelsTableProps {
  site: CallSite;
  showJudge: boolean;
}

export function ModelsTable({ site, showJudge }: ModelsTableProps) {
  return (
    <Section eyebrow="MODELS" title="">
      <Table
        headers={[
          "Model",
          "Pass rate",
          "Passed",
          "Mean score",
          ...(showJudge ? ["Judge avg"] : []),
          "Prompt tok",
          "Completion tok",
          "Latency",
          "Cost/call",
          "vs baseline",
          "Check",
        ]}
      >
        {site.models.map((m) => (
          <tr key={m.model} className="hover:bg-card/50 transition-colors">
            <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap text-heading">
              <span className="font-mono">{m.model}</span>
              {m.tier && <span className="ml-1 text-subtle text-xs">({m.tier})</span>}
              {m.is_baseline && <span className="ml-1 text-xs text-subtle">baseline</span>}
              {m.chosen && !m.is_baseline && <span className="ml-1 text-xs text-good">chosen</span>}
            </td>
            <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap text-muted">
              {formatPct(m.pass_rate)}
            </td>
            <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap text-muted">
              {m.passed != null && m.cases != null ? `${m.passed}/${m.cases}` : "n/a"}
            </td>
            <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap text-muted">
              {m.mean_score != null ? m.mean_score.toFixed(4) : "n/a"}
            </td>
            {showJudge && (
              <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap text-muted">
                {m.avg_judge_score != null ? m.avg_judge_score.toFixed(2) : "n/a"}
              </td>
            )}
            <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap text-muted">
              {formatNumber(m.avg_prompt_tokens, 1)}
            </td>
            <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap text-muted">
              {formatNumber(m.avg_completion_tokens, 1)}
            </td>
            <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap text-muted">
              {formatSeconds(m.avg_latency_s)}
            </td>
            <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap text-muted">
              {formatUsdPerCall(m.cost_per_call)}
            </td>
            <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap text-muted">
              {m.check?.ratio != null ? formatPct(m.check.ratio) : "n/a"}
            </td>
            <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap">
              {m.is_baseline
                ? <span className="text-subtle text-xs">n/a</span>
                : <PassBadge passed={m.check?.passed ?? null} />}
            </td>
          </tr>
        ))}
      </Table>
      <ul className="mt-4 space-y-1">
        {site.models.filter((m) => !m.is_baseline && m.check).map((m) => (
          <li key={m.model} className="text-xs text-muted">
            <span className="font-mono text-subtle">{m.model}:</span> {m.check!.reason}
          </li>
        ))}
      </ul>
    </Section>
  );
}

interface EvalExamplesProps {
  siteEvals: SiteEvals;
}

export function EvalExamples({ siteEvals }: EvalExamplesProps) {
  return (
    <Section
      eyebrow="EVAL EXAMPLES"
      title={`${siteEvals.examples.length} of ${siteEvals.cases} cases`}
    >
      <div className="space-y-3">
        {siteEvals.examples.map((ex, i) => (
          <details key={ex.id} open={i === 0} className="rounded-xl border border-line bg-card overflow-hidden">
            <summary className="px-4 py-3 cursor-pointer flex flex-wrap items-center gap-3 list-none">
              <span className="font-mono text-sm text-heading">{ex.id}</span>
              <div className="flex flex-wrap gap-1">
                {siteEvals.models.map((model) => {
                  const out = ex.outputs[model];
                  return (
                    <span key={model} className="flex items-center gap-1 text-xs text-muted">
                      <span className="font-mono">{model}</span>
                      <PassBadge passed={out?.passed ?? null} />
                    </span>
                  );
                })}
              </div>
            </summary>
            <div className="px-4 pb-4 border-t border-line">
              <div className="mt-3 mb-4">
                <p className="text-xs font-mono text-subtle uppercase mb-2">Inputs</p>
                <dl className="space-y-2">
                  {Object.entries(ex.inputs).map(([k, v]) => (
                    <div key={k}>
                      <dt className="text-xs font-mono text-subtle">{k}</dt>
                      <dd className="text-xs text-muted whitespace-pre-wrap mt-0.5">{formatValue(v)}</dd>
                    </div>
                  ))}
                </dl>
              </div>
              <div className="mb-4">
                <p className="text-xs font-mono text-subtle uppercase mb-2">Expected</p>
                <CodeBlock code={formatValue(ex.expected)} />
              </div>
              {ex.notes && <p className="text-xs text-subtle mb-4">{ex.notes}</p>}
              <p className="text-xs font-mono text-subtle uppercase mb-2">Outputs</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {siteEvals.models.map((model) => {
                  const out = ex.outputs[model];
                  return (
                    <div key={model} className="rounded-lg border border-line bg-panel p-3">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="font-mono text-xs text-heading">{model}</span>
                        <PassBadge passed={out?.passed ?? null} />
                        {out?.score != null && <span className="text-xs text-subtle">score {out.score}</span>}
                        {out?.judge_score != null && <span className="text-xs text-subtle">judge {out.judge_score}/5</span>}
                      </div>
                      {out ? (
                        <>
                          <div className="text-xs font-mono text-muted whitespace-pre-wrap mb-2">{out.output}</div>
                          {out.detail && <p className="text-xs text-subtle">{out.detail}</p>}
                          {out.error && <p className="text-xs text-bad">{out.error}</p>}
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

interface EvalGridProps {
  siteEvals: SiteEvals;
}

export function EvalGrid({ siteEvals }: EvalGridProps) {
  return (
    <Section eyebrow="ALL CASES" title="">
      <div className="overflow-x-auto">
        <table className="text-xs font-mono">
          <thead>
            <tr>
              <th className="text-left px-2 py-1 text-subtle font-normal whitespace-nowrap">Case</th>
              {siteEvals.models.map((m) => (
                <th key={m} className="px-2 py-1 text-subtle font-normal whitespace-nowrap">{m}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {siteEvals.grid.map((row) => (
              <tr key={row.id}>
                <td className="px-2 py-1 text-heading">{row.id}</td>
                {siteEvals.models.map((model) => {
                  const passed = row.passed[model];
                  const colorClass =
                    passed === true ? "bg-good" :
                    passed === false ? "bg-bad" :
                    "bg-line";
                  return (
                    <td key={model} className="px-2 py-1 text-center">
                      <span
                        className={`inline-block w-4 h-4 rounded-sm ${colorClass}`}
                        title={`${row.id} \u00b7 ${model} \u00b7 ${passed === true ? "PASS" : passed === false ? "FAIL" : "n/a"}`}
                      />
                    </td>
                  );
                })}
              </tr>
            ))}
            <tr className="border-t border-line">
              <td className="px-2 py-1 text-subtle">passed/total</td>
              {siteEvals.models.map((model) => {
                const total = siteEvals.grid.length;
                const passed = siteEvals.grid.filter((r) => r.passed[model] === true).length;
                return (
                  <td key={model} className="px-2 py-1 text-center text-muted">
                    {passed}/{total}
                  </td>
                );
              })}
            </tr>
          </tbody>
        </table>
      </div>
      <div className="flex items-center gap-4 mt-3 text-xs text-subtle">
        <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-sm bg-good" /> pass</span>
        <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-sm bg-bad" /> fail</span>
        <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-sm bg-line" /> n/a</span>
      </div>
    </Section>
  );
}
