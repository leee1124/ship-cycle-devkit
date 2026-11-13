---
name: sc-review
description: Stage 5 of ship-cycle. Multi-lens parallel code review — security, quality, performance, algorithm (and designer on UI changes) plus a spec-blind adversarial "cold" lens (diff-only, assumes nothing the author claims) — as separate agents, each checking named anti-patterns and real-world state (legacy rows, N≥2, unsaved-id). Blocks the PR until zero Critical/High findings survive verification.
---

# sc-review — multi-lens code review (Stage 5)

On a design-only route (`state.route.kind = "design-only"`) there is no code and no PR: this stage is never
entered, G8 is `n/a: route — design-only route`, and the critic is the independent review
(`${CLAUDE_PLUGIN_ROOT}/docs/design-only-route.md`).

**No PR without a passing review (§core 1).** Run the **effective lenses** = `state.route.lenses` ∪ the
Tier S floor (security + one lens matched to the nature + cold on a non-trivial change) ∪ every
risk-matched lens (`state.risk`) ∪ the overlay `changeNature[].reviews` of every nature in the current
`state.nature` — a nature added mid-cycle brings its lenses (§ship-cycle — Route plan). With no route, drop
the first term. Run them as **separate agents in parallel** — each is blind to the others, so they catch
different failure modes. For a UI nature the `designer` lens joins the floor — its accessibility checklist
is an outcome, never dialed away by Tier S or a route (`${CLAUDE_PLUGIN_ROOT}/docs/visual-check.md`).

## Every review checks (cross-cutting, all lenses)
- **Plan alignment**: does the implementation actually satisfy the **acceptance criteria** from
  `sc-brainstorm` (in state)? Missing/extra scope, or a deviation, is a finding — catch "built the
  wrong thing" here, not at final verify. (A defect-only review misses a widget that was never built.)
- **Production readiness** (when the change touches contracts/schema/public surface): backward
  compatibility (does it break existing clients?), migration safety, and whether docs were updated.
- **Real-world state, not just the happy path**: does it still hold for **pre-existing / legacy rows**
  (data that predates this feature, with fields unset/null), the **empty case and the N≥2 / batch case**
  (off-by-one, ordering, dedup/merge, generated-key linking — a single-item test *passes and hides* these),
  the **unsaved / no-id-yet lifecycle** (client-side rows before their first persist), and **re-run /
  partial-save / idempotence**? The spec's edge coverage is not the world's — most shipped corruption lives
  in a state the canonical never enumerated. A green test on a hand-built fixture that skips these is false
  confidence: require the test to use the **real construction path**, not a favorable synthetic row.

## Lenses (each names its anti-patterns)
- **security**: authz/ownership bypass (IDOR), paywall/entitlement leak, injection (SQLi/XSS), secrets,
  unsafe deserialization, missing input validation. Include **secrets the code never logs itself**: an HTTP
  client that logs request URLs, headers or bodies will log whatever credential is carried there, so a
  token in a URL path or query string is written to the log by a dependency, at its default level, with
  nothing in the diff to show for it. This is a lens job precisely because the author cannot see it by
  reading their own change. **Detect** it by grepping the project's own log output for the *shape* of its
  secrets (a token prefix, a key pattern); **remediate** by moving the credential out of the URL where the
  API allows, and pinning client loggers that see URLs/headers above their chatty default.
- **quality**: logic defects, **anemic domain model** (business logic stranded in services, entities as
  getter/setter bags — constitution #7), **magic numbers/strings** (unnamed literals with domain meaning;
  a closed set not modeled as an enum / union / frozen object — #3), SOLID violations, dead code, silent
  `catch {}`.
- **performance**: N+1, unbounded queries / load-all-then-filter, missing indexes, needless re-render.
- **algorithm** (when logic is non-trivial): correctness of the core computation vs. the spec.
- **designer** (UI changes only): named anti-patterns, not a vibe check —
  - **hardcoded design values**: raw hex/px/font-size/shadow that bypass the token layer (must resolve
    from tokens — a stray literal is how theming/dark-mode silently breaks);
  - **reinvented pattern**: a bespoke empty/loading/error state, card, or button where a canonical
    component exists (N one-off copies *are* the fragmented surface); duplicate/near-duplicate labels;
  - **decorative-not-informative indicator**: a "progress" element that doesn't encode progress (a fixed
    spinner where a fill/ring belongs), or a chart that misreads (wrong axis, legend showing internal keys);
  - **off-scale**: type sizes/spacing not on the defined scale;
  - **accessibility floor** — the named checks in `${CLAUDE_PLUGIN_ROOT}/docs/visual-check.md`: touch
    target below the platform minimum, contrast below AA in any theme, missing screen-reader labels/roles
    (or no focus trap on modals), clipping at the largest font scale in `visualCheck.profiles`, and
    animation that ignores reduced motion;
  - **emoji-as-icon** where a vector icon system exists.
  When the overlay declares a `design` source of truth, check the change against it — did it reuse, or
  reinvent? (A backstop: sc-design ran the reuse check first.) The lens runs once, on the result the owner
  settled in the live visual loop, not per tweak. For a UI nature the a11y floor is an outcome, not ceremony:
  this lens (or at least its accessibility checklist) is never dropped — Tier S or route. With a
  `visualCheck.designTool`, run its `critique` / `detect` / `audit` read-only — never `init`, `document` or a
  hook install inside a cycle.
- **cold / spec-blind** (adversarial — always run one on a non-trivial change): this lens gets **only the
  diff** — NOT the design doc, canonical spec, or acceptance criteria — and is told to *assume nothing the
  author claims* and find what's wrong from first principles, hunting hardest in the real-world states above
  (legacy rows, N≥2, unsaved-id, re-run). It may read repo and dependency code and official docs to
  evidence its claims, but still not the spec, design doc or author narrative. Every other lens is anchored
  to the author's plan (right for
  "built the right thing"); this one exists because **an author's own reviewers inherit the author's blind
  spots** — a wrong assumption baked into the spec gets rated "as-designed" by every spec-anchored lens, and
  only a reviewer with **no stake in the framing** catches it. It is the in-pipeline stand-in for an outside
  reviewer; when a fresh external reviewer keeps finding what your fleet waved through, this is the missing
  lens. **Review focus, after the blind pass**: the list is never in the cold lens's blind-pass brief, and
  every blind pass is a fresh agent with no prior compare in its context. When `state.reviewFocus` holds
  entries, the cold lens's findings are frozen verbatim into the review artifact first; only then does it
  receive the list and report, per entry, whether it had raised it and whether the pinned test covers it
  (recorded as the entry's `cold`; findings it adds then are `postList: true`).
  Rule: `${CLAUDE_PLUGIN_ROOT}/docs/review-focus.md`. **What it cannot settle** from what it may read — an
  intent only the spec states, a behaviour spanning tasks, a fact only a running system shows — it returns as
  `unverifiable-from-diff[]` items (`{item, where, needs, whyNotChecked}`), not as findings: the bucket is
  how it says "I'd need X", not a licence to read the spec
  (`${CLAUDE_PLUGIN_ROOT}/docs/unverifiable-from-diff.md`). Its items are frozen with its findings, before
  the review-focus list is sent; items it adds after are `postList: true`.

## Running the lenses (agent mapping + fallback)
Lens names are **roles, not fixed agent types**. Map each to whatever your environment provides, and
**verify the agent type exists before spawning** — and treat a lens that errored, was never spawned, or
returned nothing as **undetermined, not clean**: zero findings counts toward G8 only from a lens that
actually ran, or a crashed lens silently reads as a pass on the gate that blocks the PR (§core 2).
 If no dedicated reviewer exists for a lens (many setups
have no `performance-reviewer`/`algorithm-reviewer`), spawn a `general-purpose` (or `code-reviewer`) agent
with that lens's anti-patterns pasted in as the focus — **never skip the lens or abort on a missing agent
type**. Lenses are read-only, so fan out in parallel; any heavy job a lens launches (a full suite, a
build) runs under overlay `env.heavyLock` per `${CLAUDE_PLUGIN_ROOT}/docs/heavy-work.md`, and the lens
prompt carries that rule. No `heavyLock` on a small host: run heavy-launching lenses sequentially. A lens
whose lock wait times out is **not run** (like a killed lens), never a pass.
This parallel default yields to the host: once it has **killed a background job for memory**, run the
remaining lenses **sequentially**, and **never auto-relaunch a job the host killed** — report it and let the
user decide, since the pressure that killed it has not gone away. A killed lens counts as **not run**: G8
is not met until it has run to completion or the user has explicitly waived it.

**Pin the model on every lens spawn — mechanically, not from memory (§core 6).** Because lenses are
`general-purpose` spawns, the review tier lives only in `model=`, and it must be re-applied on *every* spawn.
One omission silently downgrades a top-tier review to the agent type's cheap default — the exact trap
§core 6 names, and the easiest to hit across a long run where you spawn lenses dozens of times. Defenses, in
order of strength:
- **Resolve once, copy every time.** The tier→model is already resolved into `state.models.review` at
  PREFLIGHT. Read that value and pass `model = state.models.review` on each lens `Task` call — never type a
  model name from memory, never rely on the agent type's default.
- **Anti-drift check.** Before fanning out, restate the resolved review model (e.g. "review lenses →
  opus") in one line; if any lens call omits `model=`, that restatement makes the omission visible instead
  of silent.
- **Optional: pinned lens agent definitions.** If your environment supports custom agent types, defining
  real lens agents (`sc-cold-reviewer`, `sc-security-reviewer`, …) with the model **baked into the
  definition** removes the per-spawn discipline entirely. Ship these as *optional* — they must **degrade
  gracefully** to `general-purpose` + explicit `model=` on hosts (stock Claude Code) that don't provide
  custom agent types, so portability isn't traded for enforcement.

## External / foreign-agent review — async (overlay-declared, opt-in)
The cold lens is the **in-pipeline stand-in** for an outside reviewer; it is still a same-session,
same-model-family subagent that returns synchronously. The real thing is a **different agent or model
entirely**, run out of process, taking tens of minutes, exposing progress only through a status file or
command you have to poll. None of that was modelable here — no async job, no foreign reviewer, no
completion signal — so operators hand-rolled polling waiters and tracked job ids in a scratchpad: exactly
the hand-tracked state the per-cycle state file exists to eliminate.

A nature's `reviews` entry of the form **`external:<name>`**, where `<name>` is declared in overlay
**`externalReviewers`**, adds that reviewer in **async mode**. The prefix is what keeps the core invariant
mechanical: an external reviewer **can never occupy a built-in lens's slot**, so declaring one called
`cold` cannot silently retire the in-session cold lens. The overlay supplies the commands (`launch`,
`status`, `fetch`, optional `notify` and `cancel`) because the kit stays docs-only and **never hard-codes a
vendor**. Absent the declaration every lens is in-session, as before. G8's async shape is *freeze →
snapshot → release → write-ahead → launch → poll → judge on completion*, not "spawn subagent, await
return":

1. **Freeze first, then snapshot.** Set `state.gitFreeze`
   `{ active: true, branch, since, reason: "<lens> snapshot", releaseOn: "snapshot" }` **before** capturing,
   then capture an **immutable** view of what the reviewer must read:
   `git diff <base>...<head> > <snapshot>`, a bundle/archive, or a detached worktree pinned to the head
   commit. The capture is the window that needs
   protecting: a concurrent `checkout`/`branch -f` *during* it doesn't hang anything — it silently produces
   a diff against the wrong base, which is worse, because a corrupted review input reads exactly like a
   clean one. Write the snapshot **and** the eventual `resultPath` to an artifact dir **outside the
   worktree**, the same rule the cost readout follows and for the same reason (§sc-ship G13): G12
   `git clean`s untracked files and G13 removes the worktree and this cycle's state file, so anything
   inside is gone before the PR merges — and a deferral whose evidence was deleted is a claim, not a record.
2. **Release the freeze as soon as the snapshot exists — explicitly, recording `releasedAt` and `releasedBy: "self"` — before you
   launch.** The reviewer then reads something nobody will touch and the branch is free for the whole
   review. Prefer this always: it is the difference between "this branch is locked for forty minutes" and
   "this branch is locked while a diff is written".
3. **Write ahead, then launch.** Append `{ id: null, agent, lens, status: "launching", startedAt, snapshot,
   resultPath }` to `state.reviewJobs` **before** running the launch command, then fill in the `id` it
   prints. A job that is running but unrecorded is invisible to `/status`, to `/resume` and to the freeze
   rule — and the window where that is true is precisely between the launch and the write, so close it by
   writing first. A `launching` entry `/resume` finds with no id is an **orphan**: try the reviewer's
   `status`/list command, and if it cannot be identified record `failed` with that reason rather than
   leaving it.
4. **Poll on the reviewer's cadence; don't stall the pipeline.** The in-session lenses run **in parallel
   with** the external job. The foreign reviewer is an *additional* lens, **never a replacement**: G8 still
   requires the full in-session set, cold lens included.
5. **Judge it like any other lens.** Fetch the result and apply the same severity discipline, refutation
   pass and **triage rubric** (§Triage) — an external finding is a finding. Then set the job's `status` to
   `complete` with an `endedAt`, and record where its output landed.

**Completion is surfaced, not remembered.** `/status` prints every `state.reviewJobs` entry with its status
and age; a reviewer may declare an optional `notify` command the poll loop runs on the transition to a
terminal state. No vendor lock-in either way — the `/status` line suffices on its own.

### Git-write freeze while a reader is on the live tree (fail-closed)
An out-of-process reviewer reads your branch or worktree from **outside this session**. A `git commit`,
`branch -f`, `checkout`, `rebase` or worktree removal **while it reads** can hang the reader indefinitely —
a ~1-hour hang has been observed in the field, with no error and no progress.

- **Snapshot mode (the default) holds the freeze only across the capture**, per steps 1–2. Release it the
  moment the snapshot exists and record `releasedAt`; an `active` freeze whose `releaseOn` is `snapshot`
  once that snapshot exists is a **stale freeze**, not a live one.
- **Without a snapshot** — a reviewer that insists on the live tree (`snapshot: false`) — the freeze holds
  until the job reaches a terminal status, and every stage that touches the tree or the branch
  (`sc-implement`'s **edits** and worktree moves, `sc-ship`'s commit/push and **G13 teardown**, PREFLIGHT's
  leftover-worktree recovery) **must check `state.gitFreeze.active` first and wait**. Not "just this one
  commit": the hang is caused by exactly one badly-timed write.
- **Never delete a worktree recorded as a `reviewJobs[].snapshot`.** A detached snapshot worktree is not
  this cycle's feature worktree and is not yours to prune — and `git worktree prune` is repo-scoped, so it
  reaches other cycles' snapshots too.
- This is an **operational floor, not dialable ceremony** (§ship-cycle → Tier S path → the bright line). It
  is not reduced on Tier S, and a frozen branch is never a licence to skip the write — it is an instruction
  to **wait, or to snapshot and release**.

### When the external job never lands
Overlay `maxWaitMinutes` bounds the wait. A job that exceeds it, errors, or returns nothing is recorded
`status: "timeout"` / `"failed"` **with its id, an `endedAt`, and the evidence** — never silently dropped:
- **A terminal status is a claim that needs evidence, exactly like a baseline quarantine.** `timeout`
  requires `endedAt` with `endedAt − startedAt ≥ maxWaitMinutes`; `failed` requires the reviewer's **own**
  error output recorded at `resultPath`. **A `timeout` recorded minutes after `startedAt` is not a timeout,
  it is a skipped review** — a finding, not a deferral. The wait *is* the whole cost of this lens, and the
  party that benefits from declaring it over is the one certifying it; the elapsed time is the one piece of
  evidence that costs what the review costs.
- **The in-session lenses still gate G8.** The external reviewer was always an addition; its absence never
  lowers "0 Critical/High after verification" and never excuses skipping the cold lens.
- **The absence is named, with its elapsed wait.** A declared external review that did not complete is a
  **deferral**: record it and carry it to the **pre-merge manual gate** (§sc-ship G12) with
  `startedAt → endedAt`, exactly as an unrunnable-here suite or a `gates.G7b: checklist` item is carried, so
  a review that was never actually waited for is visible as such. "The external reviewer timed out" must
  never become the standard way to ship without one, and what stops that is making both its absence **and
  its duration** visible on the PR.
- **A job whose subject is about to change is superseded, not waited out.** When G8 routes back to
  `sc-implement` on in-session findings, the in-flight external job is reviewing a diff that will not
  survive. Record `status: "superseded"` with `endedAt` and the reason, run the reviewer's optional
  `cancel` command if it declares one, **release the freeze**, and re-launch against the fixed head when
  review resumes. A superseded job is **not** a deferral and does not go on the manual gate — it was
  replaced, not skipped. Waiting out `maxWaitMinutes` on a diff you are already rewriting is never right.
- Re-launching counts against G8's loop cap like any other re-review, and **releases the freeze first**.

## Output & severity discipline (each lens)
Every lens returns, in this shape:
- **Strengths** — specific, with file refs. Mandatory: it forces real code comprehension and calibrates
  severity (a problems-only reviewer inflates). "Solid" is a valid finding.
- **Issues** — by **actual** severity (Critical/High/Medium/Low), with file:line, *why it matters*, and a
  fix. Don't mark nitpicks as Critical; don't bury a Critical as a nit.
- **Claim evidence** — a load-bearing factual claim behind a finding (a library internal, code outside the
  diff, an API contract) cites its evidence (`${CLAUDE_PLUGIN_ROOT}/docs/claim-evidence.md`). A missing
  citation is never by itself grounds to lower severity: the finding is held at its claimed severity until
  the refuter evidences or refutes it, and stays undetermined (blocking G8) if neither;
  it then exits as fix-or-explicit-owner-decision in the review artifact.
- **Data-integrity floor**: a change that can persist **wrong / duplicate / lost / orphaned** data is at
  least **High** — even if it *matches the spec* or *replicates a legacy/upstream quirk*. "The old system
  did it too" is a parity note, **not** a severity downgrade; surface it as fix-or-explicit-owner-decision,
  never a silent Low. This is the exact trap where real corruption gets waved through as "as-designed /
  faithful" — and the one an outside reviewer reliably re-flags.
- **Design-consistency floor**: a change that **reinvents an existing token/component/pattern** (a new
  bespoke empty state, an inlined color, a hand-rolled spinner) is at least a **finding**, even when it
  "looks fine" in isolation — the cost is cumulative fragmentation, paid invisibly one diff at a time.
  Surface it as **reuse-or-justify**, never a silent pass. This is the review-side backstop for
  sc-design's reuse-before-create gate.
- **Unverifiable from diff** (blind readers only — the G8 cold lens, the delta pass and the wave check's two
  passes) — the third bucket, `{item, where, needs, whyNotChecked}` each: no severity, never a finding until a
  disposition confirms it (§Triage). `whyNotChecked` is `spec-only`, `spans-tasks` or `needs-running-system` —
  never "unchanged code": a doubt that reading the repo would settle is read and raised or dropped, not parked
  here.
- **Verdict** — a clear merge call: **Yes / No / With-Fixes**, plus 1–2 sentences of reasoning.
- No verdict without having actually read the code.

## Verify findings (avoid false positives)
For each Critical/High, spawn an independent check that tries to **refute** it (does the code path
actually reach the bug? is it already mitigated elsewhere?) and opens the cited evidence for the claims the
finding rests on. A refutation is itself a load-bearing claim: it must cite its evidence, or the finding stays
undetermined at its claimed severity. Keep only findings that survive. Scale the
count of refuters to the size tier (§ship-cycle Stage 0.2 — Change-size tier): Tier S runs no verification
fleet — but **never to zero on a surviving Critical/High**, which always gets at least one refuter.

## Triage — fix here, or file and link (§core 5)
§core 5 fixes the *disposition* of an out-of-scope defect ("found, filed, not fixed here"); it does not
make the actually-hard call: of the findings that survived verification, **which belong to this change?**
Without a rubric this fails in one of two directions every time — scope balloons because everything gets
fixed, or findings get quietly under-filed because nothing does.

**Three questions. Any "yes" → fix it here. All "no" → file it and link it.**
1. Is the finding **reachable through the lines this diff touched**? (A "no" on this or Q2 for a
   Critical/High needs a `path:line` — an uncited "no" is a load-bearing claim without evidence.)
2. Does **this change make it worse** — introduce it, or amplify an existing instance?
3. Is it a **precondition for an acceptance criterion** of this change (§sc-brainstorm, in state)? On a
   Tier S run, where brainstorm collapsed to a one-liner, read the criteria from `state.goal`; if none were
   stated the answer is **no** — an absent criterion is never a yes.

Everything else is filed to the tracker with a **one-line rationale** and referenced from the PR body as
`Refs #NN` (sc-ship asserts the token). "File it" is a real outcome, not a soft skip: an unfiled finding
is a dropped one, which §core 5 rules out as firmly as fixing it here.

**Triage runs at `high` effort on every tier** (§`${CLAUDE_PLUGIN_ROOT}/docs/model-routing.md` — Effort). It is judgment-dense
work that wears no impressive artifact, so it is the first thing a right-sizing pass reaches for — and
misjudging it is how a review either balloons the branch or loses a real defect. Record each finding's
disposition (fixed-here / filed-as `#NN`) in the review artifact so G8 and sc-ship can both read it.

**Implementer concerns are items to verify.** A `DONE_WITH_CONCERNS` concern that sc-implement recorded as
not correctness/scope (§sc-implement — Route the implementer's status) is listed in the review brief — the
lenses' brief, not the cold lens's, which stays spec-blind — as an item to verify. Each gets a disposition
(fixed-here / filed-as `#NN`) in the review artifact like any finding.

**Wave-check items are items to verify, too.** Every `unresolved` entry of `state.waveReviews`
(§`${CLAUDE_PLUGIN_ROOT}/docs/wave-check.md`) goes into the same lenses' brief by the same mechanism — not
the cold lens's — and gets a disposition (fixed-here / filed-as `#NN`). Each `refutedItems` entry is listed
too, as "previously flagged, refuted at wave N — confirm": a refutation from a tier cheaper than G8's
never drops a Critical/High, which also stays unresolved for G8. A wave check that found nothing,
or was skipped by the route, reduces no lens: G8 runs the full fleet either way.

**Unverifiable-from-diff items are dispositioned before G8.** Every `state.unverifiable` item — from the
cold lens, the delta pass or a wave check (§`${CLAUDE_PLUGIN_ROOT}/docs/unverifiable-from-diff.md`) — is
settled with evidence after the lenses ran: by this triage at `high` effort, or by a scoped pass of a
spec-anchored lens on the same model and effort as that lens at G8 (the review-focus Verify rule).
The outcome is recorded in the item's `disposition` and the review artifact: `confirmed → finding #<n>` (a
finding with a severity — refuter, floors and triage as usual), `cleared: <cited reason>`, or, when neither
can be evidenced, `owner-decision: <the owner's words>` — only with `state.route.ownerPresent === true` and
the owner's answer verbatim as a human user turn, after stating whether the item falls under the
data-integrity or security floor (if so, "treated as High until shown otherwise"); no owner fails closed (a
floor item blocks G8, any other goes on the pre-merge manual gate as `manual-gate`). An item whose `needs`
the reader could have read from the repo is a lens miss: `confirmed`, `parked: true`. Passes ride on
`loops[G8]`. Never silently dropped, never auto-promoted; no
disposition goes back into the cold lens's context.

**Review-focus items are verified after the compare.** Every `state.reviewFocus` entry whose `cold` reads
`raised: false` or `pinHolds: false` (§`${CLAUDE_PLUGIN_ROOT}/docs/review-focus.md`) surfaces after the
parallel lenses ran, so it never waits for their brief: a scoped second pass of a spec-anchored lens
(quality or algorithm, on the same model and effort that lens ran with at G8 — risk upgrade included,
§Model routing) on just these items, or this triage at `high` effort, verifies each and records who did,
with `verify.evidence` it opened itself, in the entry's `verify`. Outcomes sit in the review artifact
beside the other dispositions: `covered: <pinnedBy>` (the pin holds and drives the input — verified, not
fixed-here, never sent to the delta pass), or, for a pin that does not hold — a finding — fixed-here /
filed-as `#NN`; a fixed pin is shown failing against the pre-change tree (`verify.pinFixedBy`).

## Re-review after fixes — the delta pass
An edit after the first review — including a live-visual-loop tweak during a re-show, G9 or G11 — comes here:
delta re-review, then G5–G7, counted against the loop cap (`${CLAUDE_PLUGIN_ROOT}/docs/visual-check.md`).
A re-review of fixes for findings you already have is **not a second full review**. Re-running every lens
over the whole branch re-pays the first review's cost to re-read code nobody changed, and it is where most
of a cycle's review spend goes once the first pass has landed. Scope it to what moved:

- **Input:** the fix diff — `git diff <sha the last review read>..HEAD` — plus the prior findings list.
  Record HEAD's sha in the review artifact when a review starts, so the delta is mechanical rather than
  remembered. If history was rewritten since (rebase, amend) and that sha is no longer an ancestor of
  HEAD, the delta cannot be trusted: run a full re-review.
- **The prior findings are input to check, not a spec.** Do not hand the delta reviewer the design doc,
  the acceptance criteria or the author's account of the fix — that keeps it a cold lens. "Diff-only"
  means no spec and no author narrative, not no repository: when a finding's defect sits outside the changed
  hunks, the reviewer reads the surrounding code to judge whether it is resolved.
- **Two questions, one lens:** (1) is each prior Critical/High, and each finding dispositioned
  *fixed here* (§Triage), **actually resolved** by the fix, not just touched? (Findings *filed as #NN*
  have nothing to verify here.) (2) did the fix **introduce a regression** in the lines it changed or the paths it reaches?
  What it cannot settle from the fix diff it returns as unverifiable-from-diff items (`source: "delta"`),
  dispositioned before G8 is re-judged (§Triage).
  Run it as the **cold lens** (diff-only, assumes nothing) — fixes are written by the author who missed the
  original defect, so the independent view matters more here, not less.
- **Review-focus items reach it as code locations only** — the `path:line` of the pin or the fix, never
  an entry's `input` or `expected` text (§`${CLAUDE_PLUGIN_ROOT}/docs/review-focus.md`); a `covered` entry
  does not reach it at all. For these the delta pass checks only whether the pin or fix introduced a
  regression; resolution is proven by `verify.pinFixEvidence` and the pin's passing run at G11.
- **Same tier, same model pin** as the review it follows (§Model routing). The delta pass is narrower, not
  cheaper in judgment.
- **Escalate to a full re-review** instead when the fix: reaches files or modules the first review never
  read; changes a contract, schema or persisted shape; or answers a **design flaw** (that loops to
  `sc-design`, and the redesigned change gets a fresh review).
- **The risk floor still holds.** If the fix diff touches an area `state.risk` flagged (auth, payment,
  persisted data, a public contract), also run that area's lens — the security lens above all — on the fix
  diff. The delta pass narrows scope; it never dials away a lens the Tier S path forbids dialing away.
- **External/async reviews (§above):** a relaunched external review of a fix follows the same scope — give
  it the fix diff and the prior findings, not the whole branch — unless an escalation condition applies.
- A delta pass counts against G8's loop cap like any re-review. Its findings get dispositions (§Triage)
  exactly like the first pass's.

## Gate G8 (to advance to `sc-qa`)
- **0 Critical/High** after verification. Address survivors in `sc-implement`, then re-review — a
  delta pass (§Re-review after fixes) unless an escalation condition calls for a full re-review.
- **No `state.reviewJobs` entry is still `running` or `launching`**, and `state.gitFreeze` is released. An
  in-flight job means the gate has not been judged yet — wait for it, cancel it as `superseded`, or record
  its terminal status; never set G8 while a review you launched is still reading. A `timeout`/`failed` job
  does not block G8 (the in-session lenses carry it) but **must** be on the pre-merge manual gate with its
  elapsed wait; a `superseded` one goes on neither, because it was replaced rather than skipped.
- **Every finding carries a recorded disposition** — *fixed here* or *filed as `#NN`* (§Triage). A findings
  list with no dispositions does not pass; sc-ship re-asserts this at G12, and an assertion that quantifies
  only over the findings *marked* filed would pass vacuously on an artifact that was never triaged.
- **Every implementer concern handed to review has a disposition** — the `DONE_WITH_CONCERNS` items from
  `state.telemetry.implStatus` that skipped the fix round (§Triage); one without a disposition fails G8.
  The same holds for every unresolved wave-check item in `state.waveReviews` (§Triage).
- **Every `state.unverifiable` item has a `disposition`** — confirmed (and then a finding like any other),
  cleared with a cited reason, an owner decision from an owner present, or (non-floor, no owner)
  `manual-gate` (§Triage); one without fails G8, and a floor item with no owner answer keeps G8 blocked.
- **Every missed or uncovered `state.reviewFocus` entry has a `verify` outcome** (§Triage) — and a
  fixed-here one its `pinFixedBy` with failing-first evidence; when the cold lens ran on a non-empty list,
  every entry has its `cold` record, taken after the frozen blind pass.
- If a finding is a **design flaw** (not an impl bug), loop back to `sc-design`, not `sc-implement`.
- **UI nature**: the designer lens ran (a11y floor — never dropped), and the cold lens hunted
  losing-variant leftovers in the diff **without being handed** `state.visualCheck[<nature>].cleanup` — no
  variant label, no file only a losing prototype used; when no cold lens runs, the designer lens does it.
- Set `gates.G8 = pass` (or `fail` on a loop-back), `state.gateTrees.G8` (the reviewed tree identity,
  §`${CLAUDE_PLUGIN_ROOT}/docs/state-file.md` — Tree identity) and loop count in state (respect the
  orchestrator's loop cap).

## Model routing
security/quality/algorithm review run at the **high** tier; upgrade the matching lens to **top** for
high-risk changes (auth/payment → security; complex algorithm → algorithm). style/designer may run lower.

**Effort scales with the size tier, it is not pinned at the top** (§ship-cycle Model routing → Effort):
`xhigh` for the final adversarial lens on **Tier L only**, `high` on Tier M, `medium` on Tier S. A blanket
"reviews always run at maximum" is precisely what makes a corroborated one-line fix cost a six-figure-token
review. The two exceptions that never scale down: **triage** (above) and the security lens's fail-closed
model pin.

**Pass `model = state.models['review']` and `effort = state.effort['review']` on every lens agent** (both
resolved at PREFLIGHT) — this is the
stage the default-model trap bit in practice: spawning a `quality-reviewer`/`security-reviewer` without
`model=` runs the review on that type's cheaper default instead of the intended high/top tier, silently.
Never rely on the agent-type default (§core 6).

**Security-refusing-model guard.** If PREFLIGHT set `models["review.security"]` (overlay
`modelRouting.securityReviewModel` — §ship-cycle Stage 0.7), spawn the **`security` and `authz` lenses with
that model**, not `models['review']`. Some models refuse security analysis and a review routed to one
silently no-ops; this pin guarantees the security lens runs on a model that will actually do it.

**Telemetry**: when you set `gates.G8` in state, append this stage's row to
`state.telemetry.stages['review']` — the resolved tier, model and effort, plus whatever usage the host
actually exposed (tokens/cost/wall-clock) and `null` for what it didn't. **Never estimate a figure.** The
run's cost readout is assembled from these rows at G13 (§`${CLAUDE_PLUGIN_ROOT}/docs/model-routing.md` — Cost readout); a stage that writes no
row is simply absent from it, so the readout under-reports rather than lying.
