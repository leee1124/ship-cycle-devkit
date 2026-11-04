---
name: sc-ship
description: Stage 7 of ship-cycle. Documentation + evidence-based verification + PR + cleanup. Confirms docs match the change, maps every claim to evidence, opens a PR against the overlay's base branch with review/QA summary and issue links, then deletes the merged branch and removes the feature worktree.
---

# sc-ship — docs, verify, PR, cleanup (Stage 7)

## Docs (G10)
Update README/CHANGELOG/API docs/comments to match the change **in this same change**. G10 passes when
`git diff --name-only <base>...HEAD` includes a doc file, or the PR body gives an explicit
"no docs needed" reason.
Record it: `gates.G10 = pass` in state before moving on (a no-docs reason is a pass — the reason lives in the
PR body) — a cycle interrupted later in sc-ship then resumes past the docs check instead of re-deciding it.
Keep G10 edits inside the docs globs: they are the only change the recorded `gateTrees` of G5–G9 tolerate;
anything else invalidates them and routes back to sc-implement (§`${CLAUDE_PLUGIN_ROOT}/docs/state-file.md` — Tree identity).

## Verify (G11)
**Run the verification and read the output** (§core 2). Read pass/fail from the command's own exit
code or its machine-readable report (surefire/JUnit XML, runner JSON) — **never a piped/tailed stdout line**,
which reports the pipe's last exit status and turns a red run green. Map **each acceptance criterion 1:1** to
a passing test/build/QA log. Zero claims without evidence. If anything is unproven, loop back — don't ship.

**Tag each claim with its evidence *strength*, not just its evidence.** A criterion driven end-to-end and
one that could only be review-verified (because live QA was blocked — see sc-qa) both "have evidence" but
are not equally proven; if they read the same in the PR body, the reader can't tell a validated feature
from an argued one. Label every claim with one of:
- **live** — driven end-to-end against the running system (actual API call / E2E driver / emulator).
- **test** — covered by a unit/integration test that **actually ran and passed** (name it; a
  compiled-but-unrun or `@Disabled` test is not evidence — see sc-qa G9).
- **review-only** — verified by review/inspection because live was unreachable (say *why* it was blocked).
  Any criterion whose only coverage is a suite in `state.baseline.unrunnableHere` is labelled
  **`review-only (ci-deferred)`** — name the suite and its recorded `reason` — and listed on the pre-merge
  manual gate below. The suffix is load-bearing: plain `review-only` means somebody **read the code and
  argued it correct**; `ci-deferred` means **nothing in this run observed it at all**. Do not collapse
  them. "Covered in CI" is a true statement and is **not** a `test` label here: this cycle did not observe
  it pass, and G11's labels record what *this run* proved.
  If **every** criterion lands on `review-only` for this reason, say that in one line rather than letting a
  claim map of quarantines read like a verified change.

**Appearance claims of a UI nature** (`${CLAUDE_PLUGIN_ROOT}/docs/visual-check.md` — Visual evidence) map
to `state.visualCheck[<nature>]`, not to screenshots: `owner-confirmed` → **`live (owner-confirmed)`**,
naming the profile and what was checked; `agent-captured` (no owner present) →
**`review-only (agent-captured)`** with each profile on the pre-merge manual gate; `unverified` →
`review-only` with the same gate item. Owner confirmation backs appearance claims only — a behaviour claim
(state, data, navigation) still needs a test or QA log. Accept `owner-confirmed` only when
`state.route.ownerPresent === true` (absent fails closed) **and** you — the top-level session talking to the
user — find the recorded owner words as a user turn in your own conversation, or ask the owner to re-confirm
now; `writtenBy` is advisory only. Otherwise downgrade it to `agent-captured` and put it on the manual gate.
**Stale**: accept the entry only if `visualCheck.tree` equals the final tree, or `git diff <tree>..HEAD` over
the nature's `match` ∪ declared `design.*` paths ∪ `visualCheck.sharedPaths` is empty; otherwise
re-show (the edit goes through the delta re-review) or gate it. Screenshots are optional, for the PR
record; a screenshot-diff counts only where the project declares a harness.

Surface the labels in the PR body's claim map (e.g. `- ✅ rate limit rejects 11th request — **live** (e2e:
login_spec)` / `- ✅ owner check on delete — **review-only** (dev user can't reach another owner's record)`).
This makes verification strength auditable and stops a review-only fallback from silently masquerading as a
live pass. `review-only` is a legitimate outcome, not a failure — but it must be **named as such**.

**Open implementer `notVerified` items.** Before mapping, list every `state.telemetry.implStatus`
`notVerified` item whose `coveredBy` is `null` — it is open. Each one that a PR claim or the evidence map
depends on is run now (a full suite, build or E2E under overlay `env.heavyLock`,
§`${CLAUDE_PLUGIN_ROOT}/docs/heavy-work.md`) or the claim is downgraded and the item goes on the pre-merge
manual gate; none may back a `live` or `test` label unrun. An item run now gets its `coveredBy`. The cost
readout prints the open list.

When every criterion is mapped, set `gates.G11 = pass` in state, so `/status` and resume can tell "claims
mapped" from "just entered sc-ship". While an unproven criterion loops back, leave G11 unset; record a bare
`fail` only if the cycle stops at G11, and name the criterion in the loop-back report, not in the value.

## PR (G12)
- **Check `state.gitFreeze.active` first — do not commit, push, rebase or move the branch while it is
  set** (§sc-review — Git-write freeze). An external reviewer reading this branch out of process hangs on a
  badly-timed write, and G8 should already have released the freeze; if it is still active, a review job is
  unresolved and you are shipping ahead of your own gate.
- Atomic commits; open the PR against overlay `vcs.defaultBase`.
- **Never stage generated/CI-built artifacts** listed in overlay `commit.excludePaths` (e.g. a bundle
  output dir a QA step built locally). Auto-revert / don't-stage them before committing (`git checkout --
  <path>` + `git clean` the untracked ones) so commits stay **source-only**. Forgetting this is easy — a QA
  build leaves a large generated diff in the tree — and committing a bundle bloats the PR and rots on the
  next CI build. When the setting is absent, still skip obvious build outputs (`dist/`, `build/`, bundle
  dirs) and flag them rather than committing blindly.
- **Verify the branch merges cleanly into the base — never open a PR you haven't checked.** Before
  pushing, `git fetch` the base and probe for conflicts *without touching the working tree*:
  `git merge-tree --write-tree <base> HEAD` (git ≥2.38; a `CONFLICT` line = conflicts) — or the host's
  merge-preview API. On conflict: `git merge <base>` into the branch, resolve, re-verify, then push. After
  pushing, confirm the host reports the PR **mergeable / clean** (poll its `mergeable` state — it computes
  asynchronously, so treat `null` as "retry", not "clean"). This is cheap insurance against a branch cut
  before a sibling PR merged, or one that appends to the same files (e.g. i18n/message bundles, lockfiles)
  — those conflict on content even when the logic is disjoint, and surface only at merge time otherwise. A
  concurrently-merged sibling can dirty an already-open PR, so **re-check open PRs on request**.
- **When shipping continuously (not waiting for merges), also probe sibling *open* PRs, not just the base.**
  The merge-tree check above compares against the base branch only — but two still-open PRs can collide with
  *each other* even though each merges cleanly into base. The classic case: append-only files where every PR
  adds new entries at EOF (i18n `.properties`/message bundles, changelogs, barrel exports) — they conflict on
  the same trailing lines despite disjoint logic. Before opening, list currently-open PRs that **touch any
  file in this diff** (host API: open PRs → changed files) and, if any overlap, warn in the PR body which
  sibling PR shares which file so the merge order is a conscious choice (union-merge at merge time, not a
  surprise). This is a heads-up, not a gate.
- **Coverage line, per nature, from `state.coverage`**: `percent` against `floor`, or the n/a string
  verbatim, so "never measured" cannot read as "covered". **Refuse to proceed** on any `undetermined`
  entry unless it is `undetermined (ci-deferred)` and listed on the pre-merge manual gate below.
- **Gate summary, rendered from the gate log** (`<state dir>/<branch-slug>.log.md` — `.claude/ship-cycle/`
  on Claude Code; §`${CLAUDE_PLUGIN_ROOT}/docs/state-file.md` — Gate log). The body carries a
  **"Gate summary"** table, one row per gate G1–G13: the **latest** logged result (not the
  `releaseChecklist.` sub-check rows, §state-file Gate log) and its evidence pointer,
  verbatim — an `n/a: <reason>` keeps its reason, a `degrade`/`checklist`/`deferred` keeps its manual-gate
  pointer — plus the loop count from `state.loops` and a `cleared` count when the reconcile cleared it.
  Log cells are copied as they are — the writer already escaped them; only a cell sourced from
  `state.gates` gets the cell-escaping rule here (§Gate log — Format), and "verbatim" means up to its
  200-character cap. G12 reads
  `pending (this PR)` and G13 `after merge` at render time. The state file is authoritative: where a gate's
  latest log row disagrees with `state.gates`, print the state value and mark the row `log≠state`; a gate
  with a value in `state.gates` but **no log row** renders from the state marked `(no log row)`. With no
  log at all (a pre-0.3.7 cycle), every row is such a row; say so in the table's caption. Example:

  ```markdown
  ### Gate summary
  | gate | result | evidence | loops |
  |---|---|---|---|
  | G1 | pass | criteria.md | 0 |
  | G2/G3 | n/a: config bump, nothing to design | — | 0 |
  | G6 | pass | coverage 84.2% ≥ floor 78.1 | 1 |
  | G9 | degrade | release smoke: signing deferred → Pre-merge manual gate | 0 |
  | G12 | pending (this PR) | — | 0 |
  | G13 | after merge | — | 0 |

  Route: confirmed 2026-11-04T09:20:41Z · skipped sc-design (config bump, nothing to design) · lenses
  security, quality, cold · QA full bring-up + seams
  ```

  Under the table, one **Route** line from `state.route` (absent → `Route: none (pre-0.3.13)`): when it was
  confirmed, each skipped stage with its reason, the lenses and the QA form — so a reviewer sees what was
  planned out, not only what came back `n/a`.
- If `state.bakeOff` exists, the body records **which stance won and why**, and `converged: true` when the
  candidates agreed — cycle state is deleted at G13, so the PR body is the only place the next person
  choosing for this shape of change can still read it.
- Body summarizes the review + QA results and **links the tracked issue**: `Closes #NN` (fully done →
  auto-close on merge) or `Refs #NN` (partial → progress comment, keep open). Assign the milestone if
  `vcs.tracker.milestones` is on.
- **Surface any deferred manual checks recorded in state as a pre-merge manual gate.** If a stage could
  not verify something in this environment and recorded a checklist item — a `gates.G7b: checklist` boot
  deferral (sc-implement couldn't load a full context locally), sc-qa's device-gap / reachability-blocked
  items, a `baseline.unrunnableHere` suite that is a criterion's only coverage, an `undetermined
  (ci-deferred)` `state.coverage` entry (the `ciReport` job + artifact whose coverage must clear the threshold), or a declared external
  review that ended `timeout`/`failed` (name the reviewer, the job id, **and the elapsed wait
  `startedAt → endedAt`**, so a review that was never actually waited for is visible as such — §sc-review)
  — and every open `implStatus.notVerified` item a claim depends on (§Verify (G11)), with the command that
  covers it and its expected exit code as the observable check — list them in the
  PR body under an explicit **"Pre-merge manual gate"** heading (one observable check per item), so a
  deferral can't slip in as a silent pass. For an unrunnable-here item the observable check is the **CI
  job that must show that suite executed (count > 0) and green on this branch's head commit** — a link a
  reviewer can click, not a claim they have to trust; name the suite and its recorded `reason` beside it.
  Matched `releaseChecklist` items with `manual: true` go here too (see Release checklist below), and
  every `state.visualCheck` entry that is not `owner-confirmed` — one item per profile for the owner to
  look at.
  A `gates.G9: degrade` goes here too, with its reason — and each deferred flow or part of a
  `state.releaseSmoke` entry as its own item, to be run on the release-form artifact (§sc-qa
  Release-artifact smoke). If none were recorded, say so.
- **Release checklist (overlay `releaseChecklist`).** Release steps tracked in someone's head get skipped
  on the one PR that needs them (version bump, signing-key registration, release notes, backend-first
  deploy order, symbol-map upload). Not releaseSmoke (G9: does the release artifact run); this is
  bookkeeping. Absent field or no match = no-op.
  - **Select** before writing the PR body, from the **final diff**, with the same glob rules as
    `changeNature.match`. Every `when` key given must hold: `changeNature` names the diff touches, `paths`
    any changed path, `release: true` the PR's actual base (as created or read from the host) equals
    `vcs.releaseBranch` (unset: never matches; PREFLIGHT notes it).
  - **Read the list from the base branch** (`git show origin/<base>:<overlay path>`, after a fresh fetch;
    never a local branch) when the overlay is tracked: a PR that edits its own checklist must not be able
    to delete the item that would fail it. If the base lacks the overlay file or the field, the base list
    is empty: every matching head item goes on the pre-merge manual gate as "new checklist item, not yet
    enforced" (machine items may still run); never fall back silently to the head list. If the diff
    edits `releaseChecklist`, list that edit on the pre-merge manual gate. The fields that decide whether
    an item matches — `vcs.releaseBranch` and the `changeNature` definitions — come from the same base
    overlay, and a diff edit to them goes on the manual gate too; otherwise a PR could escape an item
    by narrowing a glob instead of deleting it. A gitignored local overlay cannot be read from the base;
    its owner edits it outside the cycle.
  - **Machine item** (no `manual`): run `check` before push, alongside the merge-tree probe; judge by
    `evidence`. On a failure set `gates.G12 = fail` first, then append the row with the loop count; never
    waived, only fixed or removed by the overlay's owner.
  - **`undetermined`**: the check errored before reaching what it checks (binary missing, needs network
    or credentials). It never passes: list it on the pre-merge manual gate with the command and the
    reason, else G12 fails. Its logged result is `undetermined`, then `deferred: <id>` once on the gate.
  - **Manual item** (`manual: true`): never run by the agent; list it under **"Pre-merge manual gate"**
    with its `id`, `check` and the `evidence` that closes it ("reviewer confirms …", never the value), and
    log `deferred: <id>`. G12 counts it as satisfied **only** when listed, like a `degrade` G9.
  - **Gate log**: one sub-check row per item (`gate=G12`, evidence `releaseChecklist.<id>: exit 0 ·
    tree <prefix>`; §`${CLAUDE_PLUGIN_ROOT}/docs/state-file.md` — Gate log). **Record only** exit status,
    file path and tree id in the log and PR body, never stdout/stderr or key/hash values.
  - **Right before merge**, re-select and re-run the machine items if the tree or base changed since they
    ran (the logged tree id mismatching is stale), and re-verify the manual items are still listed in
    the body.
  - A matched item the PR neither ran nor listed fails G12 (a silent skip is what this exists to stop).
- **Verify the closing token actually landed (don't trust that you wrote it).** After opening the PR,
  **re-fetch the created body** and assert it contains the exact intended token for **every** tracked issue
  in `state`: `Closes #NN` when that issue is fully done, `Refs #NN` when partial. A bare mention (`#NN`,
  `(#NN)` in the title, or a prose heading like `#NN —`) does **not** auto-close on merge — the host only
  honors the `Closes`/`Fixes`/`Resolves` keyword, and a per-issue keyword is required (`Closes #90, closes
  #91` — not `Closes #90, #91`). If a fully-done issue's token is missing or keyword-less, **patch the body**
  before merge (or, if already merged, `comment + close` the issue). This is the same failure class the cold
  lens guards against: the narrative body reads complete while the machine-readable token silently leaked,
  leaving a finished issue open and polluting the backlog.
- **Assert every finding carries a disposition, and that filed ones were filed (§core 5).** sc-review's
  triage split each surviving finding into *fixed here* or *file-and-link* (§sc-review — Triage). Quantify
  over **every finding in the review artifact, not only the ones marked filed**: each must carry a
  disposition — *fixed here* (visible in this diff) or *filed as `#NN`* (the issue **exists** and the PR
  body carries its `Refs #NN`). A finding with **no** recorded disposition **fails this gate**: an absent
  triage record is not an empty one, and quantifying only over "marked filed" passes vacuously on the
  artifact that was never triaged at all — which is exactly the under-filing this rule exists to stop. If
  the artifact lists findings but records no dispositions, **re-run triage** (§sc-review) rather than
  passing. A finding triaged as out-of-scope and then never filed is not deferred, it is **dropped** — the
  same silent leak as a missing `Closes` token.
- If `vcs.tracker` defines a board, move the item **In Progress → Done** as work completes.
- Gate: build + test + review + QA all passed, every matched overlay `releaseChecklist` machine item passed
  and every manual one is listed on the pre-merge manual gate — a `gates.G9: degrade` or a
  `gates.G7b`/`gates.G6: checklist` counts as
  satisfied **only** when its item is on the pre-merge manual gate above, with its reason, and a gate
  recorded as `"n/a: <reason>"` for a stage that plainly had nothing to do (§ship-cycle — Pipeline) counts
  as satisfied with its reason carried to the PR body (verbatim up to the cell cap) — except a
  whole-stage `n/a` (G2/G3, G4, G9) whose `state.route` entry is now `run` — a route `n/a` the stage outgrew
  or a skip the route never planned — which fails G12 unless it is a config `n/a` (`n/a: no <x> config`)
  (§ship-cycle — Route plan) — **the branch
  merges cleanly into the base**, the opened PR
  body carries the correct `Closes`/`Refs` token for every tracked issue (re-fetched and asserted, not
  assumed), its Gate summary matches a fresh render from state + log, and every deferred finding is filed
  and referenced.
  Set `gates.G12 = pass` in state once all of the above hold and **before** merging; a failed condition
  records a bare `gates.G12 = fail` (the condition goes in the loop-back report) and loops back per the gate
  table. **A recorded `pass` does not survive time:** right before the merge — always, and especially on a
  resumed run — re-run the merge-cleanliness probe and re-fetch the `Closes`/`Refs` tokens; if either no
  longer holds, G12 is `fail` again. In the same re-check, **re-render the Gate summary** from state + log
  as they are now and, if the body's no longer matches that fresh render, **patch the body** before
  merging — a summary rendered when the PR opened goes stale as soon as a later gate, loop or clear
  lands.

## Cleanup (G13)
- **Check `state.gitFreeze.active` and `state.reviewJobs` before you delete anything.** Teardown removes a
  worktree and a branch; an out-of-process reviewer reading either hangs or dies mid-read (§sc-review).
  **Never remove a worktree that is a recorded `reviewJobs[].snapshot`** — a detached snapshot worktree is
  not this cycle's feature worktree and is not yours to prune, and `git worktree prune` is repo-scoped.
  Reaching G13 with a `running` job means G8 was set while a review was still reading: stop and resolve it,
  don't tear down around it.
- **Emit the cost readout first — before anything in this section deletes anything**
  (§`${CLAUDE_PLUGIN_ROOT}/docs/model-routing.md` — Cost readout). Print, and write to an artifact dir **outside the worktree**, one row per stage: **resolved
  tier, model, effort** and whatever usage the host actually exposed (tokens/cost/wall-clock), plus the run
  total and which risk-gated upgrades fired (`telemetry.upgrades`), plus one line per
  `telemetry.implStatus` entry (round, brief, status, reason, route) so stalls and re-dispatches are seen,
  and the open `notVerified` items (no `coveredBy`) from G11.
  **Record `unavailable` for anything the host does not expose — never estimate a number.** Ordering is
  the whole point, and the branch/state deletes below are not the only hazard: the cycle's state file
  lives in the cycle's working directory, **which is the worktree itself when PREFLIGHT created one**
  (§ship-cycle State), so the worktree removal below destroys `telemetry` exactly as the explicit delete
  does. A readout emitted after either one reports nothing.
- **Archive the gate log before the worktree removal**, by the procedure in
  §`${CLAUDE_PLUGIN_ROOT}/docs/state-file.md` — Gate log (Lifetime); G13's final row goes to the archive,
  not to state. A failed move is a warning: print the log's last rows into this run's readout rather than
  lose them.
- After merge: delete the branch **local + remote** (constitution #9); never delete protected branches.
- **Remove the feature worktree — sweep for links, then let git delete.** Teardown is the one step in the
  cycle that can destroy state **outside** the worktree, so this order is binding:
  1. **Sweep the whole worktree for links and unlink every hit, before anything is deleted.** Not just
     `node_modules/` at the root: a shared store is just as often linked **per package**
     (`node_modules/<pkg>` → a store or a sibling package), where a root-only `test -L` returns false and
     the sweep is the only thing that sees it.
     - POSIX: `find <worktree> -xdev \( -type l -o -xtype l \) -print` — empty output means nothing to
       unlink. Remove each hit with `rm <link>` or `unlink <link>` (**not** `rmdir <link>`, which fails
       with `Not a directory` and leaves the link standing).
     - Windows: `Get-ChildItem -LiteralPath <worktree> -Recurse -Force -Attributes ReparsePoint |
       Select-Object FullName, LinkType`. Remove each hit with `cmd /c rmdir "<link>"` — it deletes the
       reparse point only and behaves identically on every Windows shell and PowerShell version. Do
       **not** write a bare `rmdir` (in PowerShell it is an alias for `Remove-Item`), and do not rely on
       `Remove-Item`: on Windows PowerShell 5.1 it prompts on a link with children, and before
       PowerShell 6.2 it deletes *through* reparse points.
     The forms that walk into the target and destroy the shared install are `rm -rf <link>/` on POSIX —
     the **trailing slash** resolves the link (plain `rm -r <worktree>` does *not* descend through a
     symlink, so this bites hardest on Windows) — and `rd /s` / `Remove-Item -Recurse` on Windows, where
     recursion does follow junctions. Removing a link is not removing its target; removing the target is
     silent and unrecoverable. (When `env.sharedNodeModules` is backed by a **pnpm** content-addressable
     store the sharing is by *hardlink*, so the sweep finds nothing and there is nothing to unlink — run
     it anyway: you don't get to know from here which form the project used.)
  2. **Then `git worktree remove --force <state.worktreePath>`** — delegate the directory delete to git,
     which unlinks a link rather than descending into it. Never hand-roll a recursive delete of the
     worktree path as the first move.
  3. Teardown must not block the cycle: if removal fails because files are locked (a `node_modules`/build
     process still holding handles — common on Windows), fall back to `git worktree prune` to drop the
     registry entry and leave the directory for later deletion. **Whoever deletes it later — an operator,
     the next cycle's PREFLIGHT — is outside this procedure, so the directory you abandon must be
     link-free: re-run step 1's sweep and confirm it prints nothing before you walk away.** A failed
     directory delete is a **warning, not a gate**; a delete that recursed through a link is **damage**,
     not a warning.
- **Delete this cycle's state file** (`.claude/ship-cycle/<branch-slug>.json`): the branch is gone, so its
  branch-keyed state is dead — leaving it would show as a phantom active cycle in `/status`.
- Sync the base branch.
- **Gate**: once the cost readout has been emitted (first — not a pass condition, but it must already have
  happened by the time anything here deletes), the branch is deleted, the worktree removed (if one was
  created), the gate log archived, and the base synced, set `gates.G13 = pass` in state — the run's terminal gate. Cleanup is
  best-effort: a locked
  worktree/directory is a **warning, not a blocker**, so record the warning and still mark G13 `pass`.
- **Then offer `sc-retro`** — one line, opt-in: it diagnoses this cycle from the archived log, the cost
  readout and the transcript. It is never a gate, so G13 does not wait for it.

## Issue-tracker hygiene
Don't add third-party/competitor product names or "learning/practice" items to the tracker. Close
finished issues immediately.

## Model routing
writer runs at the **low** tier; verifier at **high** (evidence judgment); git-master at **mid**. On the
effort axis (§ship-cycle Model routing → Effort) the same split holds: docs, commit/push/PR and the
readout are `low` mechanics; the evidence mapping at G11 is judgment and stays `high` on every size tier.

**Pass `model = state.models['ship']` and `effort = state.effort['ship']` on these calls** (both resolved
at PREFLIGHT) — never the agent type's defaults; a default effort is the same silent override as a default
model (§core 6). (If a stage splits roles across tiers, resolve each from the same tierMap/effortMap.)

**Telemetry**: when setting `gates.G13`, append this stage's row to `state.telemetry.stages['ship']` —
resolved tier/model/effort plus whatever usage the host exposed, `null` for what it didn't
(§`${CLAUDE_PLUGIN_ROOT}/docs/model-routing.md` — Cost readout). Do this *before* the readout is emitted, since the readout reads it.
