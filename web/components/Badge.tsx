import type { ReactNode } from "react";

type Tone = "neutral" | "accent" | "good" | "warn" | "bad";

const toneClass: Record<Tone, string> = {
  neutral: "border-line text-muted",
  accent: "border-accent-line bg-accent-bg text-accent-fg",
  good: "border-good/30 bg-good/10 text-good",
  warn: "border-warn/30 bg-warn/10 text-warn",
  bad: "border-bad/30 bg-bad/10 text-bad",
};

interface BadgeProps {
  tone?: Tone;
  children: ReactNode;
}

export function Badge({ tone = "neutral", children }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-md border px-1.5 py-0.5 text-[11px] font-mono ${toneClass[tone]}`}
    >
      {children}
    </span>
  );
}

export function DecisionBadge({ action }: { action: "keep" | "downgrade" }) {
  return (
    <Badge tone={action === "downgrade" ? "good" : "warn"}>
      {action === "downgrade" ? "downgrade" : "keep"}
    </Badge>
  );
}

export function FoundByBadge({ foundBy }: { foundBy: string }) {
  return (
    <Badge tone={foundBy === "bob" ? "accent" : "neutral"}>
      {foundBy === "bob" ? "found by Bob" : "found by ast"}
    </Badge>
  );
}

export function PassBadge({ passed }: { passed: boolean | null }) {
  if (passed === null) return <Badge tone="neutral">n/a</Badge>;
  return <Badge tone={passed ? "good" : "bad"}>{passed ? "pass" : "fail"}</Badge>;
}
