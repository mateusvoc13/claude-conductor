# Contributing

The most useful contribution is a **new worker lane**. The loop is worker-agnostic — the
only thing that changes per worker is the invocation. Adding one is copying a function
and swapping the command.

## Add a worker lane

1. **Pin the CLI's headless flags.** Run `<cli> --help` and find the equivalents of:
   - run a single task non-interactively (Grok: `--single`; Codex: `exec`)
   - auto-approve tool use / no prompts (Grok: `--always-approve`; Codex:
     `-c approval_policy="never" -s workspace-write`)
   - set the working directory (Grok: `--cwd`; Codex: `--cd`)
   - structured/JSON output if available (Grok: `--output-format json`; Codex: `--json`)
   - a self-verify pass, if the CLI has one (Grok: `--check`)

2. **Copy `dispatch_grok`** in `conductor.py`, rename it `dispatch_<worker>`, and swap
   the `cmd` list for the flags you pinned. Keep the rest identical: worktree isolation
   via `_new_worktree`, the deterministic gate via `_verify`, and the `WorkerResult`
   return.

3. **Register it** in the `LANES` dict so `SIDEKICK_WORKER=<worker>` works from the CLI.

4. **Add a row** to the worker-lanes table in `README.md`.

5. **Prove it** with a run of `examples/demo.sh` (`SIDEKICK_WORKER=<worker> bash
   examples/demo.sh`) and paste the resulting `WorkerResult` in the PR — `verify_passed:
   true`, and confirm `main` in the demo repo was untouched.

### First good PR: the Kimi lane

`dispatch_kimi` in `conductor.py` is a documented stub. The `kimi` CLI is
Anthropic-protocol compatible, so it should mirror `dispatch_grok` closely. Pin its
headless flags and wire it up.

## Keep in mind

- **No dependencies.** `conductor.py` is standard-library Python only, on purpose — the
  demo has to run on a clean machine. Keep it that way.
- **Sandbox defaults matter.** Default a lane to its *sandboxed* invocation. If the CLI
  has a "bypass all sandboxing" mode, document it as a commented opt-in, not the default.
- **Don't route regulated data through hosted workers.** See the Safety section of the
  README.
