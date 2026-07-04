---
name: ship-cycle
description: Orchestrator for a gated development lifecycle. Runs PREFLIGHT (branch guard, worktree isolation, overlay load, change-nature + risk classification) then chains the stage skills (sc-brainstorm → sc-design → sc-tdd → sc-implement → sc-review → sc-qa → sc-ship), enforcing gates and a loop cap via a state file. Framework-agnostic via a project overlay. Triggers "ship it", "run the lifecycle", "ship-cycle", "design to PR".
---

# ship-cycle — orchestrator

A thin control skill. It runs PREFLIGHT, then **chains one skill per stage** so each stays short and
actually gets followed. Everything project-specific comes from a **project overlay config** — never
from this plugin.

Trigger example: `/ship-cycle-devkit:ship-cycle add rate limiting to the login endpoint`

## Runtime & agent dependency (honest)

Runs on stock Claude Code via the `Task` tool. The stages name specialized roles (architect, critic,
security-reviewer, executor, …). **If your environment provides those subagent types** (e.g. an agent
pack), the stages use them for real adversarial separation. **On stock Claude Code**, spawn a
`general-purpose` agent per role and paste that role's prompt from
`${CLAUDE_PLUGIN_ROOT}/prompts/` or the stage skill — independence is weaker but the flow still holds.
Do **not** collapse stages into "I'll just do it myself"; the point of a separate reviewer is that it
is not the author.

## Iron Laws (non-negotiable)

Hard stops, not suggestions. Each lists the excuses agents reach for — all rejected.

1. **NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST.** Rejected: "trivial" · "just once" · "test after".
2. **NEVER CLAIM DONE WITHOUT RUNNING VERIFICATION AND READING ITS OUTPUT.** Rejected: "should work".
3. **NO PR WITHOUT A PASSING PRE-PR REVIEW.** Rejected: "small change" · "I reviewed while writing".
4. **NEVER COMMIT ON A PROTECTED BRANCH.** Branch first, always.
5. **STAY IN SCOPE.** Unrelated work → a new branch.

## Pipeline (one skill per stage)

| # | Stage skill | Produces | Gate |
|---|---|---|---|
| 0 | PREFLIGHT (this skill) | branch, worktree, overlay, routing, state | — |
| 1 | `sc-brainstorm` | agreed problem + acceptance criteria | G1 |
| 2 | `sc-design` | interfaces/boundaries + critic sign-off | G2/G3 |
| 3 | `sc-tdd` | failing tests for core logic (Red) | G4 |
| 4 | `sc-implement` | passing code in worktree isolation (Green) + build | G5/G6/G7 |
| 5 | `sc-review` | multi-lens parallel review, 0 Critical/High | G8 |
| 6 | `sc-qa` | integration/E2E + seam contracts | G9 |
| 7 | `sc-ship` | docs + verify + PR + cleanup | G10–G13 |

Run in order; a gate must pass before the next stage. On failure, loop back per the gate table.
**Loop cap: 3 per gate** — beyond that, return to `sc-design` and notify the user.

## Stage 0 — PREFLIGHT

1. **Branch guard**: if on a protected branch (overlay `vcs.protectedBranches`), create `feature/*`|`fix/*`.
2. **Worktree isolation**: create an isolated worktree so work never touches the main checkout:
   `git worktree add ../<repo>-<branch> -b <branch>` (or reuse the branch). Record its path in state.
   This lets stack-split implementers (backend/web/mobile) run in **parallel without collisions**.
3. **Load overlay**: read `${CLAUDE_PROJECT_DIR}/<projectConfig>` (plugin `projectConfig` setting;
   default `.claude/ship-cycle.config.json`). **Absent** → built-in heuristics + log "defaults in use".
   **Malformed JSON / schema-invalid** → stop and report; do not silently fall back.
4. **Classify change nature**: map changed paths via overlay `changeNature`. Overlapping globs →
   **most-specific glob wins**; docs/i18n-only diffs prefer the docs rule. **Print the resolved routing**
   (which tests/reviews will run) so it's auditable.
5. **Classify risk** (for model routing, below).
6. **Init state**: write `.claude/.ship-cycle-state.json`.

## State (real, not a metaphor)

`.claude/.ship-cycle-state.json`:
```json
{ "goal": "...", "branch": "...", "worktreePath": "...", "stage": "sc-design",
  "gates": { "G1": "pass", "G2": "pass" }, "loops": { "G8": 1 },
  "nature": ["backend"], "risk": ["auth"] }
```
Write it at every transition; read it at PREFLIGHT to **resume** and to enforce the loop cap
(don't count loops in your head).

## Gate criteria

| Gate | Pass condition | On failure |
|---|---|---|
| G1 | acceptance criteria stated verifiably + user-agreed | re-brainstorm |
| G2/G3 | interfaces specified + 0 unresolved critic objections | re-design |
| G4 | failing tests exist for core logic (Red evidence) | reject |
| G5 | build succeeds + new tests pass (Green) | build-fixer |
| G6 | all tests for the nature green, core coverage ≥80% | debugger → sc-implement |
| G7 | (if an artifact ships) real build succeeds | build-fixer |
| G8 | 0 Critical/High (authz, paywall, anemic, N+1). UI → designer passes | → sc-implement (design flaw → sc-design) |
| G9 | 0 new defects in integration/E2E; seams reproduced | → sc-implement |
| G10 | docs matching the change exist | writer |
| G11 | every claim mapped 1:1 to a test/build/QA log | rework |
| G12 | build+test+review+QA passed; base = overlay `vcs.defaultBase` | — |

## Model routing (token efficiency)

Assign models by **cost-of-being-wrong × cost-of-verification**, not by role name.

- **Base pyramid**: *high* on design & security/quality review; *mid* on implement/QA; *low* on
  docs/style/plumbing.
- **Risk-gated upgrade**: high-risk changes bump the *single matching role* to *top* —
  auth/payment→security review, schema/API-contract→design, complex algorithm→algorithm review.
  Match the *kind* of risk, not always the same role. Usually 0–1 upgrades per run.
- **Tier → model bridge (required to execute)**: read overlay `modelRouting.tierMap`
  (e.g. `{"top":"opus","high":"opus","mid":"sonnet","low":"haiku"}`) and **pass `model=<resolved>` on
  each `Task` call**. Without a tierMap, tiers are advisory only.
- **Bigger levers first**: prompt caching (cache the repo/diff/design doc), an effort dial, and
  "cheap path first" for implementation (mid tier → verify → escalate only the failing fix).

## Lightweight path

Trivial changes (config/docs/one-liner): collapse brainstorm/design/review into one check, substitute
heavy suites with self-tests/link checks, reduce review to quality+security. **Never skip build/test
verification or the pre-PR review.**
