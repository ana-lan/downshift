# Downshift demo web app: build spec

Static demo site for Downshift ("Cut LLM costs per PR"). It reads the JSON that
`downshift export examples/supportdesk --out web/public/data` produces and renders
it. No backend, no API routes, no secrets, no runtime fetching.

Visual reference: https://activation-lens.vercel.app (same author). Reuse its
layout language: bordered rounded panels on a near-black violet background,
violet/indigo accents, mono eyebrows, stat cards, mono result tables.

## 1. Rules

- Only create files under `web/`. Do not touch anything outside `web/`.
- Do not create `package-lock.json` and do not run npm, npx, node or any command.
- Copy rule: never use em-dashes (the long dash character) in any text. Use commas,
  colons or periods.
- Every dollar figure on the site is a projection. Wherever cost numbers appear
  on a page, render the `<Disclaimer />` component somewhere on that page.
- TypeScript strict, no `any`. Server components by default. Only `ThemeToggle`
  is a client component (`"use client"`).
- Tailwind only for styling (no CSS modules, no UI libraries, no icon libraries;
  inline SVG for the two theme icons).
- Keep every file under 300 lines; split components when needed.

## 2. Stack and config files

Next.js 15 (App Router) + React 19 + TypeScript + Tailwind CSS v4, static export,
deployed on Vercel with root directory `web/`.

### web/package.json
```json
{
  "name": "downshift-web",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "npx serve out",
    "lint": "eslint .",
    "typecheck": "tsc --noEmit",
    "test": "vitest run"
  },
  "dependencies": {
    "next": "^15.5.0",
    "react": "^19.1.0",
    "react-dom": "^19.1.0"
  },
  "devDependencies": {
    "@eslint/eslintrc": "^3",
    "@tailwindcss/postcss": "^4",
    "@types/node": "^22",
    "@types/react": "^19",
    "@types/react-dom": "^19",
    "eslint": "^9",
    "eslint-config-next": "^15.5.0",
    "tailwindcss": "^4",
    "typescript": "^5",
    "vitest": "^3"
  }
}
```

### web/next.config.ts
```ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
```

### web/tsconfig.json
Standard create-next-app config: `target` ES2017, `lib` ["dom", "dom.iterable",
"esnext"], `strict: true`, `noEmit: true`, `module` esnext, `moduleResolution`
bundler, `resolveJsonModule: true`, `isolatedModules: true`, `jsx` preserve,
`incremental: true`, `plugins: [{ "name": "next" }]`, `paths: { "@/*": ["./*"] }`,
include `["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"]`,
exclude `["node_modules"]`.

### web/next-env.d.ts
```ts
/// <reference types="next" />
/// <reference types="next/image-types/global" />
```

### web/postcss.config.mjs
```js
const config = { plugins: { "@tailwindcss/postcss": {} } };
export default config;
```

### web/eslint.config.mjs
```js
import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";

const __dirname = dirname(fileURLToPath(import.meta.url));
const compat = new FlatCompat({ baseDirectory: __dirname });

const eslintConfig = [
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  { ignores: ["node_modules/**", ".next/**", "out/**", "next-env.d.ts"] },
];

export default eslintConfig;
```

### web/.gitignore
```
node_modules/
.next/
out/
*.tsbuildinfo
.vercel
```

## 3. Theme (dark by default, light toggle)

`web/app/globals.css`:
```css
@import "tailwindcss";

@custom-variant dark (&:where(.dark, .dark *));

:root {
  --bg: #faf9fc;
  --panel: #ffffff;
  --card: #f5f3fa;
  --line: #e5e3ec;
  --line-soft: #efedf4;
  --text: #3f3f46;
  --heading: #0a0810;
  --muted: #52525b;
  --subtle: #71717a;
  --accent: #7c3aed;
  --accent-2: #4f46e5;
  --accent-bg: #f5f3ff;
  --accent-line: #c4b5fd;
  --accent-fg: #6d28d9;
  --good: #059669;
  --bad: #e11d48;
  --warn: #d97706;
}

.dark {
  --bg: #0a0810;
  --panel: #100c1a;
  --card: #0c0916;
  --line: #262626;
  --line-soft: #171717;
  --text: #d4d4d4;
  --heading: #ffffff;
  --muted: #a3a3a3;
  --subtle: #737373;
  --accent: #a78bfa;
  --accent-2: #818cf8;
  --accent-bg: #2e1065;
  --accent-line: #5b21b6;
  --accent-fg: #c4b5fd;
  --good: #34d399;
  --bad: #fb7185;
  --warn: #fbbf24;
}

@theme inline {
  --color-bg: var(--bg);
  --color-panel: var(--panel);
  --color-card: var(--card);
  --color-line: var(--line);
  --color-line-soft: var(--line-soft);
  --color-text: var(--text);
  --color-heading: var(--heading);
  --color-muted: var(--muted);
  --color-subtle: var(--subtle);
  --color-accent: var(--accent);
  --color-accent-2: var(--accent-2);
  --color-accent-bg: var(--accent-bg);
  --color-accent-line: var(--accent-line);
  --color-accent-fg: var(--accent-fg);
  --color-good: var(--good);
  --color-bad: var(--bad);
  --color-warn: var(--warn);
  --font-sans: var(--font-geist-sans);
  --font-mono: var(--font-geist-mono);
}

body {
  background: var(--bg);
  color: var(--text);
}
```
Use only these token classes for colors (`bg-panel`, `bg-card`, `border-line`,
`text-heading`, `text-muted`, `text-subtle`, `text-accent`, `text-accent-2`,
`bg-accent-bg`, `border-accent-line`, `text-accent-fg`, `text-good`, `bg-good/10`,
`text-bad`, `bg-bad/10`, `text-warn`, `bg-warn/10`, ...). No raw hex in components.

`web/app/layout.tsx`:
- Fonts: `Geist` and `Geist_Mono` from `next/font/google`, variables
  `--font-geist-sans` and `--font-geist-mono`, applied on `<body>` with `font-sans
  antialiased`.
- `<html lang="en" className="dark" suppressHydrationWarning>`: dark is the default.
- In `<head>`, an inline script (via `<script dangerouslySetInnerHTML>`) that runs
  before paint: if `localStorage.getItem("theme") === "light"`, remove the `dark`
  class from `document.documentElement`. Wrap in try/catch.
- Body: `<Nav />`, then `<main className="max-w-5xl mx-auto px-4 sm:px-6 pt-4
  sm:pt-6 pb-10">{children}</main>`, then `<Footer />`.
- Metadata: title `Downshift · Cut LLM costs per PR`, description `Find every LLM
  call in your repo, prove which ones can use cheaper models, and show the cost
  impact of every PR.`, openGraph title/description the same.

`web/components/ThemeToggle.tsx` (client): a small outline button (sun icon when
dark, moon icon when light). On click toggle the `dark` class on
`document.documentElement` and save `"dark"` or `"light"` to
`localStorage("theme")`. Read the initial state from the class in a `useEffect`
to avoid hydration mismatch. `aria-label="Toggle theme"`.

## 4. Data layer

JSON files live in `web/public/data/` (committed; do not edit them): `summary.json`,
`callsites.json`, `audit.json`, `evals_summary.json`, `report.md`. Import the JSON
statically at build time.

### web/lib/types.ts (exact shapes)
```ts
export interface Downgrade { site_id: string; from: string; to: string }
export interface Pricing {
  model: string;
  input_per_mtok: number | null;
  output_per_mtok: number | null;
  tier: string | null;
}
export interface Summary {
  project: string;
  tool_version: string;
  baseline: string;
  candidates: string[];
  judge_models: string[];
  threshold: number;
  min_pass_rate: number;
  calls_per_day: number;
  days_per_month: number;
  sites_total: number;
  sites_downgraded: number;
  downgrades: Downgrade[];
  missing_evals: string[];
  cost: {
    before_monthly: number | null;
    after_monthly: number | null;
    savings: number | null;
    savings_pct: number | null;
  };
  quality: {
    baseline_pass_rate: number | null;
    after_pass_rate: number | null;
    delta: number | null;
  };
  pricing: Pricing[];
  disclaimer: string;
}
export interface PromptMessage { role: string; content: string; resolved: boolean }
export interface Decision {
  action: "keep" | "downgrade";
  model: string;
  baseline: string;
  reason: string;
  baseline_pass_rate: number | null;
  baseline_below_floor: boolean;
}
export interface ModelCheck { ratio: number | null; passed: boolean; reason: string }
export interface ModelStats {
  model: string;
  tier: string | null;
  is_baseline: boolean;
  chosen: boolean;
  cases: number | null;
  scored: number | null;
  passed: number | null;
  errors: number | null;
  pass_rate: number | null;
  mean_score: number | null;
  avg_judge_score: number | null;
  avg_prompt_tokens: number | null;
  avg_completion_tokens: number | null;
  avg_latency_s: number | null;
  cost_per_call: number | null;
  check: ModelCheck | null;
}
export interface SiteCost {
  before_model: string;
  after_model: string;
  calls_per_day: number;
  before_monthly: number | null;
  after_monthly: number | null;
  savings: number | null;
  savings_pct: number | null;
}
export interface CallSite {
  id: string;            // "supportdesk/triage.py::detect_sentiment"
  slug: string;          // "supportdesk.triage__detect_sentiment" (URL segment)
  file: string;
  line: number;
  function: string;
  api: string;
  is_async: boolean;
  found_by: string;      // "ast" | "bob"
  via: string | null;    // helper the call goes through, e.g. "supportdesk/llm.py::ask"
  purpose: string | null;
  output_contract: unknown;
  difficulty: string | null;
  grading: string | null; // "exact" | "json_fields" | "judge"
  output_format: string | null;
  temperature: number | null;
  max_tokens: number | null;
  model_in_code: string | null;
  messages: PromptMessage[] | null;
  eval_cases: number;
  decision: Decision | null;
  models: ModelStats[];   // order: baseline, then candidates
  cost: SiteCost | null;
}
export interface MetricMap { [key: string]: number }
export interface Change { id: string; kind: string; detail: string }
export interface SiteBrief {
  id: string;
  found_by: string;
  via: string | null;
  model: string | null;
  model_source: string | null;
  prompt_resolved: boolean;
}
export interface AuditData {
  labels: { [key: string]: string };
  ast: MetricMap | null;
  audit: MetricMap;
  ast_after: MetricMap | null;
  changes: Change[];
  ast_sites: SiteBrief[];
  audit_sites: SiteBrief[];
}
export interface ModelOutput {
  output: string;
  passed: boolean | null;
  score: number | null;
  judge_score: number | null;
  detail: string;
  error: string | null;
}
export interface EvalExample {
  id: string;
  inputs: { [key: string]: unknown };
  expected: unknown;
  notes: string | null;
  outputs: { [model: string]: ModelOutput | null };
}
export interface EvalGridRow { id: string; passed: { [model: string]: boolean | null } }
export interface SiteEvals {
  site_id: string;
  slug: string;
  grading: string | null;
  cases: number;
  models: string[];
  examples: EvalExample[];
  grid: EvalGridRow[];
}
```

### web/lib/data.ts
```ts
import summaryJson from "@/public/data/summary.json";
import callsitesJson from "@/public/data/callsites.json";
import auditJson from "@/public/data/audit.json";
import evalsJson from "@/public/data/evals_summary.json";
```
Cast each with `as unknown as <Type>` and export: `summary: Summary`,
`callsites: CallSite[]`, `audit: AuditData`, `evals: SiteEvals[]`, plus:
- `getCallsite(slug: string): CallSite | undefined`
- `getSiteEvals(slug: string): SiteEvals | undefined`
- `allSlugs(): string[]`
- `totalEvalCases(): number` (sum of `evals[].cases`)
Keep pure lookup helpers that take arrays as parameters in `lib/select.ts` so they
can be unit tested without the JSON: `findBySlug<T extends { slug: string }>(items, slug)`,
`sumCases(evals)`, `modelStats(site, model)`, `chosenStats(site)`,
`baselineStats(site)`, `sortBySavings(sites)` (descending, nulls last),
`auditRows(audit)` returning `{ key, label, ast, audit, astAfter }[]` in the order
of `audit.labels` keys (values `number | null`).

### web/lib/format.ts (pure, no React)
- `formatUsd(n: number | null): string` gives `$3,137.26`, null gives `n/a`.
- `formatUsdPerCall(n: number | null): string` gives `$0.000412` (6 decimals, n/a for null).
- `formatPct(rate: number | null, digits = 1): string` with 0.18 giving `18.0%`.
- `formatPts(delta: number | null): string` with 0.006 giving `+0.6 pts`, -0.02 giving `-2.0 pts`.
- `formatNumber(n: number | null, digits = 0): string` with thousands separators.
- `formatSeconds(s: number | null): string` gives `1.23 s`.
- `siteName(id: string): string` gives the part after `::`.
- `siteFile(id: string): string` gives the part before `::`.
- `formatValue(v: unknown): string` returns strings as is, anything else as
  `JSON.stringify(v, null, 2)`, null/undefined as `n/a`.

### web/lib/content.ts
Static copy used by the pages (section 7 and the docs page). Code snippets are
plain strings. IMPORTANT: GitHub expressions like `${{ secrets.GITHUB_TOKEN }}`
must be written as `\${{ secrets.GITHUB_TOKEN }}` inside template literals.

## 5. Components (web/components/)

Match these class recipes (tokens from section 3).
- `Nav.tsx`: sticky top bar `border-b border-line bg-bg/80 backdrop-blur`. Left:
  "Downshift" (bold, text-heading) with subtitle "Cut LLM costs per PR" (text-xs
  text-subtle). Links: Overview `/`, Call sites `/callsites/`, Bob audit `/audit/`,
  How it works `/how-it-works/`, Docs `/docs/`. Right: GitHub link
  (https://github.com/ana-lan/downshift) and `<ThemeToggle />`. On mobile the link
  row scrolls horizontally (`overflow-x-auto`).
- `Panel.tsx`: `rounded-2xl border border-line bg-panel px-5 sm:px-10 py-6 sm:py-10
  mt-4 sm:mt-6`. Also export `Section({ eyebrow, title, children })`: a Panel with
  eyebrow `text-xs font-mono text-accent-2 tracking-wider mb-3` (uppercase text,
  e.g. `RESULTS · SUPPORTDESK`) and title `text-xl sm:text-2xl font-semibold
  text-heading mb-5 sm:mb-6`.
- `StatCard.tsx`: `StatCard({ value, label, sub, tone })`: `rounded-xl border
  border-line bg-card px-4 sm:px-5 py-4 sm:py-5`, value `text-2xl sm:text-3xl
  font-bold` (tone: accent default, good, warn, bad), label `text-sm text-heading
  font-medium`, sub `text-xs text-subtle`. `MiniStat({ value, label, tone })`
  smaller (value `text-lg sm:text-xl`).
- `Badge.tsx`: `Badge({ tone, children })` pill `text-xs px-2 py-0.5 rounded-full
  border font-mono`; tones: neutral (border-line text-muted), accent
  (border-accent-line bg-accent-bg text-accent-fg), good (text-good bg-good/10
  border-good/30), warn, bad. Helpers: `DecisionBadge({ action })` (downgrade =
  good "DOWNGRADE", keep = warn "KEEP"), `FoundByBadge({ foundBy })` (bob = accent
  "found by Bob", ast = neutral "found by ast"), `PassBadge({ passed })` (true =
  good "PASS", false = bad "FAIL", null = neutral "n/a").
- `Table.tsx`: wrapper `rounded-xl border border-line overflow-x-auto`, table
  `w-full text-xs sm:text-sm font-mono`, header row `bg-card`, th `text-left px-3
  sm:px-4 py-2 text-subtle font-normal text-xs border-b border-line
  whitespace-nowrap`, td `px-3 sm:px-4 py-2 border-b border-line-soft
  whitespace-nowrap`, first column `text-heading`, others `text-muted`. Export
  generic `Table({ headers, children, minWidth })` taking `<tr>` children.
- `CodeBlock.tsx`: `CodeBlock({ code, label })`: `rounded-xl border border-line
  bg-card p-4 overflow-x-auto text-xs font-mono text-muted whitespace-pre`,
  optional label above in mono `text-subtle`.
- `Disclaimer.tsx`: warn-toned box `rounded-xl border border-warn/30 bg-warn/10
  px-4 py-3 text-xs sm:text-sm text-warn` with the text from
  `summary.disclaimer`.
- `Footer.tsx`: centered `text-xs text-subtle py-8`: "Open source · MIT ·
  Downshift {summary.tool_version} · Numbers are measured on local Qwen models.
  Dollar figures are projections."
- `Button.tsx`: `LinkButton({ href, variant, children })`: primary `px-4 py-2.5
  rounded-lg bg-accent-bg border border-accent-line text-accent-fg text-sm
  font-medium`, secondary `px-4 py-2.5 rounded-lg border border-line text-text
  text-sm font-medium hover:border-subtle`. External links (http) open in a new
  tab with `rel="noreferrer"`.
- `ThemeToggle.tsx` (section 3).

## 6. Pages

All pages are static. Links use `next/link` with trailing slashes.

### / (web/app/page.tsx): Overview
1. Hero panel (Panel):
   - pill: `Open source · pip install downshift` with a small accent dot.
   - H1 (`text-3xl sm:text-4xl md:text-5xl font-bold`): "Which " + "LLM calls"
     (text-accent-2) + " are you " + "overpaying" (text-accent) + " for?"
     (rest text-heading).
   - paragraph (text-muted): "Downshift finds every LLM call site in a Python repo,
     writes evals for each one, tests cheaper models against the one you use today,
     and shows the cost impact of every pull request. Downshift is the toolkit,
     IBM Bob is the brain."
   - buttons: "Read the docs" (primary, /docs/), "View on GitHub ↗" (secondary).
   - 4 StatCards (grid 1 / 2 / 4 cols):
     - `formatUsd(cost.savings) + "/mo"` label "Projected savings", sub
       "{formatPct(savings_pct)} of {formatUsd(before_monthly)} per month", tone good.
     - "{sites_downgraded} of {sites_total}" label "Call sites downgraded", sub
       "each one passed its evals at >= {formatPct(threshold, 0)} of baseline quality".
     - "{formatPct(baseline_pass_rate)} → {formatPct(after_pass_rate)}" label
       "Mean eval pass rate", sub "{formatPts(delta)} after downgrading".
     - `totalEvalCases()` label "Eval cases", sub "graded by {judge_models[0]}".
   - `<Disclaimer />` below the cards.
2. Section eyebrow `RESULTS · {project uppercase}`, title "Three of eight call sites
   can run on a smaller model" (build the numbers from summary, write numbers 1-10
   as words). MiniStats: before/month, after/month, savings/month. Table of all
   call sites (sorted by savings desc): Call site (siteName, links to detail) |
   Decision (DecisionBadge) | Model (baseline → chosen, or baseline if keep) |
   Baseline pass | Chosen pass | Savings/mo. Then the notes from `content.ts`
   `RESULT_NOTES` as a small bulleted list (text-subtle).
3. Section `STATIC ANALYSIS VS BOB`, title "Config-driven code blinds static
   analysis". Short paragraph from content. Table from `auditRows(audit)`: Metric |
   ast scan | Bob audit | ast after refactor. Link "See the full audit →" to /audit/.
4. Section `CI GUARDRAIL`, title "Every PR gets a cost diff". Content from
   `CI_DEMO` (3 MiniStats: "+$6,204.00/mo" warn, "+84.5%" warn, "$7,339.50 →
   $13,543.50"), paragraph, and CodeBlock with the Action usage snippet.
5. Section `ARCHITECTURE & STACK`, title "How the pieces fit": CodeBlock with the
   ASCII pipeline from content, then stack chips (`text-xs px-2.5 py-1 rounded-md
   border border-line text-muted font-mono`): Python, Typer, Ollama, Qwen 2.5,
   IBM Bob, GitHub Actions, PyPI, Next.js 15, TypeScript, Tailwind.
6. Closing Panel, centered: h2 "Cut your LLM bill one PR at a time", text
   "Downshift is open source, built by Anagha for the IBM Bob 2.0 Hackathon.",
   buttons GitHub (secondary), LinkedIn (primary,
   https://www.linkedin.com/in/anagha-langhe/), code `pip install downshift`.

### /callsites/ (web/app/callsites/page.tsx)
Section eyebrow `CALL SITES`, title "{sites_total} call sites, {sites_downgraded}
downgraded". Paragraph: the rule (candidate must reach >= threshold of baseline
pass rate and the floor of min_pass_rate; cheapest passing model wins; judge
passes at 4 of 5). Table (minWidth 900px), one row per call site in file order:
Call site (siteName bold + siteFile below in text-subtle, whole cell links to
`/callsites/{slug}/`) | Found by (FoundByBadge) | Difficulty | Grading | Decision
| one column per model in `summary.baseline` + `summary.candidates` showing pass
rate (chosen model's cell `text-good font-semibold`, baseline marked with `*`) |
After/mo | Savings/mo. Legend under the table. Then `<Disclaimer />`.

### /callsites/[slug]/ (web/app/callsites/[slug]/page.tsx)
Next 15: `params: Promise<{ slug: string }>`; `await params`.
`export const dynamicParams = false;` and `generateStaticParams()` returning
`allSlugs().map((slug) => ({ slug }))`. `generateMetadata` sets the title to
`{siteName(id)} · Downshift`. Unknown slug: `notFound()`.
Sections, all details shown:
1. Header panel: back link "← All call sites". Eyebrow `CALL SITE ·
   {file}:{line}`. H1 font-mono `siteName`. Badge row: FoundByBadge, `via {via}`
   (accent) if via, difficulty, grading, output_format, `async` if is_async,
   `max_tokens {n}`, `temperature {t}` (neutral badges, skip nulls). Purpose
   paragraph. "Output contract" label + text, or CodeBlock with
   `formatValue(output_contract)` if it is not a string.
2. Section `DECISION`: DecisionBadge large, "{baseline} → {model}" (or "stays on
   {baseline}"), reason text. MiniStats: Before/mo, After/mo, Savings/mo (with
   pct), Calls/day. `<Disclaimer />`.
3. Section `MODELS`: Table with a row per model: Model (name + tier + badges
   "baseline"/"chosen") | Pass rate | Passed (passed/cases) | Mean score | Judge
   avg (only when grading is "judge") | Prompt tok | Completion tok | Latency |
   Cost/call | vs baseline (check.ratio as pct) | Check (PassBadge of
   check.passed, "n/a" for baseline). Under the table, a list of each candidate's
   `check.reason` prefixed with the model name.
4. Section `PROMPT`: each message: role (uppercase mono text-subtle), content in a
   CodeBlock with `whitespace-pre-wrap`. If `resolved` is false add a warn Badge
   "not resolved statically". If messages is null: "Prompt not resolved
   statically." Also show "Model in code: {model_in_code ?? 'unresolved'}".
5. Section `EVAL EXAMPLES` ("{examples.length} of {cases} cases"): each example is
   a `<details>` (first one `open`) styled as a card. `<summary>`: case id (mono)
   + a PassBadge per model with the model name. Body: Inputs as a definition list
   (key in mono text-subtle, value in a pre-wrap block via formatValue), Expected
   (formatValue in CodeBlock), Notes (if any). Outputs: grid (1 col, 2 cols on
   md) of cards, one per model: header model name + PassBadge + "score {score}"
   and "judge {judge_score}/5" when present; output in a pre-wrap block; `detail`
   in text-xs text-subtle; `error` in text-bad.
6. Section `ALL CASES`: pass/fail grid. Table: first column case id, then one
   column per model; each cell a small square (`inline-block w-4 h-4 rounded-sm`)
   good = bg-good, bad = bg-bad, null = bg-line; `title` attribute "case · model
   · PASS/FAIL". Footer row: passed/total per model. Legend.
If the site has no evals entry, show "No evals for this call site." in 5 and 6.

### /audit/ (web/app/audit/page.tsx)
1. Section `STATIC ANALYSIS VS BOB`, title "Config-driven code blinds static
   analysis". Paragraphs from content `AUDIT_INTRO`. Table from `auditRows`:
   Metric | ast scan | Bob audit | ast after refactor (bob column text-good when
   larger than ast). Note from content `AUDIT_AFTER_NOTE`.
2. Section `WHAT BOB CHANGED`: list of `audit.changes`: kind Badge (accent) + id
   (mono) + detail (text-muted).
3. Section `CALL SITES`: two columns on md (stack on mobile). Left "ast scan
   ({n})": each site id (mono), model or warn "unresolved", prompt resolved yes/no.
   Right "Bob audit ({n})": id, FoundByBadge, via, model. Sites found by Bob get a
   left accent border (`border-l-2 border-accent pl-3`).

### /how-it-works/ (web/app/how-it-works/page.tsx)
1. Section `PIPELINE`, title "From call site to cost diff": ordered steps from
   content `PIPELINE_STEPS` (each: number, title, who: "Downshift" or "Bob" badge,
   command in mono, one-line description), then the ASCII diagram CodeBlock.
2. Section `WHERE BOB FITS`, title "Downshift is the toolkit, Bob is the brain":
   paragraph + Table from content `BOB_TASKS`: Task | Bob feature | What it did |
   Bobcoins.
3. Section `DECISION RULE`: short explanation from content `DECISION_RULE`
   (bullets) with threshold/floor numbers from summary.
4. Section `PRICING`: Table from `summary.pricing`: Model | Tier | Input $/1M |
   Output $/1M. Note "Illustrative tier prices that map local models to realistic
   API costs." `<Disclaimer />`.

### /docs/ (web/app/docs/page.tsx)
Single column like the reference site's /docs: H1 "Docs", subtitle "Install,
configure, run, and wire Downshift into CI." Then sections (h2
`text-lg font-semibold text-heading mt-10 mb-3`, body text-muted, CodeBlocks):
Install, Quickstart, Configuration, Commands, GitHub Action, Using Bob,
Methodology, Limitations, Future work. All copy comes from `content.ts` `DOCS`.
Add a small table of contents at the top (anchor links).

### web/app/not-found.tsx
Panel with "Page not found" and a link back to Overview.

## 7. Copy (web/lib/content.ts)

Export these constants exactly (fix only obvious typos).

```ts
export const REPO_URL = "https://github.com/ana-lan/downshift";
export const PYPI_URL = "https://pypi.org/project/downshift/";
export const LINKEDIN_URL = "https://www.linkedin.com/in/anagha-langhe/";

export const RESULT_NOTES = [
  "The floor did its job: on decide_refund the 3B model tied the 7B at 40%, and the 80% floor blocks both from counting as safe.",
  "Bigger is not always better: the 3B model scored below the 1.5B on classify_category and lang_of.",
  "Adding one mid-tier model (qwen2.5:3b) took projected savings from 5% to 18%.",
  "A self-graded 7B judge said draft_reply passed 100% of cases. An independent 120B judge found 14%.",
];

export const AUDIT_INTRO = [
  "The ast scanner found 7 call sites and resolved 6 of their models. It cannot see through shared helpers or config lookups.",
  "The Bob auditor started from the scan, read only the unresolved and shared call sites, and returned 8 logical call sites with every model resolved. It split the shared llm.py::ask helper into the two features that use it and found the hidden model in lang_of.",
];

export const AUDIT_AFTER_NOTE =
  "After Bob moved every model name into models.yaml, a fresh ast scan resolves 0 of 7 models. Config-driven code is normal in production, which is exactly why the auditor exists.";

export const CI_DEMO = {
  delta: "+$6,204.00/mo",
  pct: "+84.5%",
  range: "$7,339.50 → $13,543.50",
  text: "A demo PR added one new LLM call with a hard-coded 7B model and max_tokens 1024, run on every ticket. The Downshift Action commented the projected monthly increase and failed the check. Bob then reviewed the PR: route the call through models.yaml, cut max_tokens, and evaluate the 3B model first.",
};

export const ACTION_SNIPPET = `name: Cost diff
on: pull_request
permissions:
  contents: read
  pull-requests: write
  issues: write
jobs:
  cost-diff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: ana-lan/downshift@v0.1.0
        with:
          path: .
          fail-above: "500"
          github-token: \${{ secrets.GITHUB_TOKEN }}`;

export const PIPELINE_ASCII = `your repo
   │
   ▼
downshift scan ──► call sites (ast) ──► Bob auditor ──► enriched call sites
                                                          │
                     evals (Bob or downshift evalgen) ◄───┘
                                  │
                                  ▼
            downshift run  (baseline + cheaper models, judge)
                                  │
                                  ▼
            downshift report  (decide + cost)  ──► Bob applies it, opens a PR
                                  │
                                  ▼
            downshift diff  (GitHub Action on every PR)  ──► cost comment`;

export const PIPELINE_STEPS = [
  { title: "Scan", who: "Downshift", command: "downshift scan", text: "Static analysis finds every OpenAI-compatible call site, its model and prompt." },
  { title: "Audit", who: "Bob", command: "Downshift Auditor mode", text: "Bob resolves hidden models, splits shared helpers into features, and adds purpose, output contract, difficulty and grading." },
  { title: "Write evals", who: "Bob", command: "Eval Writer mode or downshift evalgen", text: "20 to 25 cases per call site, including edge cases, grounded in the refund policy." },
  { title: "Run", who: "Downshift", command: "downshift run", text: "Every eval on the baseline and each cheaper model, with tokens and latency recorded." },
  { title: "Grade", who: "Downshift", command: "downshift rescore", text: "Exact match, JSON fields, or an independent LLM judge for free text." },
  { title: "Decide and report", who: "Downshift", command: "downshift report", text: "Cheapest model that keeps quality wins, with a projected monthly cost." },
  { title: "Apply", who: "Bob", command: "Agent mode", text: "Bob moves model names into config, applies the decisions and opens the PR with the report." },
  { title: "Guard every PR", who: "Downshift", command: "downshift diff (GitHub Action)", text: "Comments the projected cost change on every pull request and can fail the check." },
];

export const BOB_TASKS = [
  { task: "Project setup", feature: "/init, AGENTS.md", did: "Generated project rules for every mode", coins: "0.95" },
  { task: "Architecture doc", feature: "Plan mode", did: "Wrote docs/architecture.md with a Mermaid diagram", coins: "0.23" },
  { task: "Audit SupportDesk", feature: "Custom mode + skill", did: "7 ast sites to 8 logical call sites, all models resolved", coins: "0.32" },
  { task: "Write evals", feature: "Custom mode + skill, document understanding", did: "181 eval cases across 8 call sites", coins: "0.92" },
  { task: "Build the report", feature: "Plan mode, then Agent mode", did: "report.py, CLI command and snapshot tests from a spec", coins: "8.34" },
  { task: "Apply decisions", feature: "Agent mode, commit + PR", did: "models.yaml refactor, downgrades, opened PR #8", coins: "1.38" },
  { task: "Apply mid tier", feature: "Agent mode, commit + PR", did: "Switched two call sites to the 3B model, opened PR #11", coins: "0.27" },
  { task: "Review a bad PR", feature: "Ask mode, context mentions", did: "Found the hard-coded model and the max_tokens cost driver", coins: "0.07" },
];

export const DECISION_RULE = [
  "A candidate passes when its eval pass rate is at least the quality threshold times the baseline's pass rate.",
  "It must also clear an absolute floor, so two equally bad models never count as safe.",
  "Among passing candidates the cheapest one wins. Otherwise the call site keeps its current model.",
  "Judge-graded cases pass at 4 of 5 or higher. Each model is priced with its own measured tokens.",
];

export const DOCS = {
  install: `pip install downshift`,
  quickstart: `# 1. find every LLM call site
downshift scan path/to/repo

# 2. write evals (Bob Eval Writer mode, or downshift evalgen)
# TODO(9c): evalgen and run commands

# 3. render the cost and quality report
downshift report --callsites path/to/repo/downshift.audit.json --out report.md

# 4. projected cost change of your branch vs main
downshift diff path/to/repo --base main`,
  config: `# downshift.yaml, next to the code you scan
version: 1

provider:
  base_url: "http://localhost:11434/v1"   # any OpenAI-compatible endpoint
  api_key_env: null                       # env var holding the key, or null

models:
  baseline: "qwen2.5:7b"                  # the model your code uses today
  candidates: ["qwen2.5:3b", "qwen2.5:1.5b", "qwen2.5:0.5b"]
  judge: null                             # grades free text; defaults to the baseline

quality_threshold: 0.95                   # fraction of baseline quality a candidate must keep
min_pass_rate: 0.80                       # floor: a candidate must also pass this share of cases

pricing:                                  # USD per 1M tokens, replace with your provider's
  "qwen2.5:7b":   { input: 2.50, output: 10.00, tier: premium }
  "qwen2.5:3b":   { input: 0.40, output: 1.60,  tier: standard }
  "qwen2.5:1.5b": { input: 0.15, output: 0.60,  tier: budget }
  "qwen2.5:0.5b": { input: 0.10, output: 0.40,  tier: nano }

volume:
  default_per_day: 20000                  # calls per day, used for monthly projections
  per_call_site: {}                       # e.g. "app/triage.py::classify": 50000

scan:
  include: ["*.py"]
  exclude: ["tests/*"]`,
  commands: [
    { name: "scan", text: "Find every LLM call site in a repository." },
    { name: "validate", text: "Check a callsites or audit file against the schema." },
    { name: "compare", text: "Compare the ast scan with a Bob audit, side by side." },
    { name: "check-evals", text: "Check eval files against the call sites they test." },
    { name: "evalgen", text: "Generate an eval set for each call site with a configured model." },
    { name: "run", text: "Run each call site's evals on the baseline and candidate models, and score them." },
    { name: "rescore", text: "Re-grade saved outputs of judge-graded call sites with the configured judge." },
    { name: "report", text: "Render the cost and quality report." },
    { name: "diff", text: "Show the projected LLM cost change between two git refs." },
    { name: "export", text: "Export JSON and the report for the demo web app." },
  ],
  bob: [
    "The bob/ folder ships a Downshift Auditor mode and two skills (downshift-audit, downshift-evals). See bob/README.md to install them in Bob IDE.",
    "The auditor starts from downshift scan output and only reads unresolved or shared call sites, which keeps it cheap.",
    "Everything except the audit and eval writing runs without Bob.",
  ],
  methodology: [
    "Evals: 20 to 25 cases per call site, graded by exact match, JSON fields, or an LLM judge (pass at 4 of 5).",
    "Models run locally with Ollama. Dollar figures use real token counts, illustrative tier prices and an assumed volume, all from downshift.yaml.",
    "downshift diff is a static projection for per-PR deltas: unresolved models are priced as the baseline, missing max_tokens assume 256 output tokens, and prompts are counted from the resolved text. It is not an absolute spend estimate.",
  ],
  limitations: [
    "Python only; detects OpenAI-compatible SDK calls.",
    "Prices are illustrative and volumes are assumed; plug in your own.",
    "Local Qwen 2.5 models on a laptop, not a production API benchmark.",
    "Eval inputs are synthetic (SupportDesk demo data), not sampled from real traffic.",
  ],
  future: [
    "GitHub Marketplace listing for the Action.",
    "downshift audit command that runs the auditor with any configured LLM.",
    "Anthropic and Gemini runners, LiteLLM and LangChain detection, a JS/TS scanner.",
    "Eval inputs sampled from real logs with PII redaction.",
  ],
};
```

## 8. File list (create exactly these)

```
web/package.json
web/next.config.ts
web/tsconfig.json
web/next-env.d.ts
web/postcss.config.mjs
web/eslint.config.mjs
web/.gitignore
web/app/globals.css
web/app/layout.tsx
web/app/page.tsx
web/app/not-found.tsx
web/app/callsites/page.tsx
web/app/callsites/[slug]/page.tsx
web/app/audit/page.tsx
web/app/how-it-works/page.tsx
web/app/docs/page.tsx
web/components/Nav.tsx
web/components/ThemeToggle.tsx
web/components/Panel.tsx
web/components/StatCard.tsx
web/components/Badge.tsx
web/components/Table.tsx
web/components/CodeBlock.tsx
web/components/Disclaimer.tsx
web/components/Footer.tsx
web/components/Button.tsx
web/lib/types.ts
web/lib/data.ts
web/lib/select.ts
web/lib/format.ts
web/lib/content.ts
```
Not in scope (Claude adds later): Vitest config and tests, CI job, case study page.
