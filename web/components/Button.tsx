import type { ReactNode } from "react";
import Link from "next/link";

type Variant = "primary" | "secondary";

interface LinkButtonProps {
  href: string;
  variant?: Variant;
  children: ReactNode;
}

export function LinkButton({ href, variant = "primary", children }: LinkButtonProps) {
  const isExternal = href.startsWith("http");
  const className =
    variant === "primary"
      ? "inline-flex items-center px-4 py-2.5 rounded-lg bg-accent-bg border border-accent-line text-accent-fg text-sm font-medium hover:opacity-90 transition-opacity"
      : "inline-flex items-center px-4 py-2.5 rounded-lg border border-line text-text text-sm font-medium hover:border-subtle transition-colors";

  if (isExternal) {
    return (
      <a href={href} target="_blank" rel="noreferrer" className={className}>
        {children}
      </a>
    );
  }

  return (
    <Link href={href} className={className}>
      {children}
    </Link>
  );
}
