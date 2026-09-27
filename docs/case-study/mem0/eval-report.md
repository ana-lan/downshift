# Downshift report

> Costs are projections: measured tokens per call x illustrative prices x assumed volume
> from the config. They are not a bill.

## Summary

| | Monthly cost |
|---|---:|
| Before (all on `qwen2.5:7b`) | $1,564.38 |
| After | $1,564.38 |
| Savings | $0.00 (0.0%) |

Downgraded **0 of 3** call sites.

Rule: a cheaper model must keep at least 95% of the baseline pass rate and pass at least 80% of cases on its own. Decisions use pass rate, not mean score.

Totals exclude 2 call sites with unknown cost (see Needs attention).

## What this analysis cost

| | One-time cost |
|---|---:|
| Eval model calls (96) | $0.02 |
| Judge calls, estimated (96) | $0.28 |
| **Total** | **$0.29** |

No payback: nothing was downgraded, so there are no projected savings.

> Priced at the same illustrative prices as the rest of the report. Judge tokens are not recorded, so each judge call is estimated as (case prompt + output + 150) tokens in and 200 out, priced as `qwen2.5:7b`. Retries and warm-up calls are not counted. Local Ollama runs cost $0 in practice.

## Decisions

| Call site | Grading | Decision | Model | Pass rate | Before / month | After / month |
|---|---|---|---|---|---:|---:|
| `mem0/memory/main.py::Memory._add_to_vector_store` | judge | keep | `qwen2.5:7b` | n/a | n/a | n/a |
| `mem0/memory/main.py::Memory._create_procedural_memory` | judge | keep | `qwen2.5:7b` | n/a | n/a | n/a |
| `mem0/reranker/llm_reranker.py::LLMReranker.rerank` | judge | keep | `qwen2.5:7b` | 71% | $1,564.38 | $1,564.38 |

## Quality per model

| Call site | `qwen2.5:7b` | `qwen2.5:3b` | `qwen2.5:1.5b` | `qwen2.5:0.5b` |
|---|--- | --- | --- | ---|
| `mem0/memory/main.py::Memory._add_to_vector_store` | **n/a** | n/a | n/a | n/a |
| `mem0/memory/main.py::Memory._create_procedural_memory` | **n/a** | n/a | n/a | n/a |
| `mem0/reranker/llm_reranker.py::LLMReranker.rerank` | **17/24 (71%), judge 3.8/5** | 13/24 (54%), judge 3.2/5 | 13/24 (54%), judge 3.2/5 | 11/24 (46%), judge 2.8/5 |

Judge-graded cases pass at 4/5 or higher; judge scores are averages on a 1 to 5 scale.

## Needs attention

### Baseline below the floor

- `mem0/reranker/llm_reranker.py::LLMReranker.rerank`: baseline passes 71% of cases, below the 80% floor.  Improve the prompt or model before downgrading.

### Missing data

- `examples/misc/movie_recommendation_grok3.py::recommend_movie_with_memory`: no eval set, not decided.
- `integrations/hermes-plugin-mem0/_openai_llm.py::DirectOpenAILLM.generate_response`: no eval set, not decided.
- `mem0/llms/anthropic.py::AnthropicLLM.generate_response`: no eval set, not decided.
- `mem0/llms/azure_openai.py::AzureOpenAILLM.generate_response`: no eval set, not decided.
- `mem0/llms/azure_openai_structured.py::AzureOpenAIStructuredLLM.generate_response`: no eval set, not decided.
- `mem0/llms/deepseek.py::DeepSeekLLM.generate_response`: no eval set, not decided.
- `mem0/llms/groq.py::GroqLLM.generate_response`: no eval set, not decided.
- `mem0/llms/lmstudio.py::LMStudioLLM.generate_response`: no eval set, not decided.
- `mem0/llms/minimax.py::MiniMaxLLM.generate_response`: no eval set, not decided.
- `mem0/llms/openai_structured.py::OpenAIStructuredLLM.generate_response`: no eval set, not decided.
- `mem0/llms/together.py::TogetherLLM.generate_response`: no eval set, not decided.
- `mem0/llms/vllm.py::VllmLLM.generate_response`: no eval set, not decided.
- `mem0/llms/xai.py::XAILLM.generate_response`: no eval set, not decided.
- `mem0/memory/utils.py::get_image_description`: no eval set, not decided.
- `mem0/memory/main.py::Memory._add_to_vector_store`: no baseline results.
- `mem0/memory/main.py::Memory._create_procedural_memory`: no baseline results.

## Details

<details>
<summary><code>mem0/memory/main.py::Memory._add_to_vector_store</code>: keep <code>qwen2.5:7b</code></summary>

- Decision: no baseline results

</details>
<details>
<summary><code>mem0/memory/main.py::Memory._create_procedural_memory</code>: keep <code>qwen2.5:7b</code></summary>

- Decision: no baseline results

</details>
<details>
<summary><code>mem0/reranker/llm_reranker.py::LLMReranker.rerank</code>: keep <code>qwen2.5:7b</code></summary>

- Decision: no cheaper model passed the checks
- `qwen2.5:3b`: keeps 76% of baseline quality, needs 95%
- `qwen2.5:1.5b`: keeps 76% of baseline quality, needs 95%
- `qwen2.5:0.5b`: keeps 65% of baseline quality, needs 95%

</details>
