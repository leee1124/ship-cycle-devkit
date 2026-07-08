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

### Split the architect by axis on large/cross-cutting/full-stack designs
One architect over a wide change produces a shallow doc and misses the seams. For a cross-cutting or
full-stack change, run **N architects in parallel, partitioned by axis** — e.g. *trigger/flow/store* vs
*data adapter*, or *frontend contract* vs *backend endpoint* vs *migration* — each with an **exclusive
slice** and each required to **state the seam contract** it exposes to the others (function names,
input/output types). Then **one** critic reviews the **union** of their docs (it must, so it catches
*inter-axis* contradictions — mismatched seam signatures, one axis's "no schema change" colliding with
another's "persist a new field"). This is the design-stage analogue of `sc-implement`'s partitioning:
same "exclusive slices + explicit seams" discipline, applied to the read-only design. Keep it to one
architect for a single-axis change — splitting there is pure overhead.

## Design review (critic)
A separate agent attacks the design (the **union** of all architect docs when the axis was split):
- Hidden assumptions, unhandled failure modes, contract mismatches, security/authz gaps, scaling/N+1.
- **Inter-axis seam mismatches**: when architects were split, the critic's first job is to check their
  seams line up (names, signatures, who-owns-what) and that no two axes made contradictory scope
  assumptions.
- **Scope discovered here loops back.** If the critic (or an architect) finds the change actually needs a
  stack/axis PREFLIGHT didn't classify — a mobile-only design that turns out to need a backend endpoint —
  that is a **re-classification event, not an in-stage patch**: tell the orchestrator to re-run change-nature
  + model routing (Stage 0.4) and add the missing implementer axis, then finish the design for the true scope.
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

### Design-consistency gate — reuse before create
Consistency isn't a review afterthought; it is decided **here**, when the UI change is designed. A crude,
uncoordinated surface — three different empty states, a bespoke spinner where a progress component exists,
ad-hoc spacing — is almost always "invented instead of reused." So for any UI change the design must:
- **Consume the project's design source of truth.** If the overlay declares one (`design.tokens` /
  `design.components` — a token file, a component inventory, or a design-system doc), read it and design
  against it. Absent an overlay entry, **inventory the repo's existing tokens/components first** and design
  against those. Never design a screen in a vacuum.
- **Reuse before create.** Color, spacing, type scale, empty/loading/error states, progress indicators,
  icons — resolve each from an existing token/component. A **new** visual primitive is allowed only with a
  one-line justification of why no existing one serves it. "It was faster to inline it" is not a
  justification — that is exactly how a surface fragments.
- **Name the canonical pattern** the change should use for each recurring surface (empty/loading/error,
  metric, progress), so the implementer wires the shared one, not a new copy.

Framework-agnostic: the overlay supplies *which* tokens/components exist; this gate enforces *reuse* of
whatever they are. It is the design-time origin of the `designer` review lens's anti-patterns (sc-review).

## Fail-closed hooks are a parallelization hazard
If the repo has a **fail-closed turn-end hook** (an i18n-symmetry gate, a lint/format gate that blocks a
turn until satisfied), it will block **parallel** implementers — each agent's turn fails on the shared
resource. Identify such hooks at design time and plan to **pre-register/freeze** what they guard (e.g. add
the needed i18n keys symmetrically) in the serial foundation step (`sc-implement` Wave 0), so the parallel
waves never trip them.

## Model routing
architect + critic run at the **high** tier; upgrade to **top** if PREFLIGHT flagged this change as a
schema migration or public-API/architecture-boundary change (see the orchestrator's model routing).

**Pass `model = state.models['design']` on the architect and critic calls** — it was resolved at
PREFLIGHT (tier + risk upgrade). Never rely on the agent type's default model (Iron Law 6).
