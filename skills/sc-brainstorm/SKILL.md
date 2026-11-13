---
name: sc-brainstorm
description: Stage 1 of ship-cycle. Discovery/brainstorming — refuse to write code for a vague goal; ask clarifying questions, propose a design sketch, and get the user's acceptance before proceeding. Produces an agreed problem statement + verifiable acceptance criteria. Can be used standalone to scope any task.
---

# sc-brainstorm — discovery (Stage 1)

**No code until the problem is agreed.** A fast implementation of the wrong thing is the most
expensive outcome. This stage ends when the user accepts a design direction — not before.

## Do
1. **Restate the goal** in your own words; surface what's ambiguous or unstated.
2. **Ask clarifying questions** for genuine forks (scope, users, constraints, edge cases, success
   metric). Use `AskUserQuestion` for decisions that are the user's to make; don't ask what you can
   verify in the code or infer from sensible defaults.
3. **Propose a design sketch** — the shape of the solution, 1–3 options with tradeoffs if the space is
   wide. Recommend one.
4. **Get explicit acceptance** of the direction.
5. **Write acceptance criteria**: verifiable bullets (given input → expected output/state), including
   edge cases and non-goals.
6. **Propose the route plan** beside the criteria — the moment the most is known about what the work
   needs. One compact table, starting from `state.size` and naming every departure from it; the rules
   (what may be skipped, what never is, growth-only, standalone) are §ship-cycle — Route plan:

   ```markdown
   Route · size M (PREFLIGHT) · nature web · tierMap: overlay · confirm together with the criteria
   | stage | plan | why | model · effort | routing why |
   |---|---|---|---|---|
   | sc-design | skip | copy change; no interface, entry path or contract moves | — | — |
   | sc-tdd | skip | verified by execution: render the screen at 320 dp and read the label | — | — |
   | sc-brainstorm | run | — | high → opus · medium | a wrong problem statement reaches every stage |
   | sc-implement | run | — | mid → sonnet · low | one-file copy edit; a wrong edit shows at review |
   | sc-review | run · security, designer, cold | §core 1 — never skipped | high → opus · high | the last check before merge; a miss ships |
   | sc-qa | skip | no seam; release smoke still runs if `appliesTo` is touched | — | — |
   | sc-ship | run | — | low → haiku · low | mechanics; the G11 verifier runs high from the same map |
   ```

   The **model · effort** column copies `state.models` / `state.effort` as PREFLIGHT resolved them
   (`tier → model · effort`); **routing why** ties the choice to the cost of being wrong at that stage. Name
   a risk upgrade that fired on its row (`top → opus (schema)`) and a `securityReviewModel` pin on the review
   row, and give a reason on any row below the stage's documented tier (on Tier S: "tier S path") (`${CLAUDE_PLUGIN_ROOT}/docs/model-routing.md` — Shown at G1). With no overlay
   `tierMap`, put the tier → model mapping you chose in the heading line (`tierMap: high→opus,
   mid→sonnet, low→haiku (chosen here)`) — the user confirms it with the rest. Record the rows as
   `state.route.routing` and the mapping as `state.route.tierMap`.

   When the criteria end in a design document, not a code change, propose the **design-only route** instead
   (`state.route.kind = "design-only"`, `state.route.designMode`; `${CLAUDE_PLUGIN_ROOT}/docs/design-only-route.md`)
   — the user confirms it like any route; never drop the cycle because the work "is design only".

   `sc-tdd` may be skipped only for a layout, copy or config change. When the criteria reduce to one
   stage's job, say so instead and recommend that skill standalone. For a UI nature, ask whether the owner
   will watch the live visual loop and record it as `state.route.ownerPresent` (`true` only on a yes)
   (`${CLAUDE_PLUGIN_ROOT}/docs/visual-check.md`).

## Don't
- Don't jump to implementation or file edits here.
- Don't ask questions with obvious defaults — pick, state the choice, move on.
- Don't invent requirements the user didn't ask for.

## Gate G1 (to advance to `sc-design`)
- Acceptance criteria are stated **verifiably**, and the user has agreed the direction **and the route
  plan**, its model and effort rows included — one confirmation for both, not two.
- Record the agreed problem + acceptance criteria in this cycle's state file
  (`.claude/ship-cycle/<branch-slug>.json`), the route plan as `state.route` with its `confirmedAt` and
  `basis` (the current `size`, `risk` and `nature`), and a `route` / `confirmed` row in the gate log; set
  `gates.G1 = pass`. Advance to the first stage the route runs.

## Root-cause analysis (defect goals) — the stage that pays for the cycle
When the goal is a **defect fix**, the "agreed problem" this stage produces is the **root cause**, never the
reported symptom. State it, and name the **≥2 independent code sites** that corroborate it. **G1 does not
pass on a restatement of the report.** This is the kit's highest-judgment work and it runs at `high` effort
on **every size tier** — it is an outcome, not ceremony (§ship-cycle → Tier S path → the bright line), and
it is also what earns Tier S at all: the same corroborating sites become `state.sizeEvidence`.

Why it is never dialed down: a request arrives as "relabel that bar as Total" and the bar is in fact a
disjoint bucket, so implementing it as reported ships a chart that actively misleads. No later gate catches
that — every downstream lens is anchored to the accepted problem statement. A few greps here are the
cheapest insurance in the pipeline.

## Lightweight (Tier S only)
When `state.size` is **S** (§ship-cycle Stage 0.2 — Change-size tier; PREFLIGHT owns it and a stage never
re-judges triviality for itself), compress this to a one-line restatement + criteria + the route (the
Tier S path, as a table) and proceed — **except** the root-cause section above, which runs unchanged.

## Model routing
Requirements/discovery (analyst) runs at the **high** tier — getting the problem wrong propagates
everywhere. Often the orchestrator does this inline with the user; **if you spawn an agent, pass
`model = state.models['brainstorm']` and `effort = state.effort['brainstorm']`** (both resolved at
PREFLIGHT) — never the agent type's defaults (§core 6).

**Telemetry**: when you set `gates.G1` in state, append this stage's row to
`state.telemetry.stages['brainstorm']` — the resolved tier, model and effort, plus whatever usage the host
actually exposed (tokens/cost/wall-clock) and `null` for what it didn't. **Never estimate a figure.** The
run's cost readout is assembled from these rows at G13 (§`${CLAUDE_PLUGIN_ROOT}/docs/model-routing.md` — Cost readout); a stage that writes no
row is simply absent from it, so the readout under-reports rather than lying.
