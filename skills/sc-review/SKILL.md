---
name: sc-review
description: Stage 5 of ship-cycle. Multi-lens parallel code review — security, quality, performance, algorithm (and designer on UI changes) as separate agents, each checking named anti-patterns. Blocks the PR until zero Critical/High findings survive verification.
---

# sc-review — multi-lens code review (Stage 5)

**Iron Law #3: no PR without a passing review.** Run the lenses (from overlay `changeNature[].reviews`)
as **separate agents in parallel** — each is blind to the others, so they catch different failure modes.

## Lenses (each names its anti-patterns)
- **security**: authz/ownership bypass (IDOR), paywall/entitlement leak, injection (SQLi/XSS), secrets,
  unsafe deserialization, missing input validation.
- **quality**: logic defects, **anemic domain model** (business logic stranded in services, entities as
  getter/setter bags — constitution #7), SOLID violations, dead code, silent `catch {}`.
- **performance**: N+1, unbounded queries / load-all-then-filter, missing indexes, needless re-render.
- **algorithm** (when logic is non-trivial): correctness of the core computation vs. the spec.
- **designer** (UI changes only): typography/spacing/hierarchy/consistency/accessibility/branding.

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
