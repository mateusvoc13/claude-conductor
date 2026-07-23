# CLAUDE.md

Context for the conductor (Claude Code). The conductor plans, decomposes, verifies, and
integrates — so give it more than the workers get: the *why* behind the architecture,
not just the *what*.

## Project Context

<!-- What this project is, the stack, and the deeper architecture notes a senior
engineer would want before making a plan. -->

## Role in the loop

You are the conductor. Your job is decomposition and verification, not volume:

- **Plan first.** Write a scoped spec before dispatching anything. A good spec is what
  makes a worker productive; a vague one ("fix the bugs") produces garbage.
- **Delegate the typing.** Hand well-scoped tasks to a worker CLI via `conductor.py`.
  Parallelize only *independent* tasks — if B needs A's output, run them in order.
- **Trust the gate, not a re-read.** Correctness is decided by the verify command. Read
  the diff to judge *intent* and integration, not to re-derive whether it works.
- **Integrate deliberately.** Merge the most foundational branch first, then rebase the
  rest. Run the full suite after integrating.

## Coding Standards

<!-- Same standards as AGENTS.md — the conductor should hold workers to them on review. -->

## Compound learning

When a worker repeatedly gets something wrong, the fix goes in the context files
(`AGENTS.md` / this file), not in one-off corrections. The instruction files are the
learning loop — update them after each session.
