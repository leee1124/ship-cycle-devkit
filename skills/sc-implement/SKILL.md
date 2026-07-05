---
name: sc-implement
description: Stage 4 of ship-cycle. Implement minimal code to pass the failing tests (TDD Green), refactor, and update docs in the same change — inside git worktree isolation so stack-split implementers (backend/web/mobile) can run in parallel without collisions. Runs tests and build.
---

# sc-implement — Green + build (Stage 4)

Make the failing tests pass with the **minimum** code, then refactor. Update docs in the same change.

## Worktree isolation (when it earns its keep)
If PREFLIGHT created a worktree (`state.worktreePath`) — i.e. this is stack-split or parallel work — do
the implementation there so it never touches the main checkout. For single-track work, no worktree was
created and the feature branch is enough. When the codebase is **split by stack**, give each stack its
own isolation:
- Spawn each stack's implementer as a separate agent with **`isolation: worktree`** so backend / web /
  mobile edit in **parallel without collisions**.
- Independent stacks → parallel. If the front end depends on a back-end API, settle that **contract
  first**, then parallelize.
- After merge, clean up worktrees: `git worktree remove <path>`.

## Implement (executor — fresh context)
Give the implementer **only the plan, the failing tests, and the conventions** (not the whole prior
conversation) to avoid context contamination. Use the stack prompt template:
`${CLAUDE_PLUGIN_ROOT}/prompts/impl-backend.md` · `impl-web.md` · `impl-mobile.md` (adapt to your stack).
Follow the engineering constitution (`${CLAUDE_PLUGIN_ROOT}/docs/engineering-constitution.md`):
authz from the principal only, DTOs not entities, whitelist validation, no N+1, no swallowed exceptions.

## Verify (this stage owns build + tests, separate from review)
- **G5**: build succeeds and the **new tests pass** (Green). Run the nature's build/test commands and
  read the output (Iron Law #2).
- **G6**: all tests for the nature are green; core coverage ≥80%. On failure, attach a debugger and loop.
- **G7**: if the change ships an artifact (APK/IPA/binary), run the **real packaging build**.
- Do **not** commit or open a PR here — that's `sc-ship`, after review.
- Set `gates.G5/G6/G7` in state.

## Model routing
executor + build-fixer run at the **mid** tier. Cheap path first: implement on mid → verify → escalate
only the failing fix (or a risk-zone diff) to a higher tier.

**Pass `model = state.models['implement']` on the executor/build-fixer calls** (resolved at PREFLIGHT) —
never the agent type's default (Iron Law 6). An escalated fix passes the higher tier explicitly too.
