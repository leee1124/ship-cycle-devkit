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
(§ship-cycle Stage 0.4) runs it from the next barrier on.
<!-- /wave-check-trigger -->

<!-- wave-check-route -->
**The route may dial it.** It is ceremony by the kit's own taxonomy — verifier/agent count
(§ship-cycle — Tier S path, the bright line) — so `state.route.waveCheck` is `"run"` by default on a Tier L
waved or multi-stack plan and may be `"skip: <reason the user saw>"`, under the route's growth-only rule.
Skipped, nothing else changes: G8 still runs the full fleet, and no gate depends on a wave check having run.
<!-- /wave-check-route -->

<!-- wave-check-rule -->
**One reviewer, two passes, cold first.** One read-only agent, spawned with
`model = state.models["review.wave"]` and `effort = state.effort["review.wave"]` (mid tier, `medium`,
resolved at PREFLIGHT — never the agent type's default, §core 6):

1. **Cold pass.** Hand it only the wave diff — `git diff <from> <tree>`, the previous barrier's recorded tree
   (the base for the first barrier) to this barrier's tree identity
   (§`${CLAUDE_PLUGIN_ROOT}/docs/state-file.md` — Tree identity), so untracked files are in it. No
   criteria, no design, no author report: the cold lens rules of sc-review, assume nothing. It returns its
   findings before it sees the spec.
2. **Spec alignment.** Then send it the acceptance criteria (§sc-brainstorm, in state) and the design:
   does this wave build what they say, and does it contradict an interface, boundary or contract a later
   wave will build on? It lists what it **cannot verify from the diff** (a requirement that lives in unchanged
   code or spans waves) as items, not passes.

A host that cannot message a live agent runs the two passes as two agents on the same pinned model. The
output is sc-review's lens shape (§sc-review — Output & severity discipline), each issue tagged **design**
when the defect is in the plan rather than in this wave's own files.

- **Read-only and alone.** It edits nothing, spawns no subagent and does not rerun the suite. A focused test
  only for a named doubt; a full suite, build or E2E it does run goes under overlay `env.heavyLock`
  (§`${CLAUDE_PLUGIN_ROOT}/docs/heavy-work.md`).
- **Out-of-process reviewer.** The git-write freeze applies exactly as §sc-review — Git-write freeze states
  it; the next wave's edits wait on it like any other write.
- **Same evidence rule as review findings.** Load-bearing claims cite evidence
  (§`${CLAUDE_PLUGIN_ROOT}/docs/claim-evidence.md`), and a Critical/High or a **design** finding gets one
  refuter (§sc-review — Verify findings) before anything acts on it. Refuted with evidence → dropped;
  neither evidenced nor refuted → undetermined, kept at its claimed severity.
- **When it may stop the waves.** Only a **design** finding that survives verification stops them: the next
  wave is not dispatched, and it routes exactly as the `BLOCKED` (design defect) row does — to sc-design,
  counting toward the loop cap as that row defines (§sc-implement — Route the implementer's status). Every
  other finding, of any severity, lets the next wave start.
- **Unresolved items go to G8.** Every surviving or undetermined finding and every cannot-verify item is
  **unresolved**. No fix round is dispatched for it here; it is listed in the sc-review brief as an item to
  verify, gets a disposition there (fixed-here / filed-as `#NN`) and G8 requires one — the mechanism the
  skipped implementer concerns use, not a second one.
- **Advisory.** It sets no `gates` entry and no `gateTrees`, increments no `loops` except through the routed
  design defect, and approves nothing.
<!-- /wave-check-rule -->

## Record

<!-- wave-check-record -->
Append one `state.waveReviews` entry per check: `wave`, `from` and `tree` (the two barrier tree identities
it read), `model` and `effort` as spawned, `findings` counted by severity (after verification), `refuted`,
`routedTo` (`"sc-design"` or `null`) and `unresolved` (`{item, severity, where, design}` each). Readers:
the sc-review brief and G8 (the unresolved items), sc-ship's cost readout (one line per entry) and sc-retro
(did a wave check catch what G8 would have, or miss what G8 later found). None decides a gate from it.
<!-- /wave-check-record -->
