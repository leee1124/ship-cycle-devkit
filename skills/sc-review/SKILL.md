---
name: sc-review
description: Stage 5 of ship-cycle. Multi-lens parallel code review — security, quality, performance, algorithm (and designer on UI changes) plus a spec-blind adversarial "cold" lens (diff-only, assumes nothing the author claims) — as separate agents, each checking named anti-patterns and real-world state (legacy rows, N≥2, unsaved-id). Blocks the PR until zero Critical/High findings survive verification.
---

# sc-review — multi-lens code review (Stage 5)

**Iron Law #3: no PR without a passing review.** Run the lenses (from overlay `changeNature[].reviews`)
as **separate agents in parallel** — each is blind to the others, so they catch different failure modes.

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
  unsafe deserialization, missing input validation.
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
  - **accessibility floor**: touch target below the platform minimum, missing labels, contrast below AA,
    no focus management/trap on modals;
  - **emoji-as-icon** where a vector icon system exists.
  When the overlay declares a `design` source of truth, check the change against it — did it reuse, or
  reinvent?
- **cold / spec-blind** (adversarial — always run one on a non-trivial change): this lens gets **only the
  diff** — NOT the design doc, canonical spec, or acceptance criteria — and is told to *assume nothing the
  author claims* and find what's wrong from first principles, hunting hardest in the real-world states above
  (legacy rows, N≥2, unsaved-id, re-run). Every other lens is anchored to the author's plan (right for
  "built the right thing"); this one exists because **an author's own reviewers inherit the author's blind
  spots** — a wrong assumption baked into the spec gets rated "as-designed" by every spec-anchored lens, and
  only a reviewer with **no stake in the framing** catches it. It is the in-pipeline stand-in for an outside
  reviewer; when a fresh external reviewer keeps finding what your fleet waved through, this is the missing
  lens.

## Running the lenses (agent mapping + fallback)
Lens names are **roles, not fixed agent types**. Map each to whatever your environment provides, and
**verify the agent type exists before spawning**. If no dedicated reviewer exists for a lens (many setups
have no `performance-reviewer`/`algorithm-reviewer`), spawn a `general-purpose` (or `code-reviewer`) agent
with that lens's anti-patterns pasted in as the focus — **never skip the lens or abort on a missing agent
type**. Scale fan-out to the host: parallel by default, but on a resource-constrained machine run the
lenses in smaller batches (or sequentially) rather than all at once.

**Pin the model on every lens spawn — mechanically, not from memory (Iron Law 6).** Because lenses are
`general-purpose` spawns, the review tier lives only in `model=`, and it must be re-applied on *every* spawn.
One omission silently downgrades a top-tier review to the agent type's cheap default — the exact trap Iron
Law 6 names, and the easiest to hit across a long run where you spawn lenses dozens of times. Defenses, in
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

A nature's `reviews` entry naming a reviewer declared in overlay **`externalReviewers`** runs in **async
mode**. The overlay supplies the commands (`launch`, `status`, `fetch`, optional `notify`) because the kit
stays docs-only and **never hard-codes a vendor**. Absent the declaration every lens is in-session, as
before. G8's async shape is *snapshot → launch → record → the cycle may suspend and resume → judge on
completion*, not "spawn subagent, await return":

1. **Snapshot first — this is what makes the freeze cheap.** Before launching, capture an **immutable**
   view of what the reviewer must read: `git diff <base>...<head> > <snapshot>`, a bundle/archive, or a
   detached worktree pinned to the head commit. Hand the reviewer **the snapshot, not the live branch**. It
   converts an unbounded freeze into a seconds-long one — the difference between "this branch is locked for
   forty minutes" and "this branch is locked while a diff is written".
2. **Record the job before anything else.** Append to `state.reviewJobs`:
   `{ id, agent, lens, status: "running", startedAt, snapshot, resultPath }`. A job that is running but
   unrecorded is invisible to `/status`, to `/resume` and to the freeze rule below — recording it is what
   lets it survive a suspended cycle instead of living in your head.
3. **Poll on the reviewer's cadence; don't stall the pipeline.** The in-session lenses run **in parallel
   with** the external job. The foreign reviewer is an *additional* lens, **never a replacement**: G8 still
   requires the full in-session set, cold lens included.
4. **Judge it like any other lens.** Fetch the result and apply the same severity discipline, refutation
   pass and **triage rubric** (§Triage) — an external finding is a finding. Then set the job's `status` to
   `complete` and record where its output landed.

**Completion is surfaced, not remembered.** `/status` prints every `state.reviewJobs` entry with its status
and age; a reviewer may declare an optional `notify` command the poll loop runs on the transition to a
terminal state. No vendor lock-in either way — the `/status` line suffices on its own.

### Git-write freeze while a job is in flight (fail-closed)
An out-of-process reviewer reads your branch or worktree from **outside this session**. A `git commit`,
`branch -f`, `checkout`, `rebase` or worktree removal **while it reads** can hang the reader indefinitely —
a ~1-hour hang has been observed in the field, with no error and no progress.

- **Set `state.gitFreeze` the moment a job launches** —
  `{ active: true, branch, since, reason: "<job id> reading", releaseOn: "snapshot" | "job-complete" }` —
  and **release it explicitly**, recording when.
- **With a snapshot (the default) the freeze releases the instant the snapshot is written**: the reviewer
  is reading a file nobody will touch and the branch is free again. Prefer this always.
- **Without a snapshot** — a reviewer that insists on the live tree — the freeze holds until the job
  reaches a terminal status, and every stage that writes git (`sc-implement`'s edits and worktree moves,
  `sc-ship`'s commit/push and worktree teardown) **must check `state.gitFreeze.active` first and wait**.
  Not "just this one commit": the hang is caused by exactly one badly-timed write.
- This is an **operational floor, not dialable ceremony** (§ship-cycle → Tier S path → the bright line). It
  is not reduced on Tier S, and a frozen branch is never a licence to skip the write — it is an instruction
  to **wait, or to snapshot and release**.

### When the external job never lands
Overlay `maxWaitMinutes` bounds the wait. A job that exceeds it, errors, or returns nothing is recorded
`status: "timeout"` / `"failed"` **with its id** — never silently dropped:
- **The in-session lenses still gate G8.** The external reviewer was always an addition; its absence never
  lowers "0 Critical/High after verification" and never excuses skipping the cold lens.
- **The absence is named.** A declared external review that did not complete is a **deferral**: record it
  and carry it to the **pre-merge manual gate** (§sc-ship G12), exactly as an unrunnable-here suite or a
  `gates.G7b: checklist` item is carried. "The external reviewer timed out" must never become the standard
  way to ship without one, and what stops that is making its absence visible **on the PR**.
- Re-launching counts against G8's loop cap like any other re-review, and **releases the freeze first**.

## Output & severity discipline (each lens)
Every lens returns, in this shape:
- **Strengths** — specific, with file refs. Mandatory: it forces real code comprehension and calibrates
  severity (a problems-only reviewer inflates). "Solid" is a valid finding.
- **Issues** — by **actual** severity (Critical/High/Medium/Low), with file:line, *why it matters*, and a
  fix. Don't mark nitpicks as Critical; don't bury a Critical as a nit.
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
- **Verdict** — a clear merge call: **Yes / No / With-Fixes**, plus 1–2 sentences of reasoning.
- No verdict without having actually read the code.

## Verify findings (avoid false positives)
For each Critical/High, spawn an independent check that tries to **refute** it (does the code path
actually reach the bug? is it already mitigated elsewhere?). Keep only findings that survive. Scale the
count of refuters to the size tier (§ship-cycle Stage 0.2 — Change-size tier): Tier S runs no verification
fleet — but **never to zero on a surviving Critical/High**, which always gets at least one refuter.

## Triage — fix here, or file and link (Iron Law 5)
Iron Law 5 fixes the *disposition* of an out-of-scope defect ("found, filed, not fixed here"); it does not
make the actually-hard call: of the findings that survived verification, **which belong to this change?**
Without a rubric this fails in one of two directions every time — scope balloons because everything gets
fixed, or findings get quietly under-filed because nothing does.

**Three questions. Any "yes" → fix it here. All "no" → file it and link it.**
1. Is the finding **reachable through the lines this diff touched**?
2. Does **this change make it worse** — introduce it, or amplify an existing instance?
3. Is it a **precondition for an acceptance criterion** of this change (§sc-brainstorm, in state)? On a
   Tier S run, where brainstorm collapsed to a one-liner, read the criteria from `state.goal`; if none were
   stated the answer is **no** — an absent criterion is never a yes.

Everything else is filed to the tracker with a **one-line rationale** and referenced from the PR body as
`Refs #NN` (sc-ship asserts the token). "File it" is a real outcome, not a soft skip: an unfiled finding
is a dropped one, and Iron Law 5 forbids that as firmly as it forbids fixing it here.

**Triage runs at `high` effort on every tier** (§ship-cycle Model routing → Effort). It is judgment-dense
work that wears no impressive artifact, so it is the first thing a right-sizing pass reaches for — and
misjudging it is how a review either balloons the branch or loses a real defect. Record each finding's
disposition (fixed-here / filed-as `#NN`) in the review artifact so G8 and sc-ship can both read it.

## Gate G8 (to advance to `sc-qa`)
- **0 Critical/High** after verification. Address survivors in `sc-implement`, then re-review.
- **No `state.reviewJobs` entry is still `running`**, and `state.gitFreeze` is released. A job still in
  flight means the gate has not been judged yet — wait for it or record its terminal status; never set G8
  while a review you launched is still reading. A `timeout`/`failed` job does not block G8 (the in-session
  lenses carry it) but **must** be on the pre-merge manual gate.
- **Every finding carries a recorded disposition** — *fixed here* or *filed as `#NN`* (§Triage). A findings
  list with no dispositions does not pass; sc-ship re-asserts this at G12, and an assertion that quantifies
  only over the findings *marked* filed would pass vacuously on an artifact that was never triaged.
- If a finding is a **design flaw** (not an impl bug), loop back to `sc-design`, not `sc-implement`.
- Set `gates.G8` and loop count in state (respect the orchestrator's loop cap).

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
Never rely on the agent-type default (Iron Law 6).

**Security-refusing-model guard.** If PREFLIGHT set `models["review.security"]` (overlay
`modelRouting.securityReviewModel` — §ship-cycle Stage 0.7), spawn the **`security` and `authz` lenses with
that model**, not `models['review']`. Some models refuse security analysis and a review routed to one
silently no-ops; this pin guarantees the security lens runs on a model that will actually do it.

**Telemetry**: when you set `gates.G8` in state, append this stage's row to
`state.telemetry.stages['review']` — the resolved tier, model and effort, plus whatever usage the host
actually exposed (tokens/cost/wall-clock) and `null` for what it didn't. **Never estimate a figure.** The
run's cost readout is assembled from these rows at G13 (§ship-cycle — Cost readout); a stage that writes no
row is simply absent from it, so the readout under-reports rather than lying.
