type Tone = "accent" | "good" | "warn" | "bad" | "violet";

const toneValueClass: Record<Tone, string> = {
  accent: "text-accent",
  good: "text-good",
  warn: "text-warn",
  bad: "text-bad",
  violet: "text-accent-2",
};

interface StatCardProps {
  value: string;
  label: string;
  sub?: string;
  tone?: Tone;
}

export function StatCard({ value, label, sub, tone = "accent" }: StatCardProps) {
  return (
    <div className="border-l border-line pl-5 pr-3">
      <div className={`text-3xl sm:text-4xl font-semibold tracking-tight tabular-nums ${toneValueClass[tone]}`}>
        {value}
      </div>
      <div className="text-sm text-heading mt-2">{label}</div>
      {sub && <div className="text-xs text-subtle mt-1 leading-relaxed">{sub}</div>}
    </div>
  );
}

interface MiniStatProps {
  value: string;
  label: string;
  tone?: Tone;
}

export function MiniStat({ value, label, tone = "accent" }: MiniStatProps) {
  return (
    <div className="border-l border-line pl-4">
      <div className={`text-lg sm:text-xl font-semibold tabular-nums ${toneValueClass[tone]}`}>
        {value}
      </div>
      <div className="text-xs text-subtle mt-0.5">{label}</div>
    </div>
  );
}
