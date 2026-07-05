---
name: sc-review
description: Stage 5 of ship-cycle. Multi-lens parallel code review — security, quality, performance, algorithm (and designer on UI changes) as separate agents, each checking named anti-patterns. Blocks the PR until zero Critical/High findings survive verification.
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

## Lenses (each names its anti-patterns)
- **security**: authz/ownership bypass (IDOR), paywall/entitlement leak, injection (SQLi/XSS), secrets,
  unsafe deserialization, missing input validation.
- **quality**: logic defects, **anemic domain model** (business logic stranded in services, entities as
  getter/setter bags — constitution #7), SOLID violations, dead code, silent `catch {}`.
- **performance**: N+1, unbounded queries / load-all-then-filter, missing indexes, needless re-render.
- **algorithm** (when logic is non-trivial): correctness of the core computation vs. the spec.
- **designer** (UI changes only): typography/spacing/hierarchy/consistency/accessibility/branding.

## Running the lenses (agent mapping + fallback)
Lens names are **roles, not fixed agent types**. Map each to whatever your environment provides, and
**verify the agent type exists before spawning**. If no dedicated reviewer exists for a lens (many setups
have no `performance-reviewer`/`algorithm-reviewer`), spawn a `general-purpose` (or `code-reviewer`) agent
with that lens's anti-patterns pasted in as the focus — **never skip the lens or abort on a missing agent
type**. Scale fan-out to the host: parallel by default, but on a resource-constrained machine run the
lenses in smaller batches (or sequentially) rather than all at once.

## Output & severity discipline (each lens)
Every lens returns, in this shape:
- **Strengths** — specific, with file refs. Mandatory: it forces real code comprehension and calibrates
  severity (a problems-only reviewer inflates). "Solid" is a valid finding.
- **Issues** — by **actual** severity (Critical/High/Medium/Low), with file:line, *why it matters*, and a
  fix. Don't mark nitpicks as Critical; don't bury a Critical as a nit.
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
