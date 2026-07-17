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

## Large cross-cutting change — waved execution (single stack)
When one change touches **many files of the same stack** (a design-system reskin, a codemod/rename across
a layer), worktree-per-stack doesn't apply — the collision risk is *within* the stack. Wave it:
- **Wave 0 (serial foundation)**: the shared single-file bottlenecks everything else imports — tokens/
  theme, shared wrappers, motion/util infra, **pre-registered i18n keys**. One agent; must land before any
  parallel wave.
- **Waves 1..N (parallel)**: partition the remaining files into **exclusive ownership sets (zero overlap)**
  — one agent per set, so N run concurrently without touching the same file. Barrier between waves; verify
  (typecheck/build) at each barrier.
- **Atomic contract-change rule**: the owner that changes a shared symbol's signature/type also updates
  that symbol's **call sites in the same wave** — otherwise the barrier's global typecheck goes red between
  waves. Pre-plan which call-site files each signature change reaches.
- **Shrink the blast radius — contract changes in a serial micro-wave.** With dozens of call sites the risk
  isn't the leaf reskins, it's the few edits that touch shared contracts. Land **signature/type changes and
  their call-site updates as their own serial step, verified once**, *before* the parallel leaf waves start
  — then a parallel agent literally can't red the types. (The atomic rule, pushed one step further.)
- **"Verify in the loop" has a precondition.** Forcing each parallel agent to run `tsc`/build inside its own
  loop is only safe when agents are **worktree-isolated** — in a *shared* working tree a whole-project
  typecheck sees every agent's half-finished edits and flags errors in files the agent doesn't own (false
  alarms; agents may "fix" each other). So either isolate (`isolation: worktree`, costly at high fan-out)
  and self-verify, or keep a shared tree with a **single barrier typecheck** and, on failure, **bisect —
  map each error to its owning file → re-dispatch only that owner**, rather than stalling the whole wave.
- **Resource-aware concurrency**: cap concurrent agents to what the machine sustains — with a heavy local
  process up (emulator/simulator/device for visual QA), too many parallel agents can exhaust RAM and freeze
  the box.

## Implement (executor — fresh context)
Give the implementer **only the plan, the failing tests, and the conventions** (not the whole prior
conversation) to avoid context contamination. Use the stack prompt template:
`${CLAUDE_PLUGIN_ROOT}/prompts/impl-backend.md` · `impl-web.md` · `impl-mobile.md` (adapt to your stack).
Follow the engineering constitution (`${CLAUDE_PLUGIN_ROOT}/docs/engineering-constitution.md`):
authz from the principal only, DTOs not entities, whitelist validation, no N+1, no swallowed exceptions.

## Verify (this stage owns build + tests, separate from review)
- **G5**: build succeeds and the **new tests pass** (Green). Run the nature's build/test commands and
  read the output (Iron Law #2).
- **G6**: no failures **new vs `state.baseline`** (the base-branch reds captured at PREFLIGHT don't
  block — don't make each implementer re-derive "mine or pre-existing?" by stash-and-compare; diff the
  run against `state.baseline.failing`), core coverage ≥80%. On a genuinely new failure, attach a
  debugger and loop.
- **No false-green (how you read G5/G6)**: judge pass/fail from the command's **own exit status or its
  machine-readable report** (surefire/JUnit XML, runner JSON) — never from a piped/tailed/grepped stdout
  line. `mvn test | grep -i fail | tail` returns the *pipeline's last* exit code (the tail's `0`), so a red
  build reads green; a `command not found` (toolchain not on `PATH` after sourcing the env) is swallowed
  the same way. Run build/test as their **own** step, check `$?`, then read the report. `set -o pipefail`
  alone does **not** rescue a `grep`-in-the-pipe check — `grep` exits `1` on no match, so a *passing* build
  turns false-RED; drop the pipe, don't just add pipefail. (Iron Law #2.)
- **G7**: if the change ships an artifact (APK/IPA/binary), run the **real packaging build**.
- **G7b — boot/context-load smoke (nature declares `bootCheck`)**: unit tests hand-assemble collaborators
  and sliced ITs skip full wiring, so a framework-wiring defect — a new type caught by an **unchanged**
  bean/mapper/component scan, a bean-scope clash, a missing-property `@Conditional` — passes every other
  gate yet the app won't boot. If the nature declares `bootCheck`, it **has a loadable context** → **run it
  on every non-inert change to that nature's production sources** and require it to pass. This is an
  **outcome floor, not ceremony**: the only thing dialed is whether the nature has a context at all (a
  UI-leaf nature declares none → never boots).
  - **Inert = safe to skip, defined narrowly**: literal code comments / Javadoc (**not** annotations —
    `@Component`/`@Scope`/`@Conditional`/`@MapperScan` edits are wiring changes → always boot), tests, and
    non-runtime assets (images, README, fixtures). **NON-inert by default (always boot)**: production
    resources on the runtime classpath (`src/main/resources/**` — `application.yml`/`.properties`,
    `spring.factories`, `@AutoConfiguration` imports; equivalently a Node DI/container-wiring module, Rails
    `config/`, `Program.cs`, …), build/dependency manifests + lockfiles, and framework config — these are
    prime boot-breakers. **When inertness is uncertain, treat as non-inert and boot** (the outcome bright
    line). "Test-only" = the diff is limited to test paths (`**/*Test.*`, `**/test/**`, `**/*.spec.*`).
  - **Depth — cheap eager context-load**: prefer the cheap full-context load
    (`@SpringBootTest(webEnvironment=NONE)` or equivalent), kept as a **standing test in the suite** so most
    changes pay **zero** extra cost (G5 already runs it). It must force **eager** bean creation — a
    lazy-init context (`spring.main.lazy-initialization=true`) can load green and still fail on first use,
    false-passing the eager `BindingException` this gate exists to catch. It proves the **DI graph is
    constructible**, not the web layer / filters / health endpoint — those stay sc-qa's HTTP bring-up (so
    G7b and G9 are not redundant). A genuinely expensive full-server/health boot belongs in **sc-qa (G9)**,
    not as an always-on G7b floor.
  - **No vacuous green** (Iron Law #2): a `bootCheck` selector that matches **zero** tests exits `0` — treat
    that as **misconfig → FAIL**, not pass. Assert a non-zero context-load test actually ran (read the
    report/count); don't trust exit `0`.
  - **Environment**: `bootCheck` needs a **full-context-capable** env — a **superset** of the sliced ITs'
    needs (an embedded/stubbed datasource sufficient for **every** bean's deps to resolve). The sliced ITs'
    rails are by definition **not enough** — that they were sliced is why the incident slipped.
  - **Can't load a context locally** (no datasource/backing service) → **don't fake a pass**: record a named
    boot-verification checklist item in state and let **sc-ship** surface it in the PR as a pre-merge gate
    (like sc-qa's device-gap deferral). **Never wire an env-dependent boot check into a CI path lacking its
    deps** — it red-blocks unrelated PRs; during an outage, doubly bad (it blocks the fix that restores the
    service). G7b lives in the **cycle** (local/pre-PR), not as a blanket CI requirement.
  - Set `gates.G7b` in state (`pass` / `checklist` / `skip`, with the reason).
- **Lockfile sync**: if you changed a dependency **manifest** (`package.json`, `go.mod`, `Gemfile`,
  `Cargo.toml`, …) that has a **committed lockfile**, regenerate the lockfile in the same change. CI and
  release builds install from the **lockfile** (`npm ci`, `--frozen-lockfile`, …), so a manifest-only edit
  is inert — or reinstalls the old version and re-breaks the very build you fixed. (`npm install
  --package-lock-only` regenerates the lockfile without touching `node_modules`.) In a workspace, keep the
  single root lockfile; delete stray per-package ones.
- Do **not** commit or open a PR here — that's `sc-ship`, after review.
- Set `gates.G5/G6/G7/G7b` in state.

## Model routing
executor + build-fixer run at the **mid** tier. Cheap path first: implement on mid → verify → escalate
only the failing fix (or a risk-zone diff) to a higher tier.

**Pass `model = state.models['implement']` on the executor/build-fixer calls** (resolved at PREFLIGHT) —
never the agent type's default (Iron Law 6). An escalated fix passes the higher tier explicitly too.
