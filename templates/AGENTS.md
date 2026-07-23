# AGENTS.md

Context for worker CLIs (Codex, Grok, and other `AGENTS.md`-reading tools). Keep it
human-curated and short. This file is the worker's whole view of the project — the
tighter it is, the less the conductor has to correct afterward.

## Project Context

<!-- What this project does, the tech stack, and the two or three patterns a newcomer
must know before touching code. One paragraph. -->

## Coding Standards

<!-- Style, naming, and testing conventions. Point at existing examples rather than
restating a style guide. -->

- Match the patterns already in the file you're editing.
- Add a test for any new behavior.
- Don't add dependencies without them being asked for.

## Review Guidelines

- Run the tests before finishing. Green is the bar, not "looks right."
- Keep changes small and focused — one concern per task.
- Don't touch files outside the scope of the task.
- Don't make architecture decisions on your own; if the task implies one, stop and say so.

## Architecture

<!-- Key directories, how data flows, where things live. Enough for the worker to place
new code correctly without guessing. -->
