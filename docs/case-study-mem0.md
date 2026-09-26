# Case study 2: mem0

Downshift run on a large, widely used open-source library it had never seen before.

| | |
|---|---|
| Repository | https://github.com/mem0ai/mem0 |
| License | Apache-2.0 |
| Commit | `94c3fe9f238f3dbf29c9ce98643bd71eb13077cd` |
| Audited | Sep 26, 2026 |
| Scope | the default setup: OpenAI provider, library code in `mem0/` |

mem0 is a memory layer for AI apps: it extracts facts from conversations, stores them,
and retrieves them later. No mem0 code is copied into Downshift. The files in
[`docs/case-study/mem0/`](case-study/mem0/) are Downshift's own outputs; the audit file
quotes mem0's Apache-2.0 prompt text.

## Why this repo

It is a different pattern from [OrchestrAI](case-study.md). mem0 supports many LLM
providers through adapter classes (OpenAI, Anthropic, Azure, Groq, DeepSeek, xAI, vLLM
and more), each with a `generate_response` method. The product features call whichever
adapter is configured. Static analysis sees the adapters; the features are one level up.

## Real repos made the scanner better

Running on real code exposed two scanner bugs, fixed with tests before this audit:

- **Anthropic calls through `**kwargs` were missed.** mem0's Anthropic adapter calls
  `client.messages.create(**params)`. The scanner required a literal `model=` for
  `messages.create` (to avoid false positives like Twilio's SMS client). It now also
  accepts a `**` splat when the file imports the matching SDK, including imports inside
  `try` blocks.
- **Files starting with a byte-order mark crashed parsing** (found on OpenBMB/ChatDev).
  Files are now read as `utf-8-sig`.

## Static analysis vs Bob

| Metric | ast scan | Bob audit |
|---|---|---|
| LLM call sites | 14 | 17 |
| Models resolved | 1 | 5 |
| Prompts resolved | 1 | 5 |
| Product features identified | 0 | 4 |

`downshift scan` finds 14 calls in 417 files. 12 are provider adapters, one is an
integration adapter and one is an example script. Only the example's model is a literal.
Each adapter also lists 116 "callers", because static caller matching goes by method name
and every test and adapter shares it. The scan is correct, but it cannot say which of the
14 matter.

The Bob auditor (custom mode + `downshift-audit` skill, one task, **3.32 Bobcoins**),
scoped to the default OpenAI setup, then:

- **Split the OpenAI adapter into the 4 features that use it**: fact extraction on
  `add()` (`Memory._add_to_vector_store`), procedural memory
  (`Memory._create_procedural_memory`), image description (`get_image_description`, only
  with vision enabled) and search reranking (`LLMReranker.rerank`).
- **Resolved every model and setting**: `gpt-5-mini` by default; temperature 0.1 and
  max_tokens 2000 from the base LLM config; the reranker builds its own LLM from its own
  config (temperature 0.0, max_tokens 100).
- **Rebuilt the prompts**, and noted that the async `add` and procedural paths send the
  same prompts as the sync ones.

Two fix-ups by hand (no Bob loop): Bob's final write was steered to contain only the 4 new
entries, and a script merged the 13 untouched scan entries back. Bob also left two long
prompt constants as placeholders; a script copied their text from
`mem0/configs/prompts.py` and says so in a note on each entry.

Files: [scan](case-study/mem0/downshift.scan.json),
[audit](case-study/mem0/downshift.audit.json).

## Cost projection

```bash
downshift estimate docs/case-study/mem0/downshift.audit.json \
  --base docs/case-study/mem0/downshift.scan.json \
  -c docs/case-study/mem0/downshift.yaml
```

| Feature | Model | Tokens/call (in + out) | Calls/day | Monthly |
|---|---|---|---|---|
| Fact extraction (`add`) | gpt-5-mini | 5,093 + 2,000 | 10,000 | $1,581.98 |
| Search reranking | gpt-5-mini | 100 + 100 | 100,000 | $675.00 |
| Image description | gpt-5-mini | 31 + 2,000 | 500 | $60.12 |
| Procedural memory | gpt-5-mini | 705 + 2,000 | 100 | $12.53 |
| **Total (Bob view)** | | | | **$2,329.62** |
| Static-only view (1 helper, model and output assumed) | gpt-5-mini | 0 + 256 | 20,000 | $307.20 |

Full output: [estimate.md](case-study/mem0/estimate.md).

**Findings**

1. **Static analysis sees plumbing, not features.** 14 call sites, 13 of them provider
   adapters or examples. The default setup runs 4 features, and cost belongs to features.
2. **Static-only pricing underestimates this bill about 7.6x** ($307 vs $2,330 a month).
3. **The reranker calls the LLM once per candidate document.** `top_k` only trims the
   results; every candidate is scored. At 10 candidates, 10,000 searches become 100,000
   LLM calls: $675 a month, 29% of the bill, from one `for` loop.
4. **Fact extraction re-sends a 33,653-character prompt on every `add()`**, about 5,100
   tokens by Downshift's estimate. Input alone is about $382 of that feature's $1,582.
   That makes it a strong candidate for prompt caching or a cheaper model, which is
   exactly what Downshift's eval step would test per feature.
5. A third-party pricing site says GPT-5 mini shuts down on Dec 11, 2026. If so, every
   feature here needs a replacement model, and evals are how to pick one safely.

## Assumptions and limitations

- **Projection, not a bill.** OpenAI list prices ($0.25 / $2.00 per 1M tokens for
  gpt-5-mini) checked Sep 26, 2026. Volume is assumed: 10,000 adds and 10,000 reranked
  searches a day with 10 candidates each, 100 procedural memories, 500 images.
- **Output is priced at `max_tokens`**, a ceiling, so feature costs are an upper bound.
- **Tokens are estimated from words**; real token counts for long prompts are usually
  higher. Runtime text (conversation, memories, documents) is not counted.
- **No evals were run** (paid API calls, $0 budget), so no downgrade recommendations.
- **Default setup only.** The other provider adapters, the integration and the example
  were copied from the scan unchanged and are not priced (0 calls a day, or no configured
  price for the example's `grok-3-beta`).

## Reproduce

```bash
git clone https://github.com/mem0ai/mem0 && cd mem0
git checkout 94c3fe9f238f3dbf29c9ce98643bd71eb13077cd
downshift scan .
```

The Bob step runs the Downshift Auditor mode with the `downshift-audit` skill on
`.downshift/callsites.json`. Screenshots: `bob_sessions/downshift_task11_mem0_a.png` to
`_e.png`.
