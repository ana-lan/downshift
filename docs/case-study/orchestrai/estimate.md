## Downshift cost diff

Projected monthly LLM cost, `bob` vs `ast`: **$540.00 -> $2,408.99 (+$1,868.99, +346.1%)**

Call sites: 5 added, 0 changed, 1 removed, 0 unchanged. Key: `+` added, `~` changed, `-` removed.

|  | Call site | Model | In + out | Calls/day | Monthly | Delta |
|---|---|---|---|---|---|---|
| + | `modules.py::chameleon` | gpt-4-0613 | 145 + 1500‡ | 200 | $566.10 | +$566.10 |
| + | `modules.py::create_readme` | gpt-4-0613 | 112 + 1500‡ | 200 | $560.16 | +$560.16 |
| + | `modules.py::debugger` | gpt-3.5-turbo-16k | 211 + 1500‡ | 600 | $119.39 | +$119.39 |
| + | `modules.py::engineer` | gpt-4-0613 | 265 + 1500‡ | 200 | $587.70 | +$587.70 |
| + | `modules.py::modify_codebase` | gpt-4-0613 | 198 + 1500‡ | 200 | $575.64 | +$575.64 |
| - | `ai.py::AI.generate_response` | gpt-4-0613† | 0§ + 1500‡ | 200 | $0.00 | -$540.00 |

- † Model not resolved by static analysis; priced as the baseline `gpt-4-0613`. Run the Bob auditor for exact models.
- ‡ No max_tokens set; assumed 1500.
- § Prompt only partly resolved; unresolved text not counted.

_Projection, not a bill: tokens estimated from source (words in resolved prompt text; output = max_tokens, or 1500 if unset) x illustrative prices x configured calls/day x 30 days._
