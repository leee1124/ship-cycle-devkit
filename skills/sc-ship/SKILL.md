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
- Body summarizes the review + QA results and **links the tracked issue**: `Closes #NN` (fully done →
  auto-close on merge) or `Refs #NN` (partial → progress comment, keep open). Assign the milestone if
  `vcs.tracker.milestones` is on.
- If `vcs.tracker` defines a board, move the item **In Progress → Done** as work completes.
- Gate: build + test + review + QA all passed.

## Cleanup (Stage 13)
- After merge: delete the branch **local + remote** (constitution #9); never delete protected branches.
- **Remove the feature worktree**: `git worktree remove <state.worktreePath>`.
- Sync the base branch.

## Issue-tracker hygiene
Don't add third-party/competitor product names or "learning/practice" items to the tracker. Close
finished issues immediately.

## Model routing
writer runs at the **low** tier; verifier at **high** (evidence judgment); git-master at **mid**.

**Pass `model = state.models['ship']` on these calls** (resolved at PREFLIGHT) — never the agent type's
default model (Iron Law 6). (If a stage splits roles across tiers, resolve each from the same tierMap.)
