# claude-conductor

You hand Claude Code a real task and watch it work. The plan is good. Then it spends
the next twenty minutes typing out boilerplate, running the test suite, fixing a lint
error, running the suite again — the grunt work. And you pay for all of it with the one
thing that actually runs out: the good model's budget. By mid-afternoon you've hit the
ceiling, and you wait for the reset.

The fix isn't a bigger model. It's noticing the smart model shouldn't be the one doing
the typing.

`claude-conductor` flips the roles. Claude Code becomes the **conductor** — it plans,
decomposes, and decides what "done" means. The typing goes to a cheaper, faster CLI
(Grok, Codex, more later) running **headless in an isolated git worktree**. A
**deterministic verify command** — your tests — decides whether the work is correct.
The conductor reads the diff, checks it matches intent, and integrates it. It never
regenerates the work.

That last part is the whole game. The conductor spends its budget only on the two things
that need judgment — decomposition and verification — and lets a worker do the volume.
It's maybe two hundred lines of Python. The idea is what matters, not the code.

```
   ┌─────────────┐   scoped spec    ┌──────────────────────────┐
   │  CONDUCTOR  │ ───────────────▶ │  WORKER CLI (headless)   │
   │ (Claude Code)│                  │  grok / codex / ...      │
   │             │                  │  in its own git worktree │
   │  plans      │                  └────────────┬─────────────┘
   │  verifies   │                               │ diff
   │  integrates │       WorkerResult (JSON)     ▼
   │             │ ◀─────────────────── ┌──────────────────────┐
   └─────────────┘   diff + pass/fail   │  DETERMINISTIC GATE  │
         │                              │  pytest / tsc / lint │
         │ judges *intent* on the diff  └──────────────────────┘
         ▼
    integrate (or send back) — never regenerate
```

## Why this shape

The interesting decision here is economic, not technical.

Worker CLIs increasingly run on **flat monthly plans**. A worker call is close to free
at the margin — you're bounded by the plan's rate limits, not by dollars per token.
Per-token API math doesn't apply. The scarce resource is the **conductor's** quota.

So the strategy inverts from "spend the smart model on everything":

- **Delegate the typing lavishly.** Volume is cheap on the worker side.
- **Spend the conductor only on planning and verification.** Correctness is decided by
  the deterministic gate — tests, not the conductor re-reading code. The conductor only
  adjudicates *intent* on the diff, which is a small read.
- **Let the worker self-verify first.** `grok --check` spawns its own verifier subagent,
  so the conductor receives already-green work and rarely has to send anything back.

## Worker lanes

| Lane | CLI | Notes | Status |
|------|-----|-------|--------|
| **Grok** | `grok --single` | Fast agentic coding; `--check` self-verify built in | proven |
| **Codex** | `codex exec` | Scoped coding from clear specs; sandbox modes; `codex exec review` as an optional second gate | proven |
| **Kimi** | `kimi` | Anthropic-protocol compatible; large context | stub — [PRs welcome](CONTRIBUTING.md) |

Adding a lane is copying one function and swapping the invocation. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## Quickstart

```bash
git clone https://github.com/mateusvoc13/claude-conductor
cd claude-conductor

# Run the end-to-end demo against a throwaway repo.
# Requires one worker CLI installed (grok or codex); prints how to install if neither is.
bash examples/demo.sh
```

Call it directly on a real repo:

```bash
# default lane is grok
python3 conductor.py ./my-app "implement the parser, make the tests pass" -- pytest -q

# pick a lane
SIDEKICK_WORKER=codex python3 conductor.py ./my-app "..." -- ./venv/bin/pytest -q
```

It prints a `WorkerResult` as JSON: the branch and worktree it used, whether verify
passed, the diff, and the tail of the worker's log. From there the conductor (or you)
integrates the branch and calls `cleanup()`.

`conductor.py` is standard-library Python only — no dependencies to install.

## Wiring it into your own repo

The worker follows whatever context files your CLIs read. Start from the templates:

- [`templates/AGENTS.md`](templates/AGENTS.md) — context for Codex / Grok workers
- [`templates/CLAUDE.md`](templates/CLAUDE.md) — context for the conductor
- [`.claude/commands/go.md`](.claude/commands/go.md) — a `/go` command: test → simplify → PR
- [`scripts/worktree.sh`](scripts/worktree.sh) — spin a worktree for hands-on work
- [`scripts/review-queue.sh`](scripts/review-queue.sh) — list open worker PRs to review

The better the context files and the tighter the verify command, the less the conductor
has to do. That's where the leverage is.

## Safety

- **Worktree isolation.** Every worker runs on its own branch in its own worktree, so
  parallel workers never collide and `main` is never touched until you integrate.
- **Sandbox by default.** The Codex lane defaults to `workspace-write` (no prompts, but
  scoped to the workspace). A `--dangerously-bypass-approvals-and-sandbox` variant is
  documented as a commented opt-in — only sane inside an already-ephemeral environment.
- **Don't route regulated data through hosted workers.** Sending *code* to a hosted
  third-party model is fine. Sending regulated user data — health records, personal PII,
  payment data — is not. For sensitive work, self-host an open-weights model.
- **One gotcha worth internalizing:** the verify command runs *outside* the worker's
  environment. Point it at the interpreter that actually has your dependencies
  (`./venv/bin/pytest`, not bare `python3 -m pytest`) or the gate will false-red on
  green work.

## The bet behind it

The model layer is commoditizing. Coding CLIs are converging on speed, price, and
distribution, and they read each other's context files. The durable, portable thing
isn't which model you picked this month — it's the setup you build around them: the
decomposition, the verify gates, the context files, the orchestration. Pick your tools
loosely. Build your setup like it'll outlive them.

This repo is one concrete instance of that setup. It's tool-agnostic on purpose — swap
the lanes as the models move.

## Prior art

- Boris Cherny's plan-then-verify discipline for Claude Code (plan first; let the agent
  verify its own work; verification as a quality multiplier).
- Designpowers / Superpowers (MC Dean, Jesse Vincent) for the specialist-agents +
  explicit-handoff pattern.

## License

MIT — see [LICENSE](LICENSE).
