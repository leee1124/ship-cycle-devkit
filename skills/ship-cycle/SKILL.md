---
name: ship-cycle
description: Drive one goal through a gated development lifecycle — requirements → design → review → test(Red) → implement(Green) → run tests → build → code review → docs → verify → PR → cleanup. Prunes test/review stages by change nature and enforces engineering-constitution gates. Project specifics (paths, VCS, i18n) come from an overlay config. Triggers "ship it", "full cycle", "design to PR", "run the lifecycle", "ship-cycle".
---

# ship-cycle — Development Lifecycle Orchestration

Take a single goal and drive it end to end as a **gated state machine**. Each stage runs an
agent with a goal-shaped prompt; a gate must pass before advancing. On gate failure, loop back
to the prior stage (loop cap: 3 — beyond that, suspect the design and escalate to the user).

This playbook is **framework-agnostic**. Anything project-specific (monorepo paths, test commands,
VCS provider/repo, i18n layout) is read from a **project overlay config** at PREFLIGHT — it never
lives in this skill. It runs on stock Claude Code using the `Task` tool and general-purpose agents;
if your environment provides specialized subagent types (architect, security-reviewer, …) it uses
them, otherwise it spawns general-purpose agents with the role prompt.

## Iron Laws (non-negotiable)

Hard stops, not suggestions. Each lists the rationalizations agents reach for to skip it — all rejected.
Treat the agent as prone to shortcuts and block them preemptively.

1. **NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST.**
   Rejected: "it's trivial" · "just this once" · "I'll add the test after" · "it's only config" (if it
   has logic). Test-after is grounds to revert and restart the stage.
2. **NEVER CLAIM DONE WITHOUT RUNNING THE VERIFICATION AND READING ITS OUTPUT.**
   Rejected: "should work" · "probably passes" · "the change is obviously correct." Fresh evidence only.
3. **NO PR WITHOUT A PASSING PRE-PR REVIEW.**
   Rejected: "small change" · "no time" · "I reviewed it while writing." Security/authz findings block merge.
4. **NEVER COMMIT ON A PROTECTED BRANCH.**
   Rejected: "quick fix" · "I'll branch afterward." Branch first, always.
5. **STAY IN SCOPE.**
   Rejected: "while I'm here" · "it's related." Unrelated work → a new branch.

## Pipeline

```
0. PREFLIGHT      branch guard + load overlay + classify change nature (routing)
1. Requirements   analyst              → verifiable Acceptance Criteria
      ↓ G1: acceptance criteria stated in a testable form
2. Design         architect            → interfaces/boundaries/tradeoffs (READ-ONLY doc)
      ↓ G2: design approved
3. Design review  critic               → attack hidden assumptions/failure modes  ──fail──▶ 2
      ↓ G3: zero unresolved objections
4. Write tests(Red) test-engineer      → turn acceptance criteria into failing tests (before impl!)
      ↓ G4: failing tests exist for core logic
5. Implement(Green) executor           → minimal code to pass + refactor + update docs
      ↓ G5: build succeeds + new tests pass
6. Run tests      [conditional matrix] → all tests green, core coverage ≥80%  ──fail──▶ 5 (attach debugger)
7. Build verify   build-fixer(if needed) → real artifact build if the change ships one  ──fail──▶ build-fixer
8. Code review    security+quality+performance(+algorithm) + designer(on UI) in parallel → 0 Critical/High  ──fail──▶ 5
9. QA(integration/E2E) qa-tester(+verifier) → independent adversarial check of the running system  ──fail──▶ 5
      ↓ G9: seams (front↔back contract) + core flows reproduced, 0 new defects (skip for trivial changes)
10. Docs          writer               → README/CHANGELOG/comments up to date
      ↓ G10: documentation matching the change exists
11. Verify        verifier             → every claim backed by evidence (test/build/QA logs)
      ↓ G11: acceptance criteria met, with evidence
12. PR            git-master           → atomic commits, push, PR (base from overlay), review/QA summary in body
13. Cleanup       delete merged branch (local+remote) + sync base
```

## Stage 0 — PREFLIGHT (mandatory)

**Discovery (vague goals)**: if the goal is ambiguous or underspecified, **do not start implementing**.
Ask clarifying questions and propose a design the user accepts first (that is stages 1–2 — never jump
straight to code). A wrong-but-fast implementation of the wrong thing is the most expensive outcome.

**Branch guard (Constitution #1)**: if the current branch is a protected branch (`main`/`master`/`dev`
per overlay `vcs.protectedBranches`), **stop immediately** and create a `feature/*`|`fix/*` branch.
If in-flight changes are unrelated to the branch's purpose, warn and propose splitting.

**Load overlay config**: read the project overlay (default `.claude/ship-cycle.config.json`; path may
be set via the plugin `projectConfig` user setting). It supplies `vcs`, `changeNature`, `i18n`, and
optional `modelRouting`. **If the overlay is absent, fall back to built-in heuristics** (classify by
file extension/path; use generic `build`/`test` commands) and log that defaults are in use.

**Classify change nature**: from `git diff --name-only` (or the goal text) map changed paths to the
overlay's `changeNature` rules. Each rule declares its `tests` and `reviews`. Multiple natures →
run the **union** in parallel. Natures with no matching files are **skipped, with the reason logged**.

Overlay `changeNature` rule shape (example — values are the project's, not the plugin's):
```json
{
  "match": "src/main/**/*.java",
  "nature": "backend",
  "tests": ["./gradlew test"],
  "reviews": ["security", "quality", "performance", "algorithm"]
}
```

Built-in fallback natures when no overlay: source code (unit + integration if a test runner is
detected), config/scripts (self-tests + fixtures), docs/i18n (link/render check; i18n handled by the
i18n-parity hook if configured).

**Routing priority**: if the change is limited to docs or i18n data only, prefer the docs/i18n rule
and skip full app test suites. Mixed code + translation → union of the matching rules.

**Risk classification (for model routing)**: independently of nature, detect the high-risk signals in
`## Model Routing` and record them; only the matching role is upgraded to the top model. Most changes
are not high-risk and run on the base pyramid.

## Model Routing (token efficiency)

**Principle**: assign models by **"cost of being wrong × cost of verification"**, not by role name.
Strong models where mistakes are expensive (design, security/quality review); cheap models where the
work is mechanical or easily verified (docs, style, plumbing). Overlay `modelRouting` may override any
mapping; the tiers below are named generically (top / high / mid / low) so they map onto whatever model
lineup the environment offers.

### Base pyramid (every run)
| Role | Tier | Rationale |
|---|---|---|
| Design (architect) · design review (critic) · requirements (analyst) | **high** | errors propagate downstream |
| Security · quality · algorithm review, final verify | **high** | adversarial reasoning (where bugs are caught) |
| Implement (executor) · test-engineer · QA (qa-tester) | **mid** | execution is fine on a mid tier |
| Docs (writer) · explore · style review · relay/plumbing | **low** | low-risk, mechanical |

### Risk-gated upgrade (high-risk changes only)
When PREFLIGHT flags high risk, upgrade **only the single role matching the risk kind** from `high → top`.

| High-risk signal | Upgraded role |
|---|---|
| auth · payment · permission/ownership checks | security review |
| schema migration · data migration | design |
| public API contract · architecture-boundary change | design |
| complex algorithm | algorithm review |
| otherwise (the majority) | none |

- Match the **kind of risk**, not "always design". Usually 0–1 roles upgraded per run.
- The top tier is typically the most expensive per token — reserve it for **irreversible/critical** points.

### Levers bigger than tier choice (apply first)
1. **Prompt caching** (cached input is far cheaper): the orchestrator and reviewers re-read the same
   repo/diff. Put shared context (repo map, diff, design doc) in cache — this usually saves more than
   any tier choice.
2. **Effort dial**: keep the model, lower reasoning effort on easy stages.
3. **Cheap path first for impl**: implement on the mid tier → verify → escalate only the failing fix
   (or a risk-zone diff) to a higher tier.

## Gate criteria

| Gate | Pass condition | On failure |
|---|---|---|
| G1 Requirements | acceptance criteria stated "verifiably" | re-analyze |
| G2/G3 Design/Review | interfaces specified + zero unresolved critic objections | re-design |
| G4 Write tests | **failing** tests exist for core logic (TDD Red evidence) | reject |
| G5 Implement | build succeeds + new tests pass (Green) | build broke → build-fixer |
| G6 Run tests | all tests for the nature green, core coverage ≥80% | debugger → 5 |
| G7 Build verify | (if an artifact ships) real build succeeds | build-fixer |
| G8 Code review | 0 Critical/High (esp. authz, paywall, anemic model, N+1). UI change → designer passes | → 5 (if it's a design flaw → 2/3) |
| G9 QA | 0 new defects in integration/E2E/exploration; seams (front↔back contract) reproduced | → 5 (attach debugger) |
| G10 Docs | documentation matching the change exists | writer |
| G11 Verify | 0 claims without evidence | rework |
| G12 PR | build+test+review+QA passed, base from overlay | — |

Loop cap: G6/G8/G9 → implement loop **max 3**. Beyond that, escalate to DESIGN + notify the user.

### Gate verification commands (make judgment gates measurable)
Soft gates state "pass = this output from this command" to prevent rubber-stamping. Commands come from
the overlay's `changeNature[].tests` and `vcs`; examples below are illustrative.
- **G3 (0 objections)**: critic's unresolved-objection list is empty.
- **G6 (coverage ≥80%)**: run the nature's test+coverage command; core classes/modules ≥80% line coverage.
- **G7 (build)**: run the nature's build command; if an artifact ships, run the real packaging build.
- **G9 (QA)**: bring the system up and exercise core flows (real API calls / E2E) → 0 new defects or
  contract mismatches.
- **G10 (docs)**: `git diff --name-only <base>...HEAD` includes a doc file, or the PR body states an
  explicit "no docs needed" reason.
- **G11 (evidence)**: map each acceptance criterion 1:1 to a passing test/build/QA log.

## Engineering-constitution enforcement points

The base constitution ships in `docs/engineering-constitution.md`; a project may extend it. Key gates:
- **#1 Branch**: hard-blocked at PREFLIGHT. Warn on out-of-scope changes.
- **#2 Docs up to date**: stage 10 is a hard gate before PR. Verify confirms doc changes exist.
- **Mandatory review before PR**: stage 8 must pass before stage 12. Security/authz defects block merge.
- **Seam defense**: when implementation is split (e.g. backend/web/mobile) nobody owns end-to-end, so
  **stage 9 QA independently checks integration and front↔back contracts**. designer(UI)/QA(integration)
  are conditional — real features only; skip for trivial changes.
- **DDD (anemic model)**: the quality-review prompt explicitly checks whether business logic lives
  outside entities in services only, and whether entities are getter/setter data bags.
- **TDD**: order can't be verified from a diff → **force stage 4 (Red) before implementation**. G4/G6
  confirm core-logic tests and coverage.
- **Branch hygiene**: stage 13 deletes merged feature/fix branches (local + remote).
- **Build verification**: stages 5/6/7 are required **separately from** code review (#8) — static
  review does not guarantee a buildable/deployable artifact.

## Per-stage agent prompts

Each stage prompt states **① goal ② acceptance criteria ③ this stage's artifact ④ gate condition**.

- **Requirements (analyst)**: decompose the goal into verifiable acceptance criteria; surface hidden
  constraints and edge cases.
- **Design (architect)**: READ-ONLY. Interfaces, boundaries, tradeoffs, alternatives. No code.
- **Review (critic)**: attack the design's failure modes. Iterate to consensus.
- **Write tests (test-engineer)**: acceptance criteria → failing tests. Given/When/Then, descriptive
  test names.
- **Implement (executor)**: give the implementer a **fresh context — only the plan, the failing tests,
  and the conventions** (not the whole prior conversation) to avoid context contamination. Minimal code
  to pass → refactor. Update docs in the same change. When the codebase is split by stack (e.g.
  backend/web/mobile), use stack-specific prompts (see `prompts/`).
  Run independent parts in parallel; if the front end depends on a back-end API, settle the contract first.
- **Code review (parallel)**: security/quality/performance(+algorithm) + **designer (on UI change:
  typography/spacing/hierarchy/consistency/accessibility/branding)**. Each lens checks named anti-patterns.
- **QA (qa-tester+verifier, conditional)**: independently and adversarially exercise the running system
  — integration/E2E/exploration/regression, especially front↔back contract mismatches. Skip for trivial
  changes.
- **Docs (writer)**: README/CHANGELOG/API docs/comments.
- **Verify (verifier)**: match claims to evidence; confirm acceptance criteria. Run the verification
  command and read its output — never accept "should work" / "probably passes" (Iron Law #2).
- **PR (git-master)**: atomic commits, base from overlay `vcs.defaultBase`, body summarizing review/QA
  and **linking the tracked issue** (`Closes #NN` when fully done / `Refs #NN` when partial). Assign
  milestone if the overlay enables it.

## Issue-tracker management (optional, overlay-driven)

If `vcs.tracker` is set (e.g. GitHub issues/milestones/project board), manage it actively:
- **PREFLIGHT**: use the tracked issue if one exists, else create one (with milestone/priority label)
  before starting; move the board to **In Progress**.
- **PR ↔ issue**: PR body uses `Closes #NN` (fully done → auto-close on merge) or `Refs #NN` (partial →
  progress comment + keep open).
- **Close on completion**: close the issue and move the board to **Done** as soon as it is finished.
- **Hygiene**: don't put third-party/competitor product names or "learning/practice" items in the tracker.
- Token scopes for the VCS provider come from the environment, never from this plugin.

## Lightweight path (scaling down)

Trivial changes (config/docs/a one-line fix) don't need the full course. When the nature is
"config/scripts" or "docs/i18n": compress requirements/design/review into one lightweight check,
substitute the heavy test suites with self-tests/link checks, and reduce code review to
quality+security. **Never skip build/test verification (#10) or the mandatory pre-PR review, on any path.**
