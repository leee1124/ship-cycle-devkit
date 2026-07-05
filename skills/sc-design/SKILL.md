---
name: sc-design
description: Stage 2 of ship-cycle. Design + adversarial design review. An architect produces interfaces/boundaries/tradeoffs (READ-ONLY, no code); a critic attacks the failure modes until zero unresolved objections remain. Enforces layered architecture and DDD from the engineering constitution.
---

# sc-design — design + review (Stage 2)

Two roles, run as separate agents for real adversarial separation.

## Design (architect — READ-ONLY, no code)
Produce a design doc, not an implementation:
- **Interfaces & boundaries**: the contracts (APIs/DTOs/module seams) the change introduces or touches.
- **Verify contracts, never assume them** (hard rule): for any API/DTO/entity the change integrates with,
  read the **actual** endpoint/entity/serialized response and record the real field names/types — do not
  guess from a plausible-looking shape. Assumed contracts silently propagate to the implementer and
  surface as runtime crashes (a real dogfood run passed `{exerciseName,weight}` when the endpoint
  returned a JPA entity `{exerciseId,estimated1rm}` → the widget crashed). If the backend returns a raw
  entity, flag it (constitution #6) and design the frontend against the *actual* serialization.
  This is the per-feature guard; for a **first cross-surface integration or a large/ahead-of-backend
  surface**, run the macro sweep (`sc-audit`) first — a whole surface can drift on assumed contracts and
  stay green until the first real integration.
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

## UI-only changes
For a pure UI change (new component/screen, no new domain logic), this stage and `sc-implement` merge
naturally under a **designer**: the "design" is the component/interaction design, produced alongside the
code. Keep the critic pass (accessibility/contract), but don't force a separate READ-ONLY architecture
doc for a widget.

## Model routing
architect + critic run at the **high** tier; upgrade to **top** if PREFLIGHT flagged this change as a
schema migration or public-API/architecture-boundary change (see the orchestrator's model routing).

**Pass `model = state.models['design']` on the architect and critic calls** — it was resolved at
PREFLIGHT (tier + risk upgrade). Never rely on the agent type's default model (Iron Law 6).
