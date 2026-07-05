---
name: sc-implement
description: Stage 4 of ship-cycle. Implement minimal code to pass the failing tests (TDD Green), refactor, and update docs in the same change — inside git worktree isolation so stack-split implementers (backend/web/mobile) can run in parallel without collisions. Runs tests and build.
---

# sc-implement — Green + build (Stage 4)

Make the failing tests pass with the **minimum** code, then refactor. Update docs in the same change.

## Worktree isolation (when it earns its keep)
If PREFLIGHT created a worktree (`state.worktreePath`) — i.e. this is stack-split or parallel work — do
the implementation there so it never touches the main checkout. For single-track work, no worktree was
created and the feature branch is enough. When the codebase is **split by stack**, give each stack its
own isolation:
- Spawn each stack's implementer as a separate agent with **`isolation: worktree`** so backend / web /
  mobile edit in **parallel without collisions**.
- Independent stacks → parallel. If the front end depends on a back-end API, settle that **contract
  first**, then parallelize.
- After merge, clean up worktrees: `git worktree remove <path>`.

## Large cross-cutting change — waved execution (single stack)
When one change touches **many files of the same stack** (a design-system reskin, a codemod/rename across
a layer), worktree-per-stack doesn't apply — the collision risk is *within* the stack. Wave it:
- **Wave 0 (serial foundation)**: the shared single-file bottlenecks everything else imports — tokens/
  theme, shared wrappers, motion/util infra, **pre-registered i18n keys**. One agent; must land before any
  parallel wave.
- **Waves 1..N (parallel)**: partition the remaining files into **exclusive ownership sets (zero overlap)**
  — one agent per set, so N run concurrently without touching the same file. Barrier between waves; verify
  (typecheck/build) at each barrier.
- **Atomic contract-change rule**: the owner that changes a shared symbol's signature/type also updates
  that symbol's **call sites in the same wave** — otherwise the barrier's global typecheck goes red between
  waves. Pre-plan which call-site files each signature change reaches.
- **Shrink the blast radius — contract changes in a serial micro-wave.** With dozens of call sites the risk
  isn't the leaf reskins, it's the few edits that touch shared contracts. Land **signature/type changes and
  their call-site updates as their own serial step, verified once**, *before* the parallel leaf waves start
  — then a parallel agent literally can't red the types. (The atomic rule, pushed one step further.)
- **"Verify in the loop" has a precondition.** Forcing each parallel agent to run `tsc`/build inside its own
  loop is only safe when agents are **worktree-isolated** — in a *shared* working tree a whole-project
  typecheck sees every agent's half-finished edits and flags errors in files the agent doesn't own (false
  alarms; agents may "fix" each other). So either isolate (`isolation: worktree`, costly at high fan-out)
  and self-verify, or keep a shared tree with a **single barrier typecheck** and, on failure, **bisect —
  map each error to its owning file → re-dispatch only that owner**, rather than stalling the whole wave.
- **Resource-aware concurrency**: cap concurrent agents to what the machine sustains — with a heavy local
  process up (emulator/simulator/device for visual QA), too many parallel agents can exhaust RAM and freeze
  the box.

## Implement (executor — fresh context)
Give the implementer **only the plan, the failing tests, and the conventions** (not the whole prior
conversation) to avoid context contamination. Use the stack prompt template:
`${CLAUDE_PLUGIN_ROOT}/prompts/impl-backend.md` · `impl-web.md` · `impl-mobile.md` (adapt to your stack).
Follow the engineering constitution (`${CLAUDE_PLUGIN_ROOT}/docs/engineering-constitution.md`):
authz from the principal only, DTOs not entities, whitelist validation, no N+1, no swallowed exceptions.

## Verify (this stage owns build + tests, separate from review)
- **G5**: build succeeds and the **new tests pass** (Green). Run the nature's build/test commands and
  read the output (Iron Law #2).
- **G6**: all tests for the nature are green; core coverage ≥80%. On failure, attach a debugger and loop.
- **G7**: if the change ships an artifact (APK/IPA/binary), run the **real packaging build**.
- **Lockfile sync**: if you changed a dependency **manifest** (`package.json`, `go.mod`, `Gemfile`,
  `Cargo.toml`, …) that has a **committed lockfile**, regenerate the lockfile in the same change. CI and
  release builds install from the **lockfile** (`npm ci`, `--frozen-lockfile`, …), so a manifest-only edit
  is inert — or reinstalls the old version and re-breaks the very build you fixed. (`npm install
  --package-lock-only` regenerates the lockfile without touching `node_modules`.) In a workspace, keep the
  single root lockfile; delete stray per-package ones.
- Do **not** commit or open a PR here — that's `sc-ship`, after review.
- Set `gates.G5/G6/G7` in state.

## Model routing
executor + build-fixer run at the **mid** tier. Cheap path first: implement on mid → verify → escalate
only the failing fix (or a risk-zone diff) to a higher tier.

**Pass `model = state.models['implement']` on the executor/build-fixer calls** (resolved at PREFLIGHT) —
never the agent type's default (Iron Law 6). An escalated fix passes the higher tier explicitly too.
