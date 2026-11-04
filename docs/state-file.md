# Cycle state file — shape, naming, collisions, migration

The per-cycle state file is `.claude/ship-cycle/<branch-slug>.json` (§ship-cycle — State). This file holds
the mechanics that only matter when something unusual happens to its name or its predecessor.

## Shape

```json
{ "goal": "...", "branch": "...", "worktreePath": "...", "stage": "sc-design",
  "gates": { "G1": "pass", "G2": "pass", "G4": "n/a: copy change, verified by execution" },
  "loops": { "G8": 1 },
  "nature": ["backend"], "risk": ["auth"], "size": "L",
  "sizeEvidence": ["src/a.py:41", "src/b.py:88"],
  "baseline": { "capturedOn": "<base-sha>", "source": "local",
                "run": null,
                "failing": ["suiteA#case", "..."], "flaky": [],
                "coverage": { "backend": { "percent": 78.1, "runStartedAt": "<iso>", "reportMtime": "<iso>" },
                              "mobile": "unmeasured: <reason>" },
                "unrunnableHere": [{ "suite": "suiteB", "reason": "no database reachable",
                                     "startupError": "<the suite's own init error, before any test ran>",
                                     "probe": "<dependency ping> → connection refused",
                                     "capturedAt": "preflight" }] },
  "coverage": { "backend": { "result": "pass", "percent": 84.2, "floor": 78.1, "threshold": 80,
                             "report": "apps/backend/build/reports/jacoco/test/jacocoTestReport.xml",
                             "format": "jacoco", "runStartedAt": "<iso>", "reportMtime": "<iso>" },
                "web": "n/a: no coverage config" },
  "models": { "brainstorm": "opus", "design": "opus", "tdd": "sonnet", "implement": "sonnet",
              "review": "opus", "qa": "sonnet", "ship": "sonnet" },
  "effort": { "design": "xhigh", "tdd": "medium", "implement": "low",
              "review": "high", "qa": "medium", "ship": "low" },
  "reviewJobs": [{ "id": "<host job id>", "agent": "<external reviewer name>",
                   "lens": "external-adversarial", "status": "running", "startedAt": "<iso>",
                   "endedAt": null, "snapshot": "<path outside the worktree>",
                   "resultPath": "<path outside the worktree>" }],
  "bakeOff": { "stances": ["mvp-first", "risk-first", "performance-first"],
               "criteria": [{ "name": "reversibility", "weight": "high" }],
               "judgeLenses": ["algorithm", "cold"],
               "candidates": [{ "stance": "risk-first", "docPath": "<path>",
                                "verdict": "winner", "reason": "<why it won or lost>" }],
               "grafts": [{ "from": "mvp-first", "what": "<the piece>", "why": "<one line>" }],
               "converged": false },
  "gitFreeze": { "active": false, "branch": null, "since": null, "releasedAt": null, "reason": null,
                 "releaseOn": "snapshot" },
  "parked": { "reason": "waiting on product for the rate-limit numbers", "resumeStage": "sc-brainstorm",
              "at": "<iso>", "holds": { "reviewJobs": [], "gitFreeze": false } },
  "reconcile": [{ "at": "<iso>", "recordedStage": "sc-implement", "continueFrom": "sc-tdd",
                  "mismatches": ["tests exist but G4 not recorded: src/test/RateLimitTest.java"],
                  "cleared": [] }],
  "telemetry": { "upgrades": ["auth → security lens: high→top"],
                 "stages": { "review": { "tier": "top", "model": "opus", "effort": "high",
                                         "tokens": null, "cost": null },
                             "design": { "tier": "high", "model": "opus", "effort": "xhigh",
                                         "candidates": 3, "stances": ["mvp-first", "risk-first",
                                         "performance-first"], "tokens": null, "cost": null } } } }
```

`baseline.source` is `local`, `ci` or `ci-status-only`. Under a CI source `baseline.run` holds the run
reference (`ref`, `commit`, `job`, `report`, `rechecked`); under `ci-status-only` every failure blocks unless
its suite is in `run.rechecked`, and `failing` holds entries only for rechecked suites. A `failing` entry is a
bare case id (captured at PREFLIGHT) or `{ "case", "capturedAt": "<stage>" }` (added by a recheck);
`flaky` cases are never exempt — a recheck replaces a suite's `failing` entries, it does not exempt `flaky`.
Shape and rules: `${CLAUDE_PLUGIN_ROOT}/docs/test-baseline.md`.

`parked` is `null` unless `stage` is `parked` (§Parking). `reconcile` is append-only, one entry per resume
(§Resume reconcile).

`coverage` (written at G6) and `baseline.coverage` (written at PREFLIGHT) hold one entry per nature;
values and rules are in sc-implement G6.

## The slug

`<branch-slug>` is the branch transformed by **exactly** `tr '/' '-'` — no case change, no other
substitution. The transformation is specified this precisely because the writer (PREFLIGHT) and every
reader (`/status`, `/resume`, `/ship`, the freeze scan) must derive the same name independently; any
looseness and they disagree about which file is the cycle's.

## Where it lives, and why `/status` must run there

The file lives in the **cycle's own working directory** — its worktree if PREFLIGHT created one, else the
main checkout. `/status`, `/resume` and `/ship` therefore run **from that directory**, so
`git branch --show-current` names *this* cycle.

Because each cycle owns a branch-named file, concurrent cycles on different branches coexist without
clobbering a shared file, and each file owns its own `loops` (per-cycle loop caps for free). Implementer
sub-worktrees carry no cycle state; only the orchestrator's cwd does.

## Collision guard

The slug is lossy: `feat/x` and `feat-x` both become `feat-x`. The JSON `branch` field is the exact record.
On init, if the target file already exists with a **different** `branch`, refuse or warn rather than
clobber another cycle.

Reusing one branch for a **new** goal overwrites its prior completed file. That is acceptable: state is
gitignored run-state, and the PR plus git history hold the real record.

## Stage values

`stage` is exactly one of these; the validator rejects any other `stage` literal in the kit.

<!-- stage-vocabulary -->
`sc-brainstorm`, `sc-design`, `sc-tdd`, `sc-implement`, `sc-review`, `sc-qa`, `sc-ship`, `parked`,
`complete`, `failed`, `cancelled`
<!-- /stage-vocabulary -->

The seven stage skills are mid-pipeline; `parked` is a deliberate pause (not terminal); `complete`, `failed`
and `cancelled` are terminal.

## Resume and selection

Read `.claude/ship-cycle/<current-branch-slug>.json`:

- a mid-pipeline `stage` → resume that cycle (reconcile first, §Resume reconcile);
- `parked` → resume only on request (`/resume`, or the user saying so). A new goal on a parked branch asks
  "resume or replace?" — never a silent overwrite, because the file is the only record of where it paused;
- `complete` / `failed` / `cancelled` / absent → a fresh cycle for this branch (init a new file).

## Parking

Users re-prioritise mid-cycle — sc-brainstorm waiting on answers is the common case — and without a state
for "paused on purpose" the operator tracks it by hand. Park from **any** non-terminal stage, on the user's
request:

1. **Settle what can be settled.** Let in-process stage subagents finish or stop them: they die with the
   session anyway, and a stopped one's output is not a result (§Resume reconcile). Poll each `running`
   `reviewJobs` entry once; release a stale `gitFreeze` (§sc-review — Git-write freeze).
2. **Record what is still live.** A cycle must not park with a `running` job or an `active` freeze unless
   `parked.holds` names them (`holds.reviewJobs: [<id>]`, `holds.gitFreeze: true`). An unrecorded hold is
   how a parked branch gets moved under a reader for days. A held freeze stays binding while parked —
   for this cycle and for every other cycle's freeze scan.
3. Write `parked = { reason, resumeStage: <the stage being left>, at, holds }`, then `stage = "parked"`.

Parking is not a gate outcome: it records nothing in `gates`, and it **does not reset `loops`** — a
pause is not a fresh attempt, so the cap survives it. Resuming clears `parked` to `null` and continues from
the reconcile's stage, which is never later than `resumeStage`.

## Resume reconcile

When a session ends, in-process subagents die and the state file outlives them, so the file can claim more
or less than the worktree shows. `/resume` and PREFLIGHT's resume path run this before continuing; it
compares worktree evidence with `stage`/`gates`:

| evidence | mismatch it reports | effect |
|---|---|---|
| uncommitted or untracked files (`git status --porcelain`) | changes before `sc-tdd`; changes after a recorded G5–G9 `pass` (the verified tree is not this one) | report; clear an invalidated pass, continue at its owner |
| commits since the base (`git log <base>..HEAD`) | code committed while `stage` is before `sc-tdd`; G4/G5 `pass` with no change at all | report; lower if a pass lost its evidence |
| test files in the diff vs the base | **tests exist but G4 not recorded** | continue at `sc-tdd`, which confirms Red (against the base if code is already there) before recording G4 |
| a recorded `pass` whose evidence is gone — a missing artifact path, coverage report or test file, a history rewritten past the verified sha | the gate and what vanished | clear that gate to `—`; continue at its owner |
| subagents running when the session died — the stage `stage`/`resumeStage` names, `bakeOff` candidates without a `docPath`, `reviewJobs` still `running` | their output is lost: partial files are evidence to inspect, not results | their stage is not done; a `running` review job is polled, never relaunched (`/resume` step 6) |

**Inference only ever lowers.** The reconcile may move `stage` earlier and clear a `pass` to `—`; it never
records a `pass`, and never moves `stage` later than recorded, however finished the worktree looks — a gate
passes only when its stage produces the evidence. Continue from the earliest stage any row points at.
A clear is not a failure, so it does not count against `loops`.

Output, printed and appended to `reconcile`: the recorded stage, the stage it continues from, each mismatch
with its evidence (`path`, sha, missing file), and the gates it cleared — or `no mismatches`.

Sequential cycles simply leave the finished file behind; it is deleted at G13 along with the branch.

## Migration (PREFLIGHT-only, one-time)

If the per-branch file is absent and a legacy bare `.claude/.ship-cycle-state.json` exists whose `branch`
**equals** the current branch, move it into the per-branch path: rewrite, then delete the bare file. If its
`branch` differs, ignore it — never read another branch's state.

## Per-role tiers

A stage whose roles span tiers (e.g. `sc-ship`: writer=low, verifier=high, git-master=mid) records its
**dominant** tier in `models`; the stage skill resolves the per-role exceptions from the same
`modelRouting.tierMap`. `effort` works the same way for work-kinds.

`models` also carries `review.security` — a flat key, sibling to `review`, absent unless overlay
`modelRouting.securityReviewModel` is set (§ship-cycle Stage 0.7).
