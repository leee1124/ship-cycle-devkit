---
description: Print the current ship-cycle run status — stage, gate table (G1–G13), loop counts, resolved model routing, and worktree — from the state file. Read-only.
disable-model-invocation: true
allowed-tools: Bash Read
---

Show the current ship-cycle run status by reading its state file (read-only — never modify it).

!`slug="$(git branch --show-current | tr '/' '-')"; if [ -z "$slug" ]; then echo "NO_BRANCH"; else cat ".claude/ship-cycle/$slug.json" 2>/dev/null || echo "NO_STATE"; fi`

Last rows of this cycle's gate log (append-only history,
§`${CLAUDE_PLUGIN_ROOT}/docs/state-file.md` — Gate log):

!`slug="$(git branch --show-current | tr '/' '-')"; f=".claude/ship-cycle/$slug.log.md"; if [ -n "$slug" ] && [ -f "$f" ]; then tail -n 8 "$f"; else echo "NO_LOG"; m="$(git worktree list --porcelain 2>/dev/null | sed -n '1s/^worktree //p')"; ls -t "$m/.claude/ship-cycle/archive/$slug"-[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]*.log.md 2>/dev/null | head -n 3; fi`

All cycles in this working directory (`.claude/ship-cycle/` — this cwd only, not sibling worktrees;
includes the current branch's own file), one line per file: stage, and for a parked one its reason, resume
stage, `at` and holds:

!`python3 -c 'import glob,json;fs=sorted(glob.glob(".claude/ship-cycle/*.json"));[print(f,"|",*(lambda s:[s.get("branch"),s.get("stage")]+([s.get("parked")] if s.get("stage")=="parked" else []))(json.load(open(f))),sep=" ") for f in fs] or print("(none)")' 2>/dev/null || ls .claude/ship-cycle/*.json 2>/dev/null || echo "(none)"`

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
- **Parked**: when `stage` is `parked`, say so first — `parked.reason`, `parked.resumeStage` (its place
  in the pipeline), and age since `parked.at` — and name any `parked.holds` (a held review job or freeze is
  still live while parked). In the **All cycles** list, print the same fields for every parked file; if
  that list fell back to bare file names (no `python3`, or a file that does not parse), say parked details for other cycles are
  unavailable rather than guessing.
- **Last reconcile** from `reconcile`, when present: the recorded stage, the stage it continued from, and
  its mismatches and cleared gates — a cleared `pass` is a finding, not a footnote.
- **Recent history** from the gate log: print its last few rows as they are (time, stage, gate, result,
  evidence). The gate table below comes from the state file, which is authoritative; if the latest log row
  for a gate disagrees with `gates`, say so rather than picking one. `NO_LOG` means the cycle started
  before 0.3.7, its log is missing, or it was archived — print any archive paths listed under it (the main
  checkout's `.claude/ship-cycle/archive/`, newest first by modification time — each archive's last write
  is its final row, so this orders `DATE.log.md` and its `-2`/`-3` siblings correctly; the glob is anchored
  on the date so `feat/a` does not list `feat/a-b`'s archives) so a finished cycle's history can still be
  found.
- **Gate table** — for **G1–G13**, show the value in `gates`: `pass` / `fail` / `—` (not yet reached) /
  a three-way value (`degrade`, `checklist`, `skip`) / `"n/a: <reason>"` (a stage deliberately skipped —
  print the reason, and never fold it in with `fail`).
- **Route plan** from `route`, when present: one line per stage — `run` or `skip` with its reason — then
  the lenses, the QA form, `confirmedAt` and `basis`. Absent (a cycle started before 0.3.13, or G1 not yet
  passed): say so; the tier then decides as before. Flag, loudly: a whole-stage gate (G2/G3, G4, G9) that
  is `n/a` while its stage's route entry is `run` — a skip the route did not plan, which G12 refuses — except
  a config `n/a` (`n/a: no <x> config`); and `size`/`risk` above `route.basis` with a skip still standing.
- **Loop counts** per gate from `loops`; the loop cap is 3 per gate — flag any gate that has hit the cap.
- **Resolved model routing** from `models` (per stage) and **effort** from `effort`.
- **Change nature** (`nature`), **risk** (`risk`), and **size tier** (`size` — S/M/L).
- **Baseline**: its `source` (`local` when absent) and, for a CI source, `baseline.run.ref` and any
  `rechecked` suites. Then the count of pre-existing failures (`baseline.failing`) — under
  `ci-status-only` print **"no failing set"** instead unless a suite was rechecked — and of
  `baseline.flaky` (not exempt); flag any `failing` entry carrying a `capturedAt` other than `preflight`
  (a bare string is `preflight`) as added mid-cycle. Separately, the suites this environment **cannot
  run** (`baseline.unrunnableHere`) with each one's `reason` — these are quarantined,
  neither passing nor regressed. Never fold the two counts together: a quarantine is not a red test. Print
  each entry's `capturedAt` and **flag anything that is not `preflight` as added mid-cycle** — that is a
  finding to check, not a quarantine to trust.
- **Coverage** from `coverage`, per nature: `result`, `percent` against `floor`, or the n/a string as
  written. Print any `undetermined` loudly with its `error`/`reason` (ci-deferred → G6 `checklist`), and flag an
  entry — or a `baseline.coverage` one — whose `reportMtime ≤ runStartedAt` as stale.
- **Release smoke** from `releaseSmoke`, per nature: `result`, each flow, any `deferred` parts, or the `n/a`
  string as written. Print a deferral loudly — it owes a pre-merge manual-gate item, never a pass — and flag
  an entry whose `tree` differs from `gateTrees.G9` as stale.
- **Review jobs** from `reviewJobs`: for each, the reviewer, lens, `status` and **age** (`startedAt` to
  now). Print a `running` job **loudly** — the cycle is not judgeable while one is in flight — and print a
  `timeout`/`failed` one with its id, since it owes a pre-merge manual-gate item.
- **Bake-off** from `bakeOff`, when present: the stances, whether a winner has been picked, and
  `converged` — a converged bake-off is a finding worth surfacing, not a footnote.
- **Git-write freeze** from `gitFreeze`: when `active`, say so first and name the branch, the reason and
  how long it has been held. A held freeze means **an out-of-process reviewer is reading this branch**:
  commits, checkouts and rebases must wait (§sc-review). Flag a **stale freeze** — a finding to release,
  not a state to respect forever — in **either** of two cases: an `active` freeze with **no** `running` job,
  **or** an `active` freeze whose `releaseOn` is `snapshot` once that snapshot exists. The second is the
  likelier leak: on the default path the freeze is meant to last only across the capture, so a live job is
  no evidence that the freeze is still legitimate.
- **Cost so far** from `telemetry`: one row per completed stage (tier / model / effort, plus tokens or cost
  where the host exposed them), the running total, and which risk-gated upgrades fired
  (`telemetry.upgrades`). Print `unavailable` for any figure the host didn't provide — **never estimate
  one**; an invented cost table is worse than an honest gap. Absent `telemetry` (a run started before this
  was recorded), say so and print the routing alone.

Keep it terse. Do not run any stage, and do not write to the state file.
