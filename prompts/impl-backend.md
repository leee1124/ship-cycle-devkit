# Backend Implementation-Agent Prompt (Spring Boot example)

Template for a **backend-only** implementation agent, kept separate from front-end work. Fill in
`{…}` and hand to `executor` (standard) or a deep autonomous agent (complex/multi-file). Never include
front-end changes. This is a *stack template* — adapt the stack line and conventions to your project.

## Stack (example)
Spring Boot / Java / JPA / Spring Security (JWT) / relational DB / Gradle / JUnit5.

## Template
```
Implement {feature/goal} in the backend ({backendPath}). Work on the current branch {branch} (do not
switch branches). Do not touch the front end ({webPath}, {mobilePath}) — separate agents own those.

## Acceptance criteria
{Verifiable criteria as bullets. e.g. given a specific input → a specific response/status}

## Constitution (must follow)
- **TDD**: write JUnit tests first (Red), then implement (Green). Given/When/Then + descriptive names.
  Unit (Service/domain) + integration (Controller+DB, spring-security-test).
- **Layered**: separate Controller / Service / Repository / DTO. Depend on interfaces.
- **DDD**: encapsulate business logic in the domain (entities/domain services). **No anemic model**
  (logic must not pile up in services while entities are getter/setter data bags). Cross-aggregate
  aggregation goes in a domain service.
- **AuthN/Z**: derive userId only from the SecurityContext principal (never from a request param =
  prevents IDOR). In the service layer, verify access is limited to **the current user's own data**.
- **Return DTOs only**: never return entities. Create response-only DTOs (records). Never leak stack
  traces / DB errors to the client (normalized errors via a global exception handler only).
- **Input validation**: validate external input on a whitelist basis (`@Valid`/`@Pattern`). Prevent
  SQLi with JPA/parameterized queries only (no string concatenation).
- **Exceptions**: don't swallow with empty catch — log.
- **i18n** (if applicable): add new message keys **symmetrically across all configured locales**
  (a parity check may block otherwise). Read-only GETs usually need no new messages.
- **Performance**: watch N+1 (fetch join/EntityGraph/@BatchSize). Query only the needed scope
  (filter/paginate in the DB; no load-all-then-filter-in-memory). Index frequently queried columns.

## Reuse/context
{Existing classes/patterns/seed data to reuse. e.g. an existing controller's security & DTO style,
a domain constants source, specific repository methods}

## Done criteria (build verification is separate from review)
- Full `./gradlew test` green (incl. new). Compiles.
- Report changed/new files & roles, added test names, and a `./gradlew test` summary.
- **Do NOT commit/PR** (review happens first). Read the real target code before writing and match its
  conventions.
```

## Notes
- When running alongside web/mobile: the backend API is the front end's dependency, so do **backend
  first (or settle the contract, then parallelize)**. If the feature is independent, run in parallel.
- Code review is separate (security/quality/performance in parallel). This agent does implement+tests only.
