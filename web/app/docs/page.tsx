import { Panel } from "@/components/Panel";
import { CodeBlock } from "@/components/CodeBlock";
import { DOCS } from "@/lib/content";

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

export default function DocsPage() {
  return (
    <Panel>
      <h1 className="text-2xl sm:text-3xl font-bold text-heading mb-2">Docs</h1>
      <p className="text-muted text-sm mb-6">
        Install, configure, run, and wire Downshift into CI.
      </p>

      {/* TOC */}
      <nav className="mb-8 rounded-xl border border-line bg-card px-4 py-3">
        <p className="text-xs font-mono text-subtle uppercase mb-2">Contents</p>
        <ul className="space-y-1">
          {sections.map((s) => (
            <li key={s.id}>
              <a href={`#${s.id}`} className="text-sm text-accent hover:underline">
                {s.label}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      {/* Install */}
      <section id="install">
        <h2 className="text-lg font-semibold text-heading mt-10 mb-3">Install</h2>
        <CodeBlock code={DOCS.install} />
      </section>

      {/* Quickstart */}
      <section id="quickstart">
        <h2 className="text-lg font-semibold text-heading mt-10 mb-3">Quickstart</h2>
        <CodeBlock code={DOCS.quickstart} />
      </section>

      {/* Configuration */}
      <section id="config">
        <h2 className="text-lg font-semibold text-heading mt-10 mb-3">Configuration</h2>
        <p className="text-muted text-sm mb-3">
          Place a <code className="font-mono text-xs">downshift.yaml</code> next to the code you scan.
        </p>
        <CodeBlock code={DOCS.config} />
      </section>

      {/* Commands */}
      <section id="commands">
        <h2 className="text-lg font-semibold text-heading mt-10 mb-3">Commands</h2>
        <ul className="space-y-2">
          {DOCS.commands.map((cmd) => (
            <li key={cmd.name} className="flex gap-3 text-sm">
              <code className="font-mono text-accent-fg bg-accent-bg border border-accent-line rounded px-2 py-0.5 text-xs shrink-0">
                {cmd.name}
              </code>
              <span className="text-muted">{cmd.text}</span>
            </li>
          ))}
        </ul>
      </section>

      {/* GitHub Action */}
      <section id="action">
        <h2 className="text-lg font-semibold text-heading mt-10 mb-3">GitHub Action</h2>
        <p className="text-muted text-sm mb-3">
          Add to your repo to get a cost diff comment on every pull request.
        </p>
        <CodeBlock code={`- uses: ana-lan/downshift@v0.1.0\n  with:\n    path: .\n    fail-above: "500"\n    github-token: \${{ secrets.GITHUB_TOKEN }}`} />
      </section>

      {/* Using Bob */}
      <section id="bob">
        <h2 className="text-lg font-semibold text-heading mt-10 mb-3">Using Bob</h2>
        <ul className="space-y-2">
          {DOCS.bob.map((item, i) => (
            <li key={i} className="flex gap-2 text-sm text-muted">
              <span className="text-accent shrink-0">&bull;</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </section>

      {/* Methodology */}
      <section id="methodology">
        <h2 className="text-lg font-semibold text-heading mt-10 mb-3">Methodology</h2>
        <ul className="space-y-2">
          {DOCS.methodology.map((item, i) => (
            <li key={i} className="flex gap-2 text-sm text-muted">
              <span className="text-accent shrink-0">&bull;</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </section>

      {/* Limitations */}
      <section id="limitations">
        <h2 className="text-lg font-semibold text-heading mt-10 mb-3">Limitations</h2>
        <ul className="space-y-2">
          {DOCS.limitations.map((item, i) => (
            <li key={i} className="flex gap-2 text-sm text-muted">
              <span className="text-accent shrink-0">&bull;</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </section>

      {/* Future work */}
      <section id="future">
        <h2 className="text-lg font-semibold text-heading mt-10 mb-3">Future work</h2>
        <ul className="space-y-2">
          {DOCS.future.map((item, i) => (
            <li key={i} className="flex gap-2 text-sm text-muted">
              <span className="text-accent shrink-0">&bull;</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </section>
    </Panel>
  );
}
