import Link from "next/link";
import { Panel } from "@/components/Panel";

export default function NotFound() {
  return (
    <Panel>
      <h1 className="text-2xl font-bold text-heading mb-3">Page not found</h1>
      <p className="text-muted text-sm mb-4">The page you are looking for does not exist.</p>
      <Link href="/" className="text-accent hover:underline text-sm">
        Back to Overview
      </Link>
    </Panel>
  );
}
