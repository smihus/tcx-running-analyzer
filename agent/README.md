# Optional AI agent pack / Дополнительные правила и скилы

This directory contains **optional**, human-readable instructions for an AI assistant analyzing output produced by **Garmin TCX Running Analyzer**. It is not imported by the Python tool and is not automatically applied to anyone's AI assistant. Nothing here is needed for normal TCX conversion.

## Contents

- [`AGENTS.md`](AGENTS.md) — entry instructions for a repository-aware agent.
- [`rules/analysis.md`](rules/analysis.md) — reliable interpretation and safety constraints; no invented treadmill speed or subjective feelings.
- [`skills/analyze-running-tcx/SKILL.md`](skills/analyze-running-tcx/SKILL.md) — how to interpret one activity JSON and produce a short report.
- [`skills/compare-running-history/SKILL.md`](skills/compare-running-history/SKILL.md) — how to compare multiple workouts in a collection JSON.

## Manual installation / Ручное подключение

The exact way to connect instructions differs between AI tools. Generic options:

1. **Explicit loading:** attach or paste `agent/rules/analysis.md` and the chosen `SKILL.md` in the agent conversation. This works independently of auto-discovery support.
2. **Repository agent rules:** if your coding agent recognizes `AGENTS.md`, copy `agent/AGENTS.md` to your working repository's root *only if you want it active*; adapt paths to where the analyzer's output lives. Merely leaving it under `agent/` does **not** guarantee discovery.
3. **Skill-aware agents:** copy each desired skill folder into the agent's documented skills discovery directory (for example `.agents/skills/<skill-name>/` where supported), or register that directory explicitly. There is no universal automatic discovery across every agent.

The `SKILL.md` files have YAML frontmatter with `name` and `description` to facilitate compatible skill loaders.

**Важное:** правила интерпретации и скилы находятся отдельно от обычного приложения. Их можно не использовать; не копируйте их в корень репозитория, если не хотите включать агента. Не загружайте в публичный репозиторий личные TCX или отчёты с чувствительными данными.

## Typical workflow / Порядок работы

1. Generate `*.running.json` for a single TCX, or `running-activities.json` for a folder.
2. Read `quality.warnings` and verify recognized `runs`. If uncertain, review the original TCX.
3. If available, include user-entered treadmill distance/speed and subjective experience separately from automated metrics.
4. Send JSON to your AI assistant together with the selected skill/rules.
5. Ask for trends and practical training follow-ups, without treating HR metrics as clinical diagnosis.
