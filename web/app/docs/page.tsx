import type { ReactNode } from "react";
import { CodeBlock } from "@/components/CodeBlock";
import { ACTION_SNIPPET, DOCS } from "@/lib/content";

const sections = [
  { id: "install", label: "Install" },
  { id: "quickstart", label: "Quickstart" },
  { id: "config", label: "Configuration" },
  { id: "commands", label: "Commands" },
  { id: "action", label: "GitHub Action" },
  { id: "bob", label: "Using Bob" },
  { id: "methodology", label: "Methodology" },
  { id: "limitations", label: "Limitations" },
  { id: "future", label: "Future work" },
];

function DocSection({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-24 border-t border-line pt-8 mt-8 first:border-t-0 first:pt-0 first:mt-0">
      <h2 className="text-xl font-semibold tracking-tight text-heading mb-4">{title}</h2>
      {children}
    </section>
  );
}

function Bullets({ items }: { items: string[] }) {
  return (
    <ul className="space-y-2">
      {items.map((item) => (
        <li key={item} className="text-sm text-muted leading-relaxed border-l border-line pl-3">
          {item}
        </li>
      ))}
    </ul>
  );
}

export default function DocsPage() {
  return (
    <div className="pt-12 sm:pt-16 pb-8">
      <div className="flex items-center gap-3 mb-3">
        <span className="h-px w-6 bg-brand" />
        <p className="text-[11px] font-mono uppercase tracking-[0.18em] text-accent-2">Docs</p>
      </div>
      <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight text-heading">
        Install, configure, run, and wire Downshift into CI
      </h1>

      <div className="mt-10 grid gap-10 lg:grid-cols-[12rem_1fr]">
        <aside className="hidden lg:block">
          <nav className="sticky top-24">
            <p className="text-[11px] font-mono uppercase tracking-wider text-subtle mb-3">
              On this page
            </p>
            <ul className="space-y-2 border-l border-line">
              {sections.map((s) => (
                <li key={s.id}>
                  <a
                    href={`#${s.id}`}
                    className="-ml-px block border-l border-transparent pl-3 text-sm text-muted hover:text-heading hover:border-accent transition-colors"
                  >
                    {s.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
        </aside>

        <div className="min-w-0 max-w-3xl">
          <DocSection id="install" title="Install">
            <CodeBlock code={DOCS.install} />
            <p className="mt-3 text-sm text-muted">Python 3.10 or newer.</p>
          </DocSection>

          <DocSection id="quickstart" title="Quickstart">
            <CodeBlock code={DOCS.quickstart} />
          </DocSection>

          <DocSection id="config" title="Configuration">
            <p className="text-sm text-muted mb-4">
              Put a <code className="font-mono text-accent">downshift.yaml</code> next to the code
              you scan. Every command also takes <code className="font-mono text-accent">-c</code>{" "}
              to point at another file.
            </p>
            <CodeBlock code={DOCS.config} />
          </DocSection>

          <DocSection id="commands" title="Commands">
            <ul className="divide-y divide-line-soft">
              {DOCS.commands.map((cmd) => (
                <li key={cmd.name} className="grid gap-1 py-2.5 sm:grid-cols-[8rem_1fr]">
                  <code className="font-mono text-sm text-accent">{cmd.name}</code>
                  <span className="text-sm text-muted">{cmd.text}</span>
                </li>
              ))}
            </ul>
            <p className="mt-4 text-xs text-subtle">
              Run <code className="font-mono">downshift COMMAND --help</code> for every option.
            </p>
          </DocSection>

          <DocSection id="action" title="GitHub Action">
            <p className="text-sm text-muted mb-4">
              Add this workflow to get a projected cost diff comment on every pull request.
              Remove <code className="font-mono text-accent">fail-above</code> to comment without
              ever failing the check.
            </p>
            <CodeBlock code={ACTION_SNIPPET} label=".github/workflows/cost-diff.yml" />
          </DocSection>

          <DocSection id="bob" title="Using Bob">
            <Bullets items={DOCS.bob} />
          </DocSection>

          <DocSection id="methodology" title="Methodology">
            <Bullets items={DOCS.methodology} />
          </DocSection>

          <DocSection id="limitations" title="Limitations">
            <Bullets items={DOCS.limitations} />
          </DocSection>

          <DocSection id="future" title="Future work">
            <Bullets items={DOCS.future} />
          </DocSection>
        </div>
      </div>
    </div>
  );
}
