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
- Record the agreed problem + acceptance criteria in `.claude/.ship-cycle-state.json`; set `gates.G1 = pass`.

## Lightweight
For a trivial, unambiguous change, compress this to a one-line restatement + acceptance criteria and proceed.

## Model routing
Requirements/discovery (analyst) runs at the **high** tier — getting the problem wrong propagates
everywhere. Often the orchestrator does this inline with the user; **if you spawn an agent, pass
`model = state.models['brainstorm']`** (resolved at PREFLIGHT) — never the agent type's default (Iron Law 6).
