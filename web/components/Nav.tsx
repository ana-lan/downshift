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

export function Nav() {
  return (
    <header className="sticky top-0 z-50 border-b border-line bg-bg/80 backdrop-blur">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 h-14 flex items-center gap-4">
        <div className="shrink-0">
          <span className="font-bold text-heading text-sm">Downshift</span>
          <span className="hidden sm:inline text-xs text-subtle ml-2">
            Cut LLM costs per PR
          </span>
        </div>
        <nav className="flex-1 overflow-x-auto">
          <ul className="flex gap-1 min-w-max">
            {navLinks.map((link) => (
              <li key={link.href}>
                <Link
                  href={link.href}
                  className="px-3 py-1.5 rounded-md text-sm text-muted hover:text-heading transition-colors whitespace-nowrap"
                >
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="flex items-center gap-2 shrink-0">
          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-subtle hover:text-heading transition-colors hidden sm:block"
          >
            GitHub
          </a>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
