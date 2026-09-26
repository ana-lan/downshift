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
  range: "$7,339.50 to $13,543.50",
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
   |
   v
downshift scan ....... call sites found by static analysis
   |
   v
Bob auditor .......... hidden models resolved, shared helpers split
   |
   v
evals ................ Bob Eval Writer, or downshift evalgen with any model
   |
   v
downshift run ........ baseline + cheaper models, graded by a judge
   |
   v
downshift report ..... cheapest safe model and projected cost per call site
   |                   -> Bob applies the decisions and opens a PR
   v
downshift diff ....... GitHub Action comments the cost change on every PR`;

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
  { task: "Build the demo app", feature: "Agent mode, spec in context", did: "Scaffolded the Next.js app from web/SPEC.md", coins: "5.68" },
  { task: "Audit OrchestrAI", feature: "Custom mode + skill, context mentions", did: "Real repo: 1 shared helper to 5 features, all models resolved", coins: "0.46" },
  { task: "Audit mem0", feature: "Custom mode + skill, context mentions, steering", did: "Real repo: 14 ast call sites to the 4 features that spend money", coins: "3.32" },
];

export const DECISION_RULE = [
  "A candidate passes when its eval pass rate is at least the quality threshold times the baseline's pass rate.",
  "It must also clear an absolute floor, so two equally bad models never count as safe.",
  "Among passing candidates the cheapest one wins. Otherwise the call site keeps its current model.",
  "Judge-graded cases pass at 4 of 5 or higher. Each model is priced with its own measured tokens.",
];

export const DOCS = {
  install: `pip install downshift`,
  quickstart: `# 1. find every LLM call site (writes path/to/repo/.downshift/callsites.json)
downshift scan path/to/repo

# 2. write evals with any configured model (or the Bob Eval Writer mode)
downshift evalgen --callsites path/to/repo/.downshift/callsites.json --out path/to/repo/.downshift/evals

# 3. run the baseline and every cheaper model on the evals
downshift run --callsites path/to/repo/.downshift/callsites.json

# 4. cost and quality report with a decision per call site
downshift report --callsites path/to/repo/.downshift/callsites.json --out report.md

# 5. projected cost change of your branch vs main
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
    { name: "estimate", text: "Project monthly LLM cost from a scan or audit file. No evals needed." },
    { name: "diff", text: "Show the projected LLM cost change between two git refs." },
    { name: "export", text: "Export JSON and the report for the demo web app." },
  ],
  bob: [
    "The .bob/ folder ships two custom modes (Downshift Auditor, Downshift Eval Writer) and their skills (downshift-audit, downshift-evals). See docs/bob.md to use them in Bob IDE.",
    "The auditor starts from downshift scan output and only reads unresolved or shared call sites, which keeps it cheap.",
    "Everything except the audit and eval writing runs without Bob.",
  ],
  methodology: [
    "Evals: 20 to 25 cases per call site, graded by exact match, JSON fields, or an LLM judge (pass at 4 of 5).",
    "Models run locally with Ollama. Dollar figures use real token counts, illustrative tier prices and an assumed volume, all from downshift.yaml.",
    "downshift diff is a static projection for per-PR deltas: unresolved models are priced as the baseline, missing max_tokens assume 256 output tokens, and prompts are counted from the resolved text. It is not an absolute spend estimate. downshift estimate uses the same projection on a single scan or audit file.",
  ],
  limitations: [
    "Python only; detects the OpenAI v1 SDK and the Anthropic messages API.",
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

export type CaseStudy = {
  slug: string;
  name: string;
  title: string;
  headline: string;
  repo: string;
  repoUrl: string;
  license: string;
  commit: string;
  audited: string;
  scope: string;
  docUrl: string;
  coins: string;
  intro: string[];
  metrics: { label: string; ast: number; bob: number }[];
  bobFound: string[];
  features: { name: string; model: string; calls: number; monthly: number }[];
  staticMonthly: number;
  staticNote: string;
  bobMonthly: number;
  bobNote: string;
  command: string;
  findings: string[];
  limitations: string[];
};

export const CASE_STUDIES: CaseStudy[] = [
  {
    slug: "orchestrai",
    name: "OrchestrAI",
    title: "OrchestrAI: one helper, five features",
    headline: "1 call site → 5 features",
    repo: "samshapley/OrchestrAI",
    repoUrl: "https://github.com/samshapley/OrchestrAI",
    license: "MIT",
    commit: "866deaad457de2d9bef2c8fb227cfa52338c31e3",
    audited: "Sep 26, 2026",
    scope: "engineering_pipeline, the pipeline set in config.yml",
    docUrl: `${REPO_URL}/blob/main/docs/case-study.md`,
    coins: "0.46",
    intro: [
      "OrchestrAI builds software with a pipeline of LLM modules: plan, write code, debug, modify, write a README. Downshift had never seen it before.",
      "Every module goes through one shared helper. The model comes from YAML and each prompt is loaded from a text file at runtime, so static analysis sees one call with nothing resolved.",
    ],
    metrics: [
      { label: "Call sites", ast: 1, bob: 5 },
      { label: "Models resolved", ast: 0, bob: 5 },
      { label: "Prompts resolved", ast: 0, bob: 5 },
      { label: "Enriched for evals", ast: 0, bob: 5 },
    ],
    bobFound: [
      "Split the helper into 5 features, one per module that calls the LLM. code_planner has no function of its own and is dispatched through a generic fallback.",
      "Resolved every model: gpt-4-0613 from config.yml for four modules, and a per-module override to gpt-3.5-turbo-16k for debugger in the pipeline YAML.",
      "Rebuilt every prompt the way the app assembles it at runtime, including the two modules that build their own user message.",
      "Found the volume multipliers: debugger retries up to 3 times per run, and modify_codebase loops until the user stops.",
    ],
    features: [
      { name: "engineer", model: "gpt-4-0613", calls: 200, monthly: 587.7 },
      { name: "modify_codebase", model: "gpt-4-0613", calls: 200, monthly: 575.64 },
      { name: "code_planner", model: "gpt-4-0613", calls: 200, monthly: 566.1 },
      { name: "create_readme", model: "gpt-4-0613", calls: 200, monthly: 560.16 },
      { name: "debugger", model: "gpt-3.5-turbo-16k", calls: 600, monthly: 119.39 },
    ],
    staticMonthly: 540,
    staticNote: "1 call site, model assumed",
    bobMonthly: 2408.99,
    bobNote: "5 features, real models and prompts",
    command: `downshift estimate docs/case-study/orchestrai/downshift.audit.json \\
  --base docs/case-study/orchestrai/downshift.scan.json \\
  -c docs/case-study/orchestrai/downshift.yaml --completion-tokens 1500`,
    findings: [
      "Static analysis alone underestimates this bill about 4.5x. It sees one call where the app makes five, seven with debugger retries.",
      "95% of projected spend is four features on gpt-4-0613, one of OpenAI's most expensive legacy models.",
      "The author already downshifted once, by hand: debugger runs on gpt-3.5-turbo-16k. On gpt-4-0613 it would cost about $1,734 a month instead of $119. Downshift makes that call per feature, backed by evals.",
      "A third-party pricing tracker lists gpt-4-0613 for deprecation on Oct 23, 2026. Downshift's eval step is how you would pick each replacement.",
    ],
    limitations: [
      "Projection, not a bill: OpenAI list prices (checked Sep 26, 2026) x assumed volume of 200 pipeline runs a day.",
      "Output assumed at 1,500 tokens per call because no module sets max_tokens. Input counts only the static system prompts, so it is a floor.",
      "No evals were run on this repo (paid API calls, $0 budget), so there are no downgrade recommendations here. The SupportDesk demo shows the full loop.",
      "Only engineering_pipeline was audited. The four other pipelines use the same helper and pattern.",
    ],
  },
  {
    slug: "mem0",
    name: "mem0",
    title: "mem0: 14 call sites, 4 real features",
    headline: "14 call sites → 4 real features",
    repo: "mem0ai/mem0",
    repoUrl: "https://github.com/mem0ai/mem0",
    license: "Apache-2.0",
    commit: "94c3fe9f238f3dbf29c9ce98643bd71eb13077cd",
    audited: "Sep 26, 2026",
    scope: "default setup: OpenAI provider, library code in mem0/",
    docUrl: `${REPO_URL}/blob/main/docs/case-study-mem0.md`,
    coins: "3.32",
    intro: [
      "mem0 is a widely used memory layer for AI apps: it extracts facts from conversations, stores them and retrieves them later.",
      "It supports many LLM providers through adapter classes. Static analysis finds the adapters; the features that actually spend money are one level up. Running on it also exposed two scanner bugs, now fixed with tests.",
    ],
    metrics: [
      { label: "LLM call sites", ast: 14, bob: 17 },
      { label: "Models resolved", ast: 1, bob: 5 },
      { label: "Prompts resolved", ast: 1, bob: 5 },
      { label: "Product features identified", ast: 0, bob: 4 },
    ],
    bobFound: [
      "Split the OpenAI adapter into the 4 features that use it: fact extraction on add(), procedural memory, image description (vision only) and search reranking.",
      "Resolved every model and setting: gpt-5-mini by default, and a separate reranker config with its own temperature and token limit.",
      "Rebuilt the prompts, and noted that the async add and procedural paths send the same prompts as the sync ones.",
      "Two fix-ups by script, no Bob loop: the 13 untouched scan entries were merged back, and two long prompt constants Bob left as placeholders were copied from source.",
    ],
    features: [
      { name: "fact extraction (add)", model: "gpt-5-mini", calls: 10000, monthly: 1581.98 },
      { name: "search reranking", model: "gpt-5-mini", calls: 100000, monthly: 675 },
      { name: "image description", model: "gpt-5-mini", calls: 500, monthly: 60.12 },
      { name: "procedural memory", model: "gpt-5-mini", calls: 100, monthly: 12.53 },
    ],
    staticMonthly: 307.2,
    staticNote: "1 OpenAI helper, model and output assumed",
    bobMonthly: 2329.62,
    bobNote: "4 features, real models, prompts and limits",
    command: `downshift estimate docs/case-study/mem0/downshift.audit.json \\
  --base docs/case-study/mem0/downshift.scan.json \\
  -c docs/case-study/mem0/downshift.yaml`,
    findings: [
      "Static analysis sees plumbing, not features: 14 call sites, 13 of them provider adapters or examples. The default setup runs 4 features, and cost belongs to features.",
      "Static-only pricing underestimates this bill about 7.6x.",
      "The reranker calls the LLM once per candidate document. At 10 candidates, 10,000 searches become 100,000 LLM calls: $675 a month, 29% of the bill, from one for loop.",
      "Fact extraction re-sends a 33,653-character prompt on every add(). Input alone is about $382 of that feature's $1,582, a strong candidate for prompt caching or a cheaper model.",
    ],
    limitations: [
      "Projection, not a bill: OpenAI list prices (checked Sep 26, 2026) x assumed volume of 10,000 adds and 10,000 reranked searches a day.",
      "Output is priced at max_tokens, a ceiling, so feature costs are an upper bound. Tokens are estimated from words; runtime text is not counted.",
      "No evals were run on this repo (paid API calls, $0 budget), so there are no downgrade recommendations here.",
      "Default setup only: the other provider adapters, the integration and the example were not audited or priced.",
    ],
  },
];
