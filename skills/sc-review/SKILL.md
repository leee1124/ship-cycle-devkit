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
  getter/setter bags — constitution #7), SOLID violations, dead code, silent `catch {}`.
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
actually reach the bug? is it already mitigated elsewhere?). Keep only findings that survive.

## Gate G8 (to advance to `sc-qa`)
- **0 Critical/High** after verification. Address survivors in `sc-implement`, then re-review.
- If a finding is a **design flaw** (not an impl bug), loop back to `sc-design`, not `sc-implement`.
- Set `gates.G8` and loop count in state (cap 3).

## Model routing
security/quality/algorithm review run at the **high** tier; upgrade the matching lens to **top** for
high-risk changes (auth/payment → security; complex algorithm → algorithm). style/designer may run lower.

**Pass `model = state.models['review']` on every lens agent** (resolved at PREFLIGHT) — this is the
stage the default-model trap bit in practice: spawning a `quality-reviewer`/`security-reviewer` without
`model=` runs the review on that type's cheaper default instead of the intended high/top tier, silently.
Never rely on the agent-type default (Iron Law 6).
