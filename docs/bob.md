# Using Downshift with IBM Bob

Downshift runs without Bob. With Bob, the Downshift Auditor closes the gaps static analysis cannot: models and prompts only known at runtime, and shared LLM helpers that serve several features.

## What ships

- `.bob/custom_modes.yaml`: the Downshift Auditor mode. It can read files and load skills, and it can edit only `downshift.audit.json`, so it cannot change your code.
- `.bob/skills/downshift-audit/`: the audit workflow (`SKILL.md`) and the field reference (`schema-reference.md`).
- `AGENTS.md` and `.bob/rules-*/`: project rules generated with Bob's `/init`.

## Use it in this repo

Bob loads project modes and skills from `.bob/` automatically. Check that **Downshift Auditor** appears in Settings > Modes and **downshift-audit** appears in Settings > Skills.

```bash
downshift scan examples/supportdesk -o examples/supportdesk/downshift.scan.json
```

Open a new Bob task, pick the Downshift Auditor mode, and send:

```
Audit @examples/supportdesk/downshift.scan.json using the downshift-audit skill.
```

Then check the result:

```bash
downshift validate examples/supportdesk/downshift.audit.json
downshift compare examples/supportdesk/downshift.scan.json examples/supportdesk/downshift.audit.json
```

## Use it in another repo

1. Copy `.bob/skills/downshift-audit/` into that repo's `.bob/skills/`, or into `~/.bob/skills/` to use it everywhere.
2. Add the `downshift-auditor` entry from `.bob/custom_modes.yaml` to that repo's `.bob/custom_modes.yaml`, or to your global modes (Settings > Modes > Edit Global Modes).
3. Write the scan file outside `.downshift/` if your `.bobignore` excludes that folder.

## Keeping Bobcoin cost low

- Point Bob at the scan file with an @mention. The skill limits reads to flagged call sites and their callers.
- One audit per task. If validation fails, fix the JSON by hand instead of asking Bob to retry.
