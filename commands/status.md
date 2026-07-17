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
- **Resolved model routing** from `models` (per stage).
- **Change nature** (`nature`) and **risk** (`risk`).

Keep it terse. Do not run any stage, and do not write to the state file.
