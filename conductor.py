#!/usr/bin/env python3
"""Conductor -> worker-CLI dispatcher.

Claude Code is the conductor: it plans, writes a scoped spec, and hands the task to a
cheaper/faster coding CLI (Grok, Codex, ...) running HEADLESS in an isolated git
worktree. It waits, then runs a DETERMINISTIC verify command (tests / typecheck / lint)
and reads back a structured result to judge *intent* and integrate -- WITHOUT
regenerating the work.

That split is the whole point. On flat monthly worker plans, a worker call is ~free at
the margin (bounded by the plan's rate limits, not $/token). The scarce resource is the
conductor's own quota. So: delegate the typing lavishly, and spend conductor cycles only
on decomposition + verification.

Why this protects the conductor's budget:
  - The worker self-verifies before returning (e.g. `grok --check`), so the conductor
    receives already-green work.
  - Correctness is decided by the deterministic gate (tests), not by the conductor
    re-reading code.
  - The conductor only adjudicates *intent* on the diff -> a small read, not a
    regeneration.

Guardrails:
  - Each worker gets its own git worktree, so parallel edits never collide.
  - Data handling: do NOT route regulated data (health records, personal PII, payment
    data) through a hosted third-party model endpoint. For sensitive work, self-host an
    open-weights model. Routing *code* through a hosted worker is fine; routing
    regulated user data through one is not.

Gotcha (all lanes): the deterministic verify_cmd runs OUTSIDE the worker's environment,
so point it at the SAME interpreter that has the deps (e.g. ['./venv/bin/pytest'], not
bare ['python3', '-m', 'pytest']) or the gate reports a false red on green work.

Usage (standalone):
    python3 conductor.py <repo> "<task>" -- <verify cmd...>
    python3 conductor.py ./app "implement X, make tests pass" -- pytest -q

    # pick the worker lane (default: grok)
    SIDEKICK_WORKER=codex python3 conductor.py ./app "..." -- pytest -q
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class WorkerResult:
    worker: str
    branch: str
    worktree: str
    exit_code: int | None
    timed_out: bool
    duration_s: float
    verify_passed: bool | None
    verify_output: str
    diff: str
    log_tail: str


def _run(cmd, cwd=None, timeout=None):
    return subprocess.run(cmd, cwd=cwd, timeout=timeout, text=True, capture_output=True)


def _new_worktree(repo_path: Path, worker: str) -> tuple[str, Path, str]:
    """Create an isolated worktree + branch. Returns (branch, worktree_path, tag)."""
    tag = uuid.uuid4().hex[:8]
    branch = f"{worker}/{tag}"
    worktree = repo_path.parent / f"{repo_path.name}--{worker}-{tag}"
    _run(["git", "worktree", "add", str(worktree), "-b", branch],
         cwd=repo_path).check_returncode()
    return branch, worktree, tag


def _verify(worktree: Path, verify_cmd: list[str] | None) -> tuple[bool | None, str]:
    """Run the deterministic gate. Cheap, and costs the conductor zero tokens."""
    if not verify_cmd:
        return None, ""
    v = _run(verify_cmd, cwd=worktree, timeout=300)
    return v.returncode == 0, ((v.stdout or "") + (v.stderr or "")).strip()


def dispatch_grok(
    repo: str,
    task: str,
    verify_cmd: list[str] | None = None,
    model: str = "grok-4.5",
    effort: str = "high",
    timeout_s: int = 900,
    self_check: bool = True,
) -> WorkerResult:
    """Hand `task` to the Grok CLI headless in an isolated worktree, then verify.

    Proven invocation (grok CLI v0.2.103):
        grok --single "<task>" --output-format json --always-approve --check \\
             --cwd <worktree> --model grok-4.5 --effort high

    `--check` spawns Grok's own verifier subagent, so the work is already self-verified
    before it comes back to the conductor.
    """
    repo_path = Path(repo).resolve()
    branch, worktree, _ = _new_worktree(repo_path, "grok")

    cmd = [
        "grok", "--single", task,
        "--output-format", "json",
        "--always-approve",
        "--model", model,
        "--effort", effort,
        "--cwd", str(worktree),
    ]
    if self_check:
        cmd.append("--check")

    started = time.monotonic()
    timed_out = False
    try:
        proc = _run(cmd, cwd=worktree, timeout=timeout_s)
        exit_code = proc.returncode
        log = (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired as e:
        timed_out, exit_code = True, None
        log = (e.stdout or "") if isinstance(e.stdout, str) else "timed out"
    duration = round(time.monotonic() - started, 1)

    diff = _run(["git", "diff", "HEAD"], cwd=worktree).stdout
    verify_passed, verify_output = _verify(worktree, verify_cmd)

    return WorkerResult(
        worker="grok", branch=branch, worktree=str(worktree),
        exit_code=exit_code, timed_out=timed_out, duration_s=duration,
        verify_passed=verify_passed, verify_output=verify_output[-3000:],
        diff=diff, log_tail=log.strip()[-3000:],
    )


def dispatch_codex(
    repo: str,
    task: str,
    verify_cmd: list[str] | None = None,
    model: str | None = None,   # None -> use ~/.codex/config.toml default
    effort: str = "high",
    timeout_s: int = 900,
    sandbox: str = "workspace-write",
) -> WorkerResult:
    """Hand `task` to the Codex CLI headless in an isolated worktree, then verify.

    Mirrors dispatch_grok; only the invocation differs. Codex has NO built-in `--check`
    self-verifier, so correctness rests entirely on the deterministic `verify_cmd` gate
    here (which is load-bearing anyway). Optionally reinforce by asking the task itself
    to run the verify before finishing, or add a `codex exec review` second pass.

    Flag mapping vs grok: exec (=--single), -c approval_policy=never + -s workspace-write
    (=--always-approve), --cd (=--cwd), -m (=--model), -c model_reasoning_effort
    (=--effort), --json (=--output-format json).

    Note: `workspace-write` disables network by default. If the worker itself must hit
    the network (e.g. `pip install` before its own test run), pass
    sandbox="danger-full-access" or add `-c sandbox_workspace_write.network_access=true`.
    The conductor's own verify_cmd runs OUTSIDE the sandbox, so it always has network.
    """
    repo_path = Path(repo).resolve()
    branch, worktree, _ = _new_worktree(repo_path, "codex")

    # Default: sandboxed + never-prompt. The worktree isolates edits; the sandbox
    # isolates the rest of the machine.
    cmd = [
        "codex", "exec", task,
        "--json",
        "--cd", str(worktree),
        "-s", sandbox,
        "-c", 'approval_policy="never"',
        "-c", f'model_reasoning_effort="{effort}"',
    ]
    if model:
        cmd += ["-m", model]

    # Opt-in alternative (drops the sandbox entirely, trusting the worktree as the only
    # boundary -- faster, but only sane inside an already-isolated/ephemeral environment):
    #   cmd = ["codex", "exec", task, "--json", "--cd", str(worktree),
    #          "--dangerously-bypass-approvals-and-sandbox", "--skip-git-repo-check"]

    started = time.monotonic()
    timed_out = False
    try:
        proc = _run(cmd, cwd=worktree, timeout=timeout_s)
        exit_code = proc.returncode
        log = (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired as e:
        timed_out, exit_code = True, None
        log = (e.stdout or "") if isinstance(e.stdout, str) else "timed out"
    duration = round(time.monotonic() - started, 1)

    diff = _run(["git", "diff", "HEAD"], cwd=worktree).stdout
    verify_passed, verify_output = _verify(worktree, verify_cmd)

    return WorkerResult(
        worker="codex", branch=branch, worktree=str(worktree),
        exit_code=exit_code, timed_out=timed_out, duration_s=duration,
        verify_passed=verify_passed, verify_output=verify_output[-3000:],
        diff=diff, log_tail=log.strip()[-3000:],
    )


def dispatch_kimi(*args, **kwargs) -> WorkerResult:
    """TODO -- good first contribution.

    The `kimi` CLI (Node) is Anthropic-protocol compatible, so this lane should mirror
    dispatch_grok closely. To wire it: confirm the CLI is installed, pin its headless
    flags (`kimi --help`), then copy dispatch_grok and swap the invocation. See
    CONTRIBUTING.md for the "add a worker lane" checklist.
    """
    raise NotImplementedError(
        "Kimi lane not wired yet -- pin `kimi` headless flags first (see CONTRIBUTING.md)"
    )


# Registry so the CLI (and callers) can look up a lane by name.
LANES = {
    "grok": dispatch_grok,
    "codex": dispatch_codex,
    "kimi": dispatch_kimi,
}


def cleanup(repo: str, res: WorkerResult) -> None:
    """Remove the worker's worktree + branch once its diff has been integrated."""
    repo_path = Path(repo).resolve()
    _run(["git", "worktree", "remove", "--force", res.worktree], cwd=repo_path)
    _run(["git", "branch", "-D", res.branch], cwd=repo_path)


def _usage() -> str:
    return (
        "usage: python3 conductor.py <repo> \"<task>\" [-- <verify cmd...>]\n"
        "       SIDEKICK_WORKER={grok|codex} python3 conductor.py ./app \"...\" -- pytest -q\n"
        "\n"
        "Dispatches <task> to a worker CLI headless in an isolated git worktree, runs the\n"
        "verify command, and prints a WorkerResult as JSON. Worker defaults to 'grok'."
    )


def main(argv: list[str]) -> int:
    if "--" in argv:
        i = argv.index("--")
        head, verify = argv[:i], argv[i + 1:]
    else:
        head, verify = argv, []

    if len(head) < 2:
        print(_usage(), file=sys.stderr)
        return 2

    repo, task = head[0], head[1]
    worker = os.environ.get("SIDEKICK_WORKER", "grok").lower()
    fn = LANES.get(worker)
    if fn is None:
        print(f"unknown worker '{worker}' -- choose one of: {', '.join(LANES)}",
              file=sys.stderr)
        return 2

    result = fn(repo, task, verify_cmd=verify or None)
    print(json.dumps(asdict(result), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
