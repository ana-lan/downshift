import { Section } from "@/components/Panel";
import { Table } from "@/components/Table";
import { CASE_STUDIES, type CaseStudy } from "@/lib/content";

const td = "px-3 py-3 border-b border-line-soft whitespace-nowrap";
const link = "text-accent hover:underline underline-offset-4";
const usd = (n: number) => n.toLocaleString("en-US", { style: "currency", currency: "USD" });

export default function CaseStudyPage() {
  return (
    <>
      <Section eyebrow="Case studies" title="Two real repos Downshift had never seen">
        <p className="text-muted text-sm leading-relaxed max-w-2xl">
          Static analysis finds where LLM calls live. Bob finds what they are and what they cost.
          Both repos are public, permissively licensed and pinned to a commit.
        </p>
        <div className="mt-6 grid gap-6 md:grid-cols-2">
          {CASE_STUDIES.map((cs) => (
            <a key={cs.slug} href={`#${cs.slug}`} className="group block border-l-2 border-accent-2 pl-4 py-1">
              <p className="text-[11px] font-mono uppercase tracking-wider text-subtle">{cs.repo}</p>
              <p className="mt-1 text-heading font-semibold group-hover:underline underline-offset-4">
                {cs.headline}
              </p>
              <p className="mt-1 text-sm text-muted">
                {usd(cs.staticMonthly)} → {usd(cs.bobMonthly)} a month, once Bob fills the gaps
              </p>
            </a>
          ))}
        </div>
      </Section>

      {CASE_STUDIES.map((cs) => (
        <Study key={cs.slug} cs={cs} />
      ))}
    </>
  );
}

function Study({ cs }: { cs: CaseStudy }) {
  return (
    <div id={cs.slug} className="scroll-mt-20">
      <Section eyebrow={`Case study · ${cs.name}`} title={cs.title}>
        <div className="grid gap-8 lg:grid-cols-[1fr_1.2fr]">
          <div className="space-y-3">
            {cs.intro.map((p, i) => (
              <p key={i} className="text-muted text-sm leading-relaxed">
                {p}
              </p>
            ))}
            <dl className="grid grid-cols-[6.5rem_1fr] gap-x-4 gap-y-1.5 pt-2 text-sm">
              <dt className="text-subtle">Repository</dt>
              <dd>
                <a href={cs.repoUrl} className={link} target="_blank" rel="noreferrer">
                  {cs.repo}
                </a>
              </dd>
              <dt className="text-subtle">License</dt>
              <dd className="text-muted">{cs.license}</dd>
              <dt className="text-subtle">Commit</dt>
              <dd>
                <a href={`${cs.repoUrl}/tree/${cs.commit}`} className={`${link} font-mono`} target="_blank" rel="noreferrer">
                  {cs.commit.slice(0, 7)}
                </a>
              </dd>
              <dt className="text-subtle">Scope</dt>
              <dd className="text-muted">{cs.scope}</dd>
              <dt className="text-subtle">Audited</dt>
              <dd className="text-muted">{cs.audited}</dd>
            </dl>
          </div>
          <Table headers={["Metric", "ast scan", "Bob audit"]}>
            {cs.metrics.map((m) => (
              <tr key={m.label}>
                <td className={`${td} text-heading`}>{m.label}</td>
                <td className={`${td} text-muted`}>{m.ast}</td>
                <td className={`${td} ${m.bob > m.ast ? "text-accent-2" : "text-muted"}`}>{m.bob}</td>
              </tr>
            ))}
          </Table>
        </div>
      </Section>

      <Section eyebrow={`${cs.name} · Bob audit`} title={`What Bob found, for ${cs.coins} Bobcoins`}>
        <ul className="divide-y divide-line-soft">
          {cs.bobFound.map((item, i) => (
            <li key={i} className="border-l-2 border-accent-2 pl-3 py-3 text-sm text-muted leading-relaxed">
              {item}
            </li>
          ))}
        </ul>
      </Section>

      <Section eyebrow={`${cs.name} · Cost projection`} title="The bill static analysis cannot see">
        <div className="grid gap-6 sm:grid-cols-2 mb-8">
          <div className="border-l border-line pl-4">
            <p className="text-[11px] font-mono uppercase tracking-wider text-subtle">Static-only view</p>
            <p className="mt-1 text-3xl font-semibold text-muted">
              {usd(cs.staticMonthly)}
              <span className="text-sm font-normal text-subtle"> / month</span>
            </p>
            <p className="mt-1 text-xs text-subtle">{cs.staticNote}</p>
          </div>
          <div className="border-l-2 border-accent-2 pl-4">
            <p className="text-[11px] font-mono uppercase tracking-wider text-subtle">With the Bob audit</p>
            <p className="mt-1 text-3xl font-semibold text-heading">
              {usd(cs.bobMonthly)}
              <span className="text-sm font-normal text-subtle"> / month</span>
            </p>
            <p className="mt-1 text-xs text-subtle">{cs.bobNote}</p>
          </div>
        </div>
        <Table headers={["Feature", "Model", "Calls/day", "Monthly"]}>
          {cs.features.map((f) => (
            <tr key={f.name}>
              <td className={`${td} font-mono text-heading`}>{f.name}</td>
              <td className={`${td} font-mono text-muted`}>{f.model}</td>
              <td className={`${td} text-muted`}>{f.calls.toLocaleString("en-US")}</td>
              <td className={`${td} text-muted`}>{usd(f.monthly)}</td>
            </tr>
          ))}
          <tr>
            <td className={`${td} text-heading font-semibold`}>Total</td>
            <td className={td} />
            <td className={td} />
            <td className={`${td} text-heading font-semibold`}>{usd(cs.bobMonthly)}</td>
          </tr>
        </Table>
        <pre className="mt-6 overflow-x-auto rounded-lg border border-line bg-card p-4 font-mono text-xs text-muted">
          {cs.command}
        </pre>
      </Section>

      <Section eyebrow={`${cs.name} · Findings`} title="What this shows">
        <ol className="space-y-4">
          {cs.findings.map((f, i) => (
            <li key={i} className="grid grid-cols-[2rem_1fr] text-sm leading-relaxed">
              <span className="font-mono text-accent">{String(i + 1).padStart(2, "0")}</span>
              <span className="text-muted">{f}</span>
            </li>
          ))}
        </ol>
      </Section>

      <Section eyebrow={`${cs.name} · Limitations`} title="Assumptions, stated plainly">
        <ul className="space-y-2 text-sm text-muted leading-relaxed list-disc pl-5">
          {cs.limitations.map((l, i) => (
            <li key={i}>{l}</li>
          ))}
        </ul>
        <p className="mt-6 text-sm">
          <a href={cs.docUrl} className={link} target="_blank" rel="noreferrer">
            Full write-up, scan, audit and config on GitHub
          </a>
        </p>
      </Section>
    </div>
  );
}
