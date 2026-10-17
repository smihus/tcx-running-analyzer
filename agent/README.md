# Optional AI-agent instructions / Дополнительные правила для ИИ

This folder is an **opt-in** workflow layer. The repository root now contains [`AGENTS.md`](../AGENTS.md) that directs compatible agents here only for opted-in workout tasks. The Python program works without any agent. The instructions **do not grant permissions to any chat**; file/process access depends on the AI environment.

## Primary user workflow / Основной порядок работы

1. User submits **one or several TCX files** (not a precomputed JSON).
2. Agent runs `Running-Workflow.ps1 -Ingest` or Python workflow CLI, preserving TCX in a private archive, and reads analyzer-generated `running-activities.json`.
3. Agent checks earlier confirmed facts and asks **only essential, unanswered** questions (sensations, treadmill readings, actual HR sensor).
4. Agent updates cumulative `running-metadata.json` using the safe metadata merge command and rebuilds derived `running-history.json`.
5. Agent analyzes the current session and comparable history using the enriched JSON. If no user facts are provided, unknown fields remain unknown.

See [`docs/AGENT_WORKFLOW.ru.md`](../docs/AGENT_WORKFLOW.ru.md) or the [English instructions](../docs/AGENT_WORKFLOW.md) for exact PowerShell/Python examples, file layout and safeguards.

## Rules and skills

- [`AGENTS.md`](AGENTS.md) — primary agent workflow and non-negotiable safeguards.
- [`rules/analysis.md`](rules/analysis.md) — interpretation and training safety.
- [`skills/analyze-running-tcx/SKILL.md`](skills/analyze-running-tcx/SKILL.md) — receive TCX, run analyzer, inspect its output.
- [`skills/maintain-running-metadata/SKILL.md`](skills/maintain-running-metadata/SKILL.md) — ask selective questions, preserve previous answers, safely merge user metadata.
- [`skills/compare-running-history/SKILL.md`](skills/compare-running-history/SKILL.md) — compare the cumulative enriched history.

## Connecting to an AI / Подключение

- **Explicit:** attach these files, or point the agent at them and instruct it to read them.
- **Agents with AGENTS.md discovery:** copy/activate `agent/AGENTS.md` at the repository's recognized entry point, updating relative paths if needed. Simply leaving `agent/AGENTS.md` in this directory does **not** guarantee activation.
- **Skill-aware agents:** register the actual skills directory as documented by the agent platform, or copy the individual `skills/<name>` folders into its discovery directory (for example `.agents/skills/` where supported).
- **Plain chat:** without a connected local workspace and execution permissions it can draft outputs but **cannot automatically run Python or change your computer's files**.

Personal training data is confidential and must stay out of the public repository. The sample patches/TCX in `examples/` and `tests/fixtures/` are **synthetic**.
