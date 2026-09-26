## Downshift cost diff

Projected monthly LLM cost, `bob` vs `ast`: **$307.20 -> $2,329.62 (+$2,022.42, +658.3%)**

Call sites: 4 added, 0 changed, 1 removed, 13 unchanged. Key: `+` added, `~` changed, `-` removed.

|  | Call site | Model | In + out | Calls/day | Monthly | Delta |
|---|---|---|---|---|---|---|
| + | `mem0/memory/main.py::Memory._add_to_vector_store` | gpt-5-mini | 5093 + 2000 | 10,000 | $1,581.98 | +$1,581.98 |
| + | `mem0/memory/main.py::Memory._create_procedural_memory` | gpt-5-mini | 705 + 2000 | 100 | $12.53 | +$12.53 |
| + | `mem0/memory/utils.py::get_image_description` | gpt-5-mini | 31 + 2000 | 500 | $60.12 | +$60.12 |
| + | `mem0/reranker/llm_reranker.py::LLMReranker.rerank` | gpt-5-mini | 100 + 100 | 100,000 | $675.00 | +$675.00 |
| - | `mem0/llms/openai.py::OpenAILLM.generate_response` | gpt-5-mini† | 0§ + 256‡ | 20,000 | $0.00 | -$307.20 |

- † Model not resolved by static analysis; priced as the baseline `gpt-5-mini`. Run the Bob auditor for exact models.
- ‡ No max_tokens set; assumed 256.
- § Prompt only partly resolved; unresolved text not counted.
- 1 call site(s) use a model with no configured price and are left out of the totals.

_Projection, not a bill: tokens estimated from source (words in resolved prompt text; output = max_tokens, or 256 if unset) x illustrative prices x configured calls/day x 30 days._
