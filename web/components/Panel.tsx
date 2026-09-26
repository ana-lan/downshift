import type { ReactNode } from "react";

interface PanelProps {
  children: ReactNode;
  className?: string;
}

export function Panel({ children, className = "" }: PanelProps) {
  return (
    <div
      className={`rounded-2xl border border-line bg-panel px-5 sm:px-10 py-6 sm:py-10 mt-4 sm:mt-6 ${className}`}
    >
      {children}
    </div>
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
      <p className="text-xs font-mono text-accent-2 tracking-wider mb-3 uppercase">
        {eyebrow}
      </p>
      <h2 className="text-xl sm:text-2xl font-semibold text-heading mb-5 sm:mb-6">
        {title}
      </h2>
      {children}
    </Panel>
  );
}
