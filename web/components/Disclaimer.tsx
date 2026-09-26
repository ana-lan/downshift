import { summary } from "@/lib/data";

export function Disclaimer() {
  return (
    <p className="flex gap-2 text-xs text-subtle leading-relaxed">
      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
      <span>{summary.disclaimer}</span>
    </p>
  );
}
