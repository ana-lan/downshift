import { summary } from "@/lib/data";

export function Footer() {
  return (
    <footer className="text-center text-xs text-subtle py-8">
      Open source &middot; MIT &middot; Downshift {summary.tool_version} &middot; Numbers are measured on local Qwen models. Dollar figures are projections.
    </footer>
  );
}
