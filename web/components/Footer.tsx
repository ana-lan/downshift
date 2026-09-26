import { summary } from "@/lib/data";
import { REPO_URL } from "@/lib/content";

const links = [
  { href: REPO_URL, label: "GitHub" },
  { href: "https://pypi.org/project/downshift/", label: "PyPI" },
  { href: "https://www.linkedin.com/in/anagha-langhe/", label: "LinkedIn" },
];

export function Footer() {
  return (
    <footer className="border-t border-line">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 flex flex-col sm:flex-row gap-3 sm:items-center sm:justify-between text-xs text-subtle">
        <p>
          Downshift {summary.tool_version} &middot; MIT &middot; Built by Anagha. Dollar figures are projections.
        </p>
        <div className="flex gap-4">
          {links.map((l) => (
            <a
              key={l.label}
              href={l.href}
              target="_blank"
              rel="noreferrer"
              className="hover:text-heading transition-colors"
            >
              {l.label}
            </a>
          ))}
        </div>
      </div>
    </footer>
  );
}
