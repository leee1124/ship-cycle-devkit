---
name: sc-implement
description: Stage 4 of ship-cycle. Implement minimal code to pass the failing tests (TDD Green), refactor, and update docs in the same change — inside git worktree isolation so stack-split implementers (backend/web/mobile) can run in parallel without collisions. Runs tests and build.
---

# sc-implement — Green + build (Stage 4)

Make the failing tests pass with the **minimum** code, then refactor. Update docs in the same change. Where
§core 3 chose execution-based verification over test-first — a layout, copy or config change arriving with
no failing tests — implement it and run that named verification instead; the rest of the stage is unchanged.

## Worktree isolation (when it earns its keep)
If PREFLIGHT created a worktree (`state.worktreePath`) — i.e. this is stack-split or parallel work — do
the implementation there so it never touches the main checkout. For single-track work, no worktree was
created and the feature branch is enough. When the codebase is **split by stack**, give each stack its
own isolation:
- Spawn each stack's implementer as a separate agent with **`isolation: worktree`** so backend / web /
  mobile edit in **parallel without collisions**.
- Independent stacks → parallel. If the front end depends on a back-end API, settle that **contract
  first**, then parallelize.
- Never remove a worktree recorded as a `reviewJobs[].snapshot`, and check `state.gitFreeze.active` first
  — an external reviewer may be mid-read on it (§sc-review).
- After merge, clean up worktrees: run **sc-ship G13 step 1's link sweep first — always, not only when
  `env.sharedNodeModules` is set**, since links also arrive via `npm link`, monorepo layouts and a manual
  `mklink` — then `git worktree remove --force <path>`.

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
- **Resource-aware concurrency**: the full suite, builds and emulators agents launch are the heavy part
  (separate agent processes cost memory too). Run them under overlay `env.heavyLock` per
  `${CLAUDE_PLUGIN_ROOT}/docs/heavy-work.md`; with no `heavyLock` on a small host, run heavy-launching agents
  sequentially.

## Implement (executor — fresh context)
Give the implementer **only the plan, the failing tests (or the named execution-based verification), and
the conventions** (not the whole prior conversation) to avoid context contamination. The stack prompt templates —
`${CLAUDE_PLUGIN_ROOT}/prompts/impl-backend.md` · `impl-web.md` · `impl-mobile.md` — are **reference, not
required reading: invoke one when the tier warrants it** (Tier M/L, or any stack you haven't briefed an
implementer on before) and skip it on Tier S, where the brief is a one-liner and loading a 60-line template
costs more than it carries. Adapt to your stack.
Follow the engineering constitution (`${CLAUDE_PLUGIN_ROOT}/docs/engineering-constitution.md`):
authz from the principal only, DTOs not entities, whitelist validation, no N+1, no swallowed exceptions.

## Verify (this stage owns build + tests, separate from review)
- **G5**: build succeeds and the **new tests pass** (Green) — or, where G4 recorded an execution-based
  verification instead, that verification ran and its output was read. Run the nature's build/test commands
  and read the output (§core 2).
- **G6**: no failures **new vs `state.baseline`** (the base-branch reds captured at PREFLIGHT don't
  block — don't make each implementer re-derive "mine or pre-existing?" by stash-and-compare; diff the
  run against `state.baseline.failing`), and core coverage clears its threshold (next bullet). On a genuinely new failure, attach a
  debugger and loop. `baseline.flaky` cases are not exempt. Under **`ci-status-only`** every
  failure blocks unless its suite is in `baseline.run.rechecked`. A failure you believe is pre-existing or
  environment-only is settled by rechecking that suite on the base commit — never the working tree — per
  `${CLAUDE_PLUGIN_ROOT}/docs/test-baseline.md`, not by argument. Suites in
  **`state.baseline.unrunnableHere`** — ones this environment cannot start,
  probed and recorded at PREFLIGHT — are diffed **around**: not a regression, and not coverage either
  (§ship-cycle Stage 0.5 — Capture a test baseline). A suite that starts and fails is a failure like any
  other. **There is no path that adds a suite to that set here**: a suite that ran at PREFLIGHT and won't
  run now is a finding, not a quarantine. The one exception is a suite that did not exist at the base
  commit and is gated by the **same dependency whose probe already failed at PREFLIGHT** — it *inherits*
  that entry (`inheritedFrom`), and inheriting is not counting: **G5 does not treat it as Green**, and its
  criterion goes to `review-only (ci-deferred)` (§sc-ship G11).
- **G6 coverage — measured from the report, or recorded as n/a, never skipped.** "Core coverage ≥80%"
  with no named command, report or core set gets skipped silently, which is §core 2 failing quietly. This
  bullet is the whole rule; the field docs are in `${CLAUDE_PLUGIN_ROOT}/docs/ship-cycle.config.schema.json`.
  Per nature in `state.nature`, write one `state.coverage[<nature>]` entry:
  - **Not configured** (no overlay `changeNature[].coverage`): the string `"n/a: no coverage config"`.
    `gates.G6 = pass` with that entry is valid; sc-ship states it in the PR body.
  - **Configured**: record `runStartedAt`, run `command` as its own step, record the report's `reportMtime`,
    then read the file at `reportPath` as `format` — never the command's stdout summary.
  - **Path matched against `corePaths`** = the file's normalised repo-relative path (forward slashes, no
    `./`; a path outside the repo matches nothing). Per format: **JaCoCo** `<package name>/<sourcefile
    name>`; **Cobertura** `<sources><source>` + `<class filename>`; **LCOV** `SF:`; **istanbul** the file
    key. An absolute path drops the repo-root prefix; a relative one takes the first `sourceRoots` entry
    under which that file exists (none configured: the repo root). JaCoCo records no source root, so a
    JaCoCo nature needs `sourceRoots` unless its `corePaths` are written package-relative.
  - **Counted, lines only — branch coverage is not gated**: JaCoCo `<sourcefile>`'s `<counter
    type="LINE">` (`covered` ÷ `covered + missed`); Cobertura `<line hits>`, covered when `hits > 0`, never
    an average of `line-rate`; LCOV `LH` ÷ `LF`; istanbul `coverage-summary.json` `lines.covered` ÷
    `lines.total` (a `coverage-final.json` alone is `format: "other"`). Each file counts once,
    deduplicated by normalised path — a multi-module or per-class listing does not double its lines, and
    natures sharing a `reportPath` run the command once. `format: "other"` must record a `method` (how the
    per-file counts were extracted), or the entry is undetermined.
  - **Base**: PREFLIGHT measures the base commit the same way (command, staleness, matching, counting)
    into `baseline.coverage[<nature>]` — **locally whenever the command can run here, even under a CI
    `baseline.source`**; else from `ciReport`'s artifact for the base commit; else `"unmeasured: <reason>"`.
  - **Result — set by the evidence, not by choice.** `percent ≥ threshold` (default 80) → `pass`, whatever
    the base. Below it: base measured → `floor = min(threshold, base percent)` (a base already under the
    threshold must not get worse); `percent ≥ floor` → `pass`, else `fail`, which loops back like a new
    failure. Base unmeasured → `undetermined (ci-deferred)`, reason `"base unknown"` — never `fail`.
  - **`undetermined`, which blocks**: the command errored before writing a report; the report is missing,
    or `reportMtime ≤ runStartedAt` (left over from an earlier run); it does not parse as `format`; or **no
    entry matches `corePaths`** — zero core lines is a vacuous 100%, not a pass. Paste the error, fix the
    coverage run, re-run (the three-state rule below).
  - **`undetermined (ci-deferred)`**: the command needs a suite in `state.baseline.unrunnableHere`, or the
    base is unknown as above. Not a pass and not a dead end: set `gates.G6 = "checklist"` (as G7b does) and
    sc-ship lists it on the pre-merge manual gate, naming `ciReport` (job + artifact) when configured.
  - Entry shape: `{ result, percent, floor, threshold, report, format, runStartedAt, reportMtime }` (+
    `method` for `other`); an undetermined entry has `percent: null` plus `error` (the run's own error
    text) or `reason` (why it is deferred).
- **No false-green (how you read G5/G6)**: judge pass/fail from the command's **own exit status or its
  machine-readable report** (surefire/JUnit XML, runner JSON) — never from a piped/tailed/grepped stdout
  line. `mvn test | grep -i fail | tail` returns the *pipeline's last* exit code (the tail's `0`), so a red
  build reads green; a `command not found` (toolchain not on `PATH` after sourcing the env) is swallowed
  the same way. Run build/test as their **own** step, check `$?`, then read the report. `set -o pipefail`
  alone does **not** rescue a `grep`-in-the-pipe check — `grep` exits `1` on no match, so a *passing* build
  turns false-RED; drop the pipe, don't just add pipefail. (§core 2.)
- **No false-red either: a check that errored is not a failing result.** The opposite polarity of the
  above, and the more expensive one, because it sends you to fix code that was already correct. When the
  probe itself fails to run — a stale handle, a driver that died, a helper that raised before reaching the
  thing under test — the honest outcome is **undetermined**, not *failed*. Three states, never two.
  - **The runner already separates them; read that, not the prose** (§core 2): `<failure>` vs `<error>` in
    JUnit/surefire XML, `FAILED` vs `ERROR` in pytest. Where a runner doesn't, the test is the **exception
    type**: the assertion library's own type is a failure; anything raised by setup, a driver or I/O is
    undetermined. "Where it happened" is not usable — a failed assertion is itself a raised exception.
  - **Record the error text with the disposition.** An undetermined check with nothing pasted is
    indistinguishable from a skipped one.
  - **Undetermined never clears a gate — it only withholds a red.** Fix the probe and re-run. A check that
    is still undetermined after the probe is fixed is a **finding**, not a pass, and its criterion cannot
    satisfy G5.
  - Never let the first observation stick: a run reporting "all N failed" with N identical infrastructure
    errors is one broken check, not N broken things.
  - Unlike `baseline.unrunnableHere`, which is pre-committed at PREFLIGHT and resolves ambiguity *toward*
    `failing`, an undetermined check is minted at check time and resolved **by re-running it** — never by
    recording it and moving on.
- **A scripted sweep's exit `0` is an aggregate, not per-file evidence** — re-parse or re-compile the
  files it touched. The trap that makes this more than caution: **parser offsets may be byte offsets, not
  character offsets** (Python's `ast` `col_offset` is UTF-8 bytes; tree-sitter is byte-based; TypeScript
  uses UTF-16 units). Slicing a `str` by them shifts by one position per *extra byte* in every preceding
  multi-byte character, cumulatively along the line — 2 per 3-byte CJK character. The result often still
  parses, so nothing necessarily errors. Slice the encoded bytes, or use the parser's own
  extract-the-source-segment helper instead of doing index arithmetic.
- **G7**: if the change ships an artifact (APK/IPA/binary), run the **real packaging build**. Building is
  not running: a diff touching `releaseSmoke.appliesTo` also needs G9's release-artifact smoke (§sc-qa).
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
  - **No vacuous green** (§core 2): a `bootCheck` selector that matches **zero** tests exits `0` — treat
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
- **Check `state.gitFreeze.active` before any git write — and, when `releaseOn` is `job-complete`, before
  editing tracked files at all.** G8 can loop back here while an **out-of-process reviewer is still reading
  this working tree**, and one badly-timed write hangs it indefinitely (§sc-review — Git-write freeze).
  Under `releaseOn: "snapshot"` the tree is yours and only branch moves are barred; under
  `releaseOn: "job-complete"` the reviewer is on the live tree, so the edits themselves must wait. The
  better move is usually neither: if the fix will rewrite what the reviewer is reading, that job is
  **superseded** — cancel it, release the freeze, and re-launch against the fixed head (§sc-review).
- Record `gates.G5/G6/G7/G7b = <result>` in state, each with `state.gateTrees[G]` = the tree identity it ran on
  (§`${CLAUDE_PLUGIN_ROOT}/docs/state-file.md` — Tree identity), and
  `state.coverage` with G6.

## Model routing
executor + build-fixer run at the **mid** tier. Cheap path first: implement on mid → verify → escalate
only the failing fix (or a risk-zone diff) to a higher tier.

**Pass `model = state.models['implement']` and `effort = state.effort['implement']` on the
executor/build-fixer calls** (both resolved at PREFLIGHT) — never the agent type's defaults (§core 6).
An escalated fix passes the higher tier explicitly too.

**Telemetry**: when you set `gates.G5`…`G7b` in state, append this stage's row to
`state.telemetry.stages['implement']` — the resolved tier, model and effort, plus whatever usage the host
actually exposed (tokens/cost/wall-clock) and `null` for what it didn't. **Never estimate a figure.** The
run's cost readout is assembled from these rows at G13 (§`${CLAUDE_PLUGIN_ROOT}/docs/model-routing.md` — Cost readout); a stage that writes no
row is simply absent from it, so the readout under-reports rather than lying.
