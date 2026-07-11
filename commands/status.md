---
description: Print the current ship-cycle run status — stage, gate table (G1–G13), loop counts, resolved model routing, and worktree — from the state file. Read-only.
disable-model-invocation: true
allowed-tools: Bash Read
---

Show the current ship-cycle run status by reading its state file (read-only — never modify it).

!`cat .claude/.ship-cycle-state.json 2>/dev/null || echo "NO_STATE"`

If the output above is `NO_STATE` (the file is missing), report that no ship-cycle run is active in this
repo — suggest starting one with `/ship-cycle-devkit:ship-cycle <goal>` — and stop.

Otherwise parse the JSON and print a compact, scannable status report:

- **Goal** and **branch** (plus `worktreePath` if one was created).
- **Current stage** (`stage`) and its position in the pipeline:
  `sc-brainstorm → sc-design → sc-tdd → sc-implement → sc-review → sc-qa → sc-ship`.
- **Gate table** — for **G1–G13**, show `pass` / `fail` / `—` (not yet reached) from `gates`.
- **Loop counts** per gate from `loops`; the loop cap is 3 per gate — flag any gate that has hit the cap.
- **Resolved model routing** from `models` (per stage).
- **Change nature** (`nature`) and **risk** (`risk`).

Keep it terse. Do not run any stage, and do not write to the state file.
