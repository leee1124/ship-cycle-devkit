---
name: ship-cycle
description: Orchestrator for a gated development lifecycle. Runs PREFLIGHT (branch guard, size tier, worktree isolation, overlay load, change-nature + risk classification, model/effort routing) then chains the stage skills sc-brainstorm → sc-design → sc-tdd → sc-implement → sc-review → sc-qa → sc-ship, enforcing gates and a loop cap via a per-cycle state file. Framework-agnostic via a project overlay. Triggers "ship it", "run the lifecycle", "ship-cycle", "design to PR".
---

# ship-cycle — orchestrator

A thin control skill: it runs PREFLIGHT, then **chains one skill per stage** so each stays short and
actually gets followed. Everything project-specific comes from a **project overlay config**, never from
this plugin. Trigger: `/ship-cycle-devkit:ship-cycle add rate limiting to the login endpoint`

## Runtime & agent dependency (honest)

Runs on stock Claude Code via the `Task` tool. The stages name specialized roles (architect, critic,
security-reviewer, executor, …); where those subagent types exist they give real adversarial separation,
and otherwise a `general-purpose` agent briefed with that role's prompt from
`${CLAUDE_PLUGIN_ROOT}/prompts/` or the stage skill is weaker but holds.

## Delegate vs act inline (orchestrator)

Spawning a subagent isn't free — it boots, gets re-briefed and **re-reads** the files — so delegating a
trivial edit costs more than doing it inline. Delegate when it buys **independence** (sc-design's critic,
sc-review's lenses and sc-qa are separate agents — §core), **tier savings** (work mechanical enough that a
cheaper-tier executor beats the orchestrator's session-fixed model), **context hygiene** (hand off what
would otherwise dump into this long-lived context), or **parallelism**. Otherwise act inline: the line is
"does delegation buy something", not diff size — a small but context-heavy or high-stakes step can still
warrant a subagent.

## The core — what not to skip

These six are what the cycle is for. Each carries its reason rather than standing as an absolute, because a
rule whose rationale you understand generalizes to cases it never named. Dial ceremony around them
(§Tier S path); don't dial them.

1. **Independent review before any PR, and it has to come back clean.** A model cannot see its own mistakes
   from inside the context that made them, so the review catches what the author's own pass structurally
   cannot. Every finding gets a disposition: fixed here, or filed with a link (§core 5).
2. **Judge pass/fail from the real output** — the command's own exit status or a machine-readable report
   (surefire/JUnit XML, runner JSON), not scraped stdout. `cmd | grep | tail` returns the *tail's* status,
   so a failed build reads green. It runs the other way too: a check that **errored before reaching the
   thing under test** says nothing about it, so the states are passed / failed / **undetermined**, never
   two. Factual traps, not discipline problems — see sc-implement G5/G6.
3. **Test-first for logic, judgment elsewhere.** For anything with a contract — a function, an endpoint, a
   state machine — write the failing test first; it is the cheapest way to find out the contract is wrong.
   For layout, copy, config and most UI tweaks the meaningful verification is running the thing, so a
   red-then-green unit test is ceremony: verify by execution and say which you chose. When genuinely
   unclear, test-first costs little and settles it.
4. **Work on a feature branch; don't commit to a protected one.** Mechanical accident prevention,
   independent of how capable the model is.
5. **Stay in scope.** Unrelated work goes to a new branch. A real defect found outside the current scope —
   a latent bug, a dead code path, a data error — gets filed and left alone here: "found, filed, not fixed
   here". Silently dropping it is the failure mode this prevents; so is fixing it and growing the diff.
6. **Pass `model=` explicitly on every stage agent.** A specialized agent type (`quality-reviewer`,
   `security-reviewer`, …) carries its own default model that overrides your tier when you omit it — how a
   top-tier review quietly ends up on a cheap default. PREFLIGHT resolves tiers into `state.models` so each
   spawn copies a concrete value (§Stage 0.7).

Worktree isolation for parallel or cross-stack work and the baseline/regression split (§Stage 0.5) belong
with these: both are bookkeeping that judgment does not replace.

## Pipeline (one skill per stage)

| # | Stage skill | Produces | Gate |
|---|---|---|---|
| 0 | PREFLIGHT (this skill) | branch, **size tier**, worktree, overlay, model+effort routing, state | — |
| 1 | `sc-brainstorm` | agreed problem + acceptance criteria + **route plan** | G1 |
| 2 | `sc-design` | interfaces/boundaries + critic sign-off | G2/G3 |
| 3 | `sc-tdd` | failing tests for the change's logic (Red) | G4 |
| 4 | `sc-implement` | passing code in worktree isolation (Green) + build | G5/G6/G7/G7b |
| 5 | `sc-review` | multi-lens parallel review, 0 Critical/High | G8 |
| 6 | `sc-qa` | integration/E2E + seam contracts | G9 |
| 7 | `sc-ship` | docs + verify + PR + cleanup | G10–G13 |

This is the default map, not a required path. Which stages run is decided once, at G1, in the confirmed
**route plan** (§Route plan, `state.route`) — a config bump has no design to critique, a copy fix has no
logic to test first. A skipped stage records `gates.<G> = "n/a: <one-line reason>"`, a decision rather than
a drift, and distinguishable from a stage never reached. For every stage that does run, **its gate must
pass before the next stage starts; on failure, loop back per the gate table's "On failure" column.**
**Loop cap: 3 per gate** (tracked in *this cycle's* state file, not in your head) — beyond that, return to
`sc-design` and notify the user (a route-skipped `sc-design` grows to `run`, §Route plan). Parking and
resuming do not reset it (§`${CLAUDE_PLUGIN_ROOT}/docs/state-file.md` — Parking).

Between every stage, artifacts pass through the state-file handoff rule below.

## Route plan — which stages run, decided at G1

PREFLIGHT sets the size tier from the diff before the requirements exist; it has to, since brainstorm already
needs a model and an effort. Which stages the cycle owes is better decided once the criteria are agreed, so
sc-brainstorm ends G1 with a **route plan** beside them, the user confirms both in one answer, and it goes to
`state.route` with the `basis` it was judged on — `state.size`, `state.risk` and `state.nature` at that moment
(shape: `${CLAUDE_PLUGIN_ROOT}/docs/state-file.md`). Each stage reads `state.route` on entry instead of
re-deriving its own skip.

- **Start from the tier** (§Stage 0.2, §Tier S path) and say where the plan departs from it: a stage added,
  the lenses and QA form chosen, a stage skipped with a one-line reason.
- **Below the tier only for ceremony stages, with a reason the user saw.** `sc-design` and `sc-qa` may be
  skipped; `sc-tdd` only when the change is layout, copy or config (§core 3, the same condition G4
  accepts), with the reason naming its execution-based verification. `sc-implement`, `sc-review` and
  `sc-ship` always run. No route drops a §core outcome or a fail-closed floor: branch guard, the pre-PR
  independent review, real-output pass/fail, the conflict check, root-cause analysis before a defect fix,
  triage, the G7b boot smoke, a touched release smoke (§sc-qa). The stage reached records
  `gates.<G> = "n/a: route — <reason>"`, so G12 counts it like any other `n/a`.
- **A stage routed `run` runs** — it does not `n/a` itself, because the route already judged it; only a
  config `n/a` (`n/a: no <x> config`) still applies. Without a route, stages judge as before.
- **Effective lenses** = `state.route.lenses` ∪ the Tier S floor (security plus one lens matched to the
  nature, plus cold on a non-trivial change) ∪ every risk-matched lens ∪ the overlay `reviews` of every
  nature in the current `state.nature` (§sc-review). **QA form** names what sc-qa runs — full bring-up +
  seams, seams only, release smoke only.
- **UI natures**: the route may name the **live visual loop** inside `sc-implement` (the owner settles the
  looks on the running app; `${CLAUDE_PLUGIN_ROOT}/docs/visual-check.md`) and records whether the owner will
  be present as `state.route.ownerPresent` (`false` ⇒ no `owner-confirmed` visual check). The loop is part
  of sc-implement, not a stage, so it is never skipped as one; the designer lens and its a11y floor join the
  lens floor for a UI nature and no route or Tier S drops them.
- **Growth only.** Once confirmed, a stage or lens can be added, never removed. Growth comes from: scope or
  nature growing (§Stage 0.4); a loop-back to sc-design — a loop cap or a G8 design flaw — which grows
  `sc-design` to `run` and tells the user; sc-tdd finding a contract in a routed skip. Re-show the user only
  the added rows, write them to `state.route`, log a `route` row. **A basis rise** — `state.size` above
  `basis.size`, a risk tag not in `basis.risk`, or a nature not in `basis.nature` — invalidates every skip:
  re-show those rows; each turns `run` unless the user re-confirms it against the new basis (which then
  updates `basis`). Every stage's "Route first" check makes this comparison before honouring a skip.
- **Growing a stage already passed.** When a grown stage's gate holds `n/a: route — …`, clear it to `—`
  with a `cleared` log row, move `stage` back to that stage, and let later gates clear as their evidence
  goes: G5–G9 by §Tree identity when the re-run changes the tree; G4 when a re-run design changes the
  criteria or the tests. A clear does not count against `loops`. G12 refuses an `n/a: route` gate whose
  route entry is now `run`, and any other whole-stage `n/a` (G2/G3, G4, G9) whose entry is `run`, unless
  it is a config `n/a` (`n/a: no <x> config`) — §sc-ship G12 and the G12 row below.
- **One stage's job → no cycle.** When the criteria reduce to a single stage's work ("just review this
  branch", "just critique the design", a parity audit), recommend that skill standalone — `sc-review`,
  `sc-design`, `sc-audit` — over a pipeline. If the user takes it, end the cycle `cancelled` with a log row
  naming the skill, then run the G13 subset that applies: archive the log
  (§`${CLAUDE_PLUGIN_ROOT}/docs/state-file.md` — Gate log); remove a worktree PREFLIGHT created, unlinking
  shared dep stores first (§sc-ship G13 step 1); delete the branch, from the base, only if PREFLIGHT created
  it (`state.branchCreated`) and it has no commits beyond the base; delete the state file. A standalone skill
  ignores a terminal state file; the §core outcomes ride with that skill.
- **No route** (a cycle started before 0.3.13): stages decide from the tier and their own `n/a` as before;
  the reconcile does not reconstruct one.

## State-file handoff — inter-stage artifact passing

Each stage **writes its output to a file** (design doc, test results, review findings) under the run's
artifact dir; the next stage **reads that file**. The orchestrator passes only **pointers (paths)**, tracked
in state — it never carries a full artifact through its own context. This is plumbing (code + files), not an
LLM step: files carry artifacts whole, with no summarizing, token spend or drift, where a summarizing pass
can silently drop an unresolved critic objection, a gate blocker or failing evidence. Put a model in a
handoff only for a genuine transformation (extract acceptance criteria, reformat for the next tool), priced
for that transformation's difficulty.

## Stage 0 — PREFLIGHT

(`§Stage 0.N` elsewhere in the kit means PREFLIGHT list item N.)

**Resuming** (a mid-pipeline state file for this branch): skip init and run the **resume reconcile**
first; it prints its mismatches, appends to `state.reconcile`, and picks the stage to continue from.
Inference only lowers — it may move the stage earlier or clear a `pass`, never record one. A **parked** file
is not resumed by a new goal: ask "resume or replace?" (`/resume` is the explicit resume). Rules:
`${CLAUDE_PLUGIN_ROOT}/docs/state-file.md` — Resume reconcile, Resume and selection.

1. **Branch guard**: if on a protected branch (overlay `vcs.protectedBranches`), create `feature/*`|`fix/*`
   and record `state.branchCreated = true` (false when the cycle started on an existing branch).
   A detached HEAD (empty `git branch --show-current`) has no cycle key — refuse and ask for a named
   branch, since state is keyed by branch.
2. **Change-size tier (S/M/L), then worktree isolation.** Pick the tier first and out loud — it is the dial
   every later stage reads, and leaving it implicit is how a one-line fix pays Tier-L ceremony. Record it
   as `state.size`; for **S** record the corroborating sites in `state.sizeEvidence: ["path:line", ...]`. S
   with fewer than two recorded sites is M: the party benefiting from S certifies it, so the evidence is
   the check. Print it here and with the routing (§Stage 0.7).

   | tier | what it is | what it gets |
   |---|---|---|
   | **S** | a single expression / constant / comment whose cause is already corroborated by **≥2 independent code sites**, with no runtime-behaviour ambiguity | branch, no worktree; inline self-verification; no verification fleet, except ≥1 independent refuter for a surviving Critical/High; security lens + one lens matched to the nature; release smoke if `appliesTo` is touched; conflict check; PR |
   | **M** | one module, one stack | worktree only if something else earns it; 1–2 lenses/verifiers |
   | **L** | multi-file, cross-stack, security-sensitive, or a migration | the full set — every stage, full lens breadth, QA (a route may skip a ceremony stage with a reason, §Route plan) |

   The tier is the starting point; the route plan at G1 (§Route plan) makes the per-stage call.
   Tier S is a claim about evidence, not diff size. Re-classification is **monotonic**, like risk (step 6):
   a tier that turns out bigger moves up and adds the ceremony back, never down to retire a stage you
   already owe.

   Then **worktree isolation (conditional)**: create one for work split across stacks or run by parallel
   implementers, where `git worktree add ../<repo>-<branch> -b <branch>` keeps them from colliding; a
   single-track sequential change needs only a feature branch. Record the path. When several
   worktrees share a dep store (overlay `env.sharedNodeModules`), **record how the link was made** (`ln -s`,
   `cmd /c mklink /J`, pnpm hardlink store): every link is a path by which a recursive delete reaches the
   store and wipes it for every other worktree, and sc-ship's G13 sweep must find it again. Removal,
   `prune`, leftover directories and a stale `index.lock` from a timed-out add each have an order a
   recursive delete gets wrong — see `${CLAUDE_PLUGIN_ROOT}/docs/worktree-recovery.md`.
3. **Load overlay**: read `${CLAUDE_PROJECT_DIR}/<projectConfig>` (plugin setting; default
   `.claude/ship-cycle.config.json`). Absent → built-in heuristics + log "defaults in use". A
   `releaseChecklist` item with `when.release: true` but no `vcs.releaseBranch` never matches: say so.
   Malformed →
   **fail closed**: stop and report, rather than running on defaults the operator didn't choose. One
   carve-out: a file that parses whose only problem is a schema-invalid `env` block — an opportunistic cost
   knob whose fallback is "spin up fresh" (see sc-qa) — emits `SC-DEGRADE-ENV` naming the section and
   fallback, ignores `env`, and continues. `env` alone, because it cannot touch a correctness floor. Say both
   fallbacks: spin up fresh; and, only if the raw `env` had `heavyLock`/`maxConcurrentHeavy`, the lock
   and `heavyHeadroomMB` are gone, so run heavy work sequentially, one job at a time (`${CLAUDE_PLUGIN_ROOT}/docs/heavy-work.md`).
   With `env.heavyLock` / `maxConcurrentHeavy` set, tag heavy work (full suite, release build, device QA) and
   queue one-shot jobs under the lock (long-lived ones go by headroom), and paste the lock path, slots, wait bound and the overlay's worker caps into
   every agent prompt that may run it — subagents do not inherit the rule; see that doc.
4. **Classify change nature**: map changed paths via overlay `changeNature` (overlapping globs →
   most-specific wins; docs/i18n-only diffs prefer the docs rule) and print the resolved routing so it is
   auditable. Not one-shot: a later stage finding the change touches a stack the diff missed —
   a "mobile-only" change needing a new backend endpoint — re-runs it and the routing, updates state and
   adds the missing implementer axis. Scope growing at the design gate is normal.
   Classification also sets **G7b applicability**: a nature declaring overlay `bootCheck` has a loadable
   application context, so G7b (sc-implement) runs the boot smoke on its non-inert changes. A
   context-bearing nature with no `bootCheck` gets a one-line prompt each cycle and G7b degrades to a manual
   checklist — undeclared never silently means "no boot floor".
   It also sets **release-smoke applicability**: a changed path matching a nature's `releaseSmoke.appliesTo`
   requires G9's release-artifact smoke (§sc-qa Release-artifact smoke).
5. **Capture a test baseline** so "no new failures" is mechanical rather than a judgment call: run the
   nature's suite on the **base commit once** and record the pass/fail set in `state.baseline`. G6/G9 diff
   against it — a failure already there is not a regression, only a new one blocks — sparing later stages
   from re-deriving "mine or pre-existing?".
   `baseline.source` is `local` (default), `ci` (the base commit's CI report ingested into `failing`) or
   `ci-status-only` (green run, no report: **every failure blocks unless its suite was rechecked**);
   `baseline.run` records the run. Rules and trade-offs: `${CLAUDE_PLUGIN_ROOT}/docs/test-baseline.md`.
   Where a nature declares `coverage`, measure it on the base too — locally if it can run here, even under a
   CI source — into `baseline.coverage[<nature>]` (§sc-implement G6).
   `baseline.unrunnableHere` records suites this environment **cannot start at all** (no database
   reachable, a service absent, a sandbox policy refusing it): neither a failure to diff against nor
   something that counts as passed. It is pre-committed against the base commit, may only shrink, and
   satisfies no acceptance criterion — evidence rules, the started-and-failed vs.
   could-not-start boundary and inheritance are in `${CLAUDE_PLUGIN_ROOT}/docs/test-baseline.md`.
   Skip the baseline only on **Tier S**, where `unrunnableHere` is then *absent, not empty*. A Tier S run
   that meets a suite it cannot start re-tiers upward to M (monotonic) and captures the baseline; it never
   mints a quarantine mid-cycle.
6. **Classify risk** (for model routing). The label dials ceremony only — the model tier and which role is
   upgraded — never an outcome: verification, fresh-eyes review and the fail-closed floors run regardless.
   Not one-shot, mirroring step 4: a later stage revealing a higher-stakes axis (a token lifetime, a
   migration, an API contract) re-classifies and re-resolves routing, monotonically.
7. **Resolve per-stage models *and effort* now (not per-spawn)**: resolve each stage's tier → a concrete
   model via overlay `modelRouting.tierMap` (base pyramid + any risk upgrade) and its work-kind → an effort
   level via `effortMap`, scaled by `state.size` (§Effort). Write both to state and print them with the
   size tier, e.g. `size=S · review→sonnet/medium, implement→sonnet/low`; record which risk upgrades fired
   in `telemetry.upgrades`. Every stage then spawns with `state.models[<stage>]` and `state.effort[<stage>]`
   (§core 6).
   **Routing guard**: a security review routed to a model that refuses security analysis silently no-ops, so
   where overlay `modelRouting.securityReviewModel` is set the `security`/`authz` lenses use it over their
   tier-resolved model — record it as `models["review.security"]` for sc-review, and when the pin differs
   print `SC-ROUTE-AVOID: security-lens <tier-model>→<securityReviewModel>`.
8. **Init state**: write this cycle's `.claude/ship-cycle/<branch-slug>.json` with everything resolved above
   plus an empty `telemetry`, an empty `reviewJobs` and `gitFreeze` inactive, and create its gate log
   `<branch-slug>.log.md` beside it with the first stage's `enter` row — archiving any log a replaced state
   file left behind first (§`${CLAUDE_PLUGIN_ROOT}/docs/state-file.md` — Gate log). Migrate a legacy bare state
   file for this branch first if one exists, and refuse if the target already belongs to a different
   `branch` (§State).

## State (real, not a metaphor)

**One state file per cycle**, keyed by the feature branch: `.claude/ship-cycle/<branch-slug>.json`
(slug = branch with `/` → `-`). It lives in the cycle's own working directory — its worktree if PREFLIGHT
created one, else the main checkout — so concurrent cycles never clobber a shared file and each owns its
`loops`. It carries `goal`/`branch`/`stage`/`gates`/`loops`, the PREFLIGHT results (`nature`, `risk`,
`size`, `baseline`, `models`, `effort`), the G1 `route`, `coverage`, `reviewJobs`, `gitFreeze`, `parked`,
`reconcile` and `telemetry`; the full shape, stage values, naming, collision guard, resume/selection,
parking, the resume reconcile and legacy migration are in `${CLAUDE_PLUGIN_ROOT}/docs/state-file.md`.
Write it at every transition; read this cycle's file at PREFLIGHT to **resume** and to enforce **its** loop
cap, rather than counting loops in your head. **Every gate value or stage change also appends one row to the
append-only gate log** `<branch-slug>.log.md` in the host's state dir — never rewritten, archived at G13,
never authoritative over the state (§`${CLAUDE_PLUGIN_ROOT}/docs/state-file.md` — Gate log).

**Park on request, from any stage** — `stage = "parked"` with `parked = {reason, resumeStage, at, holds}`;
never with a live-tree freeze, and never with a live job or freeze that `holds` does not name
(§`${CLAUDE_PLUGIN_ROOT}/docs/state-file.md` — Parking).

**One exception to per-cycle isolation: `gitFreeze` describes a repo-wide hazard.** `git worktree add /
remove / prune` and an `index.lock` recovery reach outside the cycle that runs them, and `prune` is
repo-scoped. Before any of those, scan **every** `.claude/ship-cycle/*.json` in this working directory for
an active `gitFreeze` or a `running`/`launching` `reviewJobs` entry — parked cycles included (a parked freeze has one
release valve, §`${CLAUDE_PLUGIN_ROOT}/docs/state-file.md` — Parking) — and treat another cycle's freeze as binding
(§sc-review — Git-write freeze).

## Gate criteria

| Gate | Pass condition | On failure |
|---|---|---|
| G1 | acceptance criteria stated verifiably + **route plan**, user-agreed together | re-brainstorm |
| G2/G3 | interfaces specified + 0 unresolved critic objections | re-design |
| G4 | failing tests exist for the change's logic (Red evidence) — or, for layout/copy/config, the execution-based verification is named instead (§core 3) | reject |
| G5 | build succeeds + new tests pass (Green) | build-fixer |
| G6 | no failures **new vs `state.baseline`** (`unrunnableHere` suites are neither pass nor regression; `baseline.flaky` cases are not exempt; under `ci-status-only` every failure blocks unless its suite is in `run.rechecked`); core coverage from the **report** clears its floor, or `"n/a: no coverage config"`; ci-deferred coverage → `checklist` (§sc-implement G6) | debugger → sc-implement (undetermined → fix the coverage run) |
| G7 | (if an artifact ships) real build succeeds | build-fixer |
| G7b | (if the nature declares `bootCheck`) full-context **eager** boot/context-load smoke passes on a non-inert change | build-fixer (env can't load → checklist) |
| G8 | 0 Critical/High (authz, paywall, anemic, N+1); every finding has a disposition (fixed-here / filed `#NN`); no `reviewJobs` entry still `running`/`launching`, `gitFreeze` released; UI → designer passes | → sc-implement (design flaw → sc-design) |
| G9 | 0 new defects in integration/E2E vs `state.baseline` (ignoring `unrunnableHere`; `flaky` not exempt; under `ci-status-only` every defect blocks unless its suite is in `run.rechecked`); seams reproduced; ITs that **can** run here actually ran; release-artifact smoke when `appliesTo` is touched (§sc-qa Release-artifact smoke) | → sc-implement |
| G10 | docs matching the change exist | writer |
| G11 | every claim mapped 1:1 to a test/build/QA log; a UI nature's looks → `state.visualCheck` (owner-confirmed on a profile; otherwise the pre-merge manual gate) | rework |
| G12 | build+test+review+QA passed, and every matched overlay `releaseChecklist` item ran green or (`manual`) is on the pre-merge manual gate — a `degrade` G9 / `checklist` G7b or G6 counts **only** when its item is on the pre-merge manual gate (a `deferred` release smoke included), and an `"n/a: <reason>"` gate counts with its reason carried to the PR body (not a whole-stage G2/G3, G4 or G9 `n/a` whose route entry is `run`, unless it is a config `n/a`); **branch merges cleanly into** overlay `vcs.defaultBase` (merge-tree probe + host `mergeable`); PR body's **Gate summary** matches a fresh render from state + log, re-checked right before merge | merge base + resolve, re-verify |
| G13 | merged branch deleted (local + remote); feature worktree removed if created (**linked dep stores unlinked first**, never deleted through); cycle state file deleted; gate log archived, not deleted; base synced | — |

## Model routing (resolved at PREFLIGHT)

Assign models by **cost-of-being-wrong × cost-of-verification**, not by role name: *high* on design and
security/quality review, *mid* on implement/QA, *low* on docs/style/plumbing, with a high-risk change
bumping the single matching role to *top*. Overlay `modelRouting.tierMap` turns tiers into concrete models
and `effortMap` does the same for effort; PREFLIGHT resolves both into state (§Stage 0.7) and every spawn
passes them explicitly (§core 6). Without the maps, both are advisory only. The rationale, the
security-refusing-model guard, the bigger levers, the small-but-high-stakes exception and the post-run
**cost readout** are in `${CLAUDE_PLUGIN_ROOT}/docs/model-routing.md`; PREFLIGHT needs the effort table
inline.

### Effort — on the judgment/mechanics axis, not on stage names

| effort | work |
|---|---|
| **xhigh** | design; the final adversarial review/critique — **Tier L only** |
| **high** | **root-cause analysis** (§sc-brainstorm); **triage** (fix-here / file-and-link — §sc-review); Tier M review; the G11 evidence mapping |
| **medium** | Tier S review; test design (sc-tdd); QA exploration; the edit itself when it is a multi-file refactor |
| **low** | worktree/branch setup, grep and file discovery, commit/push/PR, running tests, docs, manifest re-pinning, schema/XML validation, one-line edits |

Every stage gets an entry in `state.effort`: `brainstorm` and `qa` follow the size tier, `tdd` is
`medium`, `implement` inherits the tier, `review` scales with it, `ship` is `low` except its G11 evidence
mapping. **Root-cause analysis and triage are never dialed down**: they sit at `high` on a Tier S
change as much as a Tier L one, because they are outcomes rather than ceremony.

## Tier S path (the lightweight path)

On **Tier S** (§Stage 0.2) brainstorm/design/review collapse into one check, heavy suites give way to
self-tests/link checks, and model tiers and effort drop with them. The security lens stays even at
one-lens breadth — its `securityReviewModel` pin means nothing if the lens can be dialed away. Build/test
verification, the pre-PR review, root-cause analysis, triage and the conflict check still run — and the
release-artifact smoke when the diff touches a nature's `releaseSmoke.appliesTo` (§sc-qa).

**The bright line — dial ceremony, never an outcome.** *Ceremony* (dialable by size tier and risk): stage
count, model tier and effort level, worktree-or-not **on a single-track change**, lens breadth,
verifier/agent count, bake-off-or-not (§`${CLAUDE_PLUGIN_ROOT}/docs/bake-off.md`), QA-skip-for-trivial,
test-harness form. *Outcomes* (never dialed, for a typo fix and
an auth change alike): the six in §core; the fail-closed floors (security/data/contract); root-cause
analysis before any defect fix; the pre-PR conflict check (G12); and the git-write freeze while an
out-of-process reviewer reads the branch (§sc-review — a badly-timed `commit`/`checkout` can hang the reader
for an hour, and Tier S does not exempt you from waiting); and, for a UI nature, the accessibility floor —
the designer lens or at least its a11y checklist (§`${CLAUDE_PLUGIN_ROOT}/docs/visual-check.md`). When
unsure which side something is on, it is an outcome.

Root-cause analysis, triage and the conflict check are the cheapest stages and the first a right-sizing
pass reaches for. They are also where the cycle earns its keep: they stop you implementing a misdiagnosed
request, shipping a false positive or finding a conflict post-PR.
