# Repository agent entry point

This repository develops an **offline Python running analyzer**. For normal code-development requests, use standard engineering practices and run synthetic unit tests; never add private athlete TCX, sensor data, user metadata or personal reports to Git.

**Only when the user opts into running-workout analysis or history maintenance:** read `agent/AGENTS.md`, `agent/rules/analysis.md`, `docs/AGENT_WORKFLOW.md`, and the relevant `agent/skills/*/SKILL.md` files. The preferred workflow starts with the **user supplying TCX**, not with them executing a script or supplying a JSON. The agent executes the analyzer **only where it has authorized file and process access**, asks selectively about missing user-reported context, safely updates `running-metadata.json`, rebuilds `running-history.json`, and reports measurements separately from subjective facts. Never pretend to have written local files when the environment lacks those capabilities.

This file helps agents that discover root-level `AGENTS.md`. Actual skill registration, execution permissions and environment discovery remain agent-specific; see `agent/README.md`.

For v1.4.0 outdoor tasks, read `docs/OUTDOOR_RUNNING.md`: GPS coordinates are private, pause detection and activity classification are heuristics, and batch reports may contain multiple exports of one Garmin Activity ID. Tests may only use fabricated coordinate fixtures.
