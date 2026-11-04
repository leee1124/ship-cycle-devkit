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

A `parked` stage is not terminal: resume it below.

Otherwise, resume via the `ship-cycle` skill's PREFLIGHT resume path:

1. Re-read the state; confirm the recorded `branch` (and `worktreePath`, if set) still exist and are
   checked out. If the branch/worktree is gone, say so and stop — don't guess.
   If `stage` is `parked`, print `parked.reason`, `parked.resumeStage` and how long it has been parked;
   the stage to continue from starts as `resumeStage`.
2. **Run the resume reconcile** (§`${CLAUDE_PLUGIN_ROOT}/docs/state-file.md` — Resume reconcile) before
   anything else: print its mismatches and the stage it picks, append the entry to `reconcile`, then clear
   `parked` to `null`. The reconcile may only move the stage earlier or clear a `pass` — never record one.
3. Continue from the **stage the reconcile picked** (the recorded `stage`, or `parked.resumeStage`, when it
   found no mismatch) forward through the remaining gates, honoring the
   recorded `models`, `effort`, `nature`, `risk`, `size`, `baseline` (**including its `unrunnableHere`
   quarantine, which is read-only on resume** — resuming is not an occasion to re-derive it; §ship-cycle
   Stage 0.5), and per-gate `loops` (respect the orchestrator's loop cap — parking and resuming never reset them). Keep **appending** to
   `telemetry` rather than restarting it — a resumed run's cost readout must cover the whole run, not just
   the part after the resume. If `size` is absent (a run
   started before it was recorded), classify it now per §Stage 0.2 (Change-size tier) — but only **upward**
   from what the completed stages imply: resuming is not an occasion to re-tier a cycle downward.
4. Do **not** restart stages still recorded `pass` after the reconcile — or `"n/a: <reason>"`, which is a decision the
   resumed run inherits rather than re-makes — and do **not** re-initialize the state file; pick up exactly
   where the run left off.
5. **If `bakeOff` holds candidates but no winner, resume by judging what exists** — or by re-fanning only
   the stances whose `docPath` is missing. Restarting all N discards finished work and re-spends the
   multiplier this mode exists to justify; the criteria were fixed before the fan-out and are not re-opened
   on resume.
6. **If `reviewJobs` holds a `running` entry, resume by polling it — never by relaunching.** Run that
   reviewer's declared `status` command against the recorded `id`; a relaunch abandons a job that may be
   half an hour in and starts the clock again. If the job is gone on the host side (the process died with
   the previous session), mark it `failed` with that reason and re-launch deliberately, counting it against
   G8's loop cap. Jobs named in `parked.holds.reviewJobs` are polled the same way. Honor `gitFreeze` on resume exactly as mid-run: if it is `active`, do not move the branch
   until it is released — and if it is active with **no** `running` job, release it and say so.
