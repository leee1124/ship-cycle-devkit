# Cycle state file — shape, naming, collisions, migration

The per-cycle state file is `.claude/ship-cycle/<branch-slug>.json` (§ship-cycle — State). This file holds
the mechanics that only matter when something unusual happens to its name or its predecessor.

## Shape

```json
{ "goal": "...", "branch": "...", "worktreePath": "...", "stage": "sc-design",
  "gates": { "G1": "pass", "G2": "pass", "G4": "n/a: copy change, verified by execution" },
  "loops": { "G8": 1 },
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

## Resume and selection

Read `.claude/ship-cycle/<current-branch-slug>.json`:

- a mid-pipeline `stage` → resume that cycle;
- `complete` / `failed` / absent → a fresh cycle for this branch (init a new file).

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
