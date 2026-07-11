---
name: sc-ship
description: Stage 7 of ship-cycle. Documentation + evidence-based verification + PR + cleanup. Confirms docs match the change, maps every claim to evidence, opens a PR against the overlay's base branch with review/QA summary and issue links, then deletes the merged branch and removes the feature worktree.
---

# sc-ship — docs, verify, PR, cleanup (Stage 7)

## Docs (G10)
Update README/CHANGELOG/API docs/comments to match the change **in this same change**. G10 passes when
`git diff --name-only <base>...HEAD` includes a doc file, or the PR body gives an explicit
"no docs needed" reason.

## Verify (G11)
**Run the verification and read the output** (Iron Law #2). Map **each acceptance criterion 1:1** to a
passing test/build/QA log. Zero claims without evidence. If anything is unproven, loop back — don't ship.

**Tag each claim with its evidence *strength*, not just its evidence.** A criterion driven end-to-end and
one that could only be review-verified (because live QA was blocked — see sc-qa) both "have evidence" but
are not equally proven; if they read the same in the PR body, the reader can't tell a validated feature
from an argued one. Label every claim with one of:
- **live** — driven end-to-end against the running system (actual API call / E2E driver / emulator).
- **test** — covered by a unit/integration test (name it).
- **review-only** — verified by review/inspection because live was unreachable (say *why* it was blocked).

Surface the labels in the PR body's claim map (e.g. `- ✅ rate limit rejects 11th request — **live** (e2e:
login_spec)` / `- ✅ owner check on delete — **review-only** (dev user can't reach another owner's record)`).
This makes verification strength auditable and stops a review-only fallback from silently masquerading as a
live pass. `review-only` is a legitimate outcome, not a failure — but it must be **named as such**.

## PR (G12)
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
- Body summarizes the review + QA results and **links the tracked issue**: `Closes #NN` (fully done →
  auto-close on merge) or `Refs #NN` (partial → progress comment, keep open). Assign the milestone if
  `vcs.tracker.milestones` is on.
- **Verify the closing token actually landed (don't trust that you wrote it).** After opening the PR,
  **re-fetch the created body** and assert it contains the exact intended token for **every** tracked issue
  in `state`: `Closes #NN` when that issue is fully done, `Refs #NN` when partial. A bare mention (`#NN`,
  `(#NN)` in the title, or a prose heading like `#NN —`) does **not** auto-close on merge — the host only
  honors the `Closes`/`Fixes`/`Resolves` keyword, and a per-issue keyword is required (`Closes #90, closes
  #91` — not `Closes #90, #91`). If a fully-done issue's token is missing or keyword-less, **patch the body**
  before merge (or, if already merged, `comment + close` the issue). This is the same failure class the cold
  lens guards against: the narrative body reads complete while the machine-readable token silently leaked,
  leaving a finished issue open and polluting the backlog.
- If `vcs.tracker` defines a board, move the item **In Progress → Done** as work completes.
- Gate: build + test + review + QA all passed, **the branch merges cleanly into the base**, and the opened
  PR body carries the correct `Closes`/`Refs` token for every tracked issue (re-fetched and asserted, not
  assumed).

## Cleanup (G13)
- After merge: delete the branch **local + remote** (constitution #9); never delete protected branches.
- **Remove the feature worktree**: `git worktree remove --force <state.worktreePath>`. Teardown must not
  block the cycle: if removal fails because files are locked (a `node_modules`/build process still holding
  handles — common on Windows), fall back to `git worktree prune` to drop the registry entry and leave the
  directory for later deletion. A failed directory delete is a **warning, not a gate**.
- Sync the base branch.

## Issue-tracker hygiene
Don't add third-party/competitor product names or "learning/practice" items to the tracker. Close
finished issues immediately.

## Model routing
writer runs at the **low** tier; verifier at **high** (evidence judgment); git-master at **mid**.

**Pass `model = state.models['ship']` on these calls** (resolved at PREFLIGHT) — never the agent type's
default model (Iron Law 6). (If a stage splits roles across tiers, resolve each from the same tierMap.)
