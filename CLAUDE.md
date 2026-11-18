# CLAUDE.md

This repository is a standalone portfolio product. The full spec is in specs/1-questionnaire-copilot.md.
The working rules are in specs/00-AGENT-RULES.md. Read both before any work.

## Non-negotiable rules
- Work one phase at a time, as numbered in the spec. Stop after each phase for review.
- Before starting a phase, read PROGRESS.md to see what is already done.
- After each phase: run its acceptance commands, append to PROGRESS.md (date, phase, what was built,
  trimmed acceptance output, decisions, open questions), commit, then stop and summarize.
- One commit per task, Conventional Commits.
- Use the exact synthetic data values given in the spec. Never invent values that tests depend on.
- `make test` must never call a paid API. Model calls go through the LLM wrapper with a `stub` provider.
- Check current official docs before using any SDK, API, model name or CLI flag that may have changed.
  Record what you read in docs/sources.md.
- Ask before adding a dependency the spec does not list.
- No secrets in git. No em dashes in any file.
- README numbers come only from evals/report.md. If a target is missed, say so.
- If the spec is unclear or wrong, write the issue in PROGRESS.md under "Questions", choose the
  simplest option, and tell me in your summary.
