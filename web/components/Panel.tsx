import type { ReactNode } from "react";

interface PanelProps {
  children: ReactNode;
  className?: string;
}

export function Panel({ children, className = "" }: PanelProps) {
  return (
    <section className={`border-t border-line first:border-t-0 py-12 sm:py-16 ${className}`}>
      {children}
    </section>
  );
}

interface SectionProps {
  eyebrow: string;
  title: string;
  children: ReactNode;
}

export function Section({ eyebrow, title, children }: SectionProps) {
  return (
    <Panel>
      <div className="flex items-center gap-3 mb-3">
        <span className="h-px w-6 bg-brand" />
        <p className="text-[11px] font-mono uppercase tracking-[0.18em] text-accent-2">
          {eyebrow}
        </p>
      </div>
      <h2 className="text-2xl sm:text-3xl font-semibold tracking-tight text-heading mb-6 sm:mb-8">
        {title}
      </h2>
      {children}
    </Panel>
  );
}
