---
name: sc-design
description: Stage 2 of ship-cycle. Design + adversarial design review. An architect produces interfaces/boundaries/tradeoffs (READ-ONLY, no code); a critic attacks the failure modes until zero unresolved objections remain. Enforces layered architecture and DDD from the engineering constitution.
---

# sc-design — design + review (Stage 2)

Two roles, run as separate agents for real adversarial separation.

## Design (architect — READ-ONLY, no code)
Produce a design doc, not an implementation:
- **Interfaces & boundaries**: the contracts (APIs/DTOs/module seams) the change introduces or touches.
- **Tradeoffs & alternatives**: at least one alternative considered, with why the chosen one wins.
- **Constitution fit**: layered separation (Controller/Service/Repository/DTO); depend on interfaces;
  business logic **inside the domain** (no anemic model). See
  `${CLAUDE_PLUGIN_ROOT}/docs/engineering-constitution.md` (#3, #7).
- **Risk & data**: schema/migration impact, authz/ownership rules, failure modes.

## Design review (critic)
A separate agent attacks the design:
- Hidden assumptions, unhandled failure modes, contract mismatches, security/authz gaps, scaling/N+1.
- Return a list of objections. Iterate design ↔ review until the list is **empty**.

## Gate G2/G3 (to advance to `sc-tdd`)
- G2: interfaces are specified concretely.
- G3: the critic's unresolved-objection list is **empty** (not "addressed later" — resolved).
- Set `gates.G2 = pass`, `gates.G3 = pass`. On unresolved objections, loop within this stage
  (respect the orchestrator's loop cap of 3).

## Model routing
architect + critic run at the **high** tier; upgrade to **top** if PREFLIGHT flagged this change as a
schema migration or public-API/architecture-boundary change (see the orchestrator's model routing).
