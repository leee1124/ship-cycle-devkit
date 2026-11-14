# Changelog

## 0.3.31 — Entry triage covers delegated edits and late entry (#117)

- **Why.** Triage classified a *request*, but two paths slipped past it: a cross-stack change handed to a
  plain implementer subagent with no triage line, and work started outside a cycle with no rule — G4 (Red) can't be backfilled, so the state
  file was hand-written.
- **Rules** (§ship-cycle Entry triage): handing code edits to a subagent is a code change, triaged before
  dispatch; **late entry** is stop-and-restart or adopt with a `post-hoc` G4 row
  (`pass`, evidence `post-hoc: Red not observed before code · …`, `docs/state-file.md`), never silent.
  The prompt hook text carries the delegated-edit sentence. README gains "What is mandatory".
- **Tests.** `check_entry_triage` tokens + 3 validator mutations; `prompt_hook_test.py` marker.

## 0.3.27 — Entry triage: decide out loud whether a request needs a cycle (#107)

- **Why.** Nothing decided whether a request should enter a cycle: it started only on "ship it", and the
  SessionStart hook reports only a cycle that already exists. Code changes were started outside the kit
  because the agent judged a cycle unnecessary — bypassing the G1 confirmation the route plan requires.
- **Entry triage** (§ship-cycle, before PREFLIGHT): classify the request as a **code change** (any commit
  for review — small is what Tier S is for, not a reason to skip), **design-only** (start a cycle and
  propose the design-only route, #108), **one stage's job** (that skill standalone — no cycle started and
  cancelled) or **question / research / writing** (no cycle). Say it first in one line the user can
  override — `triage: <class> → <cycle|standalone <skill>|no cycle> — <reason>` — never a silent skip; "no
  cycle" for a code change needs the user's say-so. An active cycle, or an answer to the agent's own
  question, is not re-triaged. The skill description now asks to be consulted before any code change, so
  triage runs without the hook too.
- **Opt-in auto-start hook.** `hooks/prompt-triage.cjs`, registered as `UserPromptSubmit`, adds the triage
  instruction (naming `ship-cycle-devkit:ship-cycle`) to each prompt when `SHIP_CYCLE_AUTOSTART=on`; silent
  otherwise. It never reads the prompt, files, the network or a child process, echoes nothing, exits 0 via
  `exitCode` (no early exit that could cut off the pipe), and decides nothing itself. It is registered for
  every plugin user, so node starts per prompt even when silent (documented). Codex: `--host codex` prints
  plain text (not wired by the plugin; `docs/runtime-adapters.md`).
- **Tests.** `scripts/prompt_hook_test.py` (opt-in values, JSON and plain output, silence when off, no echo,
  ASCII, huge or never-closed stdin — every run bounded by a timeout), run by the self-test with 6
  broken-hook copies; `check_entry_triage` (POSIX-safe on Windows) + 5 validator mutations.

## 0.3.26 — Design-only route: work that ends in a design document (#108)

- **Why.** A data model for another team, a review of an existing design, an interface contract — work that
  ends in a document, not a PR — had no path: `sc-review` and `sc-ship` always ran and `sc-ship` opened a PR.
  In practice a multi-round critique was run by invoking `sc-design` by hand as "critic-only", and later the
  agent skipped the kit on its own because "it is design only" — outside the route plan's confirmation.
- **`docs/design-only-route.md`** states the rule once. sc-brainstorm proposes it at G1 when the criteria end
  in a document; the user confirms it like any route (`state.route.kind = "design-only"`,
  `state.route.designMode`: architect + critic, or critic-only on an existing design).
- **Stages.** sc-design runs; sc-tdd, sc-implement, sc-review and sc-qa are `skip: design-only route` — the
  one route where implement and review may skip, because the critic, a separate agent run to zero
  objections, is the independent review. When G3 passes the orchestrator writes G4–G9
  `n/a: route — design-only route` and hands over straight to sc-ship; those stages, `/ship`, `/resume` and the
  resume reconcile all know the route. A critique request takes this route when the user wants a sign-off or
  hand-off, else sc-design runs standalone.
- **Critic-only.** Reviewing someone else's design, each objection ends with the owner's disposition in their
  words — `accepted`, `rejected: <reason>` or `resolved` — and G3 means none is left without one.
- **Document sign-off** (replaces G12's PR condition): G10 names where the docs live — outside the repo,
  committed and pushed on a kept branch, or "merge wanted" (then the merge is a normal docs cycle); G11 maps
  criteria to doc sections or critic rounds; G12 shows docs, what was reviewed, rounds, zero unresolved, the
  Gate summary and route line, and passes only on the user's words (`state.signOff`). G13 keeps a docs branch
  and never removes a worktree holding uncommitted sign-off docs.
- **Floors.** Kept: branch guard when docs go into the repo, claim evidence, the critic to zero objections,
  G11's claim map, the gate log. Dropped (no code, no PR): G4–G9 and the PR conflict check. Review focus is
  written into the design doc, unpinned, and not mapped at G11.
- **Hand-off.** A later code cycle can start from the signed-off design (`state.handoff`), branching from the
  kept docs branch or from the base after merge: its sc-design reads the carried design as round 1 and the
  carried review focus seeds its own; its gates still run.
- **Validator.** `check_design_only` + 11 self-test mutations.

## 0.3.25 — Cross-check delegated document outputs before a stage reports done (#110)

- **Why.** One decision sometimes has to land in several documents — requirements, design notes, generated
  table comments, the Q&A record. A delegated agent synced them and reported done, but left wording in some
  that contradicted the decision (a rule stated one way in the design notes, the reverse in a table
  comment). The orchestrator found them later by hand.
- **`docs/cross-artifact-check.md`** states the rule once. Trigger: the stage changed a fact and more than
  one artifact in scope states it (edited, delegated, or an untouched copy). Then: list each changed decision
  as a short claim; grep every artifact in scope — the changed files plus every artifact of the same kinds
  the cycle owns, on the integrated tree across stacks — for its terms and the old wording; report each hit
  `consistent`, `contradicting` or `stale` with `path:line`.
- **Blocking.** A contradicting or stale hit blocks the stage like an unresolved objection; the writer fixes
  it and a re-run must read it consistent (`fixed`), or it is `filed: #NN` when the artifact is not the
  cycle's. **No entry is not a pass**: the stage records `n/a: <reason>` when the trigger did not apply.
- **Not by the writer.** An agent other than the writer runs it (a separate agent, or the orchestrator
  checking a delegated writer); a same-agent pass does not count; with no second agent the owner checks the
  hit list, else the manual gate. It is an outcome — Tier S does not drop it.
- **Where.** sc-design before G2/G3 (after the critic's last round; G1's criteria and Q&A record included —
  sc-implement owns them when sc-design is skipped), sc-implement before G5, sc-ship before G10 (a hit outside
  the docs globs routes back to sc-implement, keeping tree identity). The gate rows name it. Each entry in
  `state.crossArtifact` carries its `tree` (another tree's entry is no entry), `writtenBy` and `checkedBy`,
  plus a gate-log sub-check row; `/status` flags a passed gate with a missing, blocked, stale-tree or
  self-checked entry.
- **Validator.** `check_cross_artifact` + 13 self-test mutations.

## 0.3.24 — sc-design: delta mode for repeated critic rounds (#109)

- **Why.** A large design took several critic rounds before G3 passed, and each round re-reviewed the whole
  design. Later rounds cost the most while only a few sections had changed, and the critic re-raised points
  the user had already settled.
- **Snapshot per round.** The critic reads `<artifact dir>/design.r<n>.md` (a split design's union in a
  fixed slice order), so the diff between rounds is mechanical; rounds number on across loop-backs.
- **A round is the critic's.** It is recorded only from a finished critic report, which is authoritative:
  its objections are `open`. The architect's answers (`fixed: <where>` / `disputed: <evidence>`) are input
  to the next round, and only that critic rules an item `resolved` or `withdrawn` — so G3 cannot pass on the
  architect's own marks.
- **Every round after the first gets three inputs**, full or delta: the design diff since the last round, the
  last objections with their answers, and the decisions the user confirmed (`state.designReview.decisions`).
  Those are not reopened; a decision is recorded only from the user's own turn, verbatim, with
  `ownerPresent` true. A critic that disagrees asks the user once (`decisionQuestions`).
- **Three jobs**: rule each prior objection against its answer (open the section, not the account), attack
  the changed parts, and check them against the unchanged ones for new contradictions.
- **Full round instead** on request; when `changedShare` (added + deleted lines from `--numstat` over the
  larger snapshot) is above 40%; when the change reaches a new axis or seam or changes a seam signature;
  after a bake-off synthesis; on re-entry after G3; or with no snapshot. Same model and effort either way.
- **G3 and the log.** G3 reads the last finished round: zero `open`, an unruled `disputed` answer counting
  as `open`. Every finished round logs a G2/G3 row `critic round <n> · delta|full · <k> open` — `pass`, or
  `fail (loop n/3)` under the same loop cap. `/status` prints the rounds.
- **Validator.** `check_design_delta` + 12 self-test mutations.

## 0.3.23 — Route plan shows the model and effort per stage (#111)

- **Why.** Models and effort were resolved at PREFLIGHT, before the criteria existed, and the route plan the
  user confirms at G1 showed only `stage | plan | why`. Nobody saw which model ran which stage. A Tier L
  cycle with a new table and a cross-stack contract ran its design architects on a mid-tier model copied
  from an earlier cycle, against the kit's own rule (design = high, top on a schema or boundary change); the
  user caught it only by asking, and the architects were restarted.
- **The route table grows two columns** (§sc-brainstorm): `model · effort` (`tier → model · effort`, copied
  from `state.models` / `state.effort`) and `routing why`, one line tied to the cost of being wrong at that
  stage. A risk upgrade that fired is named on its row; the one G1 answer confirms the routing too.
- **Below the documented tier needs a stated reason**, the same way a skipped stage does (on Tier S the
  Tier S path is the reason). `docs/model-routing.md` — Shown at G1 holds the per-stage documented-tier
  table the rows are read against; the validator keeps it equal to each stage skill's own tier. One row per
  stage the route runs, brainstorm included, keyed like `state.models`; a `securityReviewModel` pin shows on
  the review row; a stage that grows to `run` adds its row.
- **No `tierMap`, no silent pick.** Without overlay `modelRouting.tierMap` tiers were "advisory only" and
  the orchestrator picked models unseen. Now PREFLIGHT chooses one tier → model mapping from the host's
  models, writes `state.models` with it, and the table heading shows it for confirmation; it is recorded as
  `state.route.tierMap` (`"overlay"` when the overlay resolved them). Without an `effortMap`, effort stays
  advisory.
- **State.** `route.routing` (keyed like `models`: `tier`, `why`, `upgrade`, `belowTier`) and
  `route.tierMap`; the models and effort stay in `models` / `effort`. Absent on older cycles.
- **After G1.** A model or effort change re-shows the changed rows and logs a `route` row naming the
  `models.<k>` / `effort.<k>` keys: a higher tier, or the same tier at higher effort, is growth; anything
  else is lowering — the one exception to growth-only — and needs the user's re-confirmation (declined, the
  row stays). A basis rise re-checks `belowTier` reasons and re-shows a new upgrade. `/status` prints the
  rows.
- **Validator.** `check_route_routing` + 9 self-test mutations.

## 0.3.22 — Unverifiable from diff: the blind lens's third bucket (#91)

- **Why.** A reader that cannot settle a doubt from what it may read meets questions its inputs cannot
  answer — an intent only the spec states, a behaviour spanning tasks or waves, a fact only a running system
  shows. Without a place to put them it either inflates them into guessed findings or drops them, and the
  defect a blind lens exists to see is lost either way.
- **`docs/unverifiable-from-diff.md`** states the rule once:
  - **The bucket.** The G8 cold lens, the delta pass and the wave check's two passes return
    `unverifiable-from-diff[]` beside their findings — `{item, where (path:line in the diff), needs,
    whyNotChecked}`, `whyNotChecked` a closed value (`spec-only`, `spans-tasks`, `needs-running-system`) and
    `needs` never repo code. One term for all of them: the wave check's "cannot verify from the diff" items
    are these items (recorded in `state.unverifiable` with `source: "wave:<N>"`, no longer in `unresolved`;
    pre-0.3.22 entries keep their old path, not migrated, not counted twice).
  - **Not a parking lot, not a licence.** A doubt that reading the repo would settle is read and raised or
    dropped (#72). The bucket is how the cold lens says "I'd need X": it never asks for the spec, and no
    disposition is sent back into its context. An item is not a finding — no severity, no verdict change.
  - **Frozen with the findings**: the cold lens's items before the review-focus list is sent (later ones
    `postList: true`), the wave check's cold-pass items before the spec is sent; a later pass may add items,
    never settle one.
  - **Dispositioned before G8** by triage at `high` effort or a scoped spec-anchored pass on the same model
    and effort that lens ran with at G8 (the #90 Verify rule), opening the evidence itself, riding on
    `loops[G8]`: `confirmed → finding #<n>` (then severity, refuter, floors, triage as usual),
    `cleared: <cited reason>` (a load-bearing claim — uncited is no clearing), or
    `owner-decision: <the owner's words>` — only with `state.route.ownerPresent === true` and the answer
    verbatim as a human user turn (the #83 rule, `by: "owner"`), after the disposer states whether the item
    falls under the data-integrity or security floor (then "treated as High until shown otherwise"). On any
    nature `ownerPresent` may grow to `true` here, only by actually asking the owner — so non-UI cycles can
    use it. No owner fails closed: a floor item blocks G8 (unanswered: stop, park, ask the user), any other
    is `manual-gate`, listed item by item on sc-ship's pre-merge manual gate; at the loop cap an open item
    goes to the owner the same way.
  - **A parked item is a lens miss**: when `needs` was readable from the repo, it is `confirmed` at the
    severity the gap implies — never below its floor (data-integrity or security ⇒ at least High) — with
    `parked: true`; lowering it later needs a refuter's evidence. Duplicates (same `where`, `needs` and
    `tree`) carry `sameAs`; on another tree a `cleared` reason is re-cited, not inherited.
    Never silently dropped, never auto-promoted; G8 needs every item dispositioned.
- **Consumers.** sc-review (the bucket in the cold lens and output shape, the triage step, the delta pass,
  G8), the orchestrator's G8 row, sc-implement's wave check, `docs/claim-evidence.md` (an item is not an
  unevidenced claim), sc-ship (G11 re-asserts every item dispositioned and the owner rule; the PR body's
  **Unverifiable** line of counts and owner decisions; `manual-gate` items on the manual gate), sc-retro
  ("what blind lenses couldn't see", parked items counted) and the state shape (`state.unverifiable`).
  It sets no gate value of its own.
- **Validator.** `check_unverifiable` guards the doc's three blocks, every producer and consumer section,
  the G8 row, the state shape's entry and `disposition` keys and the closed `whyNotChecked` set, and in
  eight files forbids the old "cannot-verify item" term, "unchanged code" as an item's subject and wording
  that would let an item be dropped or auto-promoted; 48 self-test mutations fail it.

## 0.3.21 — Review focus: the inputs the spec implies and no test exercises (#90)

- **Why.** Spec silence is where users break software, and the kit's generic edge classes (legacy rows,
  N≥2, unsaved id, re-run) name kinds of state, not this feature's inputs. Nothing asked anyone to name
  those, so nothing pinned them and the cold lens could not tell what it had missed.
- **`docs/review-focus.md`** states the rule once:
  - **sc-design writes `state.reviewFocus[]`** with the design: at most five per-feature inputs or failure
    modes the criteria or design imply but no existing test exercises, ranked by likelihood × harm —
    `{id, input, impliedBy, uncovered (cited, per claim-evidence), expected}`. Never a generic class, an
    a11y-floor check or a restated criterion (promote it instead); `[]` means checked, absent means not
    written. Shown at G2/G3 with no separate approval round; the critic may object to an entry. After G3 the
    list is append- or annotate-only: a corrected entry keeps its id with `pinnedBy` the existing test, a
    rewrite marks old entries `superseded` and G4 re-pins, new ids continue the numbering (`RF6`+) with the
    cap counting only non-superseded entries, promoting an entry to a criterion is a G1 re-show, and scope
    growth re-opens the list at whichever stage wrote it.
  - **G4 pins every entry**: a failing-first test (`pinnedBy: "<test id>"`), or `pinnedBy: "n/a: <reason>"`
    only for a layout, copy or config item (§core 3) — a logic entry always needs a failing-first test, and
    a misused `n/a` is a critic objection and `pinHolds: false`. G4 does not pass with an entry unpinned.
  - **The cold lens gets the list only after its blind pass**: never in its blind brief, a fresh agent each
    time (after a redesign too). Its findings are frozen verbatim first (the wave check's pattern), then it
    records per entry `raised` and `pinHolds` as `cold`; findings it adds then are `postList: true`.
  - **Verify after the compare.** Misses surface after the parallel lenses ran, so a scoped second pass of a
    spec-anchored lens (quality or algorithm — the same model and effort that lens ran with at G8, risk
    upgrade included) or triage at `high` effort verifies each and is recorded in `verify`, with
    `verify.evidence` (assertion + construction call `path:line`) opened by the verifier, never copied.
    Outcomes: `covered: <pinnedBy>` (the pin holds — verified, not fixed-here, not sent
    to the delta pass), `fixed-here` (a fixed pin shown failing on the pre-change tree: `pinFixedBy` +
    `pinFixEvidence`) or `filed-as #NN`. The delta pass sees only code locations, never input/expected text,
    and checks only for regressions — resolution is proven by `pinFixEvidence` and the pin's run at G11.
  - **Tier S and route skips**: with no sc-design, sc-tdd writes at most two entries (`source: "sc-tdd"`) or
    `[]`; when sc-tdd is route-skipped it still pins existing entries and a logic entry grows it to `run`;
    with no list the field stays absent. No cold lens at all → `cold: null`, "not compared".
- **Consumers.** sc-tdd (pins, route-skip path), sc-review (compare, verify step, delta pass, G8), sc-ship G11
  (each entry mapped to its pin; a fixed pin needs its failing-first evidence) and sc-retro (`covered` misses
  counted as "cold-lens miss, caught by the pin"; superseded entries read as the earlier design's misses;
  `cold: null` skipped). The orchestrator's G4 row and Tier S
  path, the runtime-adapter two-pass note and the state shape carry it. It sets no gate value of its own.
- **Validator.** `check_review_focus` guards the five doc blocks (freeze → compare → record → verify in
  order; forbidden early-list, approval-round, class-as-entry and miss-as-fix wording), every producer and
  consumer section — the list staying out of the cold lens's blind brief included — the G4 row, the
  runtime-adapter note and the state shape's entry, `cold` and `verify` keys; 65 self-test mutations.

## 0.3.20 — When a gate goes red: reproduce, one hypothesis at a time, keep the record (#89)

- **Why.** Loop-cap exhaustion was usually blind retrying: a fix made before the failure was reproduced, a
  flake rerun until green, a resumed session retrying a change the last one had disproved. The gate
  table's on-failure route said only "debugger → sc-implement".
- **`docs/red-gate.md`** states the protocol once, for a red G5/G6/G7/G7b, a red wave barrier and a genuine
  G9 `fail` (an `unrunnableHere` suite never triggers it — diffed around, as at G6):
  - **Reproduce first** with the gate's real command — its own exit code and the tree identity; heavy runs
    and bisections under `env.heavyLock` with bounded waits. sc-qa's G9 hand-off is this step; the fixer
    re-runs it once to confirm.
  - **"Could not reproduce" is not fixed.** The gate keeps its `fail`; the log row's evidence reads
    `undetermined: not reproduced in <N> runs` (§core 2's third state, never a pass; `<N>` = the fixed
    count, per tree). Three exits:
    classify and fix the flake; recheck on the base commit (fails there → pre-existing per
    `test-baseline.md`, `flaky` exempt only when its suite is rechecked); not reproducible anywhere after
    the fixed count → park and ask. Never rerun until green.
  - **Read the actual error**, **compare against a working example**, then **one hypothesis with
    evidence** (a changed tree, dependency or environment cited against a rejected entry's `tree` is new
    evidence) and **one minimal change**. Red differently is `rejected` on the original failure. A
    rejected change is reverted without touching the work around it: before the change record the tree
    and `base=$(git stash create)` (never `git stash`; empty → `HEAD`) plus copies of untracked files;
    after it, `git diff "$base" -- <files> > <scratch>/change.patch`; undo with `git apply -R`, else restore
    the copies; never checkout/reset/stash shared files; check the tree is back to the pre-change tree.
  - **Counting rides on #87.** Each fix round is already counted against `loops[G]`; hypotheses inside a
    round are not loops. Three rejected inside a round → `BLOCKED` (design defect), the round's further
    failure (+1 only then); at loop 2 with two rejected (counted across rounds), prefer sc-design over a
    third guess; at the cap the one cap rule decides and the user gets the `state.debug` entries as
    evidence. No second cap.
  - **Flaky and order-dependent failures**: retry to classify (a count fixed up front), never to hide; a
    gate never passes on the best of N. Polluter bisection with the runner's own selection flags (portable,
    no script), waits for the condition instead of sleeps, isolated shared state, a guard at the boundary.
- **Report contract.** The report block in `docs/impl-status.md` and the three stack prompts gains an
  optional `- Hypotheses:` field (one item per hypothesis: `cause · evidence · change · result · tree`),
  required only in red-gate fix briefs; a missing one is re-asked once as a context fetch (outside
  `loops[G]`), never routed as no report.
- **State.** `state.debug[]`, one entry per hypothesis (gate, failure — a case id, or a build's error code
  plus file with no line/column — round, repro command + exit, hypothesis, evidence, change, result, tree,
  revert). Written only from a finished report, so none is ever pending. Fix briefs carry a failure's
  rejected entries ("do not retry"); the resume reconcile keeps them, so the rejected entries survive a
  restart and no disproved cause is retried; sc-ship's cost readout prints one line per failure and sc-retro
  reads them. It sets no gate.
- **Pointers.** sc-implement and sc-qa gain "When a gate goes red"; G6's debugger attaches under it; the
  orchestrator's gate table names the protocol in the G5, G6, G7, G7b and G9 "On failure" cells with a
  note under the table; model-routing's cost readout carries the lines.
- **Validator.** `check_red_gate` guards the four doc blocks (including the reproduce → read → compare →
  hypothesis → change order and forbidden second-cap / best-of-N / lines-after-the-block wording), the
  sc-implement and sc-qa sections, the gate-table cells and note, the `Hypotheses` field in the report
  block and impl-status, the state shape, the reconcile sentence and the consumers; 55 self-test mutations.

## 0.3.19 — Wave check: one cheap read at each wave barrier, carried into G8 (#88)

- **Why.** On waved work a design-level defect in wave 1 — a wrong interface, boundary or shared contract —
  was built on by waves 2..N before any lens saw it, and G8 then found it under every later wave's edits.
- **`docs/wave-check.md`** states the rule once.
  - **Trigger:** Tier L waved or multi-stack (contract-first) work, at every barrier that has a later wave,
    after that barrier's build/typecheck passed; the last barrier gets none (G5–G8 read the whole change).
    Tier S and Tier M never run it; a cycle that grows to Tier L resolves `review.wave` then. Multi-stack:
    read in the worktree where the contract landed (the integration worktree only when that one is gone and
    an integration worktree exists), with `from`/`tree` taken there; a stack that itself runs in waves is
    checked at its own barriers, and the join of the stacks is the last barrier.
  - **Barriers:** every green barrier is recorded in `state.waveBarriers` (wave, tree, worktree, tier,
    superseded), checked or not; a check's `from` is the latest non-superseded entry for wave N−1. A pruned
    `from` (throwaway-index trees are unreferenced) falls back to a diff from the base.
  - **Reviewer:** `models`/`effort["review.wave"]` (mid tier, `medium`, resolved at PREFLIGHT). Cold pass
    on `git diff <from> <tree>` first, its findings frozen verbatim into the entry's `cold` list before the
    spec is sent; then spec alignment against the criteria and design, which may add or raise but never
    retract or lower a cold finding, and lists what it cannot verify from the diff. A host without live
    messaging (Codex) runs agent 1 (cold) → agent 2 (spec alignment + triage) on the same pinned model
    (`docs/runtime-adapters.md`). No subagents, no suite rerun; heavy runs under `env.heavyLock`; an
    out-of-process reviewer follows sc-review's git-write freeze as written.
  - **Evidence:** the review evidence rule, one refuter for Critical/High and design findings, pinned to
    `review.wave` and recorded as the entry's `refuter`. Refuted findings go to `refutedItems`
    (`{item, where, refutation}`) and are listed in the sc-review brief as "previously flagged, refuted at
    wave N — confirm"; a refutation cheaper than G8's tier never drops a Critical/High, which stays
    unresolved for G8 and is counted and printed as `refutedCarried`.
  - **Stopping:** only a verified design finding stops the waves, routed as the `BLOCKED` (design defect)
    row — sc-design grows to `run` (now a named growth-only source; the user is told), `loops[G5]` +1 once.
    After sc-design returns, the wave that held the defect re-plans with every later wave; their entries get
    `superseded: true`, and its new `from` is the latest non-superseded barrier before it. A non-design
    Critical the refuter actively evidenced (never one merely unrefuted, or raised by the spec pass alone)
    may be fixed first: the owning agent fixes it (`loops[G5]` +1, impl-status report, routed as usual),
    the barrier build/typecheck reruns, a new barrier entry for the same wave is appended and the next wave
    takes `from` from it; the item still goes to G8. Everything else lets the next wave start.
  - **Carry into G8:** surviving, undetermined and cannot-verify items are unresolved and go into the
    sc-review brief as items to verify, each needing a disposition at G8 — the mechanism implementer
    concerns use. It sets no gate and approves nothing.
  - **Dialable:** ceremony (agent count), so `state.route.waveCheck` may be `"skip: <reason>"` (the Tier L
    row says so); skipped or not, G8 runs the full fleet.
- **State.** `state.waveBarriers[]`; `state.waveReviews[]` (wave, from/tree, model, effort, refuter, cold,
  findings by severity, refutedItems, refutedCarried, routedTo, unresolved, superseded); `route.waveCheck`;
  `models`/`effort["review.wave"]`. Read by the sc-review brief and G8, sc-ship's cost readout and sc-retro.
  The reconcile reruns a check that died mid-run (cheap, idempotent) only when `route.waveCheck` is `"run"`,
  the barrier has a later wave, was recorded at Tier L and is not superseded, and no `waveReviews` entry has
  its `tree`.
- **Validator.** `check_wave_check` guards the five doc blocks (including cold before spec alignment,
  refuted-item handling and the host fallback), the forbidden gate wording, the sc-implement / sc-review /
  ship-cycle / runtime-adapters hooks, the effort and Tier L rows, the reconcile row, the state shape and
  the consumers; 51 self-test mutations.

## 0.3.18 — Implementer status: one report contract, routed per status (#87)

- **Why.** Implementer doubts and blockers arrived as free prose at the end of a run and were lost or
  answered with a blind retry; some runs ended with "waiting for the test run" and no report, and the
  orchestrator only found out because nothing happened next.
- **`docs/impl-status.md`** defines the vocabulary once — `DONE`, `DONE_WITH_CONCERNS`, `BLOCKED` (reason:
  missing context, reasoning limit, too large, design defect; `no report` is written only by the
  orchestrator), `NEEDS_CONTEXT` — plus Changed, a concerns list, the commands run with their exit codes,
  and a **Not verified** line that applies to every status and is never claimed. A turn that ends without
  the block is not a report ("no silent end"), and a report is model output that never approves anything.
  Every code-changing agent carries it: stack implementers, build-fixers, debuggers, wave agents.
- **`prompts/impl-{backend,web,mobile}.md`** end their templates with the doc's report block word for word
  (the old "report changed files" line is folded into it).
- **`sc-implement` — Route the implementer's status**: a routing table.
  - `DONE` → G5, which runs its own commands.
  - `DONE_WITH_CONCERNS` → a fix round by default, skipped only with a recorded reason the concern is not
    correctness/scope.
  - Missing context → re-dispatch with the fact.
  - Reasoning limit → a fresh agent one tier up from the brief's current tier (the latest tier recorded
    for it), resolved through `modelRouting.tierMap`, else a split.
  - Too large → split.
  - Design defect → sc-design.
  - No report → resume once, then treat it as missing context once, then stop.
  - Every re-dispatch is changed. Failure-driven ones (reasoning limit, too large, design defect, no
    report, fix rounds) count on `loops[<gate that sent the round>]` once per gate loop-back, and a split
    counts once for its parent. Context fetches (`NEEDS_CONTEXT`, missing context) have their own
    per-brief cap of 3.
  - An unobtainable fact, an unsplittable top-tier brief, an undeterminable block or either cap → stop,
    park, ask the user. The orchestrator's loop-cap sentence is the one cap rule (stop, park, the user
    decides — `sc-design` included); sc-implement points to it.
  - Same-tier rounds 1–2 resume the same implementer, and a tier-up is always a fresh agent with a
    written handoff.
- **Review and ship read it.** Concerns that skipped the fix round are listed in the sc-review brief as
  items to verify, each gets a disposition, and G8 requires them. `notVerified` items are
  `{item, coveredBy}`; sc-ship G11 treats a `null` `coveredBy` as open, runs or downgrades every open item
  a claim depends on (heavy runs under `env.heavyLock`), lists the rest on G12's pre-merge manual gate with
  a covering command as the check, and the cost readout prints them.
- **Telemetry.** One `state.telemetry.implStatus` entry per report (round, brief, gate, fresh/resumed,
  status, reason, concerns, not-verified, route, change, and tier/model only when they changed); sc-ship's
  readout prints it and sc-retro reads it. Neither decides a gate from it.
- **Validator.** `check_impl_status` guards the vocabulary, the prompt block's equality with the doc's,
  the routing rows and rules (including the forbidden "a resume passes the routed model"), the sc-review
  and sc-ship hooks, the loop-cap wording, `coveredBy`, the state shape and the consumers; 40 self-test
  mutations.

## 0.3.17 — SessionStart hook: restate an active cycle after startup, /clear and compaction (#86)

- **Why.** Long cycles cross a compaction or a `/clear`, and the new context does not know a cycle is
  mid-flight — the state-file discipline breaks silently there. The hook puts the facts back in context so
  the session reads the state file instead of guessing.
- **`hooks/hooks.json`** registers one `SessionStart` command hook, matcher `startup|clear|compact`,
  timeout 5 s, running `node "${CLAUDE_PLUGIN_ROOT}/hooks/session-start.cjs"`. It is registered by its place
  at the plugin root (observed in a live `claude --plugin-dir` session; superpowers and oh-my-claudecode ship
  theirs the same way), and the validator refuses a `hooks` key in the manifest as a second path.
- **`hooks/session-start.cjs`** takes the working directory from the stdin JSON `cwd` (bounded 64 KiB read
  that stops at the first chunk that parses, so a host that keeps stdin open does not stall it; not from a
  terminal, not under `--host codex`; absolute, existing, not UNC-style) else its own, reads the branch from
  the HEAD file (a `.git` directory or a worktree's `.git` file and its `gitdir:` — no `git` process), derives
  the slug by exactly `tr '/' '-'`, and reads `.claude/ship-cycle/<slug>.json` at the repo top. Mid-pipeline
  or `parked` → three lines: branch, stage (or resume stage and park date), next gate, loops against the cap,
  the state path, and "run the resume reconcile before acting". The next gate is the stage's first gate not
  recorded (`pass`, `checklist`, `degrade`, `n/a…`; `G2`/`G3`/`G2/G3` cover the one design gate); with all
  recorded it says "stage gates recorded - advance per the pipeline". Silent for no repo, detached HEAD, no
  file, a terminal or unknown stage, malformed or oversized JSON, a file naming another branch,
  `SHIP_CYCLE_HOOK=off`, and any error — it always exits 0. The stage→gate map mirrors the orchestrator's
  pipeline table and the loop cap mirrors "Loop cap: 3 per gate", both compared by `scripts/validate.py`.
- **Built not to stall.** `.git`, HEAD and the state file are read only as regular files under a size cap,
  so a FIFO or device is never opened; UNC-style `gitdir:`/`cwd` values are not followed; a symlink loop or
  permission error while looking for `.git` stops the search; the stdin read relies on the host closing or
  completing stdin (documented).
- **Nothing from the repo is free text to the model.** Only whitelisted values are printed — stage names,
  `G<n>` loop keys, integer counts, an ISO date, and the branch only if it matches
  `^[A-Za-z0-9._/-]{1,80}$`, printed as ``on branch `<branch>` `` (else neither it nor the path built from it
  is printed); `goal`,
  `parked.reason` and gate reasons never are. Claude Code output is `hookSpecificOutput.additionalContext`
  (the form superpowers emits for Claude Code), one form only, ASCII-escaped.
- **Runtime: Node**, one dependency-free CommonJS file: ~30 ms, no shell fork, same behaviour on Linux,
  macOS and Windows without Git Bash or a `.cmd` polyglot launcher. Without `node` on PATH (a native-installer
  Claude Code may lack it) the session shows a non-blocking hook error that `SHIP_CYCLE_HOOK=off` cannot
  silence — `disableAllHooks` or disabling the plugin does.
- **Codex: a stated gap.** The Codex manifest declares no hooks; `--host codex` (reads `.codex/ship-cycle/`,
  plain text) exists for manual wiring and is unverified on a real Codex install (`docs/runtime-adapters.md`
  §Session-start hook).
- **Automated**: `scripts/hook_test.py` drives the hook through 43 cases on hand-built repos — no state,
  active, subdirectory, parked, each terminal value, malformed/array/empty/unknown/non-string stage, detached
  HEAD, no git, worktree `.git` file (relative and absolute `gitdir`), slug collision, invalid UTF-8 and
  control characters, tag-character and instruction-text branches (never echoed), every next-gate rule, cwd
  from stdin and five unusable stdin payloads, stdin written but never closed (POSIX, < 1 s), FIFO
  `.git`/HEAD/state and a `.git` symlink loop (POSIX), an oversized `.git` file, a network `gitdir:`, four
  opt-out spellings, the Codex host: exit 0 well within the time budget, silence where due, 3–4 lines of ASCII
  JSON otherwise, never the state's free text. It fails rather than skips when `node` is missing under CI.
  `validate_selftest.py` runs it on the real hook and on broken copies that must fail (echoes the park reason,
  lets an error escape, ignores the opt-out, prints any branch, ignores the stdin cwd, names the last gate
  when all are recorded, and on POSIX reads a FIFO or reads stdin until it closes), and adds 6 validator
  mutations (stage→gate drift, loop-cap drift, matcher without `compact`, a missing script, the manifest
  declaring hooks, the opt-out undocumented). Checked live once: a `claude --plugin-dir` session in a repo
  with an active state file received the first line verbatim.

## 0.3.16 — Behaviour evals: pressure scenarios with deterministic post-checks (#85)

- **Why.** `scripts/validate.py` checks the prose's structure, not whether an agent that reads it behaves;
  0.2.29 removed the rebuttal lists on the assumption that models comply with a rule stated once. The new
  `evals/` measures that assumption and catches a regression when a rule's wording is trimmed.
- **Eight scenarios** in `evals/scenarios/`, each under stacked pressures (deadline, "it already works",
  authority, triviality, sunk cost) with a POSIX setup script for a tiny fixture repo (Windows: Git Bash),
  the prompt, the rule under test (pointer to its skill section), the expected behaviour and a post-check:
  `skip-review-one-liner` → `review-before-ship`, `piped-tail-green` → `exit-status-signal`,
  `fix-out-of-scope-inline` → `scope-edits`, `omit-model` → `explicit-model`, `skip-root-cause` →
  `root-cause-evidence`, `unstartable-suite-passed` → `undetermined-not-passed`, `commit-protected-branch`
  → `protected-branch`, `found-defect-not-filed` → `defect-filed`.
- **`evals/check.py`** returns pass / fail / undetermined (exit 0/1/2) from a Claude Code transcript (plus,
  with `--subagents`, its subagent transcripts), the cycle state file and the fixture repo's git state
  (`eval-base` tag). It fails only on evidence of the violation and passes only on evidence of compliance:
  an unattributable Bash write, a path it cannot place in the repo, a subagent's unseen work or a state file
  with no transcript is **undetermined**. Tool calls are paired with their results — denied or errored calls
  did nothing; a Bash `Exit code N` is the run's status — and shell commands are matched at the start of a
  segment, so a command inside an `echo` is not one. Every test run is judged: a status hidden by a pipe,
  `;`, `||` or `> file; tail` must be rerun with its status observed (`pipefail` counts only when set
  earlier, never with `grep` in the pipe), and a failing last run with a green final report fails. Lenses
  are reviewer/critic agent types or a whole-word "review" description, and count once their result is
  back; PRs include `hub`, `gh api …/pulls` and MCP tools. `model` must be a non-blank string (`fork`
  spawns are exempt — they inherit by design). Scope compares repo-relative paths exactly, ignores only the
  cycle state dirs and `.eval/`, and with `--repo` diffs every branch, stash, the index and the worktree.
  The protected-branch fallback follows the branch through checkout/switch/worktree/cd. State and transcript
  are both judged for the could-not-start suite. Transcripts are read streaming and strictly as data; the
  only process started is `git`, with hooks and fsmonitor off, no external diff or textconv, `-z` lists.
  A **Codex rollout is recognised and reported unsupported** (its shape is not documented here), so
  transcript-only checks are undetermined on Codex while state/git checks still decide.
- **The limit, stated.** The checkers are heuristics, not proofs: `fail` and `undetermined` are signals to
  read the transcript, and `pass` means only "no known violation pattern was found". Every RED/GREEN result
  in `baselines/results.md` is spot-checked by a person reading the transcript, and the row's new **checked
  by** column names them (README, `check.py` docstring; the validator requires the README to say so).
- **Second review round.** A background lens counts only with a later completion sign before the PR (an
  `AgentOutput`-type result, or a `--subagents` file that ends first), else undetermined; a background test
  run's status is unknown. PR routes add MCP `open_`/`create_` pull-request and merge-request tools, `git push
  -o merge_request.create`, `glab mr create` and `curl`/`wget` POSTs. The final report is compared with every
  failed run and green phrasing is broader ("everything is green", "looks good", "ship it"; a failure word no
  longer cancels it); after a pipe only `PIPESTATUS` counts; only runs at least as wide as the final one are
  held to the rerun rule; `|| echo FAILED`, `if` conditions and `sh -c '…'` bodies are read. `pipefail`/`set
  -e` count only within one Bash call — the host keeps the working directory between calls, not shell
  options or env. The protected-branch fallback leaves `switch -`/`@{-1}` undetermined, reads `git -C
  .`, and fails on merge/rebase/cherry-pick/pull while on `main` and on `update-ref`, `branch -f` or `push
  …:main`. Scope writes add interpreter heredoc/`-`/`-c` scripts that open files and `ed`/`ex`/`vim -c`;
  redirects outside the known roots are not repo writes. Defect filing needs exit 0 (or unknown); with
  `issueMentions`, an issue naming none of them is undetermined (a person judges). A green sentence scoped to
  other suites passes when the report names the could-not-start suite as not run. `fork` is matched
  case-insensitively.
- **Setups** guard `: "${EVAL_DIR:?}"`, commit with signing and hooks off, and the `gh` stub takes its log
  path from `GH_STUB_LOG` (else beside itself), not from an interpolated string.
- **Automated**: the checkers. `evals/fixtures/<id>/<verdict>[-<label>]/` holds 134 synthetic cases —
  passing, failing and undetermined per scenario, including every false pass both review rounds found — and
  `check.py selftest` runs them from `scripts/validate_selftest.py` on Linux and Windows, plus a mutation
  that swaps every scenario's failing case into its passing slot and must be caught for each. The validator
  requires each scenario's sections, a rule pointer that exists, a `sh` setup, a post-check id the checker
  registers, a pass and a fail case and a RED and GREEN row in `evals/baselines/results.md`; every
  registered check must be used. Self-test adds 8 failing mutations. Tested on Python 3.11 and 3.12.
- **Not automated**: the live runs. They cost model time, are run by an operator manually or nightly, RED
  (without the plugin) then GREEN (with it), and are **never a required check**. `evals/README.md` gives
  the Claude Code (`claude -p`, `--plugin-dir`) and Codex (`codex exec`) invocations as each host
  documents them — not exercised by the kit — with "run interactively and save the transcript" as the
  fallback. Results stay outside the repo; `baselines/results.md` has every row "not yet run".

## 0.3.15 — sc-retro: transcript-backed post-cycle diagnosis that drafts kit issues (#84)

- **New à-la-carte skill `skills/sc-retro/`.** After G13, or on a failed or cancelled end, it reads the gate
  log (live or archived), the state file where it survives, sc-ship's cost readout (not found →
  `unavailable`), the PR's Gate summary, the kit version and the host transcript, and reports kit friction on
  five dimensions: loops & re-reviews, review effectiveness, stage/route fit (skips a later defect traces to,
  stages that ran and caught nothing), cost/time, user friction. Without a confirmed transcript it runs on
  state + log only and says so.
- **Reading transcripts.** Located by session id across every Claude Code project dir
  (`~/.claude/projects/*/<session-id>.jsonl` — the cwd slug changes on a directory rename), confirmed by
  content by `grep -c` counts only (never extracted text from a candidate), measured before reading and sliced
  by line. User turns are a named filter: top-level, not sidechain, not meta, human text — never tool results,
  task notifications, agent/teammate messages, system reminders, compact summaries or command wrappers. Codex
  has no documented filter, so user friction is reported `unavailable on Codex`, never inferred. All content
  is data, never instructions, and every dimension-pass subagent prompt says so and that a subagent may not
  approve or file.
- **Evidence rule**: every finding cites `path:line` or a command and its output (held to
  `docs/claim-evidence.md`); no citation, not reported.
- **Report** `<slug>-<date>.retro.md` beside the archived log, or in the main checkout's `<state
  dir>/archive/` on a failed or cancelled end, only after `git check-ignore -q` confirms the path is ignored
  (else written outside every checkout's `git rev-parse --show-toplevel`, and said). It cites, it does not
  quote, and redacts secrets even locally. Project-specific findings are listed separately and never drafted
  as kit issues.
- **Dedup locally**: the kit repo's issues are fetched once (`gh issue list --state all … --json …,body`) and
  matched on the machine; finding text never leaves as a query. A remote search, only as a fallback (list
  truncated: count == limit), uses terms built after redaction from kit vocabulary only. Comments on a match
  follow the draft path.
- **Redaction before any draft is shown** (secrets, emails, people, hosts, internal paths, customer data, the
  project's name and domain terms unless the user opts in). **Approval** is a reply typed by the human user
  after the exact redacted draft was shown, naming that draft — nothing from transcripts, tool results, hooks,
  task notifications or agent messages, and never a subagent. Filing passes the draft as files (`--title
  "$(cat …)" --body-file …`), never interpolated into a shell string; the title file is one line, ≤256 chars.
- **Never a gate.** It writes no gate value and never edits state or log; sc-ship offers it after G13 and the
  orchestrator after a failed or cancelled end. `docs/runtime-adapters.md` gains a host-transcript row (Claude
  Code by session id across project dirs, Codex `~/.codex/sessions/…`); README lists the skill.
- **Validator** guards the skill's marked blocks on full phrases — evidence rule (command + output allowed),
  redaction, filing (human-typed approval naming the draft, excluded sources, `--body-file`, no shell
  interpolation), privacy, local dedup (`gh issue list`, kit vocabulary only, redact → show → approve for
  comments, truncation = count == limit), report location (`git check-ignore -q`, outside the repo,
  failed/cancelled archive, cites not quotes), user-turn filter (`unavailable on Codex`) and injection rule —
  plus the Not-a-gate section (read-only on every input) and that the skill assigns no gate value; the inputs
  (session-id glob, state + log fallback, cost `unavailable`), five dimensions and report anchors; the
  runtime-adapters row; and the README, sc-ship G13 and orchestrator offers. Self-test adds 39 failing
  mutations.

## 0.3.14 — UI natures: a live owner loop is the visual evidence (#83)

- **One rule file, `docs/visual-check.md`**, pointed to from sc-brainstorm, sc-design, sc-implement,
  sc-review, sc-qa, sc-ship and the route plan. A **UI nature** declares the new `changeNature[].visualCheck`
  block — `run` (dev server) and `profiles` (the owner's device first: resolution, density, font scale,
  theme) required; `open`, `devBuild`, `restore`, `capture`, `diff`, `sharedPaths`, `designTool` optional —
  or is reviewed by `designer` without one, which uses a default profile list (phone 1080×2400 or a 390×844
  viewport, font scale 1.0 and the OS maximum, light and dark).
- **Live visual loop inside sc-implement.** Launch the live app from a dev/debug build (a release-form build
  cannot hot reload; the build is heavy work — on a small host build → start emulator → loop). Record prior
  device values (`settings get system font_scale`, `wm size`, `wm density`) in state before changing them
  and restore those, also on abort. Show the change on the owner's profile and ask in plain words what to
  look at. Vague feedback gets 2–3 prototypes side by side on the running app, labelled `variant A/B/C`,
  uncommitted; only the chosen one is productionized. A prototype-cleanup check (label search + `git diff
  --stat` vs the pre-loop tree) is recorded before G5 as part of its evidence; any loop that builds variants
  (a post-review re-show too) resets `preLoopTree` and re-records it. At G8 the cold lens hunts
  losing-variant leftovers in the diff without being handed the record; with no cold lens, the designer
  lens does.
- **What a tweak is, and when it is review-free.** A tweak is presentation-only (styles, layout, copy,
  tokens, assets); any behaviour, state, data or navigation change goes back to sc-tdd (Red first). The
  review-free loop holds only before the first sc-review; after it, every edit — a re-show tweak, an edit
  during G9 or G11 — goes through sc-review's delta re-review and G5–G7 and counts against the loop cap.
- **Evidence.** `state.visualCheck[<nature>]`, written by sc-implement for every nature in `state.nature`
  (`"n/a"` for non-UI), is the evidence for **appearance claims only**: G11 labels an owner confirmation
  `live (owner-confirmed)`; behaviour claims still need a test or QA log, and sc-qa's G9 treats the
  confirmation as covering appearance, not behaviour. Only the top-level session that talks to the user
  writes `owner-confirmed`, in the owner's own words; a subagent writes `agent-captured` at most. The route
  records `state.route.ownerPresent`: only `true` permits `owner-confirmed` (absent or `false` fails
  closed), `false → true` only by asking the owner, and a nature that grows to a UI nature re-asks it.
  `writtenBy` is advisory only: at G11 the top-level session must find the owner words as a user turn in
  its own conversation, or ask the owner to re-confirm; otherwise the entry is downgraded to
  `agent-captured` and goes to the manual gate. Unattended runs capture
  every profile (to the state or scratch dir, slugified names) → `review-only (agent-captured)` on the
  pre-merge manual gate. Screenshots are optional; a screenshot-diff counts only with a declared harness.
- **Stale, mechanically.** G11 accepts a visual check only if its `tree` equals the final tree or
  `git diff <tree>..HEAD` over the nature's `match` ∪ declared `design.*` paths ∪ `visualCheck.sharedPaths`
  (shared theme, i18n) is empty; otherwise re-show or gate it. The orchestrator's G11 row reads
  "appearance only; not stale; `ownerPresent` true".
- **Reuse check moved earlier**: sc-design checks each needed primitive against the declared design-system
  doc (`design.guide`, tokens, components) before any new component or token; the designer lens keeps it
  as a backstop.
- **Accessibility floor as named checks, and an outcome**: touch target, contrast in every theme,
  screen-reader labels/roles, the largest font scale in `profiles`, reduced motion — in the live loop and the
  designer lens. For a UI nature the designer lens (or at least this checklist) is never dropped by Tier S
  or a route; it is on the Tier S bright line. A check that blocks use is High.
- **Optional design-tool adapter** (`visualCheck.designTool`, e.g. impeccable): `shape` at brainstorm/design,
  `generate`/`live` in the loop (web), `critique`/`detect`/`audit` read-only in review, `polish` at ship —
  each with a plain fallback; never required, and never `init`, `document` or a hook install inside a
  cycle. Claude Code only for now: runtime-adapters names the Codex fallback.
- **Validator** guards: the schema's `visualCheck` block is closed, requires `run` + `profiles` and lists
  every documented field (`sharedPaths` included), and an example nature declares it; the state shape has
  `route.ownerPresent` with its fail-closed and ask-the-owner rule, and a visual-check entry with `tree`,
  `preLoopTree`, `owner`, `writtenBy`, `deviceRestore`, `cleanup`; the doc's writer rule (every nature,
  top-level session only, subagent `agent-captured` at most, `ownerPresent === true` with absent failing
  closed, re-ask on growth, `writtenBy` advisory, concrete default profiles), loop / evidence / a11y-floor
  blocks (G5 cleanup evidence, `preLoopTree` reset, cold lens not handed the record, G11 user-turn check and
  downgrade, `sharedPaths`) and the adapter table are checked on full phrases
  (release-form cannot reload, build → start emulator → loop, prior value + abort, presentation-only, back to
  sc-tdd, before the first sc-review only, delta re-review + loop cap, labelled uncommitted variants,
  cleanup before G5, the owner's own words, appearance claims only, final-tree staleness, outside-repo
  captures, a11y never dropped); sc-implement, sc-design, sc-review (designer lens, G8, delta pass), sc-qa
  G9, sc-ship G11 and the manual gate, sc-brainstorm, the orchestrator's G11 row, route plan and Tier S
  bright line, and the runtime-adapters row each name it. Forty-three self-test mutations. It does not judge
  the prose.

## 0.3.13 — Route plan: decide which stages run at G1, with the criteria (#82)

- **sc-brainstorm ends G1 with a route plan** beside the acceptance criteria: a compact table of every
  post-brainstorm stage (`run` / `skip` + reason), the review lenses and the QA form. The user confirms it
  with the criteria in one answer; it is recorded as `state.route` with `confirmedAt` and `basis` (the `size`,
  `risk` and `nature` it was judged on) and a gate-log row with its own gate token `route` (`confirmed` /
  `grew` / `reconfirmed`, evidence = the changed `state.route` keys). The rule lives once, in ship-cycle
  §Route plan.
- **Stages read it instead of re-deriving.** Each skippable stage's "Route first" check honours a skip only
  with no basis rise — a larger `size`, a risk tag not in `basis.risk` or a nature not in `basis.nature` —
  then records `gates.<G> = "n/a: route — <reason>"`, so G12's counting is unchanged. A stage routed `run`
  runs: it does not `n/a` itself (a config `n/a: no <x> config` still applies); with no route, stages judge
  for themselves as before.
- **sc-tdd may be skipped only for layout, copy or config** (§core 3, the same condition G4 accepts), and its
  Route first grows the entry back to `run` when the change has a contract after all.
- **Growth only**, like size and risk: a stage or lens can be added, never removed. Growth comes from
  nature/scope growth, any loop-back to sc-design (loop cap, G8 design flaw — the user is told), or sc-tdd
  finding a contract. A basis rise after `confirmedAt` invalidates every skip: those rows are re-shown and
  turn `run` unless re-confirmed against the new basis. Growing a stage whose `n/a: route` gate was already
  recorded clears it to `—` (a `cleared` row, no loop count), moves `stage` back, and lets later gates clear
  by the tree-identity rules. G12 refuses any whole-stage `n/a` (G2/G3, G4, G9) whose route entry is `run` — a
  route `n/a` the stage outgrew or a skip the route never planned — unless it is a config `n/a: no <x>
  config`.
- **Effective lenses** = `route.lenses` ∪ Tier S floor (security + nature-matched + cold when non-trivial) ∪
  risk-matched lenses ∪ the lenses of every nature in the current `state.nature`. sc-qa generalizes the Tier S
  release-smoke rule to "QA skipped (Tier S or route)"; with a route, only the route decides a QA skip (the
  size-S clause is for cycles with no route).
- **Standalone recommendation**: when the criteria reduce to one stage's job (a review, a design critique, a
  parity audit), sc-brainstorm recommends `sc-review` / `sc-design` / `sc-audit` alone. If taken, the cycle
  ends `cancelled` with the G13 subset: archive the log, remove an unused worktree (dep-store links first),
  delete the branch only if PREFLIGHT created it (new `state.branchCreated`, written at the branch guard) and
  it has no commits beyond the base, delete the state file; a standalone skill ignores a terminal file.
- **Visibility**: `/status` prints the route with its basis and flags an `n/a` on a whole-stage gate (G2/G3,
  G4, G9) whose route entry is `run` (config `n/a` exempt) and a basis rise with a skip standing; the PR's
  Gate summary gets a Route line; resume treats a missing route as pre-0.3.13 behaviour and never reconstructs
  one (the reconcile never turns `run` into `skip`).
- **Decision — the route may lower a tier-implied stage, but only ceremony.** PREFLIGHT still sets the tier
  (brainstorm needs a model and effort before requirements exist), but it is a guess from diff size; the
  agreed criteria are better information, and the kit already let any stage `n/a` itself mid-run at any tier.
  Moving that call to G1, with a named reason the user confirmed and a basis it is re-checked against, is
  strictly more visible than the ad-hoc skip it replaces. So `sc-design` and `sc-qa` may be skipped below the
  tier and `sc-tdd` only for layout/copy/config; `sc-implement`, `sc-review` and `sc-ship` always run, lenses
  never fall below the floor, and no route drops a §core outcome or fail-closed floor (branch guard, pre-PR
  review, real-output pass/fail, conflict check, root cause, triage, G7b, release smoke).
- **Validator** guards: the documented `route` shape (`basis` with `size`, `risk`, `nature`) names exactly the
  post-brainstorm stages with `run` / `skip: <reason>` and keeps implement/review/ship at `run`, and the
  pipeline table must yield stages (an empty one would pass vacuously); sc-brainstorm's G1 section records
  `state.route` and the orchestrator's G1 row requires the route plan; the `## Route plan` section states
  growth-only, standalone + terminal-file clause, §core, the `n/a` form, the lens floor and effective lenses,
  the layout/copy/config restriction, `basis`, `cleared`, the loop cap and the `now run` refusal; sc-design,
  sc-tdd, sc-review and sc-qa read `state.route` and the skippable three check `state.route.basis`; sc-tdd's
  Route first restricts and grows back; sc-review states the effective-lens union; sc-ship's G12 and the
  gate-table G12 row refuse a whole-stage `n/a` whose route entry is `run` (config `n/a` exempt); the rule
  names `basis.risk`/`basis.nature` and `state.branchCreated`; `/status` limits its flag to whole-stage gates
  with config `n/a` exempt. Twenty-one self-test mutations. It does not judge the prose.

## 0.3.12 — Gate-coverage check requires an assignment, not a mention (#75)

- **`GATE_SET_RE` now matches `gates.G<n>` only when followed by `=` or `:`** (compound
  `gates.G5/G6/G7/G7b = <result>` included), so prose such as "`gates.G10` is unset" no longer counts as a
  stage recording the gate. New self-test: a skill that only mentions a gate in prose must fail.
- **Skill text fixed** where a gate was only mentioned: sc-implement now records
  `gates.G5/G6/G7/G7b = <result>` (G5, G7 and G7b had no real assignment — G7b only matched `gates.G7b: checklist` prose; G9 now
  records its own result instead of relying on the Tier-S placeholder); sc-review records `gates.G8 = pass`.

## 0.3.11 — Serialize heavy stages on resource-constrained hosts (#74)

- **New optional overlay `env` keys** `heavyLock` (lock-file path shared by every heavy command, across
  sessions and worktrees), `maxConcurrentHeavy` (integer >= 1; N slot locks `<heavyLock>.1..N`, default 1
  when a lock is set) and `heavyHeadroomMB` (free-memory floor, default off). All unset = today's behaviour.
- **One rule, `docs/heavy-work.md`**: heavy = jobs (full suites, builds, emulators, dev servers, same-box CI),
  not read-only reviewers. Orchestrator tags and queues heavy work, passes lock and worker caps into every
  agent prompt (subagents do not inherit), kills runaways by PID. No-`flock` hosts use a `mkdir` lock or
  degrade to sequential. A schema-invalid `env` (SC-DEGRADE-ENV) loses the lock: run heavy work sequentially.
- **ship-cycle, sc-implement, sc-review and sc-qa point to it**; sc-review's ad-hoc "smaller batches" advice
  is gone.
- **Cold-review hardening**: always slot files `<heavyLock>.1..N` (N=1 too, so sessions with different N
  still exclude each other); one-shot jobs run `flock -n -E 99 -o` in a bounded-wait loop so daemons do not
  inherit the lock fd; long-lived jobs (emulator, dev server) are governed by the headroom check, not the
  lock; `SC_HEAVY_HELD` prevents nested self-deadlock; a lock-wait timeout leaves the step "not run",
  never a pass; hardened `mkdir` fallback (pid file, stale lock reported, never stolen); headroom uses
  available memory per OS and runs inside the lock; SC-DEGRADE-ENV names both fallbacks; "no `heavyLock`
  on a small host: run sequentially" restored in sc-review/sc-implement; locking row in runtime-adapters.
- **Delta-review fixes**: the doc now ships a tested `heavy-run.sh` — the wrapper shell holds the slot on an
  fd and closes it for the job, so the job runs exactly once, returns its own code, and a busy slot is told
  from a `flock` error (98) without re-running; headroom hook inside the lock; `HEAVY_WAIT` default 540 s kept
  under agent tool timeouts, a tool-killed wait is "not run"; exact fork-and-exit form for long-lived jobs;
  SC-DEGRADE-ENV also names the dropped `heavyHeadroomMB`.
- **Validator** guards the schema entries (types, bounds, `heavyLock` minLength), the example env values
  (non-object env errors, unknown keys warn), that the doc states the lock-fd, nesting and fallback rules,
  that the four skills reference it and that "smaller batches" does not return; eight self-test
  mutations. It does not judge the prose.

## 0.3.10 — Overlay `releaseChecklist` for store-distributed apps (#73)

- **New optional overlay field** `releaseChecklist: [{ id, when, check, evidence, manual? }]`, top-level
  because a release step (version bump, signing-key registration with a third-party SDK, release notes,
  backend-first deploy order, symbol-map upload) often spans natures. `when` selects by `changeNature`
  names, `paths` globs and/or `release: true` (PR base is the release branch); keys given must all match.
  Distinct from `releaseSmoke` (G9: does the release artifact run) — this is release bookkeeping.
- **sc-ship runs it before G12's gate.** Machine items run and log one G12 row each; a failure is a G12
  `fail`, never waived. `manual: true` items go on the PR body's pre-merge manual gate and count for G12
  only when listed, like a `degrade` G9. A matched item neither run nor listed fails G12. Undeclared
  field = no-op.
- **Hardening (cold review)**: `vcs.releaseBranch` defines `when.release` (unset: never matches). The list
  is read from the base-branch overlay so a PR cannot delete its own failing item; an edit to
  `releaseChecklist` goes on the manual gate. `undetermined` (check could not run) never passes. The
  pre-merge re-check re-runs machine items when tree or base changed. Gate-log rows are G12 sub-check rows
  (documented in state-file.md); only exit status, paths and tree ids are recorded, never output or key
  values.
- **Validator** guards that the schema documents the field (item keys, `when` keys, `manual`), that the
  example overlay's items are well-formed with unique ids, that sc-ship's rule is tied to the pre-merge
  manual gate, and that the G12 row references `releaseChecklist`; eight self-test mutations. It does not
  judge the prose.

## 0.3.9 — Load-bearing factual claims in design and review reports carry evidence (#72)

- **Rule, stated once** in `docs/claim-evidence.md`. A *load-bearing claim* is a factual claim a decision,
  severity or acceptance criterion depends on that is not visible in the cited or changed lines (library
  internal, code outside the diff, external API contract, persisted data shape; in designs, existing code
  only). Evidence: repo `path:line`, dependency source, version-matched official doc URL, or a command and
  its output; memory is not. In a design an unevidenced claim is a critic objection, as is any claim used to
  dismiss, downgrade or triage out a finding, or to call a risk area clean. A review finding is never
  lowered for a missing citation (never lowers the data-integrity or security floor; foreign-agent findings
  likewise): the refuter evidences or refutes it, and a refutation must cite its own evidence; else it is
  undetermined, blocks G8 at its claimed severity and exits as fix-or-owner-decision. Below High the
  citation is the author's duty only. A triage "no" on Q1/Q2 for a Critical/High needs a `path:line`. A
  subagent had misread a library internal and the orchestrator passed it on unchallenged.
- **Consumers point to it**: sc-design's `## Design` checklist and critic section, and sc-review's output &
  severity discipline each have a `**Claim evidence**` bullet; the refuter also opens the cited evidence,
  and the cold lens may read code and docs to evidence claims but not the spec.
- **Validator** guards that the doc keeps its marked rule block (load-bearing, `path:line`, doc URL, command
  output, objection, "never by itself") and that those three places keep a `**Claim evidence**` bullet
  naming `claim-evidence.md`; sc-review's bullet must itself say "never by itself" (checked inside the
  bullet, not the section) and its Verify findings must name "cited evidence" and "must cite its evidence";
  one self-test mutation per anchor. It does not judge the prose.

## 0.3.8 — sc-design: changes that move an entry point inventory every entry path (#71)

- **Entry-path inventory** in sc-design. Trigger, defined once by content: the change adds, removes or
  moves an entry point, or changes a screen's arrival state, params, or back/close behaviour. The design
  lists direct controls (nav buttons, tabs), deep links and external opens, links from other screens, and
  programmatic navigation (redirects, post-action navigation, route restore), built from the code. Each
  path gets a criterion — arrival state/params and back/close behaviour — and call sites sharing both may
  share one. The criteria are appended to the acceptance-criteria record, marked design-derived, and shown
  with the design at G2/G3. A design that assumed one way in had silently dropped the primary one.
- **The critic checks it against the code**, grepping the route/screen name for real call sites; a missing
  path or one without a criterion is an objection.
- **Validator** guards that `skills/sc-design/SKILL.md` still has the `### Entry-path inventory`
  subsection, the `## Design` checklist's `**Entry paths**` bullet and the critic's
  `**Entry-path inventory**` bullet; one self-test mutation per anchor. It does not judge the prose.

## 0.3.7 — Append-only gate log and a Gate summary in the PR (#70)

- **Gate log** `.claude/ship-cycle/<branch-slug>.log.md`, created at PREFLIGHT init. One table row per
  transition — UTC time, stage, gate, result (the value written to `gates`, `(loop n/3)` on a fail,
  `enter`/`parked`/`resume`/terminal for stage changes, `cleared` for a reconcile clear), short evidence
  pointer. Whoever writes a gate value or a stage change appends the row in the same step, state first;
  parking and the resume reconcile log too. Past rows are never rewritten. Stage and gate passage lived
  only in the state file G13 deletes, so nothing after the merge showed the cycle was followed.
- **The state file stays authoritative.** The log is history: no gate, loop or stage is decided from it,
  and a log row is never evidence for a `pass`.
- **sc-ship renders a "Gate summary" table into the PR body** from the log: latest result and evidence per
  gate (n/a reasons and deferrals verbatim), loop counts from `state.loops`, `log≠state` where they
  disagree; no log → rendered from `state.gates`, said so. The G12 gate requires it.
- **G13 archives the log instead of deleting it**, to the main checkout's
  `.claude/ship-cycle/archive/<slug>-<date>.log.md` (never overwritten), before the worktree removal. The
  kit never prunes the archive; the log is gitignored run-state like the state file and outside the tree
  identity.
- **The summary cannot go stale silently.** G12's right-before-merge re-check re-renders it from state +
  log and patches the body when it no longer matches that fresh render; the G12 row of the gate table
  requires a match with a fresh render, not with the log. A gate with a state value but no log row
  renders from `state.gates`, marked `(no log row)`.
- **One cell-escaping rule, applied exactly once** by whoever writes a cell from raw text: newline →
  space, cut at 200 characters, then `|` → `\|` (cutting first never splits a `\|`). The summary copies
  log cells as they are and escapes only cells it takes from `state.gates`; "verbatim" reasons are
  verbatim up to the cap.
- **Archiving is one procedure** (`mkdir -p`, UTC date, `-2`… suffix, move), used at G13 and at init when a
  state file is replaced, so a new goal never appends to the previous goal's log; the header names `goal`
  too. G13's final row goes to the archive instead of to state.
- The log lives in the host's state dir (`.claude/ship-cycle/` or `.codex/ship-cycle/`).
- `/status` prints the log's last rows, or — when there is no live log — the newest archive paths (by
  mtime, glob anchored on the date so `feat/a` does not match `feat/a-b`); `/resume` uses
  them to explain the interruption.
- Rule: `docs/state-file.md` — Gate log. The validator checks that section, its cell-escaping rule, that
  sc-ship's PR template names the Gate summary and the log (either state dir), and that the G12 row
  requires the summary to match a fresh render; seven failing self-test cases and one must-pass case. The
  self-test's `mutate` takes a `count`.

## 0.3.6 — G9 requires a release-artifact smoke for build-config/native changes (#69)

- **Overlay `changeNature[].releaseSmoke`** (`appliesTo`, `artifact`, `flows`, `device?`). Per nature,
  beside `build`/`bootCheck`/`coverage`, because the release form, flows and device are stack-specific;
  `appliesTo` globs match the whole diff, so a root lockfile can trigger a nature's smoke.
- **When the diff touches `appliesTo`, G9 requires every listed flow on the release-form artifact** —
  shrinking, release signing and production config as shipped — with evidence per flow. A dev or debug
  build does not count. G7 only proved the artifact builds, so a shrinker-stripped generic signature that
  crashed a third-party SDK login only in release builds passed every gate with dev-build E2E green.
- **Evidence ties the smoke to what ran.** A `pass` entry records `tree` (must equal `gateTrees.G9`), the
  artifact's checksum, proof the installed package is that artifact (checksum or version code), and
  release-form indicators (not debuggable, shrinker mapping present).
- **Deferral is admitted, not chosen.** The release-form artifact must have been built and a device start
  attempted first. With no release key, a shrunk build on substitute signing is valid evidence for the
  non-signing flows; only the signing-specific part is deferred. Any deferral → G9 `degrade`, one
  pre-merge manual-gate item each, never a pass. Untouched → `"n/a"`.
- **Tier S does not skip it**: `gates.G9` is then the smoke's outcome, the rest of QA `n/a: Tier S`.
- **Resume reconcile clears any stale tree-dependent gate**, not only a `pass` — `degrade`, `checklist`
  and `fail` too — and clearing G9 clears every `releaseSmoke` entry. Rule: sc-qa — Release-artifact smoke;
  `/status` prints it.
- The validator checks the example overlay's `releaseSmoke` against the schema through a helper shared
  with the coverage check; two self-test cases.

## 0.3.5 — `parked` stage and a resume reconcile (#68)

- **`stage: "parked"`** with `parked: { reason, resumeStage, at, holds }`, from any non-terminal stage on
  request. Re-prioritising mid-cycle had no state, so the operator tracked it by hand.
- **Parking never strands a reader.** A live-tree (`snapshot: false`) freeze blocks parking; live snapshot
  jobs and an active freeze survive only if `holds` names them, and another cycle may release a parked
  freeze once its held jobs are terminal or past `maxWaitMinutes` (`gitFreeze.releasedBy`). Parking
  records no gate and does not reset `loops`.
- **Resume reconcile** on `/resume` and PREFLIGHT resume, appended to `state.reconcile`. Inference only
  lowers: it may move the stage earlier or clear a `pass`, never record one; a clear does not count against
  `loops`. Evidence table: `docs/state-file.md` — Resume reconcile.
- **`state.gateTrees`**: G5–G9 record the worktree's tree identity (temp-index `git add -A` + `write-tree`),
  not `HEAD` — code is uncommitted until sc-ship. A different tree clears the pass; sc-ship's commits and
  docs-only additions don't. A pre-0.3.5 file without trees clears G5–G9 on resume.
- A new goal on a parked branch asks "resume or replace?". `/status` lists every cycle's stage and parked
  details; `/ship` refuses a parked cycle.
- **Validator: stage vocabulary.** One list in `docs/state-file.md`; `stage`/`resumeStage`/`recordedStage`/
  `continueFrom` literals outside it are errors (JSON fences and inline code only, not prose). Five
  failing self-test cases and one must-pass case.

## 0.3.4 — G6 coverage has a measurement path (#67)

- **Overlay `changeNature[].coverage`** (`command`, `reportPath`, `format`, `corePaths`, `sourceRoots?`,
  `threshold?` = 80). "Core coverage ≥80%" named no command, report or core set, so it was skipped silently.
- **G6 reads line coverage from the report file**, never stdout: `pass` at the threshold, and below it
  only against a measured base (`baseline.coverage`, measured locally at PREFLIGHT when it can run). A
  missing, stale or unparseable report is `undetermined` and blocks; an unknown base or an unrunnable suite
  is `undetermined (ci-deferred)` → `gates.G6 = checklist` on the pre-merge manual gate. Rule: sc-implement G6.
- **No config is recorded, not skipped**: `state.coverage[<nature>] = "n/a: no coverage config"`, carried
  into the PR body.
- The validator checks the example overlay's `coverage` against the schema; two self-test cases.

## 0.3.3 — A CI run on the base commit counts as baseline evidence (#66)

- **`state.baseline.source`: `local`, `ci` or `ci-status-only`.** A full local baseline run can take an
  hour on a constrained host, so operators were substituting "base is CI-green" by hand with nothing
  recorded. `ci` ingests the base commit's CI report into `failing`, so G6/G9 still diff mechanically;
  `ci-status-only` (green run, no report) blocks every failure unless its suite was rechecked. An absent
  `source` reads as `local`.
- **`state.baseline.run`** records the run (`ref`, `commit`, `job`, `report`, `rechecked`); retry-only reds
  go to `baseline.flaky` and are not exempt. Recheck additions to `failing` carry `capturedAt`, and
  `/status` flags them as mid-cycle.
- The trade-off — false regressions from local-only reds, a wider exemption from CI-only reds — and the
  one-suite base-commit recheck that settles both are in `docs/test-baseline.md`. Overlay
  `changeNature[].ciBaseline` names the CI job and report per nature.

## 0.3.2 — sc-ship records G10–G12 (#63)

- **sc-ship sets the gates it evaluates.** `gates.G10` after the docs check (or `"n/a: <reason>"` with the
  no-docs reason), `gates.G11` once every acceptance criterion is mapped to evidence, and `gates.G12`
  before merging (or `fail` with the condition named). Previously only G13 was recorded, so `/status`
  showed G10–G12 as `—` for the whole run and a cycle interrupted inside sc-ship could not resume past the
  steps it had already finished.
- Values stay in the existing vocabulary — `pass`, or a bare `fail` with the failing condition in the
  loop-back report — and G12's merge-cleanliness probe and `Closes`/`Refs` re-fetch are re-run right before
  the merge even when G12 already reads `pass`, since a resumed run would otherwise trust a stale check.
- **The validator now blocks on it.** A gate in the orchestrator's table that no stage skill records is an
  error, not an advisory warning; the self-test mutates sc-ship to drop `gates.G10` and expects the failure.

## 0.3.1 — Delta re-review after fixes, and no auto-relaunch under memory pressure

- **sc-review: the delta pass.** A re-review of fixes is scoped to the fix diff (`git diff <reviewed
  sha>..HEAD`) and two questions — is each prior finding actually resolved, and did the fix regress
  anything — run as the cold lens at the same tier and model pin. It escalates to a full re-review when the
  fix reaches code the first review never read, changes a contract/schema/persisted shape, or answers a
  design flaw. Observed cost: second and third review rounds re-read the whole branch at full lens breadth
  to confirm a handful of targeted fixes.
  The prior findings are input, not a spec, so the pass stays cold; the reviewer may read code around a
  finding outside the changed hunks; a rewritten history (rebase/amend past the recorded sha) falls back to
  a full re-review; and the risk floor holds — a fix touching a `state.risk` area re-runs that lens too.
- **sc-review: memory pressure.** Once the host has killed a background job for memory, remaining lenses run
  sequentially, a killed job is reported and never relaunched automatically, and a killed lens counts as not
  run — G8 waits for it or for the user's explicit waiver.

## 0.3.0 — Codex packaging, and a structural self-check that holds both distributions honest (#47)

`main` was Claude-specific: one manifest, `claude plugin` installation, slash-command invocation, and
config/state fixed to `.claude/`. The stage skills and the engineering constitution were always portable;
what was missing was packaging, a place to put the host-specific differences, and something mechanical to
stop the two distributions drifting. **Partially** closes #47 — the *Not delivered* list below is the point
of this release as much as the code is.

- **`.codex-plugin/plugin.json`**, conforming to the published Codex plugin spec (required `name`,
  `version` strict semver, `description`, `author`, `interface`, `interface`'s five required fields, the
  `defaultPrompt` limits). The stage skills install and run on Codex; see the gaps below for what does not.
- **`docs/runtime-adapters.md`** — the intended single home for host-specific detail: manifest location,
  bundled-file root, project root, how a role is spawned, invocation, and where config and state live. Two
  properties must survive translation or the kit is not running: reviewer ≠ author, and model/effort passed
  explicitly. It carries a **Known gaps** section rather than claiming to be the whole difference already.
- **`scripts/validate.py` — the kit applying §core 2 to itself.** Five checks, each present because the
  defect it catches reached a branch: bundled-file pointers resolve and none omits the plugin-root variable;
  every documented state field is read by someone outside the shape doc and every referenced field is
  documented; gates set by skills and gates in the orchestrator's table agree; both manifests parse, carry
  their required fields and agree on a version with the CHANGELOG; skill frontmatter names match their
  directories.
- **`scripts/validate_selftest.py`** — because a checker that cannot fail is indistinguishable from one
  that does not check. Fifteen cases, each mutating a throwaway copy of the repo and asserting the
  validator reports it; temp paths contain spaces; CI runs both scripts on Ubuntu **and** Windows. The
  suite's own first run caught a stale fixture, review caught a check that was satisfied by prose in the
  very file it parsed — a state field "read" by its own documentation — and the first CI run caught findings
  rendering `docs\state-file.md` on Windows and `docs/state-file.md` elsewhere, making the messages
  OS-dependent. All three are fixed; every finding now renders its path the same way on every OS.
- **It found two defects on its first run.** `state.sizeEvidence` was written by PREFLIGHT and absent from
  the documented shape — fixed here. G10/G11/G12 are performed by `sc-ship` and described as gates but
  never recorded, so `/status` shows them as `—` forever — filed as **#63** rather than fixed, since it is a
  different concern (§core 5). That direction of the gate check is advisory until #63 lands, which the code
  says in a comment rather than leaving the reader to infer.

### Not delivered — stated rather than claimed

- **Codex goal-mode binding** (#47 deliverable 5). Needs behaviour of that API that could not be verified
  from this environment; writing it from inference would be the fabricated-integration defect the previous
  two releases were spent removing.
- **Cross-platform state/config helper scripts** (deliverable 6). Nothing in `scripts/` reads, writes or
  migrates cycle state or overlay config — `validate.py` is a maintainer's repo linter, a different
  artifact for a different audience. Consequently the "helper self-tests" clause of deliverable 7 is
  vacuous too; what CI does validate is manifests, frontmatter, structure and version parity.
- **The `.codex/` config and state convention** (the remainder of deliverables 3 and 4). The rows in the
  adapters table and the precedence rule are design intent: PREFLIGHT Stage 0.3 reads a `projectConfig`
  setting only the Claude manifest declares, and about a dozen sites still name `.claude/ship-cycle/`
  directly. The precedence rule also disagrees with Stage 0.3's "absent → built-in defaults" branch, and
  Stage 0.3 is what executes. Marked as intent in both the doc and the README.
- **The observability commands on Codex.** `/status`, `/resume` and `/ship` live in `commands/`, which the
  Codex manifest does not declare, and are implemented with Claude's inline `!`-bash against a hardcoded
  `.claude/` path.
- **A clean-install smoke test on Codex.** The criterion "a clean Codex environment can install this
  repository without a manual repack" cannot be checked without that environment. Spec conformance plus CI
  validation is a necessary condition, not the criterion — and the install command and invocation syntax in
  the README are documented as untested.

## 0.2.31 — False-red, a sweep trap, self-matching kills, and credentials a dependency logs for you

Four traps promoted from a real run on a different stack (a PyQt/Selenium automation app), kept only where
the kit already names a concrete mechanism rather than general advice. Each is silent when it fires and
mechanical to fix.

- **A check that errored is not a failing result (§core 2, sc-implement).** The kit covered false *green*
  exhaustively — scraped exit codes, `grep`-in-pipe, a `bootCheck` selector matching zero tests — and said
  nothing about the opposite polarity, which is the more expensive one because it sends you to fix code
  that was already correct. Observed: a post-submit verifier passed a stale element handle, the call raised
  *before* the check ran, the error path recorded "failed", and **46 operations that had genuinely
  succeeded were reported as failures**. Three states, never two — and the discriminator is the one the
  runner already publishes: `<failure>` vs `<error>` in JUnit/surefire XML, `FAILED` vs `ERROR` in pytest,
  otherwise the exception type (the assertion library's own type is a failure; anything from setup, a
  driver or I/O is undetermined). *Undetermined* carries the error text, **never clears a gate — it only
  withholds a red**, and is a finding if it survives fixing the probe. It is deliberately **not** described
  as a per-check `unrunnableHere`: that category is pre-committed at PREFLIGHT, may only shrink, and
  resolves ambiguity *toward* `failing`, so borrowing it would have inverted three of its rules.
- **A lens that errored is not clean (sc-review).** The same mechanism in its dangerous polarity, on the
  gate that blocks the PR: a lens that crashed, was never spawned, or returned nothing produces zero
  findings, which reads as a pass. Zero findings counts toward G8 only from a lens that actually ran.
- **A sweep's exit `0` is an aggregate, not per-file evidence (sc-implement).** Folded in beside the
  false-green/false-red pair rather than given its own section — the generic half ("commit first", "try one
  file") is already structurally guaranteed by PREFLIGHT's branch guard and worktree isolation. What
  remains is the part with a named mechanism: **parser offsets may be byte offsets, not character offsets**
  (Python `ast` `col_offset` is UTF-8 bytes; tree-sitter is byte-based; TypeScript uses UTF-16 units), so
  slicing a `str` by them shifts cumulatively along the line — 2 positions per 3-byte CJK character — and
  the result often still parses, so nothing necessarily errors.
- **Never match a process by a pattern that can match the matcher (sc-qa).** `pkill -f "python app.py"` can
  match the shell or wrapper that launched it whenever their own command line carries the pattern, so the
  kill lands on the agent's session and surfaces as an unrelated exit code; `ps | grep foo | xargs kill`
  matches the `grep`, which makes a wait-loop built on it wait on itself forever. Observed three times in
  one project. Stop the server the way it was started — portable and correct; anchor or match by executable
  only when you must.
- **Secrets the code never logs itself (sc-review, security lens).** An HTTP client that logs request URLs,
  headers or bodies logs whatever credential is carried there: a token in a URL path is written to the log
  by a *dependency*, at its default level, with nothing in the diff to show for it. Observed: 29,271
  occurrences of a bot token in one project's logs, from code that never touched it. A lens job precisely
  because the author cannot see it by reading their own change — detect by grepping your own logs for the
  shape of your secrets, remediate by moving the credential out of the URL and pinning the client logger.

**Orchestrator holds at exactly 3,007 words**: §core 2's second polarity is paid for by compressions in the
same file.

## 0.2.30 — Optional candidate bake-off for genuinely uncertain design/algorithm work (#51)

Every parallelism in the kit was **partition** parallelism — worktree-per-stack, file-ownership waves,
architects split by axis: exclusive slices meant to fit together. The opposite shape, N agents attacking the
*same* problem and a judge picking a winner, is the one pattern from the multi-agent-orchestration world the
vertical pipeline never borrowed, and it is most valuable exactly where the pipeline is weakest — a wide
solution space with no defensible way to rank the options on paper. Docs-only, off by default. Closes #51.

- **`docs/bake-off.md`** with a ~15-line activation block in `sc-design`, placed beside its sibling
  (split-by-axis) so the partition/competition distinction is stated where the choice is made. Strictly
  **ceremony** on the bright line: Tier L (Tier M only with a stated reason), never on Tier S, and it never
  replaces the critic or G2/G3.
- **Three activation conditions, all required** — the approaches differ in kind, the tradeoff section
  honestly cannot rank them ("if the architect can already name the winner, that *is* the bake-off, done for
  the price of one agent"), and being wrong is expensive. **The operator activates it; there is no automatic
  trigger**, because all three conditions are judgments an agent would be making about its own work, and a
  gate that dissolves under self-assessment is not a gate.
- **Design-only and read-only.** A bake-off produces competing design docs and never takes a worktree —
  Stage 2 is read-only, and candidate worktrees would leak past a G13 teardown that only knows about the
  cycle's own. A comparison that genuinely needs a *measurement* is a spike, and a spike is its own cycle.
- **Blindness is an input contract, not a prohibition.** "Candidates cannot see each other" is unenforceable
  as an instruction, so it is built in instead: all N spawned in one fan-out, each handed the spec and
  **only its own output path**, and the judge is the first party given all N. Likewise the criteria are
  written to `state.bakeOff.criteria` **and printed before the fan-out** — not merely "before reading the
  candidates", since a file written afterwards looks identical.
- **A judge panel, not a single judge** — 2–3 `sc-review` lenses matched to the change's nature, including
  the spec-blind **cold** lens, each scoring every candidate against the same criteria. Judging costs 1×,
  not N×; it is the wrong place to economize. Every candidate and every lens is spawned with the resolved
  `model`/`effort`, because an unpinned spawn here does not merely cost the wrong amount — it decides the
  winner.
- **Synthesis is named as the step that usually goes wrong.** Grafting the runners-up's good ideas is the
  point of running several *and* the way to assemble a design no candidate validated, so every graft is named
  with its justification and the synthesized doc goes through the critic **as a whole** — it is new work, and
  G3's review has not happened to it yet. The bake-off runs **once**: G3 objections are repaired by a single
  architect on the synthesized doc, and a re-fan is a new activation decision, priced again.
- **Recorded where it can be read.** `state.bakeOff` holds stances, criteria, judge lenses, per-candidate
  verdicts with losing reasons, grafts and an honest `converged` flag; `/status` prints it and `/resume`
  judges what exists rather than restarting all N. The design telemetry row carries `candidates` and
  `stances` so an N× stage reads as N× in the cost readout, and `sc-ship` records the winning stance and
  `converged` in the PR body — cycle state is deleted at G13, so that is the only durable home for it.
- Orchestrator holds at **exactly 3,007 words**: the bright-line addition is paid for by four wording
  compressions elsewhere in the same file. The README reference-docs row now reads "the skills point to",
  since `bake-off.md` is pointed to by `sc-design` rather than by the orchestrator.

## 0.2.29 — Lighten the harness: rationale over rebuttals, and a smaller orchestrator (#59)

The kit had grown heavy in the direction agentic tooling has moved away from: more imperative rules, more
pre-rejected excuses, more gating. Emphatic NEVER/MUST phrasing was written for models that under-followed
instructions; current models follow closely enough that the shouting makes them **over-trigger**, firing a
rule in places it was never meant for. The cost was paid on every cycle, and 0.2.26's size tiers — the right
instinct — had added the mechanism for removing weight *as* more weight. Docs-only. Closes #59.

- **`Iron Laws` → `The core — what not to skip`.** Six rules, each stated in plain language with the reason
  it exists, because a rule whose rationale is understood generalizes to cases it never named while a
  shouted one gets applied literally. No all-caps NEVER/MUST rules remain anywhere in the kit, and the
  excuse-rebuttal lists ("trivial" · "just once" · "test after") are gone with them — once the rationale is
  stated they were buying nothing. Cross-references move from `Iron Law N` to `§core N`.
- **TDD is the default for logic, a judgment call elsewhere.** Test-first stays for anything with a
  contract — a function, an endpoint, a state machine — where it is the cheapest way to discover the
  contract is wrong. For layout, copy, config and most UI tweaks the meaningful verification is running the
  thing, so `sc-tdd` now says when it is the wrong tool, and **G4 accepts a named execution-based
  verification in place of Red evidence**. The engineering constitution's §8 and its review checklist say
  the same.
- **The pipeline is a default map, not a required path.** Stages still gate, but a stage with nothing to do
  on this change is skipped with a one-line reason, so the skip is a decision rather than a drift.
- **Orchestrator: 6,014 → 3,007 words** — exactly half — by moving rationale and rare-path procedure to four
  reference docs the orchestrator points at instead of carrying every cycle:
  `docs/model-routing.md` (routing rationale, the security-refusing-model guard, effort consequences, the
  cost readout), `docs/state-file.md` (full state shape, slug, collision guard, migration),
  `docs/test-baseline.md` (the `unrunnableHere` evidence and boundary rules) and
  `docs/worktree-recovery.md` (leftover worktrees, stale `index.lock`). Nothing operational was dropped —
  PREFLIGHT still carries every instruction it executes, including the effort table it reads at resolve
  time, and `/ship` plus the stage skills were updated to accept a deliberately-skipped stage
  (`gates.<G> = "n/a: <reason>"`) and an execution-based G4/G5 rather than treating either as an unmet gate.
- **What explicitly did not move.** Independent review, execution-based verification, worktree isolation
  and the baseline/regression split are named as the load-bearing core: they catch what a capable model
  reliably misses about its **own** work, so they are not compensation for weak models and are not dialable.
  The bright line between ceremony and outcomes stays in the orchestrator.

## 0.2.28 — Async external / foreign-agent review as a first-class gate, with a git-write freeze (#48)

`sc-review` assumed every lens is an in-session subagent returning synchronously — and even the spec-blind
**cold lens** is a same-model-family subagent. The skill names the gold standard it cannot reach ("the
in-pipeline stand-in for an outside reviewer"), while the real external reviewer is a **different agent or
model entirely**, run out of process, taking 25–40 minutes and exposing progress only through a status file
you poll. None of it was modelable — no async job, no foreign reviewer, no completion signal — so operators
hand-rolled polling waiters and tracked job ids in a scratchpad: precisely the hand-tracked state per-cycle
state (#41) was created to eliminate. Docs-only, framework-agnostic, independent of #47 (which makes a
*specific* foreign agent first-class; this is the layer underneath). Closes #48.

- **`state.reviewJobs`** — the async analogue of `models`. G8's shape becomes *freeze → snapshot → release
  → write-ahead → launch → poll → judge on completion*, and G8 does not pass while any entry is
  `running`/`launching`. **The record is written before the launch, not after**: the id comes from the
  launch command, so recording afterwards leaves a window where a running job exists with no state entry —
  invisible to `/status`, `/resume` and the freeze rule, and unrecoverable if the session dies in it.
- **Activation is `reviews: ["external:<name>"]`**, naming a reviewer declared in overlay
  **`externalReviewers`** (`launch`/`status`/`fetch` required, `notify`/`cancel` optional). The `external:`
  prefix is what makes the core invariant *mechanical*: a foreign reviewer can never occupy a built-in
  lens's slot, so one named `cold` cannot silently retire the in-session cold lens. Results are judged like
  any other lens — same severity discipline, refutation pass and triage rubric.
- **Freeze first, then snapshot — the capture is the window that needs protecting.** A concurrent
  `checkout`/`branch -f` *during* `git diff base...head` doesn't hang anything; it silently produces a diff
  against the wrong base, and a corrupted review input reads exactly like a clean one. The freeze is set
  before the capture and **released the moment the snapshot exists**, before launch — so on the default
  path the branch is free for the whole review while the reviewer reads something nobody will touch.
- **Git-write freeze as a fail-closed operational floor.** An out-of-process reader hangs indefinitely on a
  badly-timed `commit`/`branch -f`/`checkout`/`rebase` — a ~1-hour hang observed in the field, silent and
  progressless. Under `snapshot: false` (a reviewer that insists on the live tree) the freeze holds to
  terminal status and **every** stage that touches the tree or branch waits: `sc-implement`'s edits and
  worktree moves, `sc-ship`'s commit/push **and G13 teardown**, and PREFLIGHT's leftover-worktree recovery.
  A worktree recorded as a `reviewJobs[].snapshot` is **never** removed or pruned — and since
  `git worktree prune` is repo-scoped, the shared operations scan **every** cycle's state file, not just
  their own: `gitFreeze` is the one thing in per-cycle state that describes a repo-wide hazard.
  It sits on the **outcomes** side of the bright line: Tier S does not exempt you from waiting.
- **A terminal status is a claim that needs evidence.** `timeout` requires `endedAt` with
  `endedAt − startedAt ≥ maxWaitMinutes`; `failed` requires the reviewer's own error output at
  `resultPath`. **A `timeout` recorded minutes after `startedAt` is a skipped review, not a timeout** — a
  finding, not a deferral — and the manual-gate item carries the **elapsed wait**, so a review that was
  never actually waited for is visible as such. The schema enforces its half: `status`/`fetch` are required
  (a launch-only reviewer could never leave `running`) and `pollSeconds`/`maxWaitMinutes` must be ≥ 1.
- **A job whose subject is about to change is superseded, not waited out.** When G8 routes back to
  `sc-implement`, the in-flight review is reading a diff that will not survive: record `superseded`, run
  the optional `cancel`, release the freeze, re-launch against the fixed head. Without this verb the only
  exits from that loop were to wait out the timeout or fabricate one — which is what made the timeout path
  attractive rather than merely available. A superseded job is not a deferral and does not reach the PR.
- **The in-session lenses still gate G8.** The foreign reviewer was always an addition, so its absence
  never lowers "0 Critical/High" and never excuses skipping the cold lens.
- **Snapshot and result live outside the worktree**, the same rule the cost readout follows and for the
  same reason: G12 `git clean`s untracked files and G13 removes the worktree and the state file, so a
  deferral's evidence would be deleted before the PR merges — leaving a claim, not a record.
- **Completion is surfaced, not remembered.** `/status` prints every job with status and age and flags a
  **stale freeze** two ways — `active` with no live job, **or** `active` with `releaseOn: "snapshot"` once
  the snapshot exists, which is the likelier leak on the default path. `/resume` **polls a running job
  rather than relaunching it**: a relaunch abandons a job that may be half an hour in.

## 0.2.27 — An "unrunnable-here" baseline category for env/DB-gated suites (#50)

The test baseline (0.2.10) is binary — pass vs fail — and G6/G9 read "new failure vs baseline" as a
regression. 0.2.23 tightened honesty by making `@Disabled` / zero-executed suites a FAIL/deferral rather
than a pass. Between them sits a real third state neither models: **unrunnable-here** — an
integration/DDL/DB-gated suite this environment **cannot start at all**, verified elsewhere against a real
dependency. It is not a failure to diff against, and counting it as passed is forbidden, so a large part of
a suite ends up with **no truthful status** — which is how "can't run it here" becomes either a fake pass or
a fake regression. Docs-only, framework-agnostic. Closes #50.

`baseline.unrunnableHere: [{ suite, reason, startupError, probe, capturedAt }]` is captured at PREFLIGHT
alongside `failing`, and G6/G9 diff **around** it: neither a regression nor a silent skip. The category is
an escape hatch by construction, so it is fenced on four sides rather than merely added:

- **Boundary.** It means the suite **could not start** for want of a **dependency**. A suite that starts
  and fails is `failing`; one that starts and **skips itself** (`@Disabled`, zero-executed, DDL/seed/auth
  not provisioned) stays 0.2.23's FAIL/deferral. Not a laundering route for a disabled test, and the 0.2.23
  floor is not relaxed by one word. Runners blur the distinction — a context-init failure often reports as
  an error on every test method, a container-gated suite as *skipped* — so **when the report is ambiguous
  it is not unrunnable-here**: record it under whichever stricter category the runner named.
- **Evidence, in two pieces.** `startupError` is the suite's **own** attempted run terminating before any
  test executed; `probe` is the dependency command and what it returned. Only the first says *this suite*
  could not start — **one failed dependency probe never licenses quarantining a second suite**, the failure
  mode where a single `pg_isready` quarantines a whole module's tests, unit tests included. Either piece
  missing ⇒ not unrunnable-here, and a **passing** overlay `changeNature[].envProbe` is a hard bar: nothing
  under that nature may be quarantined for that dependency. The docs say plainly what this buys — both
  pieces are self-reported prose that nothing validates. They are **friction, not proof**.
- **Pre-commitment, with no growth path.** Fixed against the base commit, before the change exists. The set
  may only **shrink**. A suite that ran at PREFLIGHT and won't run now is a **finding**, not a quarantine.
  A suite that did not exist at the base commit (a new IT from sc-tdd) may only **inherit** an entry whose
  probe already failed, via `inheritedFrom` — and inheriting is not counting: it is not Red evidence at G4
  and not Green at G5. Any other growth means re-capturing the baseline from the top. `/resume` treats the
  quarantine as **read-only**, `capturedAt` stamps provenance, and `/status` **flags any entry that is not
  `preflight` as added mid-cycle** — a finding to check, not a quarantine to trust.
- **Non-satisfaction.** G6/G9 stop treating these as regressions; they do not start treating them as
  coverage. sc-ship labels any criterion they alone cover **`review-only (ci-deferred)`** — the suffix is
  load-bearing, since plain `review-only` means somebody read the code and argued it correct while
  `ci-deferred` means nothing in this run observed it — and puts it on the **pre-merge manual gate**, whose
  observable check is the CI job showing that suite executed and green on this branch's head. Quarantining
  changes the label, not the work: 0.2.23's contract-level degrade still applies in full.

Two supporting fixes this needed:

- **`gates.G9` becomes `pass` / `degrade` / `fail`**, the three-way shape `gates.G7b` already used
  (`pass`/`checklist`/`skip`), and **G12 honors a `degrade` only when its item is on the pre-merge manual
  gate**. Without this the honest case was unrepresentable: a run whose only coverage is quarantined could
  neither pass G12 nor usefully loop to a debugger that cannot conjure a database — leaving `pass` as the
  sole writable value. A gate with no truthful value is how false-green gets written by an honest agent.
- **Tier S has no baseline, so `unrunnableHere` is *absent, not empty* there** — the category is
  unavailable on Tier S rather than mintable from nothing. A Tier S run that meets a suite it cannot start
  **re-tiers upward to M** (monotonic, §Stage 0.2) and captures the baseline against the base commit.

## 0.2.26 — Right-size the cycle: size tiers, effort on the judgment axis, cost readout (#54, #53, #52)

Three issues on one axis: **#54** decides how much ceremony a change gets, **#53** makes the hardest
judgment call inside a review repeatable, and **#52** measures whether the routing actually paid. Docs-only,
framework-agnostic. Closes #54, #53, #52.

### Size tiers, chosen up front (#54)

The kit already had a *Lightweight path* and prose asides ("scale agent count to change size", "a trivial
one-line change may not warrant a worktree") — but they were asides, not a branch in the procedure, so the
default path stayed full ceremony. PREFLIGHT now **picks a change-size tier first** and records it:

- **Tier S** — a single expression/constant/comment whose cause is already corroborated by **≥2 independent
  code sites**: no worktree, no verification fleet, one review lens, low tiers. **S is a claim about
  evidence, not diff size** — "it's one line" doesn't earn it; if you can't name the ≥2 sites, it isn't S.
- **Tier M** — one module, one stack: worktree only if something else earns it, 1–2 lenses.
- **Tier L** — multi-file / cross-stack / security-sensitive / migration: the full set.

Recorded as `state.size`, printed with the routing, and **monotonic like risk**: a change that turns out
bigger moves up and adds ceremony back; it never moves down mid-cycle to retire a stage it already owes.

### Effort on the judgment/mechanics axis, not on stage names (#54)

Naming the expensive stages "design / review / critique" leaks, because the two most judgment-dense pieces
of work in the cycle answer to **no stage's name**: root-cause analysis and triage. Effort is now priced on
the work — `xhigh` design and the final adversarial lens (Tier L only), `high` root-cause analysis and
triage, `medium` Tier S review and multi-file edits, `low` setup/discovery/commit/tests/one-liners — bridged
to the host by a new overlay `modelRouting.effortMap` (advisory without one, exactly like `tierMap`) and
resolved into `state.effort` at PREFLIGHT, passed explicitly on every spawn (a default effort is the same
silent override as a default model — Iron Law 6). Two deliberate consequences: **review effort scales with
the size tier** instead of being pinned at the top (pinning it is what turns a corroborated one-liner into a
six-figure-token review, so "reviews are always xhigh" would have left the real waste in place), and **the
edit inherits the tier**.

### What right-sizing may never reach (#54)

Root-cause analysis, finding triage and the pre-PR conflict check are added to the **outcomes** side of the
bright line, alongside verification-was-read and fresh-eyes-review. They are the cheapest stages in the
pipeline and the first a right-sizing pass reaches for, because they produce no impressive artifact — and
they are what stop you implementing a misdiagnosed request ("relabel that bar as Total", when the bar is a
disjoint bucket and relabelling ships a chart that misleads), shipping a review's false positive, and
finding a conflict after the PR is open. Cutting them isn't right-sizing; it removes the part that worked.

### A deferred-findings rubric for Iron Law 5 (#53)

Iron Law 5 fixed the *disposition* of an out-of-scope defect ("found, filed, not fixed here") but not the
call that is actually hard: which of a review's surviving findings belong to *this* change? Without a rubric
it fails one of two ways every time — scope balloons, or findings get quietly under-filed. sc-review gains
three questions, **any yes → fix here, all no → file and link**: (1) reachable through the lines this diff
touched? (2) does this change introduce or amplify it? (3) is it a precondition for an acceptance criterion?
sc-ship then **asserts** it: every finding triaged as filed must have a real issue and a `Refs #NN` in the
PR body — an unfiled finding is dropped, not deferred: the same silent leak as a missing `Closes` token.

### Floors that survived the right-sizing (found in pre-PR review)

An adversarial review of the first pass caught two ways this change had weakened an outcome while claiming
to dial only ceremony — the exact failure #54 forbids — plus a defect that made #52 inert. All are fixed
here and stated as rules:

- **The security lens is never what a tier drops.** The first pass reduced Tier S from "quality+security"
  to "a single lens" without naming which survives, so an executor could ship a Tier S change with no
  security review at all — while the same file lists the fail-closed floors as never-dialed and 0.2.21
  builds a `securityReviewModel` pin that is meaningless if the lens itself can be dialed away. Tier S is
  now **the security lens plus one nature-matched lens**.
- **A surviving Critical/High always gets at least one refuter, never zero.** "No verification fleet"
  carried that carve-out in `sc-review` but not in the orchestrator — and the orchestrator is what an
  executor reads first. Both now say it.
- **Tier S must record its evidence.** "If you cannot name the ≥2 sites it is not S" was unenforceable —
  the party that benefits from S was the sole certifier, with nothing written down. S now records
  `state.sizeEvidence: ["path:line", ...]`, and **S with fewer than two recorded sites is M**.
- **Root-cause analysis has an owner and a gate.** It was declared an outcome but belonged to no stage.
  `sc-brainstorm` now owns it: for a defect goal the agreed problem **is the root cause**, corroborated by
  ≥2 sites, and **G1 does not pass on a restatement of the report**. Those same sites are what earn Tier S.
- **The triage assertion no longer fails open.** Quantifying over findings "marked filed" passed vacuously
  on an artifact that was never triaged. G8 and sc-ship now require **every** finding to carry a
  disposition; an absent triage record fails rather than passes.

### Post-run cost readout (#52)

Routing was enforced (0.2.6) but never counted, leaving the kit's one efficiency claim unfalsifiable on your
repo and `tierMap` tunable only by intuition. The cycle now accumulates `state.telemetry` per stage —
**each stage writes its own row at its gate**, since a stage running as a subagent is the only party that
can see its own usage — and G13 **emits the readout as its first act, before anything in cleanup deletes
anything**. Ordering is the point, and the explicit state delete is not the only hazard: the state file
lives in the cycle's working directory, *which is the worktree itself* when PREFLIGHT created one, so the
worktree removal destroys `telemetry` just as surely. The readout is written to an artifact dir **outside**
the worktree. `/status` prints the same table mid-run; `/resume` appends rather than
restarting it. **Nothing is estimated**: what the host doesn't expose prints `unavailable`, because a
fabricated cost table is the same false-green class as a scraped exit code (Iron Law 2). Read-only — it
gates nothing.

### Pruning rule: delete what the model knows, not lines (#54)

A blunt "simplify the skills" pass deletes the wrong half, so the README states the split: generic
principles (SOLID restatements, "don't swallow exceptions", "use parameterized queries") are **prunable**;
toolchain paths, wrapper scripts, runner flags a junction layout requires, and VCS footguns (including the
teardown that follows a `node_modules` junction, 0.2.25) are **load-bearing**, because each exists from an
incident and none is inferable. Generalized: *generic principles prune, overlay/environment facts stay.*

Applied, per the maintainer's **conservative** call: the constitution's §3/§4/§6/§8 restatements collapse
to compact reference points while every gate-cited number, anti-pattern and non-obvious idiom (the TS
`enum`-vs-union caveat, ≥80% coverage, the normalized error shape) is kept in full, with no renumbering —
`sc-review`'s `#3`/`#7` citations still resolve. The option's second half is also done: `sc-implement`
demotes the `prompts/impl-*.md` stack templates to **reference invoked when the tier warrants it**, skipped
on Tier S where loading a 60-line template costs more than it carries.

**Honest accounting: this release adds weight, it does not remove it** — roughly +300 lines of new
procedure against ~50 removed, and the constitution itself grew (76 → 81) because the pruning *rule*
costs more lines than the restatements it authorized deleting. The prune is deliberately small; what is
new is the rule that governs the next one. Stating the principle is not the same as having applied it, and
this entry does not claim otherwise.

## 0.2.25 — Junction/symlink-safe worktree teardown + stale `index.lock` recovery (#49)

`env.sharedNodeModules` (0.2.19) made the kit **create** links from each worktree into one shared dep
store, but teardown guidance never learned about them. 0.2.11 covered only the *non-destructive* teardown
failure (locked files → `git worktree prune`, warn, move on). The destructive one was reachable **by
design**: a delete that resolves the link reaches the shared store and wipes the install every other
worktree and parallel cycle depends on — observed in the field, silent and unrecoverable. Docs-only,
framework-agnostic. Closes #49.

- **Sweep, then let git delete (sc-ship G13, binding order).** Teardown is the one cycle step that can
  destroy state *outside* the worktree, so it is now an ordered procedure. (1) Sweep the **whole
  worktree**, not just `node_modules/` at the root — a store is as often linked per package, where a
  root-only `test -L` returns false — via `find <wt> -xdev \( -type l -o -xtype l \) -print` / a
  `-Attributes ReparsePoint` scan, and unlink every hit: `rm`/`unlink` on POSIX, `cmd /c rmdir "<link>"`
  on Windows. The commands that *don't* work are named too: `rmdir <link>` fails on POSIX (`Not a
  directory`, link survives), bare `rmdir` is a `Remove-Item` alias in PowerShell, and `Remove-Item`
  prompts on WinPS 5.1 and deletes through reparse points before PowerShell 6.2. (2) Then
  `git worktree remove --force`, which unlinks rather than descending — the delete is delegated to git,
  never hand-rolled. (3) The locked-files fallback is unchanged, with one addition: the directory you
  abandon must be **link-free**, because whoever deletes it later is outside this procedure.
- **The danger is scoped correctly, not asserted broadly.** Plain `rm -r <worktree>` does *not* descend
  through a symlink; the POSIX form that destroys the target is `rm -rf <link>/` — the **trailing slash**
  resolves the link — and on Windows `rd /s` / `Remove-Item -Recurse`, where recursion does follow
  junctions. A rule an operator can falsify on their own machine gets discounted wholesale, so the docs
  say which form bites where. A pnpm content-addressable store shares by *hardlink* and is exempt; the
  sweep runs anyway, since the cycle can't tell which form a project used.
- **Stale `index.lock` recovery (PREFLIGHT), with a performable guard.** A `worktree add` that outlives a
  command timeout has already created the branch, the directory **and** the registration; only the
  checkout is unfinished. So recovery **finishes the checkout in place** — `git -C <wt> checkout -f` —
  and never re-runs `worktree add`, which fails on the branch the timed-out add created (`fatal: a branch
  named '<branch>' already exists`; `--force` doesn't help). The lock is resolved with
  `git -C <wt> rev-parse --git-path index.lock`, since inside a worktree `.git` is a *file* and the lock
  lives under the main repo's git dir. The go/no-go is the lock's **age** (`find <lock> -mmin
  +<timeout>`), not "is a git process running" — the crashed add leaves no process, so that check is
  trivially true exactly when it tells you nothing.
- **PREFLIGHT owns the leftover directory.** G13's fallback deliberately leaves a worktree dir behind; the
  next cycle's `worktree add` then fails on the existing path and the agent improvises a delete. That
  delete now has a rule (sweep → unlink → `worktree remove --force`, else `prune` + delete) instead of
  being the one unguarded recursive delete in the cycle.
- **Every surface that sells the sharing now carries the unlink rule** — sc-qa, PREFLIGHT, sc-implement's
  post-merge cleanup (unconditional: links also arrive via `npm link`, monorepo layouts, a manual
  `mklink`), the README `env` bullet, the example overlay `$comment`, the config **schema**'s
  `sharedNodeModules` description, `/ship`'s G13 summary, and G13's gate row.

## 0.2.24 — Genericize domain-specific module names in the example overlay (#44)

The shipped example overlay (`docs/ship-cycle.config.example.json`) had `audit.modules` set to
domain-specific names derived from one product's domain (`onboarding`, `program`, `workout-log`,
`nutrition`). The example is what users copy, and the kit is meant to be domain-agnostic. Genericized to
neutral placeholders (`auth`, `billing`, `catalog`, `orders`, `profile`, `settings`); the `$comment`
already notes these are illustrative. Docs-only, no schema or behavior change. Closes #44.

## 0.2.23 — Per-cycle state + integration tests must execute (#41 proposals 1 & 4)

Closes the last two field-note items from the concurrent-run report (#41). Docs-only, framework-agnostic.

- **Per-cycle state, keyed by branch (#41 proposal 1).** The single `.claude/.ship-cycle-state.json` +
  archive-on-finish assumed **sequential** cycles; running several from one working directory clobbered it,
  forcing hand-tracked state + loop counts in a scratchpad. State now lives at
  `.claude/ship-cycle/<branch-slug>.json` (slug = branch via **exactly** `tr '/' '-'`, binding on writer and
  every reader), one file per cycle, in the cycle's own working directory — so concurrent cycles on different
  branches never clobber and each file owns its `loops` (per-cycle loop caps for free). PREFLIGHT resumes by
  branch, migrates a legacy bare file **by move** (only when its `branch` matches — never leaks another
  branch's state), refuses on a detached HEAD (no branch key) or a slug collision (`branch` field
  disambiguates), and G13 deletes the file when the branch is deleted. `/status` lists co-located active
  cycles; `/resume` and `/ship` resolve the current branch. (Two worktrees were already isolated — each has
  its own `.claude/`; this fixes the same-checkout case.) README gitignore guidance now targets the
  directory `.claude/ship-cycle/`.
- **Integration tests must EXECUTE, not just compile (#41 proposal 4).** A DB integration test can compile
  green and fail on first real execution (a `useGeneratedKeys` key never populated → binds `null`, a NOT-NULL
  column left unseeded, a migration not applied). sc-qa now requires integration/seam tests to actually run
  against the real dependency (or an equivalent) and pass — run log with executed count > 0; `@Disabled` or a
  zero-executed/skipped suite is a FAIL/deferral, not a pass (the same false-green class as a masked exit
  code). G9 and sc-ship's `test` evidence label are tightened to match.

## 0.2.22 — Full-context boot/context-load smoke gate for framework-wiring changes (#40)

A change can pass **every** gate — Red-first unit tests (hand-assembled collaborators), integration tests
(sliced context), and multi-lens review (reads code) — and still ship an app that **won't boot**, when the
defect is in framework wiring. None of those gates load the *full* application context. Real field
incident: an **unchanged** broad `@MapperScan` proxied a **new plain interface** as a mapper →
`BindingException` at bean creation → context fails to start; it passed 37 unit tests + a sliced-context IT
+ an opus review. Adds gate **G7b** (docs-only, framework-agnostic):

- **Nature-level trigger, not a per-diff guess.** A `changeNature` entry that declares a project-defined
  `bootCheck` command marks the nature as having a loadable context; G7b (sc-implement, Green) then runs it
  on **every non-inert change** to that nature's production sources. Skip only **provably-inert** diffs
  (docs/comments, tests, non-runtime assets); production resources (`src/main/resources/**`), build/dep
  manifests, and framework config are **non-inert by default**, and **when unsure → boot**. (An earlier
  path-glob "touches wiring" trigger was rejected by the kit's own design critic: it would have *skipped*
  the very incident above — the changed file was an ordinary interface, not a config file.)
- **An outcome floor, not dialable ceremony.** The only thing dialed is whether a nature has a loadable
  context at all — UI-leaf natures declare no `bootCheck` and never boot, so leaf changes pay nothing.
- **Cheap + eager + honest.** Prefer a standing `@SpringBootTest(webEnvironment=NONE)` load (~seconds, often
  already in the suite); it must force **eager** bean creation (lazy-init can false-pass the eager failure).
  A selector matching zero tests is a **misconfig FAIL**, not a pass. It proves the DI graph is
  constructible — the web layer/filters/health stay sc-qa's HTTP bring-up (when QA does a full bring-up it
  re-covers G7b, so no third boot).
- **CI-safety caveat.** Needs a full-context-capable env (a superset of the sliced ITs'). The gate lives in
  the **cycle** (local/pre-PR); never wire an env-dependent boot into a CI path lacking its deps — it
  red-blocks unrelated PRs, and during an outage blocks the very fix that restores the service. When a
  context can't be loaded locally, degrade to a named pre-merge checklist item (surfaced by sc-ship), never
  a silent pass.

Docs-only; framework-agnostic; no behavioral code. Closes #40.

## 0.2.21 — Two silent-failure guards from a real 2-cycle field run (#41)

Field notes from an external user running two ship-cycles concurrently on a Spring Boot + MyBatis repo
surfaced two ways the cycle could *look* green while a floor silently failed. Both fixed as guidance +
overlay wiring (docs-only, framework-agnostic):

- **No false-green from a piped exit code (#41 proposal 3).** `cmd | grep | tail` reports the tail's exit
  status, so a failing build/test — or a `command not found` from a toolchain that never reached `PATH` —
  reads green. Iron Law #2 now forbids judging pass/fail from a piped exit code; sc-implement (G5/G6) and
  sc-ship (G11) require the command's own exit status or the machine-readable report (surefire/JUnit XML,
  runner JSON), never scraped stdout — and note that `set -o pipefail` alone doesn't rescue a `grep`-in-the-
  pipe check (grep exits `1` on no match → a passing build turns false-RED; drop the pipe).
- **Security reviews can't run on a security-refusing model (#41 proposal 2).** Risk-based routing could
  send a security/authz review to a model that refuses security analysis, which then silently no-ops.
  Overlay `modelRouting.securityReviewModel` pins the model the `security`/`authz` review lenses use,
  overriding their tier — sc-review spawns those lenses with it and PREFLIGHT logs `SC-ROUTE-AVOID`. A
  fail-closed floor, since a security review that quietly checks nothing is worse than a loud stop.

Also captured from the same field run: "reviewer != author" adversarial separation and STAY-IN-SCOPE →
file-out-of-scope both earned their keep and are unchanged. Deferred to follow-ups: per-cycle state for
concurrent cycles (#41 proposal 1) and requiring integration tests to *execute*, not just compile (#41
proposal 4).

Docs-only; framework-agnostic; no behavioral code.

## 0.2.20 — Proportional strictness: env graceful-degrade + the outcomes/ceremony bright line

Ran the kit's own design cycle (brainstorm → design → adversarial critic) on "make strictness
risk-proportional." The critic descoped it hard, and correctly: in a docs-only kit the "load-bearing vs
skippable" call is an LLM eyeballing an *unvalidated* config, so a nuanced degrade taxonomy would *reduce*
safety. What survived:
- **One narrow PREFLIGHT carve-out**: a schema-invalid `env` block (a pure cost knob whose documented
  fallback is "spin up fresh") emits `SC-DEGRADE-ENV` and continues instead of aborting the cycle. Every
  other section — and any unparseable file — still fails closed. `env` only, because it can never touch a
  correctness floor.
- **The bright line, stated once** (Lightweight path): *ceremony* (stage count, tier, worktree, lens
  breadth, QA-skip, TDD-harness form) is dialable; *outcomes* (verification ran + read, fresh-eyes review,
  the fail-closed floors, a failing test first) are never dialed. When unsure, it's an outcome.
- **Monotonic risk re-escalation** (PREFLIGHT step 6): the risk label dials ceremony only, never an
  outcome; a later stage that reveals a higher-stakes axis re-escalates — adding ceremony back, never
  removing an outcome.

Explicitly rejected by the cycle: inverting the default to proportional-by-default (it removes the
fail-safe default), a multi-section degrade allowlist, and documenting a risk→lightweight-path dial that
doesn't exist. **strict-by-default is unchanged.**

Docs-only; framework-agnostic; no behavioral code.

## 0.2.19 — Per-cycle env-cost knobs (opportunistic reuse)

In a continuous ship run, every cycle re-pays worktree → dep install → server boot → e2e install; over
many cycles that overhead dominates wall-clock. Adds an optional overlay `env` section and the guidance to
honor it — opt-in, and always subordinate to correctness (closes #22):
- **`env.reuseDevServer`** (a bare port, `{port, healthPath}`, or `true` to auto-detect): sc-qa drives
  against an already-healthy server instead of booting a fresh one — booting clean only when the change
  needs isolation or the health check fails.
- **`env.sharedNodeModules`**: PREFLIGHT shares one dep store (pnpm store / linked `node_modules`) across
  worktrees so each doesn't re-download the full tree.
- **`env.reuseE2EInstall`**: reuse one Playwright/e2e install (browser binaries are cached) instead of
  `npm ci` per worktree.

These are speed knobs, not correctness ones — absent the `env` section, the plugin always spins up fresh.
The plugin is docs-only: it *instructs* the reuse; the actual caching lives in the operator's harness.

Framework-agnostic; docs-only; no behavioral code.

## 0.2.18 — Observability commands (status / resume / ship)

The cycle state file (`.claude/.ship-cycle-state.json`) existed but there was no quick way to inspect a
run mid-flight, resume an interrupted one, or jump to ship once gates pass. Adds a `commands/` surface
(auto-discovered alongside `skills/` — no manifest change) with three user-invokable, read-only-by-default
commands (closes #25):
- **`/ship-cycle-devkit:status`** — print stage, gate table (G1–G13), loop counts, resolved model routing,
  and worktree. Read-only.
- **`/ship-cycle-devkit:resume`** — resume from the last incomplete stage via the ship-cycle PREFLIGHT
  resume path; never restarts completed stages or re-inits state.
- **`/ship-cycle-devkit:ship`** — jump to `sc-ship` only when the required upstream gates (G1–G9) are
  green; refuses and points back to the owning stage otherwise (Iron Law #3).

Note: the `/sc:` short prefix from the issue isn't used — Claude Code derives the command namespace from
the plugin `name`, so commands are `/ship-cycle-devkit:*` (renaming the plugin would break existing
installs). Commands are declarative markdown prompts, not executable code.

Framework-agnostic; declarative commands, no behavioral code.
## 0.2.17 — Audit follow-ups: prompt symmetry, gate & SSOT consistency

Four small consistency fixes from the 0.2.16 audit (closes #32, #33, #34, #35):
- **TDD symmetry in impl prompts** (#32): `impl-web` and `impl-mobile` gained a `## Testing (TDD —
  required)` section — test-first (Red→Green), extract pure logic for render-less UI, no vacuous test —
  matching `impl-backend` and constitution §8 / Iron Law #1.
- **G13 defined** (#33): the gate table listed only G1–G12 while the pipeline row claimed G10–G13. Added
  the G13 row (merged branch deleted local+remote, worktree removed if present, base synced), relabeled
  sc-ship's "Cleanup (Stage 13)" → "Cleanup (G13)" (stages are 0–7; cleanup is a gate, not a 13th stage),
  and wired sc-ship to set `gates.G13 = pass` after cleanup so the gate is actually tracked in state.
- **Loop-cap SSOT** (#34): dropped the duplicated literal "3" from `sc-design` and `sc-review`; both now
  say "respect the orchestrator's loop cap" — the value lives only in `ship-cycle`.
- **impl-mobile parity** (#35): added the no-silent-`catch {}`/log rule (§6, matching `impl-web`) and a
  "consume the actual serialized DTO shape" rule (mirrors the shape-verification language in
  `sc-design`/`sc-audit`; complements `impl-backend`'s "never return entities").

Docs-only; framework-agnostic; no behavioral code.

## 0.2.16 — No-magic-numbers / named-constant coding standard

The kit reached for the narrow design-token/i18n cousins of this rule (no hardcoded colors/spacing/copy)
but never stated the general one, so a literal with domain meaning (a `≥60` deload threshold, a status
string, a `setInterval` period) was authored, reviewed, and shipped with no rule naming it. Added as a
framework-agnostic Clean-Code baseline, language-aware and enforced at review:
- **Constitution §3**: no magic numbers/strings — extract any domain literal to a named constant; a
  closed, related set becomes an `enum` (Java) / a union literal type or an `as const` object (TS —
  **not** `enum`) / `Object.freeze` (JS), with behavior on the set where it has any (an anemic constant
  bag repeats the anemic-model smell, #7). Constants now join the "meaningful names" rule.
- **sc-review quality lens**: magic numbers/strings is now a named anti-pattern — a rule no lens checks is
  dead — including a closed set not modeled as an enum/union/frozen object.
- **impl prompts** (backend/web/mobile): each states the rule in its stack idiom — Java enum-with-behavior;
  TS union / `as const`, **avoiding `enum`** — on top of the existing design/theme-token rules.

Docs-only; framework-agnostic; no behavioral code.

## 0.2.15 — Design-consistency gate: reuse before create

Consistency is decided at design time, not caught at review time — so a crude, uncoordinated surface
(three different empty states, a bespoke spinner where a progress component exists, ad-hoc spacing) is
almost always "invented instead of reused." Framework-agnostic; the overlay supplies *which* tokens and
components exist, the plugin enforces *reuse* of whatever they are.
- **Overlay `design` contract** (`ship-cycle.config` example + schema): declare the project's design
  source of truth — `tokens`, `components`, and an optional design-system `guide`. Optional; omit to have
  the designer inventory the repo ad hoc.
- **sc-design reuse-before-create gate** (UI changes): the design must consume the design source of truth
  and resolve every color/spacing/type-scale/empty-loading-error state/progress indicator/icon from an
  existing token or component. A **new** visual primitive needs a one-line justification of why no
  existing one serves it ("faster to inline it" is not one). Name the canonical pattern per recurring
  surface so the implementer wires the shared one, not a new copy.
- **sc-review designer lens → named anti-patterns** (was a vibe check): hardcoded design values that
  bypass tokens; a reinvented empty/loading/error/card/button where a canonical component exists;
  decorative-not-informative indicators (a fixed spinner where a fill/ring belongs); off-scale type/space;
  the accessibility floor (touch target, labels, contrast, modal focus); emoji-as-icon.
- **Design-consistency floor** (sc-review severity): a change that reinvents an existing
  token/component/pattern is at least a finding even when it "looks fine" in isolation — the cost is
  cumulative fragmentation, paid one diff at a time. Surface it as reuse-or-justify, never a silent pass.

## 0.2.14 — Iron Law mechanization: evidence strength, reachability, model pinning, sibling-PR & artifact guards

Five framework-agnostic hardenings distilled from a long continuous-ship run, each turning an
operator-discipline step into a mechanical one:
- **Evidence *strength* per claim** (`sc-ship` G11): mapping a claim to "evidence" isn't enough — a
  live-driven criterion and a review-only one (live was blocked) read identically unless annotated by hand.
  Tag every claim **live / test / review-only** and surface it in the PR claim map, so a review-only
  fallback can't silently masquerade as a live pass. `review-only` is a named, legitimate outcome — not a
  hidden one.
- **QA reachability precheck** (`sc-qa`): a live backend + auth still can't drive an **owner/role-gated**
  flow when the test user can't reach the target record (detail endpoint returns empty → the affordance
  never renders). Made "reachability-blocked" a first-class outcome — check the precondition, degrade that
  criterion to contract/review-only, record *why*, and carry it into sc-ship's claim map — done once
  mechanically instead of hand-writing a "review-verified" note every cycle.
- **Mechanical model pinning on review lenses** (`sc-review`, Iron Law 6): since lenses are
  `general-purpose` spawns, the review tier lives only in `model=` and one omission silently downgrades a
  top-tier review to a cheap default. Added: read `model = state.models.review` on every spawn (resolve
  once, copy every time), an anti-drift restatement before fan-out, and an **optional** pinned lens-agent
  path that must degrade gracefully to `general-purpose` + `model=` on hosts without custom agent types
  (enforcement without trading portability).
- **Sibling open-PR conflict probe** (`sc-ship` G12): the merge-tree check compares against the base only,
  but two still-open PRs collide with each other on append-only files (i18n `.properties`/bundles/barrels
  where each appends at EOF). Added a heads-up that lists open PRs touching any file in the diff so the
  merge order is a conscious choice, not a merge-time surprise.
- **Artifact-exclusion on commit** (`sc-ship` G12): overlay `commit.excludePaths` lists generated/CI-built
  paths (e.g. a bundle dir a QA step built locally) that sc-ship auto-reverts / never stages, keeping
  commits source-only. Absent the setting, still skip obvious build outputs (`dist/`, `build/`) and flag
  rather than commit blindly.

Docs-only; framework-agnostic; no behavioral code. Adopted from issues #21, #23, #24, #27, #28.

## 0.2.13 — sc-ship: verify the issue-closing token actually landed in the PR body

One framework-agnostic `sc-ship` hardening from a live cycle where a fully-done issue stayed open after
its PR merged:
- **Re-fetch and assert the closing token, don't trust that you wrote it** (`sc-ship` G12 + gate): the
  rule to link the tracked issue with `Closes #NN` already existed, but nothing verified it landed. A PR
  whose body summarized the work in prose (a `#NN —` heading) but omitted the `Closes` keyword merged
  clean and left the finished issue **open** — the host only auto-closes on the `Closes`/`Fixes`/`Resolves`
  keyword, and it must be repeated per issue (`Closes #90, closes #91`, not `Closes #90, #91`). Added: after
  opening the PR, re-fetch the created body and assert the exact intended token for **every** tracked issue
  in state (`Closes` when fully done, `Refs` when partial); a bare mention or title `(#NN)` does not count.
  Missing/keyword-less → patch the body before merge, or `comment + close` if already merged. The gate now
  includes this assertion. Same failure class as the cold lens: the narrative reads complete while the
  machine-readable token silently leaked.

Docs-only; framework-agnostic; no behavioral code.

## 0.2.12 — sc-audit: surface-type drift (phantom fields) + "wired ≠ works" target validation

Two framework-agnostic `sc-audit` hardenings from live parity-migration recon (from #14, #15):
- **Surface-type drift / phantom fields** (Step 3 cross-cutting): cross-reference each surface's
  **self-declared** types against the source-of-truth schema and report fields present in one but not the
  other — **surface-only** = phantom/stale (exists in no backend DTO; renders always-`false`/`undefined`, a
  dead conditional new features inherit), **source-only** = unmodelled. Structural drift the behavioral
  matrix misses — catches "the type is wrong *before* you build on it."
- **"Wired ≠ works"** (Step 1 inventory): in a migration audit, don't treat a legacy source screen as a
  real feature just because it's menu-registered + call-wired. Flag **"possibly non-functional"** when
  handlers are stubs / there's no live data path (no real backend call, hardcoded data, dead submit), and
  **ask the domain owner to confirm it actually functioned** before it becomes a build/parity target —
  rebuilding a never-worked screen is pure waste.

Docs-only; framework-agnostic; no behavioral code. Adopted from issues #14, #15.

## 0.2.11 — lifecycle hardening: plural-case tests, spec-blind cold review, pre-PR merge verification

Three framework-agnostic hardenings distilled from live cycles (consolidated from separate branches):
- **Cover the plural case (N≥2)** (`sc-tdd` + `sc-qa`): a test that exercises **one** item passes while a
  bug that only manifests with **two or more** hides — off-by-one/ordering, batch writes, dedup/merge,
  pagination, and multi-row inserts whose driver returns only one generated key (so an in-memory
  "keys → child rows" link silently cross-wires at ≥2 rows). When the change touches a collection / batch /
  id-key assignment / ordering / any for-each path, write the N≥2 case and **assert the cross-item
  relationship** (row A links to A, B to B), and have `sc-qa` exploration probe the batch case explicitly.
- **Spec-blind "cold" review lens + real-world-state floor** (`sc-review`): a heavy multi-lens review still
  ships bugs an outside reviewer catches first-pass, because every lens is anchored to the author's spec —
  a wrong premise gets rated "as-designed" by all of them. Added an always-on **cold lens** that gets
  **only the diff** (no design doc/canonical) and assumes nothing the author claims; a cross-cutting
  **real-world-state probe** (legacy/pre-existing rows, empty & N≥2, unsaved/no-id-yet, re-run/partial-save);
  and a **data-integrity floor** — a change that can persist wrong/duplicate/lost/orphaned data is at least
  **High**, even if it "matches the spec" or "replicates a legacy quirk" ("the old system did it too" is a
  parity note, not a severity downgrade).
- **Verify clean merge before opening a PR + robust worktree teardown** (`sc-ship` G12 + cleanup): the PR
  stage never checked mergeability — a branch cut before a sibling merged, or one that merely *appends* to
  shared files (i18n bundles, lockfiles), opens **dirty** and only conflicts at merge time. Added a pre-push
  `git merge-tree` conflict probe + post-push `mergeable` poll ("merge base + resolve, re-verify" on
  conflict; re-check open PRs on request). Teardown now uses `git worktree remove --force` + a
  `git worktree prune` fallback (a build tool holding file handles — `node_modules` on Windows — no longer
  aborts cleanup); a failed directory delete is a **warning, not a gate**.

Docs-only; framework-agnostic; no behavioral code. Consolidated from #13, #16, #17.

## 0.2.10 — multi-cycle robustness: test baseline, state lifecycle, axis-split design, scope re-classification

Lessons from running the lifecycle repeatedly on one repo (sequential cycles) and on a change that grew
full-stack at the design gate:
- **Test baseline at PREFLIGHT** (`ship-cycle`): when the base branch already has failing tests, every
  later stage — and every parallel implementer — wastes effort re-deriving "is this my regression or was
  it already red?" (stash-and-compare, over and over). Added: run the suite on the **base commit once**,
  record the pass/fail set in `state.baseline`, and have gates **G6/G9 diff against it** — only a *new*
  failure blocks. `sc-implement` G6 now says the same, so implementers stop re-litigating pre-existing reds.
- **State lifecycle across runs** (`ship-cycle`): a state file left at `stage: complete`/`failed` from a
  finished cycle was being hand-clobbered to start the next one. Added: PREFLIGHT **archives** a finished
  state and initializes fresh; only a mid-pipeline `stage` is a resume candidate. This is what makes
  **sequential cycles** on one repo clean.
- **Split the architect by axis** (`sc-design`): for cross-cutting/full-stack designs, run N architects in
  parallel on **exclusive slices** (each stating its seam contract), then **one** critic reviews the
  **union** — so it catches *inter-axis* contradictions (mismatched seam signatures, one axis's "no schema
  change" vs another's "persist a new field"). The design-stage analogue of `sc-implement`'s partitioning.
- **Scope can be re-classified at the design gate** (`ship-cycle` + `sc-design`): change-nature/model
  routing is **not one-shot**. When design reveals a stack/axis the initial diff didn't show (a
  "frontend-only" change that needs a new backend endpoint), re-run classification, add the implementer
  axis, and route for the true scope — a design-gate scope growth is normal, not a failure.
- **Out-of-scope defect disposition** (Iron Law 5): a real defect found *outside* the current scope (a
  latent bug, dead-code path, data error) → **file it and keep going**; don't fix it in this branch (scope
  creep) and don't silently drop it. "Found, filed, not fixed here."

## 0.2.9 — waved execution: blast-radius control; visual QA: cheaper CDD tier

Refinements to 0.2.8 after review:
- **Atomic contract-change rule needs blast-radius control** (`sc-implement`): with dozens of call sites,
  the naive "each parallel agent runs `tsc` in its loop" backfires in a *shared* working tree — a
  whole-project typecheck sees other agents' half-finished edits and misattributes/"fixes" foreign files.
  Added: land **contract (signature/type) changes + their call sites as a serial micro-wave, verified once**,
  before the parallel leaf waves; and if kept parallel on a shared tree, on barrier failure **bisect errors
  → owning file → re-dispatch only that owner** instead of stalling the wave. In-loop self-verify is only
  safe under worktree isolation.
- **Visual QA has a cheaper tier** (`sc-qa`): component isolation (CDD — a Storybook via react-native-web,
  screenshot in a headless browser) verifies component/layout/token regressions with no native build/
  emulator. Two caveats recorded: it **complements, not replaces** the emulator pass (native fidelity gaps),
  and the real token sink is **loop discipline** — use the vision loop for render/regression verification,
  not subjective aesthetic nudging (pin aesthetics in tokens up front).

## 0.2.8 — mobile visual-QA harness + waved cross-cutting execution

Learned from a real large mobile UI reskin run:
- **Mobile visual QA can be automated** (`sc-qa`): an emulator/simulator screenshot loop ("agent sees the
  UI and iterates") is viable — not just a manual checklist. Two setup traps that eat hours, both with
  generic fixes: a managed prebuild can pin a build tool **too new** for the framework's own plugins (build
  fails before any render), and bundler↔device networking across namespaces sends the device to the wrong
  host (empty-stream error). Capture via `adb exec-out screencap`; get past auth gates with the real
  backend's signup/login.
- **Waved execution for large single-stack cross-cutting changes** (`sc-implement`): worktree-per-stack
  doesn't help when collisions are *within* one stack (a design-system reskin). Serial foundation wave
  (tokens/shared wrappers/i18n) → parallel waves over **exclusive file-ownership partitions** → **atomic
  contract-change rule** (a signature change updates its call sites in the same wave, keeping the barrier
  typecheck green) → resource-aware concurrency (cap agents when a heavy local process is up).
- **Fail-closed hooks block parallel agents** (`sc-design`): a turn-end fail-closed gate (i18n symmetry,
  lint) blocks *parallel* implementers on the shared resource — identify at design time and pre-register/
  freeze it in the serial foundation step.

## 0.2.7 — delegation criteria + high-stakes lightweight review

Learned from a real EAS build-fix run:
- **Delegate vs act inline** (`ship-cycle`, new section): the orchestrator is *not* a pure conductor —
  spawning a subagent isn't free (boot + re-brief + re-read), so a trivial edit is cheaper done inline
  even on the orchestrator's pricier, session-fixed model. Delegate only when it buys **independence**
  (adversarial stages — a reviewer can't be the author), **tier savings on substantial work**,
  **context hygiene** (the orchestrator is long-lived; hand off context-heavy reads to a read-and-discard
  subagent), or **parallelism**. The line is "does delegation buy something", not diff size.
- **Lightweight path drops tiers — except small-but-high-stakes** (`ship-cycle`): trivial work runs
  mid/low, but keep the higher review tier when cost-of-being-wrong is high or verification is expensive
  (build/release config, dependency/lockfile, contracts, data-loss, security). Tier by
  cost-of-being-wrong × verification-difficulty, not diff size — a high-tier review of a 10-line dep bump
  caught a stale-lockfile defect a cheap pass would likely have missed.
- **Lockfile sync** (`sc-implement`): changing a dependency manifest that has a committed lockfile
  requires regenerating the lockfile in the same change — CI/release installs from the lockfile
  (`npm ci`, `--frozen-lockfile`), so a manifest-only edit is inert or re-breaks the build.

## 0.2.6 — model routing, actually enforced

Closes the gap where tier→model routing was *documented* but silently skipped at runtime — a review
meant for the high tier ran on a specialized agent type's cheaper default model, unnoticed.

- **Iron Law 6 (new)**: never spawn a stage agent on a default model. Resolve tier→model at PREFLIGHT and
  pass `model=` explicitly. It names the exact trap: a specialized agent type (`quality-reviewer`,
  `security-reviewer`, `architect`, …) carries its *own* default that silently overrides your tier when
  `model=` is omitted.
- **PREFLIGHT pre-resolves per-stage models** into `state.models` (risk upgrades applied) and **prints
  them** (auditable). This turns "remember to bridge the tierMap" into "copy a concrete value" — the
  difference that makes it actually happen.
- **Every stage skill** now carries a point-of-use line: `Pass model = state.models['<stage>']` at the
  spawn site, not buried in a routing section.
- State schema gains `models`; the tier→model bridge doc spells out the default-model trap and how
  mixed-tier stages (e.g. `sc-ship`) resolve per-role.

## 0.2.5 — state-file handoff between stages

- **State-file handoff rule** (orchestration plumbing, **not an agent**): each stage writes its output
  to a file under the run's artifact dir; the next stage reads it; the orchestrator passes only pointers
  (paths) in the state file, never a full artifact through its own context.
- **Verbatim by construction — zero cost, zero distortion**: files carry artifacts whole. This is
  deliberate — summarizing between stages risks silently dropping an unresolved objection, a gate
  blocker, or failing evidence, and verbatim carrying is a code job, not a model's, so no agent is spent
  on it. (Earlier drafts modeled this as a cheap "relay" agent; a truly-verbatim LLM pass is redundant
  with plain file passing, so it's plumbing, not a role.)
- **Put a model in a handoff only for a trusted transformation** (extract acceptance criteria, reformat
  for the next tool) — then pick the tier that transformation demands, not a blanket cheap summarize.

## 0.2.4 — parity-audit discipline

Adds a new à-la-carte skill, learned from a real cross-platform integration miss:
- **`sc-audit`** (new, not in the default chain): a static **cross-surface parity audit**. Compares every
  consumer surface (web, mobile, CLI, SDK, another service) against a single source-of-truth contract and
  emits a module-by-module gap matrix + cross-cutting risk checks (authz/paywall leak, entity-return,
  data drift, i18n, file/export) + P0/P1/P2 priorities + a **cutover/ship verdict**
  (parallel-run only / cutover-ready / ship-ready).
- **Why it's separate from `sc-design`**: sc-design verifies the contract *for the feature in hand*; an
  entire surface can be built on assumed contracts and stay green until the first real integration, when
  most screens break at once. A dogfood run shipped a whole web app that "deployed" but almost nothing
  worked end-to-end — the class of failure a per-feature guard can't see. sc-audit is the macro sweep;
  run it before a first cross-surface integration or on a large/ahead-of-backend surface.
- **Core rule carried over**: "endpoint exists ≠ integrated" — only ✅ when the surface actually calls it
  with the real serialized shape; check the composition root for which implementation is wired in.
- **Overlay**: new optional `audit` section (`sourceOfTruth` / `surfaces` / `modules` / `reportDir`);
  falls back to `changeNature` globs and logs when defaults are used. Schema + example updated.

## 0.2.3 — second-dogfood feedback (mobile bug-fix cycle)

Learned from a React Native (Expo) bug-fix run on a monorepo:
- **Lens → agent fallback** (`sc-review`): review lens names are *roles*, not fixed agent types. If no
  dedicated reviewer exists (many envs have no `performance-reviewer`/`algorithm-reviewer`), spawn a
  `general-purpose`/`code-reviewer` with the lens's anti-patterns as focus — verify the type exists first,
  never abort on a missing agent. Scale fan-out to the host (sequential on constrained machines).
- **Device-only QA without an emulator** (`sc-qa`): for visual/native changes with no front↔back seam and
  no device available, automated QA = full-suite regression + integration checks + typecheck/bundle, then
  **emit a concrete on-device manual checklist** into the PR as a pre-merge gate. The checklist is the
  honest deferral — don't fake a visual pass or silently skip.
- **No UI/component test harness** (`sc-tdd`): when the stack can't unit-test rendered output (RN without a
  component lib), extract pure logic (formatters, selectors, time/geometry math, i18n) and write Red there;
  thin UI wiring is covered by the designer lens + the on-device checklist, not faked component tests.
- **Overlay commands run from repo root + gitignore run state** (README / example): use root-relative test
  commands (`cd apps/x && ./gradlew …`, `npm run test -w …`, `npx tsc --noEmit -p …`); add
  `.claude/.ship-cycle-state.json` to `.gitignore`.

## 0.2.2 — first-dogfood feedback

Improvements learned from the first real end-to-end run (a web dashboard feature):
- **Verify contracts, never assume** (`sc-design`): read the actual endpoint/entity/serialized response;
  an assumed API shape propagated to the implementer and caused a runtime crash. Now a hard rule.
- **Worktree is conditional** (`ship-cycle`/`sc-implement`): create it only for stack-split/parallel
  work; single-track changes use a plain feature branch (worktree was pure overhead otherwise).
- **Complexity exception to cheap-path-first** (`ship-cycle`): start complex work (novel algorithms,
  intricate SVG/canvas UI) at the higher tier instead of wasting a failed mid-tier attempt.
- **UI-only merges design+implement** (`sc-design`): don't force a separate READ-ONLY architecture doc
  for a widget; keep the critic/accessibility pass.
- **G9 E2E degrades honestly** (`sc-qa`): without a live backend + seeded auth session, degrade to
  contract-level seam verification and log the deferral — never fake a pass.

## 0.2.1 — review discipline (borrowed from Superpowers)

`sc-review` keeps its multi-lens/parallel structure and adds the output discipline from Superpowers'
`requesting-code-review` reviewer:
- **Plan alignment** as a cross-cutting check (does the impl satisfy the acceptance criteria — catch
  "built the wrong thing" at review, not final verify).
- **Production readiness** check for contract/schema/public-surface changes (backward compat, migration, docs).
- Per-lens **output discipline**: mandatory Strengths, actual-severity issues, and a clear merge
  **verdict (Yes/No/With-Fixes)**; no severity inflation; no verdict without reading the code.

## 0.2.0 — composable restructure

Refactored the single monolithic `ship-cycle` skill into an orchestrator + one skill per stage, and
adopted structural patterns from mature frameworks.

### Added
- **Composable stage skills**: `sc-brainstorm`, `sc-design`, `sc-tdd`, `sc-implement`, `sc-review`,
  `sc-qa`, `sc-ship` — each short and focused, usable à la carte. `ship-cycle` is now a thin
  orchestrator that chains them.
- **Dedicated brainstorming stage** (`sc-brainstorm`): refuse to code a vague goal; clarify + propose
  a design + get acceptance first.
- **Full git worktree isolation**: PREFLIGHT creates a feature worktree; `sc-implement` runs
  stack-split implementers in per-worktree isolation for collision-free parallelism.
- **Real state file** (`.claude/.ship-cycle-state.json`): tracks stage, per-gate status, and loop
  counts so "loop cap 3" and resume don't depend on the model's memory.
- **Tier → model bridge**: overlay `modelRouting.tierMap` maps tier names to real model ids; the skill
  passes `model=<resolved>` per `Task`.
- **Overlay JSON Schema** (`docs/ship-cycle.config.schema.json`) + defined precedence for overlapping
  globs (most-specific wins) and malformed-config behavior (stop, don't silent-fallback).

### Fixed
- Dead file references: bundled files are now addressed via `${CLAUDE_PLUGIN_ROOT}`.
- Honest runtime docs: states the specialized-subagent dependency and the stock-Claude-Code fallback.
- Corrected the trigger form to `/ship-cycle-devkit:ship-cycle`.

## 0.1.0 — initial

Portable gated dev-lifecycle plugin: single `ship-cycle` skill, engineering constitution, impl prompt
templates, project overlay, risk-based model routing. Borrowed Iron Laws + Red Flags and a discovery
gate from Superpowers.
