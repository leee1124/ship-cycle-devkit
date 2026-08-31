---
description: Print the current ship-cycle run status — stage, gate table (G1–G13), loop counts, resolved model routing, and worktree — from the state file. Read-only.
disable-model-invocation: true
allowed-tools: Bash Read
---

Show the current ship-cycle run status by reading its state file (read-only — never modify it).

!`slug="$(git branch --show-current | tr '/' '-')"; if [ -z "$slug" ]; then echo "NO_BRANCH"; else cat ".claude/ship-cycle/$slug.json" 2>/dev/null || echo "NO_STATE"; fi`

All cycles in this working directory (`.claude/ship-cycle/` — this cwd only, not sibling worktrees;
includes the current branch's own file):

!`ls .claude/ship-cycle/*.json 2>/dev/null || echo "(none)"`

If the first output is `NO_BRANCH`, you are on a **detached HEAD** — ship-cycle state is keyed by branch, so
there is no run to inspect here; report that and stop.

If it is `NO_STATE` (no file for the current branch), report that no ship-cycle run is active on this branch
— suggest starting one with `/ship-cycle-devkit:ship-cycle <goal>` — and stop. (Caveat: right after
upgrading the plugin mid-cycle, a legacy bare `.claude/.ship-cycle-state.json` is migrated only on the next
PREFLIGHT, so a read-only `/status` may briefly show `NO_STATE` for a live run — `/resume` or the next stage
migrates and recovers it.)

Use the **All cycles** list to see co-located concurrent cycles (multiple branch files can coexist in one
`.claude/ship-cycle/`); it does **not** reach sibling worktrees, which hold their own state.

Otherwise parse the JSON and print a compact, scannable status report:

- **Goal** and **branch** (plus `worktreePath` if one was created).
- **Current stage** (`stage`) and its position in the pipeline:
  `sc-brainstorm → sc-design → sc-tdd → sc-implement → sc-review → sc-qa → sc-ship`.
- **Gate table** — for **G1–G13**, show `pass` / `fail` / `—` (not yet reached) from `gates`.
- **Loop counts** per gate from `loops`; the loop cap is 3 per gate — flag any gate that has hit the cap.
- **Resolved model routing** from `models` (per stage) and **effort** from `effort`.
- **Change nature** (`nature`), **risk** (`risk`), and **size tier** (`size` — S/M/L).
- **Baseline**: the count of pre-existing failures (`baseline.failing`) and, separately, the suites this
  environment **cannot run** (`baseline.unrunnableHere`) with each one's `reason` — these are quarantined,
  neither passing nor regressed. Never fold the two counts together: a quarantine is not a red test. Print
  each entry's `capturedAt` and **flag anything that is not `preflight` as added mid-cycle** — that is a
  finding to check, not a quarantine to trust.
- **Review jobs** from `reviewJobs`: for each, the reviewer, lens, `status` and **age** (`startedAt` to
  now). Print a `running` job **loudly** — the cycle is not judgeable while one is in flight — and print a
  `timeout`/`failed` one with its id, since it owes a pre-merge manual-gate item.
- **Git-write freeze** from `gitFreeze`: when `active`, say so first and name the branch, the reason and
  how long it has been held. A held freeze means **an out-of-process reviewer is reading this branch**:
  commits, checkouts and rebases must wait (§sc-review). An `active` freeze with **no** `running` job is a
  **stale freeze** — flag it as a finding to release, not a state to respect forever.
- **Cost so far** from `telemetry`: one row per completed stage (tier / model / effort, plus tokens or cost
  where the host exposed them), the running total, and which risk-gated upgrades fired
  (`telemetry.upgrades`). Print `unavailable` for any figure the host didn't provide — **never estimate
  one**; an invented cost table is worse than an honest gap. Absent `telemetry` (a run started before this
  was recorded), say so and print the routing alone.

Keep it terse. Do not run any stage, and do not write to the state file.
