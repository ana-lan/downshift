import Link from "next/link";
import { ThemeToggle } from "@/components/ThemeToggle";
import { REPO_URL } from "@/lib/content";

const navLinks = [
  { href: "/", label: "Overview" },
  { href: "/callsites/", label: "Call sites" },
  { href: "/audit/", label: "Bob audit" },
  { href: "/how-it-works/", label: "How it works" },
  { href: "/docs/", label: "Docs" },
];

function Mark() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true">
      <defs>
        <linearGradient id="ds-mark" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="var(--cyan)" />
          <stop offset="0.55" stopColor="var(--blue)" />
          <stop offset="1" stopColor="var(--violet)" />
        </linearGradient>
      </defs>
      <rect x="3" y="4" width="4" height="16" rx="1.5" fill="url(#ds-mark)" />
      <rect x="10" y="9" width="4" height="11" rx="1.5" fill="url(#ds-mark)" />
      <rect x="17" y="14" width="4" height="6" rx="1.5" fill="url(#ds-mark)" />
    </svg>
  );
}

export function Nav() {
  return (
    <header className="sticky top-0 z-50 bg-bg/85 backdrop-blur">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center gap-6">
        <Link href="/" className="flex items-center gap-2 shrink-0">
          <Mark />
          <span className="font-semibold tracking-tight text-heading">Downshift</span>
        </Link>
        <nav className="flex-1 overflow-x-auto">
          <ul className="flex gap-5 min-w-max">
            {navLinks.map((link) => (
              <li key={link.href}>
                <Link
                  href={link.href}
                  className="text-sm text-muted hover:text-heading transition-colors whitespace-nowrap"
                >
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="flex items-center gap-3 shrink-0">
          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer"
            className="hidden sm:block text-sm text-muted hover:text-heading transition-colors"
          >
            GitHub
          </a>
          <ThemeToggle />
        </div>
      </div>
      <div className="h-px bg-brand opacity-50" />
    </header>
  );
}
