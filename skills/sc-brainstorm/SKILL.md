---
name: sc-brainstorm
description: Stage 1 of ship-cycle. Discovery/brainstorming — refuse to write code for a vague goal; ask clarifying questions, propose a design sketch, and get the user's acceptance before proceeding. Produces an agreed problem statement + verifiable acceptance criteria. Can be used standalone to scope any task.
---

# sc-brainstorm — discovery (Stage 1)

**Iron Law: no code until the problem is agreed.** A fast implementation of the wrong thing is the most
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

## Don't
- Don't jump to implementation or file edits here.
- Don't ask questions with obvious defaults — pick, state the choice, move on.
- Don't invent requirements the user didn't ask for.

## Gate G1 (to advance to `sc-design`)
- Acceptance criteria are stated **verifiably** and the user has agreed the direction.
- Record the agreed problem + acceptance criteria in this cycle's state file
  (`.claude/ship-cycle/<branch-slug>.json`); set `gates.G1 = pass`.

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
re-judges triviality for itself), compress this to a one-line restatement + criteria and proceed —
**except** the root-cause section above, which runs unchanged.

## Model routing
Requirements/discovery (analyst) runs at the **high** tier — getting the problem wrong propagates
everywhere. Often the orchestrator does this inline with the user; **if you spawn an agent, pass
`model = state.models['brainstorm']` and `effort = state.effort['brainstorm']`** (both resolved at
PREFLIGHT) — never the agent type's defaults (Iron Law 6).

**Telemetry**: when you set `gates.G1` in state, append this stage's row to
`state.telemetry.stages['brainstorm']` — the resolved tier, model and effort, plus whatever usage the host
actually exposed (tokens/cost/wall-clock) and `null` for what it didn't. **Never estimate a figure.** The
run's cost readout is assembled from these rows at G13 (§ship-cycle — Cost readout); a stage that writes no
row is simply absent from it, so the readout under-reports rather than lying.
