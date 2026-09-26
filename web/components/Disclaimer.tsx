import { summary } from "@/lib/data";

export function Disclaimer() {
  return (
    <div className="rounded-xl border border-warn/30 bg-warn/10 px-4 py-3 text-xs sm:text-sm text-warn">
      {summary.disclaimer}
    </div>
  );
}
