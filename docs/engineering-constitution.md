# Engineering Constitution

Baseline engineering rules the `ship-cycle` skill enforces at its gates. A project may extend these,
but should not weaken them. Framework-agnostic.

## 1. Branching & flow
- **Never commit directly to a protected branch** (`main`/`master`/`dev`). Create a `feature/*` or
  `fix/*` branch first.
- **Commit and open PRs at the right time.** When a meaningful unit of work is complete and verified
  (build/test), commit; open a PR at an appropriate point (default base: your integration branch).
  Don't leave work uncommitted for long.
- **Review before every PR.** After build/test pass and before opening a PR, run code review and
  check adherence to #3–#9. Address findings (especially security/authz/logic defects) before opening.
  No merge without review.
- **Stay on-topic.** On a feature/fix branch, make only changes related to that branch's purpose.
  Unrelated work goes on a new branch. Don't mix concerns.

## 2. Documentation
- Update README and related docs (API docs, CHANGELOG, comments) as part of the work — keep docs
  current in the same change that adds/changes/removes behavior.

## 3. Architecture & design (SOLID & Clean Code)
- Keep layers separated (Controller, Service, Repository, DTO).
- Small methods with a single responsibility; meaningful, domain-language names for methods, variables,
  **and constants** — no unexplained literals (see the no-magic-numbers rule below).
- Depend on interfaces/abstractions, not concrete classes, so change stays cheap.
- **No magic numbers/strings**: extract any literal with domain meaning into a named constant. A closed,
  related set becomes an `enum` (Java) / a union literal type or an `as const` object (TS — **not**
  `enum`, whose runtime cost and `isolatedModules`/bundler pitfalls make the union the idiom) /
  `Object.freeze({...})` (JS). Where such a set carries behavior, put the behavior on it (a method on the
  enum, a lookup on the frozen object) rather than scattering `switch`es — an anemic constant bag repeats
  the anemic-model smell (#7).

## 4. Input validation & security (OWASP Top 10)
- Validate external input with framework features and regex on a **whitelist** basis.
- Prevent SQL injection: use an ORM or parameterized queries — never string-concatenate SQL.
- Prevent XSS: escape/encode all HTML output.

## 5. Authentication & authorization
- For every resource-mutating request (C/U/D), verify in the **service layer** that the current user's
  identity matches the data's owner.

## 6. Minimize data exposure & handle exceptions
- Never return entities directly; return a DTO containing only what's needed.
- Don't swallow exceptions (`catch {}`) — log them.
- To the client, hide concrete error detail (stack traces, DB errors); return a normalized safe error
  shape (e.g. `{ "code": "ERR001", "message": "The request could not be processed." }`).

## 7. Domain-Driven Design (DDD)
- Model around the domain (Entity, Value Object, Aggregate). Encapsulate business logic **inside** the
  domain model; the service layer only composes use cases.
- Separate bounded contexts clearly; communicate across contexts via DTOs or events. Package by domain.
- Reflect the ubiquitous language consistently in class/method/variable names.

## 8. Test-Driven Development (TDD)
- Follow Red-Green-Refactor: write a failing test first (Red), pass it minimally (Green), then refactor.
- Structure tests as Given/When/Then with a descriptive name.
- Separate unit / integration / E2E tests. Keep coverage of core business logic at **≥80%**.

## 9. Branch management
- Delete merged feature/fix branches immediately (local + remote).
- Clean up stale experiment/test branches at an appropriate time.
- Never delete protected branches (`dev`, `main`/`master`).

## 10. Code-review checklist
- The review must include adherence to #3–#9, checking **specific anti-patterns** (not a vague
  "compliant?"):
  - **DDD (#7)**: anemic domain model — business logic stranded in services while entities are
    getter/setter data bags.
  - **TDD (#8)**: order can't be seen in a diff → **enforce at development time**. Implementation tasks
    must include "write the failing test first (Red), then implement (Green)"; at commit/PR, confirm the
    core logic has tests and adequate coverage.
  - Review prompts must name each dimension's anti-patterns (authz bypass / paywall leak, anemic model,
    N+1, weak validation, etc.).
- **Build/run verification is separate from code review** — static review does not guarantee a
  buildable/deployable artifact. Verify build/test (and real artifact builds where relevant) before PR.
