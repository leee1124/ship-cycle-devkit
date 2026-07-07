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

## PR (G12)
- Atomic commits; open the PR against overlay `vcs.defaultBase`.
- **Verify the branch merges cleanly into the base — never open a PR you haven't checked.** Before
  pushing, `git fetch` the base and probe for conflicts *without touching the working tree*:
  `git merge-tree --write-tree <base> HEAD` (git ≥2.38; a `CONFLICT` line = conflicts) — or the host's
  merge-preview API. On conflict: `git merge <base>` into the branch, resolve, re-verify, then push. After
  pushing, confirm the host reports the PR **mergeable / clean** (poll its `mergeable` state — it computes
  asynchronously, so treat `null` as "retry", not "clean"). This is cheap insurance against a branch cut
  before a sibling PR merged, or one that appends to the same files (e.g. i18n/message bundles, lockfiles)
  — those conflict on content even when the logic is disjoint, and surface only at merge time otherwise. A
  concurrently-merged sibling can dirty an already-open PR, so **re-check open PRs on request**.
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

## Cleanup (Stage 13)
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
