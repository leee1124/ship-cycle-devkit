---
name: sc-tdd
description: Stage 3 of ship-cycle. Turn acceptance criteria into failing tests BEFORE any implementation (TDD Red). Runs the tests and confirms they fail for the right reason. Test type is chosen by change nature from the project overlay.
---

# sc-tdd — write failing tests (Stage 3, Red)

**Iron Law #1: no production code without a failing test first.** This stage produces the tests; the
next stage makes them pass. Rejected excuses: "trivial" · "just once" · "I'll add tests after".

## Do
1. For each acceptance criterion, write a test that encodes it: **Given/When/Then**, descriptive name.
2. Choose the test type by **change nature** (from the overlay `changeNature[].tests` for this diff) —
   e.g. unit (service/domain) + integration (controller+DB) for backend; component/E2E for web;
   unit + algorithm for mobile. Don't write test types the nature doesn't call for.
3. **Run them and read the output.** Confirm they **fail for the intended reason** (missing behavior),
   not a compile error or typo. A test that passes now, or errors for the wrong reason, is not Red.

## When the stack has no UI/component test harness
Some stacks can't unit-test rendered output (e.g. React Native without a component-testing lib, or any UI
with no render harness). Don't skip Red, and don't bolt on a heavy harness just to satisfy it: **extract the
change's pure logic** — formatters, calculators, selectors/reducers, time/geometry math, i18n resolution —
into testable modules and write the failing tests there. The thin UI wiring that remains (props, layout,
event handlers) is covered by `sc-review` (designer lens) + the `sc-qa` on-device checklist, not by faked
component tests. If a fix genuinely has **no** extractable logic, say so explicitly and route its
verification to review/QA rather than writing a vacuous test.

## Don't
- Don't implement the feature to make them pass — that's `sc-implement`.
- Don't write vacuous tests (asserting trivialities) to fake Red.

## Gate G4 (to advance to `sc-implement`)
- Failing tests exist for the **core logic** of every acceptance criterion, and you have **run them and
  seen them fail** for the right reason. Set `gates.G4 = pass`.

## Model routing
test-engineer runs at the **mid** tier.

**Pass `model = state.models['tdd']` on the test-engineer call** (resolved at PREFLIGHT) — never the
agent type's default model (Iron Law 6).
