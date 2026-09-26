import type { ReactNode } from "react";

type Tone = "neutral" | "accent" | "good" | "warn" | "bad";

interface BadgeProps {
  tone?: Tone;
  children: ReactNode;
}

const toneClass: Record<Tone, string> = {
  neutral: "border-line text-muted",
  accent: "border-accent-line bg-accent-bg text-accent-fg",
  good: "text-good bg-good/10 border-good/30",
  warn: "text-warn bg-warn/10 border-warn/30",
  bad: "text-bad bg-bad/10 border-bad/30",
};

export function Badge({ tone = "neutral", children }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center text-xs px-2 py-0.5 rounded-full border font-mono ${toneClass[tone]}`}
    >
      {children}
    </span>
  );
}

export function DecisionBadge({ action }: { action: "keep" | "downgrade" }) {
  return (
    <Badge tone={action === "downgrade" ? "good" : "warn"}>
      {action === "downgrade" ? "DOWNGRADE" : "KEEP"}
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
  return <Badge tone={passed ? "good" : "bad"}>{passed ? "PASS" : "FAIL"}</Badge>;
}
