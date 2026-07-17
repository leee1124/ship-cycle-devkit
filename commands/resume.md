---
description: Resume an interrupted ship-cycle from its state file, continuing at the last incomplete stage (does not restart completed stages or re-init state).
disable-model-invocation: true
allowed-tools: Bash Read
---

Resume a mid-pipeline ship-cycle run.

!`slug="$(git branch --show-current | tr '/' '-')"; if [ -z "$slug" ]; then echo "NO_BRANCH"; else cat ".claude/ship-cycle/$slug.json" 2>/dev/null || echo "NO_STATE"; fi`

If the output is `NO_BRANCH` (detached HEAD): ship-cycle state is keyed by branch — report there is no
branch to resume and stop.

If the output is `NO_STATE` (no file for the current branch): a legacy bare `.claude/.ship-cycle-state.json`
from an older version may still hold this branch's run — invoke the `ship-cycle` PREFLIGHT resume path,
which **migrates** a branch-matching legacy file (move) and resumes from it (migration is PREFLIGHT-only;
this command doesn't move files itself). If there is genuinely no state for this branch, report there is
nothing to resume and suggest starting a run with `/ship-cycle-devkit:ship-cycle <goal>`; then stop.

If the state's `stage` is a terminal value (`complete` / `failed` / `cancelled`): report that the last run
already finished (name the outcome) and do **not** resume — suggest a fresh run instead.

Otherwise, resume via the `ship-cycle` skill's PREFLIGHT resume path:

1. Re-read the state; confirm the recorded `branch` (and `worktreePath`, if set) still exist and are
   checked out. If the branch/worktree is gone, say so and stop — don't guess.
2. Continue from the **last incomplete stage** (`stage`) forward through the remaining gates, honoring the
   recorded `models`, `nature`, `risk`, `baseline`, and per-gate `loops` (respect the orchestrator's loop
   cap).
3. Do **not** restart already-`pass` stages and do **not** re-initialize the state file — pick up exactly
   where the run left off.
