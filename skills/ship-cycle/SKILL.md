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
| 1 | `sc-brainstorm` | agreed problem + acceptance criteria | G1 |
| 2 | `sc-design` | interfaces/boundaries + critic sign-off | G2/G3 |
| 3 | `sc-tdd` | failing tests for the change's logic (Red) | G4 |
| 4 | `sc-implement` | passing code in worktree isolation (Green) + build | G5/G6/G7/G7b |
| 5 | `sc-review` | multi-lens parallel review, 0 Critical/High | G8 |
| 6 | `sc-qa` | integration/E2E + seam contracts | G9 |
| 7 | `sc-ship` | docs + verify + PR + cleanup | G10–G13 |

This is the default map, not a required path. Run it in order unless a stage plainly has nothing to do here
— a config bump has no design to critique, a copy fix has no logic to test first — and record the skip as
`gates.<G> = "n/a: <one-line reason>"`, a decision rather than a drift, and distinguishable from a stage
never reached. For every stage that does run, **its gate must pass before the
next stage starts; on failure, loop back per the gate table's "On failure" column.**
**Loop cap: 3 per gate** (tracked in *this cycle's* state file, not in your head) — beyond that, return to
`sc-design` and notify the user.

Between every stage, artifacts pass through the state-file handoff rule below.

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

1. **Branch guard**: if on a protected branch (overlay `vcs.protectedBranches`), create `feature/*`|`fix/*`.
   A detached HEAD (empty `git branch --show-current`) has no cycle key — refuse and ask for a named
   branch, since state is keyed by branch.
2. **Change-size tier (S/M/L), then worktree isolation.** Pick the tier first and out loud — it is the dial
   every later stage reads, and leaving it implicit is how a one-line fix pays Tier-L ceremony. Record it
   as `state.size`; for **S** record the corroborating sites in `state.sizeEvidence: ["path:line", ...]`. S
   with fewer than two recorded sites is M: the party benefiting from S certifies it, so the evidence is
   the check. Print it here and with the routing (§Stage 0.7).

   | tier | what it is | what it gets |
   |---|---|---|
   | **S** | a single expression / constant / comment whose cause is already corroborated by **≥2 independent code sites**, with no runtime-behaviour ambiguity | branch, no worktree; inline self-verification; no verification fleet, except ≥1 independent refuter for a surviving Critical/High; security lens + one lens matched to the nature; conflict check; PR |
   | **M** | one module, one stack | worktree only if something else earns it; 1–2 lenses/verifiers |
   | **L** | multi-file, cross-stack, security-sensitive, or a migration | the full set — every stage, full lens breadth, QA |

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
   `.claude/ship-cycle.config.json`). Absent → built-in heuristics + log "defaults in use". Malformed →
   **fail closed**: stop and report, rather than running on defaults the operator didn't choose. One
   carve-out: a file that parses whose only problem is a schema-invalid `env` block — an opportunistic cost
   knob whose fallback is "spin up fresh" (see sc-qa) — emits `SC-DEGRADE-ENV` naming the section and
   fallback, ignores `env`, and continues. `env` alone, because it cannot touch a correctness floor.
4. **Classify change nature**: map changed paths via overlay `changeNature` (overlapping globs →
   most-specific wins; docs/i18n-only diffs prefer the docs rule) and print the resolved routing so it is
   auditable. Not one-shot: a later stage finding the change touches a stack the diff missed —
   a "mobile-only" change needing a new backend endpoint — re-runs it and the routing, updates state and
   adds the missing implementer axis. Scope growing at the design gate is normal.
   Classification also sets **G7b applicability**: a nature declaring overlay `bootCheck` has a loadable
   application context, so G7b (sc-implement) runs the boot smoke on its non-inert changes. A
   context-bearing nature with no `bootCheck` gets a one-line prompt each cycle and G7b degrades to a manual
   checklist — undeclared never silently means "no boot floor".
5. **Capture a test baseline** so "no new failures" is mechanical rather than a judgment call: run the
   nature's suite on the **base commit once** and record the pass/fail set in `state.baseline`. G6/G9 diff
   against it — a failure already there is not a regression, only a new one blocks — sparing later stages
   from re-deriving "mine or pre-existing?".
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
   plus an empty `telemetry`, an empty `reviewJobs` and `gitFreeze` inactive. Migrate a legacy bare state
   file for this branch first if one exists, and refuse if the target already belongs to a different
   `branch` (§State).

## State (real, not a metaphor)

**One state file per cycle**, keyed by the feature branch: `.claude/ship-cycle/<branch-slug>.json`
(slug = branch with `/` → `-`). It lives in the cycle's own working directory — its worktree if PREFLIGHT
created one, else the main checkout — so concurrent cycles never clobber a shared file and each owns its
`loops`. It carries `goal`/`branch`/`stage`/`gates`/`loops`, the PREFLIGHT results (`nature`, `risk`,
`size`, `baseline`, `models`, `effort`), `reviewJobs`, `gitFreeze` and `telemetry`; the full shape, naming,
collision guard, resume/selection and legacy migration are in
`${CLAUDE_PLUGIN_ROOT}/docs/state-file.md`.
Write it at every transition; read this cycle's file at PREFLIGHT to **resume** and to enforce **its** loop
cap, rather than counting loops in your head.

**One exception to per-cycle isolation: `gitFreeze` describes a repo-wide hazard.** `git worktree add /
remove / prune` and an `index.lock` recovery reach outside the cycle that runs them, and `prune` is
repo-scoped. Before any of those, scan **every** `.claude/ship-cycle/*.json` in this working directory for
an active `gitFreeze` or a `running` `reviewJobs` entry, and treat another cycle's freeze as binding
(§sc-review — Git-write freeze).

## Gate criteria

| Gate | Pass condition | On failure |
|---|---|---|
| G1 | acceptance criteria stated verifiably + user-agreed | re-brainstorm |
| G2/G3 | interfaces specified + 0 unresolved critic objections | re-design |
| G4 | failing tests exist for the change's logic (Red evidence) — or, for layout/copy/config, the execution-based verification is named instead (§core 3) | reject |
| G5 | build succeeds + new tests pass (Green) | build-fixer |
| G6 | no failures **new vs `state.baseline`** (`unrunnableHere` suites are neither pass nor regression); core coverage ≥80% | debugger → sc-implement |
| G7 | (if an artifact ships) real build succeeds | build-fixer |
| G7b | (if the nature declares `bootCheck`) full-context **eager** boot/context-load smoke passes on a non-inert change | build-fixer (env can't load → checklist) |
| G8 | 0 Critical/High (authz, paywall, anemic, N+1); every finding has a disposition (fixed-here / filed `#NN`); no `reviewJobs` entry still `running`/`launching`, `gitFreeze` released; UI → designer passes | → sc-implement (design flaw → sc-design) |
| G9 | 0 new defects in integration/E2E vs `state.baseline` (ignoring `unrunnableHere`); seams reproduced; ITs that **can** run here actually ran | → sc-implement |
| G10 | docs matching the change exist | writer |
| G11 | every claim mapped 1:1 to a test/build/QA log | rework |
| G12 | build+test+review+QA passed — a `degrade` G9 / `checklist` G7b counts **only** when its item is on the pre-merge manual gate, and an `"n/a: <reason>"` gate counts with its reason carried to the PR body; **branch merges cleanly into** overlay `vcs.defaultBase` (merge-tree probe + host `mergeable`) | merge base + resolve, re-verify |
| G13 | merged branch deleted (local + remote); feature worktree removed if created (**linked dep stores unlinked first**, never deleted through); cycle state file deleted; base synced | — |

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
verification, the pre-PR review, root-cause analysis, triage and the conflict check still run.

**The bright line — dial ceremony, never an outcome.** *Ceremony* (dialable by size tier and risk): stage
count, model tier and effort level, worktree-or-not **on a single-track change**, lens breadth,
verifier/agent count, bake-off-or-not (§`${CLAUDE_PLUGIN_ROOT}/docs/bake-off.md`), QA-skip-for-trivial,
test-harness form. *Outcomes* (never dialed, for a typo fix and
an auth change alike): the six in §core; the fail-closed floors (security/data/contract); root-cause
analysis before any defect fix; the pre-PR conflict check (G12); and the git-write freeze while an
out-of-process reviewer reads the branch (§sc-review — a badly-timed `commit`/`checkout` can hang the reader
for an hour, and Tier S does not exempt you from waiting). When unsure which side something is on, it is an
outcome.

Root-cause analysis, triage and the conflict check are the cheapest stages and the first a right-sizing
pass reaches for. They are also where the cycle earns its keep: they stop you implementing a misdiagnosed
request, shipping a false positive or finding a conflict post-PR.
