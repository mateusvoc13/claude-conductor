---
description: Verify a change end-to-end, simplify it, and open a PR.
---

Take the work on the current branch to a mergeable state. Do it in this order and don't
skip the verification:

1. **Test it end-to-end.** Run the real verification for this change — the test suite,
   a typecheck, hitting the endpoint, or driving the UI. Don't claim it works without
   running something that proves it. If it fails, fix and re-run until green.

2. **Simplify.** Re-read the diff with fresh eyes. Remove anything that doesn't earn its
   place — dead code, needless abstraction, over-broad changes. Keep it focused on the
   one thing this branch is for.

3. **Open the PR.** Write a context-rich description: what changed, why, and how it was
   verified (paste the passing output). Keep the diff small.

If any step can't be completed, stop and say so plainly — don't paper over a red test or
an unverifiable change.
