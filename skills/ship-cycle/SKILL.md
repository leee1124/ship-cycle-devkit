---
name: ship-cycle
description: Orchestrator for a gated development lifecycle. Runs PREFLIGHT (branch guard, change-size tier, worktree isolation, overlay load, change-nature + risk classification, model/effort routing) then chains the stage skills (sc-brainstorm → sc-design → sc-tdd → sc-implement → sc-review → sc-qa → sc-ship), enforcing gates and a loop cap via a state file. Framework-agnostic via a project overlay. Triggers "ship it", "run the lifecycle", "ship-cycle", "design to PR".
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

## Delegate vs act inline (orchestrator)

The orchestrator is **not a pure conductor** — spawning a subagent isn't free (it boots, gets re-briefed,
and **re-reads** the files), so delegating a trivial edit costs *more* (latency + tokens) than just doing
it inline. Delegate only when it **buys** something:

- **Independence (adversarial stages)** — an author can't review their own work. sc-design's critic,
  sc-review's lenses, and sc-qa **must** be separate agents; a fresh set of eyes is the whole point (it's
  what catches the author's blind spots). Non-negotiable.
- **Tier savings on substantial work** — mechanical work big enough that running it on a cheaper tier (a
  mid/low executor) beats doing it inline on the orchestrator's own (pricier, session-fixed) model.
- **Context hygiene** — the orchestrator is a **long-lived context**; everything it reads inline stays
  for the whole run. Hand off work that would dump a lot into it (reading large files, multi-step
  exploration) to a subagent that reads-and-discards and returns only the conclusion.
- **Parallelism** — independent work that can run concurrently.

Otherwise **act inline**: trivial + low-context + no independence needed (a few-line edit, a quick check).
The dividing line is **"does delegation buy something", not diff size** — a small but context-heavy or
high-stakes step can still warrant a subagent; a small trivial one does not.

## Iron Laws (non-negotiable)

Hard stops, not suggestions. Each lists the excuses agents reach for — all rejected.

1. **NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST.** Rejected: "trivial" · "just once" · "test after".
2. **NEVER CLAIM DONE WITHOUT RUNNING VERIFICATION AND READING ITS OUTPUT — AND NEVER JUDGE PASS/FAIL FROM
   A PIPED EXIT CODE.** Rejected: "should work" · "the grep said no failures". `cmd | grep | tail` returns
   the *tail's* status, so a failed build (or a `command not found`) reads green. Check the command's **own**
   exit status, or read the **machine-readable report** (surefire/JUnit XML, runner JSON) — never scraped
   stdout. (See sc-implement G5/G6 for why `pipefail` alone doesn't rescue a `grep`-in-the-pipe check.)
3. **NO PR WITHOUT A PASSING PRE-PR REVIEW.** Rejected: "small change" · "I reviewed while writing".
4. **NEVER COMMIT ON A PROTECTED BRANCH.** Branch first, always.
5. **STAY IN SCOPE.** Unrelated work → a new branch. A real defect you find **outside** the current
   scope (a latent bug, a dead-code path never wired up, a data error) → **file it** (issue/tracker) and
   keep going; do **not** fix it in this branch (scope creep) and do **not** silently drop it. The
   disposition is "found, filed, not fixed here."
6. **NEVER SPAWN A STAGE AGENT ON A DEFAULT MODEL.** Resolve tier→model at PREFLIGHT and pass `model=`
   explicitly on every stage agent call. Rejected: "the agent type has a sensible default" (a specialized
   type like `quality-reviewer` carries its own model that silently overrides your tier — this is exactly
   how a top/high-tier review ends up running on a cheap default) · "low-risk, doesn't matter" (then it
   resolves to a cheap tier anyway — still pass it, so the choice is auditable not accidental).

## Pipeline (one skill per stage)

| # | Stage skill | Produces | Gate |
|---|---|---|---|
| 0 | PREFLIGHT (this skill) | branch, **size tier**, worktree, overlay, model+effort routing, state | — |
| 1 | `sc-brainstorm` | agreed problem + acceptance criteria | G1 |
| 2 | `sc-design` | interfaces/boundaries + critic sign-off | G2/G3 |
| 3 | `sc-tdd` | failing tests for core logic (Red) | G4 |
| 4 | `sc-implement` | passing code in worktree isolation (Green) + build | G5/G6/G7/G7b |
| 5 | `sc-review` | multi-lens parallel review, 0 Critical/High | G8 |
| 6 | `sc-qa` | integration/E2E + seam contracts | G9 |
| 7 | `sc-ship` | docs + verify + PR + cleanup | G10–G13 |

Run in order; a gate must pass before the next stage. On failure, loop back per the gate table.
**Loop cap: 3 per gate** (tracked in *this cycle's* state file, not in your head) — beyond that, return to
`sc-design` and notify the user.

Between **every** stage, artifacts pass through the **state-file handoff rule** (plumbing, not an agent) — see below.

## State-file handoff — inter-stage artifact passing

Each stage **writes its output to a file** (design doc, test results, review findings) under the run's
artifact dir; the next stage **reads that file**. The orchestrator passes only **pointers (paths)**,
tracked in the state file — it never carries a full artifact through its own context. This is plain
orchestration plumbing (code + files), **not an LLM step**.

- **Verbatim by construction — zero cost, zero distortion.** Files carry artifacts whole: no
  summarizing, no token spend, no drift. This is deliberate. Summarizing between stages risks silently
  dropping an unresolved critic objection, a gate blocker, or failing evidence — and a model asked to
  condense might do exactly that. Passing the file verbatim removes the risk entirely, and verbatim
  carrying is a **code** job, not a model's — so no agent is spent on it.
- **Always on, every transition.** No branching on "is this handoff big enough": every stage persists
  its artifact and records the pointer, uniformly.
- **State** (`.claude/ship-cycle/<branch-slug>.json`, one per cycle): tracks each stage's artifact path + a one-line status.
- **When to put a model in a handoff instead**: only when you genuinely want a *trusted transformation*
  (extract acceptance criteria, reformat for the next tool). Then pick the tier that transformation's
  difficulty demands — never a blanket cheap "just summarize everything" pass.

## Stage 0 — PREFLIGHT

1. **Branch guard**: if on a protected branch (overlay `vcs.protectedBranches`), create `feature/*`|`fix/*`.
   A **detached HEAD** (empty `git branch --show-current`) has **no cycle key** — refuse and ask for a named
   branch, since state is keyed by branch (§State).
2. **Change-size tier (S/M/L), then worktree isolation.** Pick the tier **first and out loud** — it is the
   dial every later stage reads, and leaving it implicit is exactly why a one-line fix pays Tier-L ceremony.
   Record it as `state.size`, and for **S** record the corroborating sites as
   `state.sizeEvidence: ["path:line", "path:line"]`. **S with fewer than two recorded sites is not S** — if
   you cannot write them down it is M, because the party that benefits from S is the one certifying it.
   **Print the tier here, inline, before the worktree decision below** (state itself is written at step 8),
   and again with the routing (§Stage 0.7 — Resolve per-stage models and effort).

   | tier | what it is | what it gets |
   |---|---|---|
   | **S** | a single expression / constant / comment whose cause is already corroborated by **≥2 independent code sites**, with no runtime-behaviour ambiguity | branch, **no worktree**; inline self-verification; **no verification fleet** — except a surviving Critical/High, which still gets **≥1 independent refuter, never zero**; **the security lens plus one lens matched to the change nature** — the security lens never drops; conflict check; PR |
   | **M** | one module, one stack | worktree only if something else earns it; 1–2 lenses/verifiers |
   | **L** | multi-file, cross-stack, security-sensitive, or a migration | the full set — every stage, full lens breadth, QA |

   **Tier S is a claim about evidence, not about diff size.** "It's one line" does not earn it; the
   corroborated cause does. If you cannot name the ≥2 sites, it is not S. **Re-classification is monotonic,
   like risk (step 6)**: a tier that turns out bigger than it looked moves **up** and adds the ceremony
   back — it never moves down mid-cycle to retire a stage you already owe. Tier dials *ceremony only*,
   never an outcome (§Tier S path → the bright line).

   Then **worktree isolation (conditional)**: create an isolated worktree **only when it earns its keep** —
   the change is split across stacks (backend/web/mobile) or runs parallel implementers, where
   `git worktree add ../<repo>-<branch> -b <branch>` lets them work **without collisions**. For a
   single-track change (one platform, sequential), a plain feature branch is enough — worktree is pure
   overhead. Record the worktree path in state when used. When several worktrees are created and overlay
   `env.sharedNodeModules` is set, share one dep store across them (pnpm store / linked `node_modules`) so
   each doesn't re-install the full tree — see sc-qa's per-cycle cost note. **Record how the store is
   linked** (`ln -s`, `cmd /c mklink /J`, or a pnpm hardlink store), because teardown has to find it again:
   every link made here is a path by which a recursive delete reaches the shared store and wipes it for
   every other worktree and parallel cycle. sc-ship's Cleanup (G13) step 1 owns that sweep; it is not
   optional and it is not conditional on this flag.
   **Before any worktree removal or `prune` here**, confirm the path is not a `reviewJobs[].snapshot` of an
   active cycle and that no cycle holds an `active` `gitFreeze` — `prune` drops registry entries
   **repo-wide**, not just this cycle's (§sc-review — Git-write freeze).
   **If the worktree path already exists** — a leftover from a previous cycle whose teardown hit the
   locked-files fallback — do **not** clear it with a recursive delete. Run G13 step 1's link sweep and
   unlink every hit first; then `git worktree remove --force <path>` if git still tracks it, otherwise
   `git worktree prune` and delete the now link-free directory.
   **Stale `index.lock` after a timed-out `worktree add`.** On a large/slow filesystem the checkout can
   outlive a command timeout. By then the add has created the branch, the directory **and** the
   registration — only the checkout is unfinished — and it leaves an `index.lock` behind, under the *main*
   repo's git dir: resolve it with `git -C <worktree> rev-parse --git-path index.lock`, not
   `<worktree>/.git/…` (inside a worktree `.git` is a **file**, not a directory). Whatever resumes the
   checkout then fails with exit 128 (`Unable to create '…/index.lock': File exists`).
   - **Gate the recovery on the lock being stale, not held.** `find "$(git -C <worktree> rev-parse
     --git-path index.lock)" -mmin +<the timeout you just exceeded, in minutes>` printing the path is your
     go-ahead; printing nothing means an add is still in flight — **wait, don't delete**, since deleting a
     live lock corrupts the checkout in progress. ("No git process is running" is *not* the check: the
     crashed add you're recovering from leaves no process, so it is trivially true exactly when it tells
     you nothing.)
   - **Then finish the checkout in place — do not re-run `worktree add`.** Delete the stale lock and run
     `git -C <worktree> checkout -f`. Re-adding cannot work: the branch the timed-out add already created
     makes it fail with `fatal: a branch named '<branch>' already exists`, and `--force` does not help.
     Only if the checkout still fails, restart cleanly — sweep + unlink (G13 step 1), delete the
     directory, `git worktree prune`, then `git worktree add <path> <branch>` **without `-b`**, since the
     branch already exists. Raise the timeout rather than looping; a lock that reappears right after you
     delete it means an add is still running.
3. **Load overlay**: read `${CLAUDE_PROJECT_DIR}/<projectConfig>` (plugin `projectConfig` setting;
   default `.claude/ship-cycle.config.json`). **Absent** → built-in heuristics + log "defaults in use".
   **Malformed → fail closed: stop and report; do not silently fall back.** *One* narrow carve-out: if the
   file parses and the only problem is a **schema-invalid `env`** block — a purely opportunistic cost knob
   whose documented fallback is "spin up fresh" (see sc-qa) — emit `SC-DEGRADE-ENV` (name the section + the
   fallback), ignore `env`, and continue. `env` only, because it can never touch a correctness floor; every
   other section (`vcs`, `changeNature`, `modelRouting`, `i18n`, `design`) and any unparseable file still
   halts. (A docs-only kit has no validator — the "safe to skip?" call is an LLM eyeballing an unvalidated
   file, so it's kept to one always-safe section, not a taxonomy that could misclassify a load-bearing block
   as skippable.)
4. **Classify change nature**: map changed paths via overlay `changeNature`. Overlapping globs →
   **most-specific glob wins**; docs/i18n-only diffs prefer the docs rule. **Print the resolved routing**
   (which tests/reviews will run) so it's auditable. **Classification is not one-shot**: if a later stage
   (especially `sc-design`) discovers the change touches a stack or axis the initial diff didn't show —
   e.g. a "mobile-only" change that design reveals needs a new backend endpoint — **re-run this
   classification and the model routing**, update state, and add the missing implementer axis. A scope
   that grows at the design gate is normal, not a failure; route for the scope you actually have.
   Classification also sets **G7b applicability**: a nature that declares overlay `bootCheck` has a
   loadable application context, so G7b (sc-implement) runs the boot/context-load smoke on its non-inert
   changes. If a nature looks **context-bearing** (a backend/service stack) but declares **no** `bootCheck`,
   **print a loud one-line prompt every cycle** — "declare `bootCheck` for nature X so boot is gated" — and
   let G7b degrade to a manual checklist; undeclared must never silently mean "no boot floor". (Printed
   every cycle, not a two-strike block: per-cycle state is per-branch and not carried across cycles (deleted
   at G13, or overwritten when a branch is reused), so there is no cross-cycle memory to remember the earlier
   nag.)
5. **Capture a test baseline** (so "no new failures" is mechanical, not a judgment call): run the
   nature's test suite on the **base commit once** and record the pass/fail set in state (`baseline`).
   Pre-existing failures on the base branch otherwise force every later stage (sc-tdd/implement/qa) — and
   every parallel implementer — to re-derive "is this my regression or was it already red?" by hand
   (repeatedly, via stash-and-compare). With a baseline recorded, gates G6/G9 diff against it: a failure
   already in `baseline` is not a regression; only a **new** one blocks. Skip only on the **Tier S** path —
   and a skipped baseline means `unrunnableHere` is **absent, not empty**: the category is *unavailable* on
   Tier S, because there is no pre-committed set for it to be pre-committed against. A Tier S run that meets
   a suite it cannot start **re-tiers upward to M** (§Stage 0.2, monotonic) and captures the baseline
   against the base commit; it never mints a quarantine mid-cycle.

   **A third category — `unrunnableHere`.** Pass/fail is binary and some suites are neither: an
   integration/DDL/DB-gated suite this environment **cannot start at all** (no database reachable, a
   service absent, a sandbox policy refusing the connection), verified elsewhere against a real dependency.
   It is not a failure to diff against, and 0.2.23 rightly forbids counting it as passed — so today a large
   part of a suite ends up with **no truthful status**, which is how "can't run it here" quietly becomes
   either a fake pass or a fake regression. Record it instead:
   `baseline.unrunnableHere: [{ suite, reason, startupError, probe, capturedAt }]`. (`failing` is
   per-case, `unrunnableHere` per-suite — a suite that could not start has no cases to enumerate.)
   - **The boundary is where the suite stops.** *Unrunnable-here* means the suite **could not start**
     because a **dependency** is missing. A suite that **starts and fails** is `failing`. A suite that
     starts and **skips itself** — `@Disabled`, zero-executed, DDL/seed/auth not provisioned — stays
     0.2.23's **FAIL/deferral**. This category is **not a laundering route for a disabled test**; it exists
     only for a dependency the environment refuses to provide. Runners blur this: a context-init failure is
     commonly reported as an *error on every test method* (reads like `failing`) and a container-gated
     suite as *skipped* (reads like 0.2.23). **When the report is ambiguous it is not unrunnable-here** —
     record it under whichever stricter category the runner named, and say in one line why.
   - **Two pieces of evidence, and the dependency probe is the weaker one.** Record (a) `startupError` —
     the **suite's own attempted run** in this baseline, terminating with an initialization error **before
     executing any test**; paste the error line — and (b) `probe`, the dependency command and what it
     returned (`connection refused`, `no such host`, a policy denial). Only (a) says *this suite* could not
     start; (b) says the environment is missing something, and **one (b) never licenses quarantining a
     second suite**. **Either piece missing ⇒ not unrunnable-here.** Where the nature declares overlay
     `envProbe`, run it — a **passing** `envProbe` is a hard bar: nothing under that nature may be
     quarantined for that dependency. Be honest about what this buys: both pieces are self-reported prose
     that nothing validates. They are **friction, not proof**. What actually holds this category shut is
     that it is fixed at the base commit (below) and that it satisfies nothing (further below).
   - **Pre-committed: fixed at PREFLIGHT, and it may only shrink.** It is classified **against the base
     commit, before this change exists**. Moving a suite **out** (it became runnable) is free and always
     welcome. **There is no path that adds a suite mid-cycle.** A suite that ran at PREFLIGHT and won't run
     now is a **finding** — attach a debugger; it is an environment regression this change may have caused.
     A suite **not in the baseline run at all** (written this cycle by sc-tdd, or never selected by the
     nature's `tests` command) may only **inherit** an existing entry, and only when it is gated by the
     **same dependency whose probe already failed at PREFLIGHT** — recorded with
     `inheritedFrom: "<the PREFLIGHT entry>"`. Any other growth means re-running this step against the base
     commit from the top, never editing the set in place.
   - **It never satisfies anything.** G6/G9 stop treating these suites as regressions; they do **not**
     start treating them as coverage. sc-ship maps every acceptance criterion whose only coverage is an
     unrunnable-here suite to `review-only (ci-deferred)` (§sc-ship G11) and surfaces it on the pre-merge
     manual gate (§sc-ship G12).
6. **Classify risk** (for model routing, below). The label dials **ceremony only** — the model tier and
   which role is upgraded — **never an outcome**: verification, fresh-eyes review, and the fail-closed
   floors run regardless of the label. **Not one-shot (mirrors step 4):** if a later stage reveals a
   higher-stakes axis the initial diff didn't show (a token lifetime, a migration, an API contract),
   re-classify and re-resolve routing. Re-escalation is **monotonic** — it may add ceremony back (restore a
   dropped tier, reinstate a lens or QA) but never removes an outcome.
7. **Resolve per-stage models *and effort* now (not per-spawn)**: for each stage, resolve its tier → a
   concrete model via overlay `modelRouting.tierMap` (base pyramid + any risk upgrade), and its work-kind →
   an effort level via `modelRouting.effortMap`, scaled by `state.size` (§Model routing → Effort). Write
   both to state (`models`, `effort`) and **print them** with the size tier (auditable, e.g.
   `size=S · review→sonnet/medium, implement→sonnet/low`). Record which risk upgrades fired in
   `telemetry.upgrades` — that list is what the post-run readout reports (§Cost readout).
   Every stage then spawns with `model = state.models[<stage>]` (and `state.effort[<stage>]`) — never an
   agent type's default. This turns "remember to bridge the tierMap" into "copy a concrete value", which is
   the difference that makes it actually happen.
   **Routing guard — a security review must never run on a model that refuses security analysis** (it would
   silently no-op — "ran" but checked nothing). If overlay `modelRouting.securityReviewModel` is set, the
   **`security` and `authz` review lenses use that model**, overriding their tier-resolved model — record it
   in state alongside `models.review` (as `models["review.security"]`, a flat key sibling to `review`) so
   sc-review spawns those lenses with it (§sc-review); when the pin differs from the tier-resolved model,
   **print** `SC-ROUTE-AVOID: security-lens <tier-model>→<securityReviewModel>` (no log on a no-op pin). This is
   a fail-closed floor, not ceremony: a security review that quietly no-ops is worse than a loud stop. (Absent
   the setting, the security lens uses its tier model as before — the guard is opt-in, since only the operator
   knows which model refuses.)
8. **Init state**: write this cycle's `.claude/ship-cycle/<branch-slug>.json` (including `branch`, `size`,
   `sizeEvidence` when the tier is S, `models`, `effort`, `baseline` including its `unrunnableHere` set,
   an empty `telemetry`, an empty `reviewJobs`, and `gitFreeze` inactive). First
   migrate a legacy bare state file if one exists for this branch, and refuse if the
   target file already belongs to a different `branch` (§State). A **detached HEAD** (empty slug) has no
   cycle key — that's caught at step 1.

## State (real, not a metaphor)

**One state file per cycle**, keyed by the feature branch: `.claude/ship-cycle/<branch-slug>.json`, where
`<branch-slug>` is the branch transformed by **exactly** `tr '/' '-'` (no case change, no other substitution
— binding identically on the writer here and on every reader, so they can never disagree). The file lives in
the **cycle's own working directory** (its worktree if PREFLIGHT created one, else the main checkout), and
`/status`/`/resume`/`/ship` run **from that directory** so `git branch --show-current` names *this* cycle.
So concurrent cycles on different branches — coexisting in one checkout's `.claude/ship-cycle/`, or each in
its own worktree — never clobber a shared file, and each file owns its `loops` (per-cycle loop caps for
free). Implementer sub-worktrees carry **no** cycle state — only the orchestrator's cwd does. Shape:
```json
{ "goal": "...", "branch": "...", "worktreePath": "...", "stage": "sc-design",
  "gates": { "G1": "pass", "G2": "pass" }, "loops": { "G8": 1 },
  "nature": ["backend"], "risk": ["auth"], "size": "L",
  "baseline": { "capturedOn": "<base-sha>", "failing": ["suiteA#case", "..."],
                "unrunnableHere": [{ "suite": "suiteB", "reason": "no database reachable",
                                     "startupError": "<the suite's own init error, before any test ran>",
                                     "probe": "<dependency ping> → connection refused",
                                     "capturedAt": "preflight" }] },
  "models": { "brainstorm": "opus", "design": "opus", "tdd": "sonnet", "implement": "sonnet",
              "review": "opus", "qa": "sonnet", "ship": "sonnet" },
  "effort": { "design": "xhigh", "tdd": "medium", "implement": "low",
              "review": "high", "qa": "medium", "ship": "low" },
  "reviewJobs": [{ "id": "<host job id>", "agent": "<external reviewer name>",
                   "lens": "external-adversarial", "status": "running", "startedAt": "<iso>",
                   "endedAt": null, "snapshot": "<path outside the worktree>",
                   "resultPath": "<path outside the worktree>" }],
  "gitFreeze": { "active": false, "branch": null, "since": null, "releasedAt": null, "reason": null,
                 "releaseOn": "snapshot" },
  "telemetry": { "upgrades": ["auth → security lens: high→top"],
                 "stages": { "review": { "tier": "top", "model": "opus", "effort": "high",
                                         "tokens": null, "cost": null } } } }
```
Write it at every transition; read **this cycle's** file at PREFLIGHT to **resume** and to enforce **its**
loop cap (don't count loops in your head — each cycle's file owns its own `loops`). **Resume/select**: read
`.claude/ship-cycle/<current-branch-slug>.json` — a mid-pipeline `stage` resumes that cycle; `complete` /
`failed` / absent means a **fresh** cycle for this branch (init a new file). Because each cycle owns a
branch-named file there is no shared active file to clobber and no "archive the stale active file" dance —
concurrent cycles coexist, and sequential ones just leave the finished file behind (deleted at G13 when the
branch is). **One exception to per-cycle isolation: `gitFreeze` describes a *repo-wide* hazard.**
`git worktree add / remove / prune` and an `index.lock` recovery reach outside the cycle that runs them —
`prune` is repo-scoped. Before any of those, scan **every** `.claude/ship-cycle/*.json` in this working
directory, not just this branch's, for an `active` `gitFreeze` or a `running` `reviewJobs` entry, and treat
another cycle's freeze as binding on the shared operation (§sc-review — Git-write freeze).
**Collision guard**: the slug is lossy (`feat/x` and `feat-x` both → `feat-x`), so the JSON
`branch` field is the exact record — on init, if the target file already exists with a **different**
`branch`, refuse/warn rather than clobber another cycle. **Migration (PREFLIGHT-only, one-time)**: if the
per-branch file is absent and a legacy bare `.claude/.ship-cycle-state.json` exists whose `branch` **equals**
the current branch, **move** it into the per-branch path (rewrite, then delete the bare file); if its
`branch` differs, ignore it (never read another branch's state). Reusing one branch for a **new** goal
overwrites its prior completed file — acceptable: state is gitignored run-state and the PR + git history hold
the real record. `models` is resolved once at PREFLIGHT (§Stage 0.7) with risk
upgrades already applied — every stage reads its model from here rather than re-deriving it. A stage
whose roles span tiers (e.g. `sc-ship`: writer=low, verifier=high, git-master=mid) records its dominant
tier here; the stage skill resolves the per-role exceptions from the same tierMap. (§Stage 0.N is PREFLIGHT
list item N — §Stage 0.2 is "Change-size tier, then worktree isolation", §Stage 0.5 is "Capture a test
baseline", and §Stage 0.7 is "Resolve
per-stage models *and effort*".) The map also carries `review.security` (a flat key,
sibling to `review`, absent unless overlay `modelRouting.securityReviewModel` is set — §Stage 0.7).

## Gate criteria

| Gate | Pass condition | On failure |
|---|---|---|
| G1 | acceptance criteria stated verifiably + user-agreed | re-brainstorm |
| G2/G3 | interfaces specified + 0 unresolved critic objections | re-design |
| G4 | failing tests exist for core logic (Red evidence) | reject |
| G5 | build succeeds + new tests pass (Green) | build-fixer |
| G6 | no failures **new vs `state.baseline`** (pre-existing base-branch reds don't block; `baseline.unrunnableHere` suites are neither pass nor regression), core coverage ≥80% | debugger → sc-implement |
| G7 | (if an artifact ships) real build succeeds | build-fixer |
| G7b | (if the nature declares `bootCheck`) full-context **eager** boot/context-load smoke passes on a non-inert change | build-fixer (env can't load → checklist) |
| G8 | 0 Critical/High (authz, paywall, anemic, N+1); **every finding carries a disposition** (fixed-here / filed `#NN`); **no `reviewJobs` entry still `running`/`launching`** and `gitFreeze` released. UI → designer passes | → sc-implement (design flaw → sc-design) |
| G9 | 0 new defects in integration/E2E (new vs `state.baseline`, ignoring `baseline.unrunnableHere`); seams reproduced; ITs that **can** run here actually ran | → sc-implement |
| G10 | docs matching the change exist | writer |
| G11 | every claim mapped 1:1 to a test/build/QA log | rework |
| G12 | build+test+review+QA passed — a `degrade` G9 / `checklist` G7b counts **only** when its item is on the pre-merge manual gate; base = overlay `vcs.defaultBase`; **branch merges cleanly into base** (merge-tree probe + host `mergeable`) | merge base + resolve, re-verify |
| G13 | merged branch deleted (local + remote); feature worktree removed if one was created (**linked dep stores unlinked first**, never deleted through); **cycle state file deleted**; base synced | — |

## Model routing (token efficiency)

Assign models by **cost-of-being-wrong × cost-of-verification**, not by role name.

- **Base pyramid**: *high* on design & security/quality review; *mid* on implement/QA; *low* on
  docs/style/plumbing. (Inter-stage handoff is not a model step — see the state-file handoff rule.)
- **Risk-gated upgrade**: high-risk changes bump the *single matching role* to *top* —
  auth/payment→security review, schema/API-contract→design, complex algorithm→algorithm review.
  Match the *kind* of risk, not always the same role. Usually 0–1 upgrades per run.
- **Tier → model bridge (required to execute)**: read overlay `modelRouting.tierMap`
  (e.g. `{"top":"opus","high":"opus","mid":"sonnet","low":"haiku"}`), resolve every stage's tier at
  PREFLIGHT into `state.models` (§Stage 0.7), and **pass `model = state.models[<stage>]` on each stage's
  agent call**. Without a tierMap, tiers are advisory only. **The trap (Iron Law 6)**: a specialized
  agent type — `quality-reviewer`, `security-reviewer`, `architect`, etc. — carries its *own* default
  model that **silently overrides your tier** when you omit `model=`. That is precisely how a review
  intended for the top/high tier ends up on a cheaper default without anyone noticing. Pre-resolving into
  `state.models` and passing it explicitly is the fix — never trust the agent-type default.
- **Security-refusing-model guard**: some models **refuse security analysis**, so a security/authz review
  routed to one silently no-ops — it "ran" but checked nothing. Overlay `modelRouting.securityReviewModel`
  pins the model the `security`/`authz` lenses use, overriding their tier (§Stage 0.7 → spawned in
  sc-review) — set it to the most capable model that will actually *do* security review. A fail-closed
  floor, not dialable ceremony.
- **Bigger levers first**: prompt caching (cache the repo/diff/design doc), the effort dial above, and
  "cheap path first" for implementation (mid tier → verify → escalate only the failing fix). **Exception**:
  for inherently complex work (novel algorithms, intricate UI like SVG/canvas), start at the higher tier —
  cheap-path-first there just buys a wasted failed attempt.

### Effort — on the judgment/mechanics axis, not on stage names

Tier says *which model*; **effort** says how hard it thinks. Keying effort to stage names leaks, because
the two most judgment-dense pieces of work in the cycle answer to no stage's name: **root-cause analysis**
and **triage** (which findings are real, which are false positives, which are out of scope). Price the
*work*, and let the size tier scale it:

| effort | work |
|---|---|
| **xhigh** | design; the final adversarial review/critique — **Tier L only** |
| **high** | **root-cause analysis** (§sc-brainstorm); **triage** (fix-here / file-and-link — §sc-review); Tier M review; the G11 evidence mapping |
| **medium** | Tier S review; test design (sc-tdd); QA exploration; the edit itself when it is a multi-file refactor |
| **low** | worktree/branch setup, grep and file discovery, commit/push/PR, running tests, docs, manifest re-pinning, schema/XML validation, one-line edits |

**Every stage gets an entry in `state.effort`** — `brainstorm` and `qa` follow the size tier, `tdd` is
`medium`, `implement` inherits the tier, `review` scales with the tier, `ship` is `low` except its G11
evidence mapping. A stage whose roles span kinds records its **dominant** effort here and resolves the
per-role exceptions from the same map, exactly as `models` already does for tiers (§State).

Two consequences, both deliberate:
- **Review effort scales with the size tier** instead of being pinned at the top. Pinning every review at
  maximum is what turns a corroborated one-line fix into a six-figure-token verification pass — so a
  blanket "reviews are always xhigh" rule would leave the actual waste untouched.
- **The edit inherits the tier.** A one-liner whose cause is already pinned is `low`; a multi-file
  refactor *is* design work and is priced as such.

**Bridge to the host (mirrors tierMap).** Overlay `modelRouting.effortMap` maps these levels onto whatever
your host calls them; PREFLIGHT resolves per-stage effort into `state.effort` (§Stage 0.7) and every spawn
passes it explicitly, exactly as with `model=` — a default effort is the same silent override as a default
model (Iron Law 6). **Without an `effortMap`, effort levels are advisory only** — same rule as tiers.

**Root-cause analysis and triage are never dialed down.** They sit at `high` on a Tier S change as much as
a Tier L one, because they are *outcomes*, not ceremony (§bright line). Right-sizing that reaches them is
not a saving: it is how you ship the wrong fix confidently. When a request arrives as "relabel that bar as
Total" and the bar is in fact a disjoint bucket, implementing it as stated ships a chart that actively
misleads — root-cause analysis is the only stage that catches it, and it costs a few greps.

## Tier S path (the lightweight path)

**Tier S** (§Stage 0.2 — config/docs/one-liner with a corroborated cause): collapse brainstorm/design/review
into one check, substitute heavy suites with self-tests/link checks, reduce review to **the security lens
plus one lens matched to the change nature** (the security lens never drops — it is a fail-closed floor,
and its `securityReviewModel` pin is meaningless if the lens itself can be dialed away), run **no
verification fleet** except that a surviving Critical/High still gets **at least one** independent refuter,
take no worktree, and **drop the model tiers** (mid/low instead of high) and the effort levels with them.
**Never skip build/test verification, the pre-PR review, root-cause analysis, triage, or the pre-PR
conflict check.**

**The bright line — dial ceremony, never an outcome.** *Ceremony* (dialable by size tier and risk): stage
count, model tier **and effort level**, worktree-or-not, lens breadth, **verifier/agent count**,
QA-skip-for-trivial, TDD-harness form. *Outcomes* (never dialed, for a typo fix and an auth change alike):
verification actually ran and its output was read; review by fresh eyes before any PR; the fail-closed
floors (security/data/contract); a failing test before prod code; **root-cause analysis before any defect
fix**; **triage of every finding** (fix-here or filed-and-linked — never silently dropped, Iron Law 5 +
§sc-review); **the pre-PR conflict check** (G12); and **the git-write freeze while an out-of-process
reviewer is reading the branch** (§sc-review — an operational floor: a badly-timed `commit`/`checkout` can
hang the reader for an hour, and Tier S does not exempt you from waiting). When unsure which side something
is on, it is an outcome — keep it.

**The three that pay for the cycle.** Root-cause analysis, triage and the conflict check are the cheapest
stages in the pipeline and the ones a right-sizing pass reaches for first, because they have no impressive
artifact to show. They are also where the cycle earns its keep: they are what stop you implementing a
misdiagnosed request, shipping a review's false positive, and discovering a conflict after the PR is open.
Cutting them is not right-sizing — it is removing the part that was working.

## Cost readout (post-run)

Model routing is this kit's efficiency claim, and 0.2.6 made it **enforced**. Enforcement is not
measurement: a per-stage tier that is pinned but never counted leaves the claim unfalsifiable on *your*
repo and leaves `tierMap`/`effortMap` tunable only by intuition. So the cycle **reports what it spent**.

- **Accumulate as you go — each stage writes its own row at its gate.** When a stage sets its gate in
  state, it appends to `state.telemetry.stages[<stage>]` the **resolved tier, model and effort** (already in
  `models`/`effort`) plus whatever usage the host actually exposes — tokens, cost, wall-clock. Each stage
  skill carries this instruction next to its gate; the orchestrator does not write rows on their behalf,
  because a stage that runs as a subagent is the only party that can see its own usage.
  `telemetry.upgrades` records which risk-gated upgrades fired (§Stage 0.7).
- **Never invent a number.** Most hosts expose no per-agent token count. Record `null` and print
  `unavailable` for what you cannot measure; the resolved tier/effort per stage is *always* recordable and
  is itself the useful half. A fabricated cost table is worse than an honest gap — it is the same
  false-green class as a scraped exit code (Iron Law 2).
- **Emit before *anything* in G13 deletes anything.** The state file lives in the cycle's working
  directory — **which is the worktree itself when PREFLIGHT created one** (§State) — so removing the
  worktree destroys `telemetry` just as surely as deleting the file does. sc-ship therefore emits the
  readout as the **first** act of G13 and writes it to an artifact dir **outside** the worktree; otherwise
  the only record of what the run cost is destroyed by the step that ends the run (§sc-ship Cleanup).
- **Read-only.** The readout changes no gate and blocks nothing; it exists so an operator can see whether
  routing paid off here and tune `tierMap`/`effortMap` with data instead of an asserted percentage.
`/status` prints the same table mid-run.

**Exception — small but high-stakes.** Keep the higher review tier even for a tiny diff when
cost-of-being-wrong is high or verification is expensive: build/release config, **dependency/lockfile
changes**, API/data contracts, data-loss paths, security. Tier by cost-of-being-wrong ×
verification-difficulty, **not by diff size** — e.g. a 10-line dependency bump can silently waste an
expensive cloud rebuild, so its review earns the high tier though it "looks" trivial. (Real run: a
high-tier review of exactly such a bump caught a stale-lockfile defect a cheaper pass would likely
have missed.)
