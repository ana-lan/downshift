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
