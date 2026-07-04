# Changelog

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
