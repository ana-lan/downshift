import type { ReactNode } from "react";
import Link from "next/link";

type Variant = "primary" | "secondary";

interface LinkButtonProps {
  href: string;
  variant?: Variant;
  children: ReactNode;
}

const variantClass: Record<Variant, string> = {
  primary: "bg-brand text-white dark:text-slate-950 font-semibold hover:opacity-90",
  secondary: "border border-line text-heading hover:bg-card",
};

export function LinkButton({ href, variant = "primary", children }: LinkButtonProps) {
  const className = `inline-flex items-center rounded-md px-4 py-2 text-sm transition ${variantClass[variant]}`;
  if (href.startsWith("http")) {
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
