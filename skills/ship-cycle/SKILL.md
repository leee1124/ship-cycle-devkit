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
2. **NEVER CLAIM DONE WITHOUT RUNNING VERIFICATION AND READING ITS OUTPUT.** Rejected: "should work".
3. **NO PR WITHOUT A PASSING PRE-PR REVIEW.** Rejected: "small change" · "I reviewed while writing".
4. **NEVER COMMIT ON A PROTECTED BRANCH.** Branch first, always.
5. **STAY IN SCOPE.** Unrelated work → a new branch.
6. **NEVER SPAWN A STAGE AGENT ON A DEFAULT MODEL.** Resolve tier→model at PREFLIGHT and pass `model=`
   explicitly on every stage agent call. Rejected: "the agent type has a sensible default" (a specialized
   type like `quality-reviewer` carries its own model that silently overrides your tier — this is exactly
   how a top/high-tier review ends up running on a cheap default) · "low-risk, doesn't matter" (then it
   resolves to a cheap tier anyway — still pass it, so the choice is auditable not accidental).

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
- **State** (`.claude/.ship-cycle-state.json`): tracks each stage's artifact path + a one-line status.
- **When to put a model in a handoff instead**: only when you genuinely want a *trusted transformation*
  (extract acceptance criteria, reformat for the next tool). Then pick the tier that transformation's
  difficulty demands — never a blanket cheap "just summarize everything" pass.

## Stage 0 — PREFLIGHT

1. **Branch guard**: if on a protected branch (overlay `vcs.protectedBranches`), create `feature/*`|`fix/*`.
2. **Worktree isolation (conditional)**: create an isolated worktree **only when it earns its keep** —
   the change is split across stacks (backend/web/mobile) or runs parallel implementers, where
   `git worktree add ../<repo>-<branch> -b <branch>` lets them work **without collisions**. For a
   single-track change (one platform, sequential), a plain feature branch is enough — worktree is pure
   overhead. Record the worktree path in state when used.
3. **Load overlay**: read `${CLAUDE_PROJECT_DIR}/<projectConfig>` (plugin `projectConfig` setting;
   default `.claude/ship-cycle.config.json`). **Absent** → built-in heuristics + log "defaults in use".
   **Malformed JSON / schema-invalid** → stop and report; do not silently fall back.
4. **Classify change nature**: map changed paths via overlay `changeNature`. Overlapping globs →
   **most-specific glob wins**; docs/i18n-only diffs prefer the docs rule. **Print the resolved routing**
   (which tests/reviews will run) so it's auditable.
5. **Classify risk** (for model routing, below).
6. **Resolve per-stage models now (not per-spawn)**: for each stage, resolve its tier → a concrete model
   via overlay `modelRouting.tierMap` (base pyramid + any risk upgrade). Write the result to state
   `models` and **print it** (auditable, e.g. `review→opus, implement→sonnet`). Every stage then spawns
   with `model = state.models[<stage>]` — never an agent type's default. This turns "remember to bridge
   the tierMap" into "copy a concrete value", which is the difference that makes it actually happen.
7. **Init state**: write `.claude/.ship-cycle-state.json` (including `models`).

## State (real, not a metaphor)

`.claude/.ship-cycle-state.json`:
```json
{ "goal": "...", "branch": "...", "worktreePath": "...", "stage": "sc-design",
  "gates": { "G1": "pass", "G2": "pass" }, "loops": { "G8": 1 },
  "nature": ["backend"], "risk": ["auth"],
  "models": { "brainstorm": "opus", "design": "opus", "tdd": "sonnet", "implement": "sonnet",
              "review": "opus", "qa": "sonnet", "ship": "sonnet" } }
```
Write it at every transition; read it at PREFLIGHT to **resume** and to enforce the loop cap
(don't count loops in your head). `models` is resolved once at PREFLIGHT (§Stage 0.6) with risk
upgrades already applied — every stage reads its model from here rather than re-deriving it. A stage
whose roles span tiers (e.g. `sc-ship`: writer=low, verifier=high, git-master=mid) records its dominant
tier here; the stage skill resolves the per-role exceptions from the same tierMap.

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
  docs/style/plumbing. (Inter-stage handoff is not a model step — see the state-file handoff rule.)
- **Risk-gated upgrade**: high-risk changes bump the *single matching role* to *top* —
  auth/payment→security review, schema/API-contract→design, complex algorithm→algorithm review.
  Match the *kind* of risk, not always the same role. Usually 0–1 upgrades per run.
- **Tier → model bridge (required to execute)**: read overlay `modelRouting.tierMap`
  (e.g. `{"top":"opus","high":"opus","mid":"sonnet","low":"haiku"}`), resolve every stage's tier at
  PREFLIGHT into `state.models` (§Stage 0.6), and **pass `model = state.models[<stage>]` on each stage's
  agent call**. Without a tierMap, tiers are advisory only. **The trap (Iron Law 6)**: a specialized
  agent type — `quality-reviewer`, `security-reviewer`, `architect`, etc. — carries its *own* default
  model that **silently overrides your tier** when you omit `model=`. That is precisely how a review
  intended for the top/high tier ends up on a cheaper default without anyone noticing. Pre-resolving into
  `state.models` and passing it explicitly is the fix — never trust the agent-type default.
- **Bigger levers first**: prompt caching (cache the repo/diff/design doc), an effort dial, and
  "cheap path first" for implementation (mid tier → verify → escalate only the failing fix). **Exception**:
  for inherently complex work (novel algorithms, intricate UI like SVG/canvas), start at the higher tier —
  cheap-path-first there just buys a wasted failed attempt.

## Lightweight path

Trivial changes (config/docs/one-liner): collapse brainstorm/design/review into one check, substitute
heavy suites with self-tests/link checks, reduce review to quality+security, and **drop the model tiers**
(mid/low instead of high). **Never skip build/test verification or the pre-PR review.**

**Exception — small but high-stakes.** Keep the higher review tier even for a tiny diff when
cost-of-being-wrong is high or verification is expensive: build/release config, **dependency/lockfile
changes**, API/data contracts, data-loss paths, security. Tier by cost-of-being-wrong ×
verification-difficulty, **not by diff size** — e.g. a 10-line dependency bump can silently waste an
expensive cloud rebuild, so its review earns the high tier though it "looks" trivial. (Real run: a
high-tier review of exactly such a bump caught a stale-lockfile defect a cheaper pass would likely
have missed.)
