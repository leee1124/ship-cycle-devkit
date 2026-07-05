---
name: sc-audit
description: À-la-carte parity audit. Statically compares every consumer surface (web, mobile, CLI, SDK, another service) against a single source-of-truth contract (an API, schema, or spec) and emits a module-by-module gap matrix + cross-cutting risk checks + P0/P1/P2 priorities + a cutover/ship verdict. Run it before a first cross-surface integration or on a large surface — not per feature. Triggers "parity audit", "integration gap report", "are the frontends actually wired", "release-readiness audit".
---

# sc-audit — cross-surface parity audit (à la carte)

Not a pipeline stage. A **periodic/on-demand health check** you run when a whole surface may have drifted
from the contract it's supposed to consume — the failure this catches is macro, not per-feature.

## Why this exists (the failure mode)

`sc-design` verifies contracts **for the feature in hand**. But an entire surface can be built against
*assumed* contracts and stay green in isolation — nothing fails until the first real integration, at
which point most screens break at once. A real dogfood run shipped a whole web app whose pages assumed
field names the backend never returned; it "deployed" but almost nothing worked end-to-end. A static
parity audit surfaces that class of drift **before** you wire the surfaces together or cut over.

Run sc-audit when: a first cross-surface integration is imminent · a surface is large or was built ahead
of its backend · you're deciding whether a stub/local layer can be removed · you're gauging
release-readiness across platforms.

## Procedure

### 0. Fix the baseline (state it at the top of the report)
- Date, comparison branch, and commit (`git rev-parse <base>`).
- **State the method explicitly**: "static comparison of code; runtime/E2E verification is separate."
  A static audit cannot prove behavior — only contract alignment. Say so, in the conclusion too.

### 1. Inventory (parallel readers — one per surface)
Read the **source of truth** and each **consumer surface** concurrently:

| Target | What to collect |
|---|---|
| Source of truth (API / schema / spec) | Every endpoint/type: method + path + auth annotation + the **actual serialized shape** (real field names/types, not the entity name) |
| Each consumer surface | Its routes/screens/commands + the calls it actually makes + **which implementation is wired in** |

Surfaces and their paths come from the overlay `audit.surfaces` (fall back to `changeNature` globs, and
log that defaults are in use). **Presence is not integration**: a file existing does not mean it's wired —
check the composition root / DI / client factory for which implementation is actually injected
(real client vs. local/stub/mock).

### 2. Module-by-module parity matrix
Group the contract into domain modules (from overlay `audit.modules`, else derive from the API and log
it). Reconcile the full endpoint inventory against the module list so **no endpoint is unclassified**
(internal/seed endpoints: confirm they're internal, then exclude explicitly).

Per module:

| Feature | Contract (API) | Surface A | Surface B | Gap |
|---|---|---|---|---|

Verdict symbols: ✅ wired · 🔶 partial (present but unwired/incomplete) · ❌ absent · N/A.
**"Endpoint exists" is never ✅.** Only mark ✅ when the surface code actually calls it with the real
shape. Append a "remaining checks" bullet list per module.

### 3. Cross-cutting risk checks (tie to the engineering constitution)
See `${CLAUDE_PLUGIN_ROOT}/docs/engineering-constitution.md`:
- **Authz / paywall (#5)**: missing double-defense (route guard + service-layer ownership); locked
  content leaking through a list/summary DTO.
- **Contract shape (#6)**: source-of-truth returning raw entities instead of DTOs; any surface built
  against a guessed shape rather than the real serialization.
- **Data integrity**: local/stub schema ↔ backend entity drift → migration risk on cutover.
- **i18n**: key symmetry across locales/namespaces; raw keys / `???` reaching the screen. If the project
  provides an i18n-parity config (overlay `i18n.configPath`), use it.
- **Files/export**: "API call succeeded" ≠ "file actually opens/validates" — flag as a static-audit blind spot.

### 4. Prioritize
- **P0 — blocker**: not closable → cannot ship / cannot cut over.
- **P1 — operational**: shippable but must be cleaned up early in operation.
- **P2 — decide**: keep-and-migrate, or formally deprecate.

### 5. Verdict (last section — two gradeable judgments)
1. **Cutover-ready?** (can the stub/local layer be removed — full contract consumption): every screen
   goes through the real client · a data-migration path exists · offline/failure UX is defined.
2. **Ship-ready?**: all P0 closed · per-role authz regression done · no raw i18n keys · export/files
   actually open · no locked-content leak · module QA scenarios listed.

Print one overall label: **parallel-run only** / **cutover-ready** / **ship-ready**. Lead the report with
a one-sentence conclusion: "current state is X-level, and is *not* yet Y-level."

### 6. Save + hand off
- Path: `docs/audits/parity-audit-YYYY-MM-DD.md` (override via overlay `audit.reportDir`).
- Section order: **conclusion first** → inventory → module matrix → cross-cutting risks → priorities → verdict.
- Every judgment is backed by evidence (file path, route, endpoint) in a table — **no guessed verdicts**.
- Propose P0 findings into the issue tracker / roadmap after writing the report (don't silently drop them).

## Model routing
Inventory/readers run at **low–mid** (mechanical collection scales with surface count — fan out, or go
sequential on constrained hosts). The matrix reconciliation, risk checks, and verdict run at **high** —
this is the judgment the audit exists for. Bridge tiers via overlay `modelRouting.tierMap`.

## Relationship to the pipeline
sc-audit is **not** chained by `ship-cycle`. It informs it: a P0 from the audit becomes a `ship-cycle`
goal, and `sc-design`'s per-feature "verify contracts, never assume" rule is the same discipline applied
one feature at a time. Audit = the macro sweep; sc-design = the per-change guard.
