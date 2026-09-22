# Worktree recovery (rare paths)

Read this when PREFLIGHT (§Stage 0.2) hits one of two states: the worktree path already exists, or a
`worktree add` timed out and left an `index.lock` behind. Both have a recovery order that a plain recursive
delete gets wrong. Everything here is operational bookkeeping, not judgment — the order matters because the
wrong one destroys state belonging to *other* cycles.

## Before any removal or `prune`

`git worktree prune` drops registry entries **repo-wide**, not just this cycle's. Before removing or
pruning anything, confirm:

- the path is not a `reviewJobs[].snapshot` of an active cycle, and
- no cycle holds an `active` `gitFreeze`

by scanning **every** `.claude/ship-cycle/*.json` in this working directory, not just this branch's
(§ship-cycle — State; §sc-review — Git-write freeze).

## The worktree path already exists

A leftover from a previous cycle whose teardown hit the locked-files fallback. Do **not** clear it with a
recursive delete: a linked dependency store (pnpm store, linked `node_modules`, a junction) is reachable
through it, and deleting through the link wipes the store for every other worktree and parallel cycle.

1. Run sc-ship's G13 step 1 link sweep and unlink every hit.
2. `git worktree remove --force <path>` if git still tracks it.
3. Otherwise `git worktree prune` and delete the now link-free directory.

## Stale `index.lock` after a timed-out `worktree add`

On a large or slow filesystem the checkout can outlive a command timeout. By then the add has created the
branch, the directory **and** the registration — only the checkout is unfinished — and it leaves an
`index.lock` behind under the *main* repo's git dir. Resolve its path with
`git -C <worktree> rev-parse --git-path index.lock`, not `<worktree>/.git/…`: inside a worktree `.git` is a
**file**, not a directory. Whatever resumes the checkout otherwise fails with exit 128
(`Unable to create '…/index.lock': File exists`).

**Gate the recovery on the lock being stale, not held.**

```
find "$(git -C <worktree> rev-parse --git-path index.lock)" -mmin +<the timeout you just exceeded, in minutes>
```

Printing the path is your go-ahead. Printing nothing means an add is still in flight — wait, don't delete;
deleting a live lock corrupts the checkout in progress.

"No git process is running" is *not* the check: the crashed add you are recovering from leaves no process,
so it is trivially true exactly when it tells you nothing.

**Then finish the checkout in place — do not re-run `worktree add`.** Delete the stale lock and run
`git -C <worktree> checkout -f`. Re-adding cannot work: the branch the timed-out add already created makes
it fail with `fatal: a branch named '<branch>' already exists`, and `--force` does not help.

Only if the checkout still fails, restart cleanly: sweep and unlink (G13 step 1), delete the directory,
`git worktree prune`, then `git worktree add <path> <branch>` **without `-b`**, since the branch already
exists.

Raise the timeout rather than looping. A lock that reappears right after you delete it means an add is
still running.
