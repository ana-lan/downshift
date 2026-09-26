import { Section } from "@/components/Panel";
import { Table } from "@/components/Table";
import { CodeBlock } from "@/components/CodeBlock";
import { Disclaimer } from "@/components/Disclaimer";
import { Badge } from "@/components/Badge";
import { summary } from "@/lib/data";
import { formatUsd } from "@/lib/format";
import {
  PIPELINE_STEPS,
  PIPELINE_ASCII,
  BOB_TASKS,
  DECISION_RULE,
} from "@/lib/content";

export default function HowItWorksPage() {
  return (
    <>
      <Section eyebrow="PIPELINE" title="From call site to cost diff">
        <ol className="space-y-4 mb-6">
          {PIPELINE_STEPS.map((step, i) => (
            <li key={i} className="flex gap-4">
              <span className="text-accent font-mono text-sm shrink-0 w-5 pt-0.5">{i + 1}.</span>
              <div>
                <div className="flex flex-wrap items-center gap-2 mb-1">
                  <span className="font-semibold text-heading text-sm">{step.title}</span>
                  <Badge tone={step.who === "Bob" ? "accent" : "neutral"}>{step.who}</Badge>
                  <code className="text-xs font-mono text-muted">{step.command}</code>
                </div>
                <p className="text-sm text-muted">{step.text}</p>
              </div>
            </li>
          ))}
        </ol>
        <CodeBlock code={PIPELINE_ASCII} label="Pipeline" />
      </Section>

      <Section
        eyebrow="WHERE BOB FITS"
        title="Downshift is the toolkit, Bob is the brain"
      >
        <p className="text-muted text-sm mb-5">
          Bob contributes at two points: the audit (resolving hidden models, splitting helpers) and writing evals. Everything else is deterministic Python.
        </p>
        <Table headers={["Task", "Bob feature", "What it did", "Bobcoins"]}>
          {BOB_TASKS.map((task, i) => (
            <tr key={i} className="hover:bg-card/50 transition-colors">
              <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap text-heading">
                {task.task}
              </td>
              <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap text-muted font-mono">
                {task.feature}
              </td>
              <td className="px-3 sm:px-4 py-2 border-b border-line-soft text-muted">
                {task.did}
              </td>
              <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap text-muted font-mono">
                {task.coins}
              </td>
            </tr>
          ))}
        </Table>
      </Section>

      <Section eyebrow="DECISION RULE" title="">
        <ul className="space-y-2 mb-5">
          {DECISION_RULE.map((rule, i) => (
            <li key={i} className="flex gap-2 text-sm text-muted">
              <span className="text-accent shrink-0">&bull;</span>
              <span>{rule}</span>
            </li>
          ))}
        </ul>
        <p className="text-xs text-subtle">
          Threshold: {summary.threshold * 100}% &middot; Floor: {summary.min_pass_rate * 100}%
        </p>
      </Section>

      <Section eyebrow="PRICING" title="">
        <Table headers={["Model", "Tier", "Input $/1M", "Output $/1M"]}>
          {summary.pricing.map((p) => (
            <tr key={p.model} className="hover:bg-card/50 transition-colors">
              <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap text-heading font-mono">
                {p.model}
              </td>
              <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap text-muted">
                {p.tier ?? "n/a"}
              </td>
              <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap text-muted">
                {p.input_per_mtok != null ? formatUsd(p.input_per_mtok) : "n/a"}
              </td>
              <td className="px-3 sm:px-4 py-2 border-b border-line-soft whitespace-nowrap text-muted">
                {p.output_per_mtok != null ? formatUsd(p.output_per_mtok) : "n/a"}
              </td>
            </tr>
          ))}
        </Table>
        <p className="text-xs text-subtle mt-3">
          Illustrative tier prices that map local models to realistic API costs.
        </p>
        <div className="mt-4">
          <Disclaimer />
        </div>
      </Section>
    </>
  );
}
