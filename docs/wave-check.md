# Wave check — one cheap read at each wave barrier (#88)

Waved work lands in steps, and each step is built on the one before. A design-level defect in wave 1 — a
wrong interface, a boundary drawn in the wrong place, a shared contract that misreads the criteria — is
otherwise built on by waves 2..N before any lens sees it, and G8 then finds it under every later wave's
edits. One cheap reviewer at the barrier catches it while it is still one wave's worth of code. It does not
replace G8: G8 stays the gate and runs its full fleet whatever the wave checks found.

<!-- wave-check-trigger -->
**When it runs.** On **Tier L** work executed in waves — sc-implement's waved execution (wave 0, then the
parallel waves) or multi-stack work whose contract-first step lands before the stacks parallelize — at
every barrier that has a later wave, **after that barrier's build/typecheck has passed**. A red barrier goes
to sc-implement's bisect route first; the check reads a green barrier only. The last barrier gets none:
G5–G8 read the whole change next. Tier S and Tier M never run it; a cycle that grows to Tier L
(§ship-cycle Stage 0.2, Stage 0.4) resolves `review.wave` then and runs it from the next barrier on.

**Multi-stack work.** The contract-first barrier is read in the worktree where the contract landed; only
when that worktree no longer exists, in the integration worktree that merges the stacks, if there is one.
`from`/`tree` are tree identities taken in the worktree read
(§`${CLAUDE_PLUGIN_ROOT}/docs/state-file.md` — Tree identity): `from` is its base (the contract step forks
from it), `tree` is that worktree after the contract step. Later stack barriers: a stack that itself runs in
waves gets a check at each of its own barriers that has a later wave, in that stack's worktree; the join of
the parallel stacks is the last barrier and gets none.
<!-- /wave-check-trigger -->

<!-- wave-check-barriers -->
**Every barrier is recorded, checked or not.** At each green barrier append `{wave, tree, worktree, tier,
superseded, fixRound}` to `state.waveBarriers` (`tier` = `state.size` then, `superseded: false`,
`fixRound: false`) — also when the route
skips the check or the barrier is the last. A check's `from` is the `tree` of **the latest non-superseded
entry for wave N−1 with the same `worktree`** (the base for the first barrier) — parallel stacks
share one object store, so another stack's entry would diff the wrong trees; entries are looked up that way, never by position or
wave number alone, because a re-plan or a fix round appends a second entry for the same wave. The ids come
from a throwaway index
and nothing references them, so `git gc` may prune one: if `git cat-file -e <from>` fails, diff from the
base instead and say so in the entry.
<!-- /wave-check-barriers -->

<!-- wave-check-route -->
**The route may dial it.** It is ceremony by the kit's own taxonomy — verifier/agent count
(§ship-cycle — Tier S path, the bright line) — so `state.route.waveCheck` is `"run"` by default on a Tier L
waved or multi-stack plan and may be `"skip: <reason the user saw>"`, under the route's growth-only rule.
Skipped, nothing else changes: G8 still runs the full fleet, and no gate depends on a wave check having run.
<!-- /wave-check-route -->

<!-- wave-check-rule -->
**Two passes, cold first, on one pinned model.** Spawn with `model = state.models["review.wave"]` and
`effort = state.effort["review.wave"]` (mid tier, `medium`, resolved at PREFLIGHT — never the agent type's
default, §core 6):

1. **Cold pass.** Hand it only the wave diff — `git diff <from> <tree>` between the two barrier tree
   identities, so untracked files are in it. No criteria, no design, no author report: the cold lens rules
   of sc-review, assume nothing. Its findings are **frozen verbatim** into the entry's `cold` list before
   the spec is sent.
2. **Spec alignment.** Then send the acceptance criteria (§sc-brainstorm, in state), the design and the
   frozen cold findings: does this wave build what they say, and does it contradict an interface, boundary
   or contract a later wave will build on? What it **cannot verify from the diff** (a requirement that lives
   in unchanged code or spans waves) it lists as unverifiable-from-diff items, not passes — the one bucket
   and shape of §`${CLAUDE_PLUGIN_ROOT}/docs/unverifiable-from-diff.md`, which the cold pass may fill too.
   It may add findings and raise a cold finding's severity;
   it never retracts or lowers one — only a refuter can.

**Host without live messaging** (Codex, or any host that cannot send a running agent a second message —
§`${CLAUDE_PLUGIN_ROOT}/docs/runtime-adapters.md`): agent 1 runs the cold pass on the diff only; its frozen
findings are passed to agent 2, which runs spec alignment and the triage above. Both on the same pinned
model and effort. The output is sc-review's lens shape (§sc-review — Output & severity discipline), each
issue tagged **design** when the defect is in the plan rather than in this wave's own files.

- **Read-only and alone.** It edits nothing, spawns no subagent and does not rerun the suite. A focused test
  only for a named doubt; a full suite, build or E2E it does run goes under overlay `env.heavyLock`
  (§`${CLAUDE_PLUGIN_ROOT}/docs/heavy-work.md`).
- **Out-of-process reviewer.** The git-write freeze applies exactly as §sc-review — Git-write freeze states
  it; the next wave's edits wait on it like any other write.
- **Same evidence rule as review findings.** Load-bearing claims cite evidence
  (§`${CLAUDE_PLUGIN_ROOT}/docs/claim-evidence.md`), and a Critical/High or a **design** finding gets one
  refuter (§sc-review — Verify findings) before anything acts on it, **pinned to `review.wave`** too
  (recorded as the entry's `refuter`). It either evidences the finding (confirmed), refutes it with evidence
  (to `refutedItems`, `{item, where, refutation}`), or neither (undetermined, kept at its claimed severity).
- **A cheap refutation never drops a Critical/High.** The refuter runs below G8's tier, so a Critical/High
  it refutes is still recorded in `refutedItems` **and** stays unresolved for G8, counted in
  `refutedCarried` (by severity) rather than in `findings`, and printed as such. A refuted Medium/Low leaves
  the counts and is only listed for G8 to confirm.
- **When it may stop the waves.** Only a **design** finding that survives verification stops them: the next
  wave is not dispatched, and it routes exactly as the `BLOCKED` (design defect) row does — to sc-design
  (which grows to `run` under the route's growth-only rule, and the user is told), incrementing `loops[G5]`
  once (§sc-implement — Route the implementer's status), under the loop cap. When sc-design returns, the
  wave whose diff held the defect re-plans with every later wave: their `waveBarriers` and `waveReviews`
  entries get `superseded: true`, and the re-planned wave's `from` is the latest non-superseded barrier
  before it in the same `worktree` (the base when the redesign reaches wave 0). Every other finding, of any severity, lets the next
  wave start.
- **A confirmed Critical may be fixed first.** Decided: only a non-design Critical the refuter actively
  **evidenced** (confirmed) — never one merely unrefuted, undetermined, or raised by the spec pass alone,
  which never by itself triggers an edit round. The sequence: the agent that owns its file set fixes it
  (`loops[G5]` +1, a fix round as sc-implement counts it); it ends with the report block of
  `${CLAUDE_PLUGIN_ROOT}/docs/impl-status.md` and is routed by §sc-implement — Route the implementer's
  status; the barrier build/typecheck reruns; a new `waveBarriers` entry for the same wave is appended with `fixRound: true`; the
  next wave starts with its `from` = that new barrier's `tree`. The item stays unresolved — G8 verifies the
  fix like any other.
- **Unresolved items go to G8.** Every surviving or undetermined finding is **unresolved**; it is listed in
  the sc-review brief as an item to verify, gets a disposition there (fixed-here / filed-as `#NN`) and G8
  requires one — the mechanism the skipped implementer concerns use, not a second one. `refutedItems` are
  listed there too, as "previously flagged, refuted at wave N — confirm". Its unverifiable-from-diff items
  are appended to `state.unverifiable` with `source: "wave:<N>"` and dispositioned before G8 by that doc's
  step (confirmed → finding / cleared / owner-decision), not carried in `unresolved`.
- **Advisory.** It sets no `gates` entry and no `gateTrees`, increments no `loops` except through the routed
  design defect or a confirmed-Critical fix round, and approves nothing.
<!-- /wave-check-rule -->

## Record

<!-- wave-check-record -->
Append one `state.waveReviews` entry per check: `wave`, `from` and `tree` (the two barrier tree identities
it read), `model` and `effort` as spawned, `refuter` (the refuter's model and effort), `cold` (the cold
pass's findings, verbatim, frozen before the spec was sent), `findings` counted by severity (after
verification), `refutedItems`, `refutedCarried` (refuted Critical/High still carried, by severity),
`routedTo` (`"sc-design"` or `null`), `unresolved` (`{item, severity, where, design}` each) and
`superseded`. Readers: the sc-review brief and G8 (unresolved and refuted items of every entry, superseded
ones included — a re-plan does not resolve an item), sc-ship's cost readout (one line per entry) and sc-retro
(did a wave check catch what G8 would have, or miss what G8 later found). None decides a gate from it.

**A check that died mid-run is rerun.** The reconcile reruns a wave check — cheap and idempotent — only when
`route.waveCheck` is `"run"`, the barrier has a later wave in its `worktree`, its `waveBarriers` entry was
recorded at `tier` `L`, is not superseded and is not `fixRound` (that barrier needs no check of
its own — G8 verifies the fix), and no `waveReviews` entry has a `tree` equal to that barrier's `tree`
(matched on tree, not wave number, so a re-planned wave is judged by its new barrier).
<!-- /wave-check-record -->
