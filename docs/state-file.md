# Cycle state file — shape, naming, collisions, migration

The per-cycle state file is `.claude/ship-cycle/<branch-slug>.json` (§ship-cycle — State). This file holds
the mechanics that only matter when something unusual happens to its name or its predecessor.

## Shape

```json
{ "goal": "...", "branch": "...", "worktreePath": "...", "stage": "sc-design",
  "gates": { "G1": "pass", "G2": "pass", "G4": "n/a: copy change, verified by execution" },
  "gateTrees": { "G5": "<tree id of the worktree the build/tests ran on>" },
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
  "releaseSmoke": { "mobile": { "result": "pass", "tree": "<tree id, equal to gateTrees.G9>",
                                 "artifact": "<path> sha256:<digest> (release variant)",
                                 "installed": "<installed path> sha256:<digest> | versionCode <n>",
                                 "releaseForm": { "debuggable": false, "mapping": "<shrinker mapping path>" },
                                 "device": "<emulator or device>",
                                 "flows": [{ "flow": "login", "evidence": "<log or screenshot path>" }],
                                 "deferred": [{ "part": "signature-bound login", "reason": "no release key; ran on substitute signing" }] },
                    "wearable": { "result": "deferred", "tree": "<tree id>", "reason": "no emulator could start",
                             "buildLog": "<release-form build log>", "deviceAttempt": "<start attempt log>" },
                    "backend": "n/a" },
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
                 "releaseOn": "snapshot", "releasedBy": null },
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

`gateTrees[G]` is the **tree identity** of the worktree a tree-dependent gate (G5, G6, G7, G7b, G8, G9) was
judged on, written with its `pass` (or `checklist`/`degrade`) by the stage that sets it. It is a tree, not
`HEAD`, because the code stays uncommitted until sc-ship: a `HEAD` sha would not change when the judged code
did. A pass without a tree cannot be shown to cover the tree that ships, so the reconcile treats it as
evidence gone. `gitFreeze.releasedBy` names who released the freeze: `"self"`, or the branch of another
cycle that released it (§Parking).

### Tree identity

Stage everything — tracked, modified and untracked, minus ignored files and this run's state — into a
throwaway index and write it as a tree. The real index is never touched, and the pathspecs are anchored at
the repo root so the id does not depend on the current directory:

```bash
idx="$(mktemp -d)/index"
GIT_INDEX_FILE="$idx" git read-tree HEAD &&
GIT_INDEX_FILE="$idx" git add -A -- ':/' &&
GIT_INDEX_FILE="$idx" git rm -r -q --cached --ignore-unmatch -- ':(top).claude/ship-cycle' &&
GIT_INDEX_FILE="$idx" git write-tree      # → the tree id
rm -rf "$(dirname "$idx")"
```

The state dir is dropped with `rm --cached` rather than an `:(exclude)` pathspec: when it is gitignored, an
exclude naming it makes `git add` exit 1 and the chain yields no id. Treat an empty id as a failed check, never
as a match. The writer and the reconcile run exactly this, so equal ids mean an equal worktree. Committing does
not change the id (with the state dir untracked, a clean worktree's id is `HEAD^{tree}`), so sc-ship's
commits keep every recorded tree valid. The one allowed difference is the docs sc-ship adds at G10: a recorded tree still holds when

```bash
git diff --quiet <recorded tree> <current tree> -- ':/' <one ':(exclude,top)<glob>' per docs glob>
```

exits 0, with the docs globs from overlay `changeNature`'s docs rule, anchored at the root (no overlay:
`README.md`, `CHANGELOG.md` and `docs/` only — a bare `*.md` would also excuse edits to markdown that *is*
code, such as skill files). Any other difference clears the gate. Ignored, untracked files (`.env`, build
output) are outside the id by design: changing only those does not invalidate a gate.

`parked` is `null` unless `stage` is `parked` (§Parking). `reconcile` is append-only, one entry per resume
(§Resume reconcile).

`coverage` (written at G6) and `baseline.coverage` (written at PREFLIGHT) hold one entry per nature;
values and rules are in sc-implement G6.

`releaseSmoke` (written at G9) holds one entry per nature: an object — `result` `pass`/`fail`/`deferred`,
its `tree` (must equal `gateTrees.G9`), artifact and installed-package identity, release-form indicators,
evidence per flow, any `deferred` parts — or `"n/a"` (diff did not touch `appliesTo`) / `"n/a: <reason>"`
(no config). Any deferral goes on the pre-merge manual gate. Rules are in sc-qa — Release-artifact smoke.

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
gitignored run-state, and the PR plus git history hold the real record. The same guard applies to the gate
log (§Gate log): its header names the exact `branch`, and a log whose header names a different branch is
not appended to.

## Stage values

`stage` is exactly one of these; the validator rejects any other value written as `stage`, `resumeStage`,
`recordedStage` or `continueFrom` in the kit.

<!-- stage-vocabulary -->
`sc-brainstorm`, `sc-design`, `sc-tdd`, `sc-implement`, `sc-review`, `sc-qa`, `sc-ship`, `parked`,
`complete`, `failed`, `cancelled`
<!-- /stage-vocabulary -->

The seven stage skills are mid-pipeline; `parked` is a deliberate pause (not terminal); `complete`, `failed`
and `cancelled` are terminal.

## Resume and selection

Read `.claude/ship-cycle/<current-branch-slug>.json`:

- a mid-pipeline `stage` → resume that cycle (reconcile first, §Resume reconcile);
- `parked` → **ask "resume or replace?"** — PREFLIGHT with a new goal never resumes it silently and never
  overwrites it silently, because the file is the only record of where the cycle paused. `/resume` is the
  explicit "resume";
- `complete` / `failed` / `cancelled` / absent → a fresh cycle for this branch (init a new file).

## Parking

Users re-prioritise mid-cycle — sc-brainstorm waiting on answers is the common case — and without a state
for "paused on purpose" the operator tracks it by hand. Park from **any** non-terminal stage, on the user's
request:

1. **Stop in-process work.** Let stage subagents finish or stop them; they die with the session anyway, and
   a stopped one's output is not a result (§Resume reconcile).
2. **Settle review jobs.** Poll each `running` or `launching` `reviewJobs` entry once (a `launching` one with
   no id is resolved as sc-review's orphan rule says). A **live-tree** job (`snapshot: false`) holds the
   freeze for as long as it runs, and a parked branch may sit for days — so **refuse to park** while one is
   active: supersede or cancel it, or re-launch it on a snapshot and release the freeze, first. A
   snapshot-mode job reads a copy, not the branch, so it may stay running and be held.
3. **Record what is still live.** Name every still-`running`/`launching` job in `parked.holds.reviewJobs`,
   and set `holds.gitFreeze: true` if the freeze is still `active` (it can only be a snapshot-mode freeze
   mid-capture; a stale one is released here). A cycle must not park with a live job or an active freeze
   that `holds` does not name — an unrecorded hold is invisible to every other cycle's freeze scan.
4. Write `parked = { reason, resumeStage: <the stage being left>, at, holds }`, then `stage = "parked"`,
   and append a `parked` line to the gate log (§Gate log).

A held freeze stays binding while parked, for this cycle and for every other cycle's freeze scan — with one
release valve, because nobody may be around to release it: **another cycle may release a parked cycle's
freeze** once every held job is terminal or older than overlay `maxWaitMinutes`. It sets `releasedAt` and
`releasedBy: <its own branch>` in the parked file and touches nothing else there. Re-read that file
immediately before writing, and abort if its `stage` or `gitFreeze` changed since the check — the owner may
have resumed, and a release racing a resume frees a branch its owner is about to freeze again.

Parking is not a gate outcome: it records nothing in `gates`, and it **does not reset `loops`** — a pause is
not a fresh attempt, so the cap survives it.

## Resume reconcile

When a session ends, in-process subagents die and the state file outlives them, so the file can claim more
or less than the worktree shows. `/resume` and PREFLIGHT's resume path run this before continuing.

The **recorded stage** is `parked.resumeStage` when `stage` is `parked`, else `stage`. The reconcile
compares worktree evidence with it and with `gates`:

| evidence | mismatch it reports | effect |
|---|---|---|
| a tree-dependent gate (G5–G9) with any value — `pass`, `degrade`, `checklist`, `fail`, or a diff-dependent `n/a` such as `n/a: Tier S — <reason>` — whose `gateTrees[G]` is missing, or differs from the current tree identity outside the docs globs (§Tree identity). Only a config-based `n/a` (e.g. `n/a: no releaseSmoke config`) is exempt | the gate judged a different tree | clear the gate (clearing G9 also clears every `releaseSmoke` entry, `"n/a"` included — applicability depends on the diff); continue at its owner |
| uncommitted or untracked files (`git status --porcelain`) | changes while the recorded stage is before `sc-tdd` | report only — tree-dependent gates are judged by the row above |
| commits since the base (`git log <base>..HEAD`) | code committed while the recorded stage is before `sc-tdd`; a G4/G5 `pass` with no change at all | report; clear a pass that lost its evidence |
| test files in the diff vs the base | **tests exist but G4 not recorded** | continue at `sc-tdd`, which confirms Red (against the base if code is already there) before recording G4 |
| a recorded `pass` whose other evidence is gone — a missing artifact path, coverage report or test file | the gate and what vanished | clear the gate; continue at its owner |
| a gate recorded `pass` for a stage **after** the recorded stage (G8 `pass` while it reads `sc-tdd`) | a pass the pipeline could not have produced yet | clear the gate |
| subagents running when the session died — the recorded stage, `bakeOff` candidates without a `docPath`, `reviewJobs` still `running`/`launching` | their output is lost: partial files are evidence to inspect, not results | their stage is not done; a review job is polled, never relaunched (`/resume` step 6) |

**Inference only ever lowers.** The reconcile may move the stage earlier and clear a `pass` (to `—`); it
never records a `pass` and never continues later than the recorded stage, however finished the worktree
looks — a gate passes only when its stage produces the evidence. Continue from the earliest stage any row
points at.

**A clear does not count against `loops`.** The cap bounds attempts that *failed*; a clear means the
evidence for a past attempt is gone, not that the work failed — counting it would let a crashed session
spend a cycle's retries.

Output, printed and appended to `reconcile`: `recordedStage`, `continueFrom`, each mismatch with its
evidence (path, sha, missing file), and the gates it `cleared` — or `no mismatches`. The gate log gets one
`cleared` line per cleared gate and one `resume` line (§Gate log).

## Gate log

The state file says where a cycle **is**; nothing in it says how it got there, and G13 deletes it. A
reviewer, a hook or the user who wants to check that the cycle was actually followed needs a record that
survives the merge. That record is an **append-only gate log** in the host's state directory, beside the
state file: `<state dir>/<branch-slug>.log.md`, where the state dir is `.claude/ship-cycle/` on Claude Code
and `.codex/ship-cycle/` on Codex (§`${CLAUDE_PLUGIN_ROOT}/docs/runtime-adapters.md`; same slug, same
working directory, §The slug). The rest of this section writes the Claude path; read it as the host's.

**The state file stays authoritative.** The log is a history for humans, sc-ship's PR summary and
`/resume`'s explanation; no gate, loop count, reconcile row or stage choice is ever *decided* from it. When
the two disagree, the state file wins and the disagreement is reported — the log is not evidence for a
`pass` (§Resume reconcile: inference only lowers).

### Format

PREFLIGHT's init creates the file with a header line naming the exact `branch` and `goal` and a table
header; every transition after that appends **one row**:

```markdown
<!-- ship-cycle gate log · branch: feat/rate-limit · goal: add rate limiting to login -->
| at (UTC) | stage | gate | result | evidence |
|---|---|---|---|---|
| 2026-11-04T09:02:11Z | sc-brainstorm | — | enter | PREFLIGHT: size M, nature backend, risk auth |
| 2026-11-04T09:20:40Z | sc-brainstorm | G1 | pass | acceptance criteria: <artifact dir>/criteria.md |
| 2026-11-04T09:21:05Z | sc-design | G2/G3 | n/a: config bump, nothing to design | — |
| 2026-11-04T10:02:13Z | sc-implement | G6 | fail (loop 1/3) | 2 new failures: RateLimitTest#burst |
| 2026-11-04T10:40:56Z | sc-implement | G6 | pass | coverage 84.2% ≥ floor 78.1 · tree 4b1e… |
| 2026-11-04T11:15:00Z | parked | — | parked | waiting on product for the limits · resume sc-review |
| 2026-11-05T08:00:12Z | sc-review | G8 | cleared | reconcile: tree changed since G8 |
```

- **at** — UTC ISO-8601 with `Z`, second precision.
- **stage** — the stage recorded in state when the line is written (one of §Stage values).
- **gate** — the gate id as the gate table writes it (`G7b`, `G2/G3`), or `—` for a stage change.
- **result** — exactly the value written to `gates` (`pass`, `fail`, `degrade`, `checklist`, `skip`,
  `n/a: <reason>` with the reason verbatim), plus `(loop n/3)` on a `fail`; for a stage change `enter`,
  `parked`, `resume` or the terminal value; `cleared` for a reconcile clear; `deferred: <part>` for each
  manual-gate deferral as it is recorded.
- **evidence** — a short pointer, never the evidence itself: a path, a test id, a tree id prefix, a job id,
  a CI link; `—` when there is none.

<!-- gate-log-cell-escaping -->
**Cell escaping — one rule, applied exactly once, by whoever writes a cell from raw text:** first each
newline (CR, LF or CRLF) → one space, then cut to **200 characters** (a cut cell ends with `…`), **then**
`|` → `\|`. Cutting before escaping means a cut never splits a `\|`. The log writer applies it when it
appends a row, so a log cell is already escaped: sc-ship's Gate summary **copies log cells as they are**
and escapes only the cells it sources from `gates` itself (`log≠state` and `(no log row)` rows) —
escaping a log cell again would turn `\|` into `\\|`. Free text (an n/a reason, a parked reason, an
evidence pointer) is the only thing that can break a row; an unescaped `|` shifts every later column and a
newline ends the row early. "Verbatim" for a reason carried into a cell (G12's n/a reasons included)
means verbatim up to the cap.
<!-- /gate-log-cell-escaping -->

**Sub-check rows.** sc-ship's release checklist (overlay `releaseChecklist`) appends one row per item
with `gate` = `G12` and evidence `releaseChecklist.<id>: exit 0 · tree <prefix>`. These are sub-check rows,
not the G12 value: the Gate summary and the reconcile take the latest G12 row whose evidence does not
start with `releaseChecklist.`. A failing item sets `gates.G12 = fail` first, then appends its row.

### Who appends

**Whoever writes a gate value or a stage change appends its line in the same step** — the stage skill
setting `gates.<G>`, PREFLIGHT entering the first stage, a stage handing over to the next, the loop-back
that records a `fail`, parking (§Parking step 4), a resume (one `resume` line plus one `cleared` line per
gate the reconcile cleared), and a terminal `stage`. Write the state first, then the line: a crash between
the two leaves the log one row short, never ahead of the state. The one exception is G13 (§Lifetime).

**Never rewrite, reorder or delete a past line** — a cleared gate is a new `cleared` row, a retry is a new
row, a corrected mistake is a new row that says so. The log is the only place a cleared or retried pass is
still visible after the state moved on.

A cycle started before 0.3.7 has no log. Do not reconstruct one from the state; create the file at the next
transition with a first row `| <at> | <stage> | — | resume | log started mid-cycle (pre-0.3.7 state) |`.

### Lifetime, archive and git

The log sits in the state dir, which is gitignored run-state like the state file — never commit it (the PR
body's Gate summary is the committed, reviewable record). It is outside the tree identity for the same
reason the state file is (§Tree identity), so appending never invalidates a gate.

**Archiving** — the one procedure, used at G13 and at init:

1. Target dir: the **main checkout's** `<state dir>/archive/` — the main checkout is the first entry of
   `git worktree list`, because a cycle's worktree is removed with its live log inside it. Create it with
   `mkdir -p`.
2. Name: `<branch-slug>-<YYYY-MM-DD>.log.md`, the date in **UTC**. If that name exists, add `-2`, `-3`, … —
   an archive is never overwritten. The existence check and the move are not atomic; two archivers racing
   for one name is accepted, because only one cycle owns a slug at a time (§Collision guard).
3. **Move** the live log there (do not copy and leave it).

**At G13** sc-ship archives the log **before** it removes the worktree. G13's own outcome is then written
**only** to the archived copy — the final row goes to the archive *instead of* to the state file, because
the state file is deleted in the same step and nothing would read it.

**At init**, when PREFLIGHT replaces a state file — a fresh cycle on a branch whose previous file is
terminal, or a parked one the user chose to replace (§Resume and selection) — it archives any existing live
log for that slug first, then creates the new one. A new goal never appends to the previous goal's log;
the `goal` in the header is what tells the two apart in the archive.

The kit **never prunes** `archive/`; it lives until the user deletes it. The freeze scan and `/status`'s
cycle list read `*.json` only, so neither a live log nor an archive is ever mistaken for a cycle.

## Migration (PREFLIGHT-only, one-time)

A pre-0.3.5 file has no `gateTrees`, so on resume the reconcile clears its G5–G9 passes (evidence gone) and
those stages re-run. That is the price of not trusting a pass nobody can tie to a tree.

If the per-branch file is absent and a legacy bare `.claude/.ship-cycle-state.json` exists whose `branch`
**equals** the current branch, move it into the per-branch path: rewrite, then delete the bare file. If its
`branch` differs, ignore it — never read another branch's state.

## Per-role tiers

A stage whose roles span tiers (e.g. `sc-ship`: writer=low, verifier=high, git-master=mid) records its
**dominant** tier in `models`; the stage skill resolves the per-role exceptions from the same
`modelRouting.tierMap`. `effort` works the same way for work-kinds.

`models` also carries `review.security` — a flat key, sibling to `review`, absent unless overlay
`modelRouting.securityReviewModel` is set (§ship-cycle Stage 0.7).
