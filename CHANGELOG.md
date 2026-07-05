# Changelog

## 0.2.5 — inter-stage relay

- **`sc-relay`** (new, low tier): a relay woven into **every** stage transition. It carries the prior
  stage's output (design doc, test results, review findings) to the next stage's agent so the
  orchestrator doesn't hold every artifact in its own context.
- **Verbatim only — no compress/summarize/edit (hard rule)**: the relay runs on a weak/fast model, and
  a weak model asked to summarize may compress wrong and silently drop an unresolved objection, a gate
  blocker, or failing evidence. Its job is mechanical carrying + bookkeeping (state file + a one-line
  progress note), never judgment — judgment belongs to the next stage's agent.
- **Always on, every transition**: branching on "is this handoff big enough to relay" is more overhead
  and a worse failure mode than one uniform fast pass; nothing slips through un-relayed.
- Named in the model-routing low tier alongside docs/style/plumbing.

## 0.2.4 — parity-audit discipline

Adds a new à-la-carte skill, learned from a real cross-platform integration miss:
- **`sc-audit`** (new, not in the default chain): a static **cross-surface parity audit**. Compares every
  consumer surface (web, mobile, CLI, SDK, another service) against a single source-of-truth contract and
  emits a module-by-module gap matrix + cross-cutting risk checks (authz/paywall leak, entity-return,
  data drift, i18n, file/export) + P0/P1/P2 priorities + a **cutover/ship verdict**
  (parallel-run only / cutover-ready / ship-ready).
- **Why it's separate from `sc-design`**: sc-design verifies the contract *for the feature in hand*; an
  entire surface can be built on assumed contracts and stay green until the first real integration, when
  most screens break at once. A dogfood run shipped a whole web app that "deployed" but almost nothing
  worked end-to-end — the class of failure a per-feature guard can't see. sc-audit is the macro sweep;
  run it before a first cross-surface integration or on a large/ahead-of-backend surface.
- **Core rule carried over**: "endpoint exists ≠ integrated" — only ✅ when the surface actually calls it
  with the real serialized shape; check the composition root for which implementation is wired in.
- **Overlay**: new optional `audit` section (`sourceOfTruth` / `surfaces` / `modules` / `reportDir`);
  falls back to `changeNature` globs and logs when defaults are used. Schema + example updated.

## 0.2.3 — second-dogfood feedback (mobile bug-fix cycle)

Learned from a React Native (Expo) bug-fix run on a monorepo:
- **Lens → agent fallback** (`sc-review`): review lens names are *roles*, not fixed agent types. If no
  dedicated reviewer exists (many envs have no `performance-reviewer`/`algorithm-reviewer`), spawn a
  `general-purpose`/`code-reviewer` with the lens's anti-patterns as focus — verify the type exists first,
  never abort on a missing agent. Scale fan-out to the host (sequential on constrained machines).
- **Device-only QA without an emulator** (`sc-qa`): for visual/native changes with no front↔back seam and
  no device available, automated QA = full-suite regression + integration checks + typecheck/bundle, then
  **emit a concrete on-device manual checklist** into the PR as a pre-merge gate. The checklist is the
  honest deferral — don't fake a visual pass or silently skip.
- **No UI/component test harness** (`sc-tdd`): when the stack can't unit-test rendered output (RN without a
  component lib), extract pure logic (formatters, selectors, time/geometry math, i18n) and write Red there;
  thin UI wiring is covered by the designer lens + the on-device checklist, not faked component tests.
- **Overlay commands run from repo root + gitignore run state** (README / example): use root-relative test
  commands (`cd apps/x && ./gradlew …`, `npm run test -w …`, `npx tsc --noEmit -p …`); add
  `.claude/.ship-cycle-state.json` to `.gitignore`.

## 0.2.2 — first-dogfood feedback

Improvements learned from the first real end-to-end run (a web dashboard feature):
- **Verify contracts, never assume** (`sc-design`): read the actual endpoint/entity/serialized response;
  an assumed API shape propagated to the implementer and caused a runtime crash. Now a hard rule.
- **Worktree is conditional** (`ship-cycle`/`sc-implement`): create it only for stack-split/parallel
  work; single-track changes use a plain feature branch (worktree was pure overhead otherwise).
- **Complexity exception to cheap-path-first** (`ship-cycle`): start complex work (novel algorithms,
  intricate SVG/canvas UI) at the higher tier instead of wasting a failed mid-tier attempt.
- **UI-only merges design+implement** (`sc-design`): don't force a separate READ-ONLY architecture doc
  for a widget; keep the critic/accessibility pass.
- **G9 E2E degrades honestly** (`sc-qa`): without a live backend + seeded auth session, degrade to
  contract-level seam verification and log the deferral — never fake a pass.

## 0.2.1 — review discipline (borrowed from Superpowers)

`sc-review` keeps its multi-lens/parallel structure and adds the output discipline from Superpowers'
`requesting-code-review` reviewer:
- **Plan alignment** as a cross-cutting check (does the impl satisfy the acceptance criteria — catch
  "built the wrong thing" at review, not final verify).
- **Production readiness** check for contract/schema/public-surface changes (backward compat, migration, docs).
- Per-lens **output discipline**: mandatory Strengths, actual-severity issues, and a clear merge
  **verdict (Yes/No/With-Fixes)**; no severity inflation; no verdict without reading the code.

## 0.2.0 — composable restructure

Refactored the single monolithic `ship-cycle` skill into an orchestrator + one skill per stage, and
adopted structural patterns from mature frameworks.

### Added
- **Composable stage skills**: `sc-brainstorm`, `sc-design`, `sc-tdd`, `sc-implement`, `sc-review`,
  `sc-qa`, `sc-ship` — each short and focused, usable à la carte. `ship-cycle` is now a thin
  orchestrator that chains them.
- **Dedicated brainstorming stage** (`sc-brainstorm`): refuse to code a vague goal; clarify + propose
  a design + get acceptance first.
- **Full git worktree isolation**: PREFLIGHT creates a feature worktree; `sc-implement` runs
  stack-split implementers in per-worktree isolation for collision-free parallelism.
- **Real state file** (`.claude/.ship-cycle-state.json`): tracks stage, per-gate status, and loop
  counts so "loop cap 3" and resume don't depend on the model's memory.
- **Tier → model bridge**: overlay `modelRouting.tierMap` maps tier names to real model ids; the skill
  passes `model=<resolved>` per `Task`.
- **Overlay JSON Schema** (`docs/ship-cycle.config.schema.json`) + defined precedence for overlapping
  globs (most-specific wins) and malformed-config behavior (stop, don't silent-fallback).

### Fixed
- Dead file references: bundled files are now addressed via `${CLAUDE_PLUGIN_ROOT}`.
- Honest runtime docs: states the specialized-subagent dependency and the stock-Claude-Code fallback.
- Corrected the trigger form to `/ship-cycle-devkit:ship-cycle`.

## 0.1.0 — initial

Portable gated dev-lifecycle plugin: single `ship-cycle` skill, engineering constitution, impl prompt
templates, project overlay, risk-based model routing. Borrowed Iron Laws + Red Flags and a discovery
gate from Superpowers.
