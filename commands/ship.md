---
description: Jump straight to the sc-ship stage (docs + verify + PR + cleanup) when the required upstream gates are green. Refuses to ship if any required gate is unmet.
disable-model-invocation: true
allowed-tools: Bash Read
---

Fast-forward the active ship-cycle run to its ship stage.

!`slug="$(git branch --show-current | tr '/' '-')"; if [ -z "$slug" ]; then echo "NO_BRANCH"; else cat ".claude/ship-cycle/$slug.json" 2>/dev/null || echo "NO_STATE"; fi`

If the output is `NO_BRANCH` (detached HEAD): ship-cycle state is keyed by branch — report there is no run
to ship and stop. If it is `NO_STATE` (no file for the current branch): report there is no active run to
ship and stop.

**Gate check before shipping** — the ship stage must not run on an unfinished cycle. From `gates`, verify
the required upstream gates are `pass`: **G1** (agreed criteria), **G2/G3** (design + critic), **G4**
(failing tests / Red), **G5/G6/G7/G7b** (build + coverage + artifact + boot smoke where required), **G8**
(review: 0 Critical/High), **G9** (QA: no new defects).

- A **conditional gate that is legitimately N/A** counts as satisfied even though it shows `—`, not `pass`:
  **G7** when no artifact ships, **G7b** when the nature declares no `bootCheck`. Treat these as met.
- If **any** required gate is missing or genuinely not `pass` (a `fail`, or `—` on a gate that *does*
  apply): report exactly which gates are unmet and refuse to ship — point back to the stage that owns each
  failing gate (e.g. G8 → `sc-review`). Do **not** skip a gate, and never open a PR when a required gate is
  unmet (Iron Law #3).
- If **all** required gates pass: invoke the `sc-ship` skill to run stage 7 — G10 (docs match the change),
  G11 (every claim mapped to evidence), G12 (build/test/review/QA green + clean merge + `Closes`/`Refs`
  tokens; base = overlay `vcs.defaultBase`), then G13 cleanup (delete branch local+remote, remove the
  worktree if present, sync base).
