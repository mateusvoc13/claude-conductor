#!/usr/bin/env bash
# End-to-end demo of the conductor -> worker -> verify loop.
#
# Builds a throwaway git repo with a failing stub + a test, dispatches the task to a
# worker CLI headless in an isolated worktree, and prints the resulting WorkerResult.
# Nothing here touches your real projects.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKER="${SIDEKICK_WORKER:-grok}"

# --- Preflight: is a worker CLI actually installed? ------------------------------------
if ! command -v "$WORKER" >/dev/null 2>&1; then
  cat <<EOF
This demo needs a worker CLI on your PATH. None found for: $WORKER

Install one, then re-run:
  • Grok CLI   ->  https://docs.x.ai/  (then: export SIDEKICK_WORKER=grok)
  • Codex CLI  ->  npm i -g @openai/codex  (then: export SIDEKICK_WORKER=codex)

The loop is worker-agnostic — the only thing that changes per lane is the invocation
inside conductor.py.
EOF
  exit 0
fi

# --- Build a throwaway repo ------------------------------------------------------------
SANDBOX="$(mktemp -d)"
trap 'rm -rf "$SANDBOX"' EXIT
REPO="$SANDBOX/demo-app"
mkdir -p "$REPO"
cd "$REPO"

git init -q
git config user.email demo@example.com
git config user.name "conductor demo"

cat > fizzbuzz.py <<'PY'
def fizzbuzz(n: int) -> str:
    """Return 'Fizz' for multiples of 3, 'Buzz' for 5, 'FizzBuzz' for both, else str(n)."""
    raise NotImplementedError  # <- the worker's job is to make the test below pass
PY

# Uses stdlib `unittest` so the verify gate needs no pip install — the demo stays green
# on a clean machine. (In a real repo, point the gate at your own runner, e.g.
# ./venv/bin/pytest -q — see the "gotcha" note in the README.)
cat > test_fizzbuzz.py <<'PY'
import unittest
from fizzbuzz import fizzbuzz


class TestFizzBuzz(unittest.TestCase):
    def test_cases(self):
        self.assertEqual(fizzbuzz(1), "1")
        self.assertEqual(fizzbuzz(3), "Fizz")
        self.assertEqual(fizzbuzz(5), "Buzz")
        self.assertEqual(fizzbuzz(15), "FizzBuzz")


if __name__ == "__main__":
    unittest.main()
PY

git add -A
git commit -qm "stub: failing fizzbuzz"

# --- Dispatch + verify -----------------------------------------------------------------
echo "==> Dispatching to '$WORKER' in an isolated worktree; verify gate = python3 -m unittest"
echo

SIDEKICK_WORKER="$WORKER" python3 "$HERE/conductor.py" \
  "$REPO" \
  "Implement fizzbuzz() in fizzbuzz.py so test_fizzbuzz.py passes. Do not edit the test." \
  -- python3 -m unittest -q test_fizzbuzz

echo
echo "==> Done. 'main' in the demo repo was never touched — the worker's changes live on"
echo "    its own branch/worktree. In real use the conductor reads the diff above, judges"
echo "    intent, integrates the branch, and calls cleanup()."
