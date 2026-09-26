import { Section } from "@/components/Panel";
import { Table } from "@/components/Table";
import { CodeBlock } from "@/components/CodeBlock";
import { Disclaimer } from "@/components/Disclaimer";
import { Badge } from "@/components/Badge";
import { summary } from "@/lib/data";
import { formatUsd, formatPct } from "@/lib/format";
import { PIPELINE_STEPS, PIPELINE_ASCII, BOB_TASKS, DECISION_RULE } from "@/lib/content";

const td = "px-3 py-3 border-b border-line-soft";

export default function HowItWorksPage() {
  return (
    <>
      <Section eyebrow="Pipeline" title="From call site to cost diff">
        <ol className="grid gap-4 md:grid-cols-2">
          {PIPELINE_STEPS.map((step, i) => (
            <li key={step.title} className="rounded-xl border border-line bg-card p-5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-sm text-accent">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span className="font-semibold text-heading">{step.title}</span>
                <Badge tone={step.who === "Bob" ? "accent" : "neutral"}>{step.who}</Badge>
              </div>
              <code className="mt-2 block text-xs font-mono text-subtle">{step.command}</code>
              <p className="mt-2 text-sm text-muted leading-relaxed">{step.text}</p>
            </li>
          ))}
        </ol>
        <div className="mt-8">
          <CodeBlock code={PIPELINE_ASCII} label="Data flow" />
        </div>
      </Section>

      <Section eyebrow="Where Bob fits" title="Downshift is the toolkit, Bob is the brain">
        <p className="text-muted text-sm leading-relaxed max-w-3xl mb-6">
          Bob does the parts that need real code understanding: auditing call sites, writing
          evals, applying the decisions and reviewing pull requests. Scanning, running, grading,
          costing and the CI diff are deterministic Python that runs without Bob.
        </p>
        <Table headers={["Task", "Bob feature", "What it did", "Bobcoins"]}>
          {BOB_TASKS.map((task) => (
            <tr key={task.task} className="hover:bg-card/60 transition-colors">
              <td className={`${td} whitespace-nowrap text-heading`}>{task.task}</td>
              <td className={`${td} whitespace-nowrap text-accent-2`}>{task.feature}</td>
              <td className={`${td} text-muted font-sans`}>{task.did}</td>
              <td className={`${td} whitespace-nowrap text-muted tabular-nums`}>{task.coins}</td>
            </tr>
          ))}
        </Table>
      </Section>

      <Section eyebrow="Decision rule" title="How a model gets picked">
        <ul className="grid gap-3 sm:grid-cols-2">
          {DECISION_RULE.map((rule) => (
            <li key={rule} className="text-sm text-muted leading-relaxed border-l border-line pl-3">
              {rule}
            </li>
          ))}
        </ul>
        <p className="mt-5 text-xs font-mono text-subtle">
          threshold {formatPct(summary.threshold, 0)} &middot; floor{" "}
          {formatPct(summary.min_pass_rate, 0)} &middot; judge{" "}
          {summary.judge_models[0] ?? "n/a"}
        </p>
      </Section>

      <Section eyebrow="Pricing" title="Illustrative prices">
        <Table headers={["Model", "Tier", "Input / 1M tokens", "Output / 1M tokens"]}>
          {summary.pricing.map((p) => (
            <tr key={p.model}>
              <td className={`${td} whitespace-nowrap text-heading`}>{p.model}</td>
              <td className={`${td} whitespace-nowrap text-muted`}>{p.tier ?? "n/a"}</td>
              <td className={`${td} whitespace-nowrap text-muted tabular-nums`}>
                {formatUsd(p.input_per_mtok)}
              </td>
              <td className={`${td} whitespace-nowrap text-muted tabular-nums`}>
                {formatUsd(p.output_per_mtok)}
              </td>
            </tr>
          ))}
        </Table>
        <p className="mt-4 text-xs text-subtle">
          Tier prices that map the local models to realistic API costs. Replace them with your
          provider&apos;s prices in downshift.yaml.
        </p>
        <div className="mt-3">
          <Disclaimer />
        </div>
      </Section>
    </>
  );
}
