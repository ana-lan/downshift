# mem0 eval brief (for Bob subagents)

Write eval sets for 3 mem0 features. Format: `.bob/skills/downshift-evals/format-reference.md`
(read it first). Ignore the SupportDesk-specific rules in that skill (refund policy, tickets).
Output folder: `docs/case-study/mem0/evals/`. File name = slug of the call site id
(drop `.py`, `/` -> `.`, `::` -> `__`). Every case has `grading: "judge"`, and `expected` is a
rubric a grader can check point by point.

Data rules: synthetic only. Invented people, no real names, emails, phone numbers or
addresses. No copied text from any website or dataset.

Every case: `id` (prefix + number), `inputs` with exactly the prompt's placeholders,
`expected` rubric, `grading: "judge"`, one-line `notes`. Only cases a careful human
would grade the same way. Do not run commands.

## 1. mem0/memory/main.py::Memory._add_to_vector_store (prefix `mem-`, 15 cases)
Placeholders: summary, last_k_messages, recently_extracted_memories_json,
existing_memories_json, new_messages_json, observation_date, current_date.
JSON placeholders are JSON strings (lists of `{"role","content"}` or of `{"id","text"}`).
Keep conversations short (2 to 6 messages). Dates in 2026.
Rubric: output is a JSON object `{"memory": [...]}`; list the facts that must be captured;
each text is self-contained (names the person, no "he/she" without a referent); no fact
already in existing or recently extracted memories is repeated; nothing invented.
Cover: personal facts, preferences, plans with dates, assistant recommendations the user
accepted, a conversation with nothing memorable (expected: empty list), duplicates of
existing memories (must not repeat), relative dates ("next Friday") resolved against
observation_date.

## 2. mem0/memory/main.py::Memory._create_procedural_memory (prefix `proc-`, 12 cases)
Placeholders: role, content (one agent-history message; role is "assistant" or "user").
`content` is a short agent execution log, 3 to 8 steps: browsing, coding, data or file tasks.
Rubric: has Task Objective and Progress Status; one numbered step per agent action in
order; each step's Action Result is copied verbatim (quote the exact strings to check);
errors in the log are recorded; nothing invented.
Cover: a finished task, a half-done task, a task with an error and a retry, a log with
exact numbers or URLs that must survive verbatim, a one-step log.

## 3. mem0/reranker/llm_reranker.py::LLMReranker.rerank (prefix `rr-`, 24 cases)
Placeholders: query, doc_text. Documents are short memory lines (1 to 2 sentences) like
mem0 stores, e.g. "Priya prefers aisle seats on long flights."
Expected rubric: "Output is only a single number (no words) between A and B." Use the
prompt's own bands and keep them wide enough that careful humans agree:
- 8 clearly relevant, directly answers the query: between 0.8 and 1.0
- 8 related topic but does not answer: between 0.3 and 0.7
- 8 unrelated: between 0.0 and 0.3
Drop any case where the band is debatable. Include a few tricky ones: same keyword but
different meaning, a paraphrase with no shared words, a negation ("dislikes" vs "likes").
