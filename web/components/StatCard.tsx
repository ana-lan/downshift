type Tone = "accent" | "good" | "warn" | "bad";

interface StatCardProps {
  value: string;
  label: string;
  sub?: string;
  tone?: Tone;
}

const toneValueClass: Record<Tone, string> = {
  accent: "text-accent",
  good: "text-good",
  warn: "text-warn",
  bad: "text-bad",
};

export function StatCard({ value, label, sub, tone = "accent" }: StatCardProps) {
  return (
    <div className="rounded-xl border border-line bg-card px-4 sm:px-5 py-4 sm:py-5">
      <div className={`text-2xl sm:text-3xl font-bold ${toneValueClass[tone]}`}>
        {value}
      </div>
      <div className="text-sm text-heading font-medium mt-1">{label}</div>
      {sub && <div className="text-xs text-subtle mt-0.5">{sub}</div>}
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
    <div className="rounded-xl border border-line bg-card px-4 py-3">
      <div className={`text-lg sm:text-xl font-bold ${toneValueClass[tone]}`}>
        {value}
      </div>
      <div className="text-xs text-subtle mt-0.5">{label}</div>
    </div>
  );
}
