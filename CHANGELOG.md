# Changelog

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
