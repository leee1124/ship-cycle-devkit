---
name: sc-qa
description: Stage 6 of ship-cycle. Independent, adversarial QA of the running system — integration/E2E/exploration/regression, with special focus on seams (front↔back contract) when implementation was split across stacks. Conditional; skip for trivial changes.
---

# sc-qa — integration & seam QA (Stage 6)

When implementation is **split by stack**, nobody owned end-to-end — so a separate agent brings the
system up and checks it **independently and adversarially**, distinct from the unit tests the
implementers wrote.

## Do
- **Bring the system up** and exercise the **core user flows** for real (actual API calls / E2E driver),
  not mocked.
- **Seam checks**: verify the front↔back **contract** — field names, types, status codes, error shapes,
  pagination, auth headers. Contract mismatches between separately-built stacks are the #1 seam defect.
- **Exploration + regression**: probe edge cases and adjacent flows the change could have broken —
  including the **N≥2 / batch case**: a defect that only surfaces with multiple rows/items (ordering,
  dedup/merge, pagination, generated-key linking) is invisible when you exercise just one.
- **Written ≠ run — integration/seam tests must EXECUTE against the real dependency (or an equivalent) and
  pass.** A test that only **compiles** is not coverage: a DB integration test can compile green and fail on
  first real execution — a sequence/identity key `useGeneratedKeys` never populated (so the test binds
  `null`), a NOT-NULL column left unseeded, a migration not applied. `@Disabled`, a suite skipped because
  DDL/seed/auth wasn't provisioned, or "it builds" all read as *done* while covering nothing — the same
  false-green class as a masked exit code (Iron Law #2). Require the actual **run log** (executed count > 0,
  all green) as evidence; a **zero-executed or skipped** suite is a FAIL/deferral, not a pass. If the env
  genuinely can't run them, take the honest degrade below (contract-level + log the deferral) — never bank a
  compiled-but-unrun suite as verified.
- **The one carve-out, and where it stops: `baseline.unrunnableHere`** (§ship-cycle Stage 0.5 — Capture a
  test baseline). A suite the environment **cannot start** — no DB reachable, a service absent, a sandbox
  policy refusing the connection, each recorded at PREFLIGHT with a **probe** — is neither a pass nor a
  regression: G9 diffs around it. That is the whole of the exception. A suite that **starts and skips
  itself** (`@Disabled`, zero-executed, DDL/seed/auth not provisioned) is **still a FAIL/deferral**;
  moving it into `unrunnableHere` mid-cycle to get past this gate is the precise abuse this category must
  not enable, and the pre-committed set plus the probe requirement is what forbids it. And quarantine is
  not coverage: a criterion whose only evidence is an unrunnable-here suite ships as
  **`review-only (ci-deferred)`** (§sc-ship G11) on the pre-merge manual gate (§sc-ship G12), never as
  `test`. And quarantining changes the **label, not the work**: 0.2.23's honest degrade still applies in
  full — contract-level seam verification for every criterion the quarantined suite was meant to cover,
  plus the logged deferral. `unrunnableHere` is where you record *why* a suite didn't run; it is never
  permission to skip the fallback that stands in for it.
- Headless is fully feasible for backend (boot + curl) and web (dev server + an E2E driver); native
  mobile is partial (device/emulator screenshot → a vision agent, or a UI-automation CLI).
- **E2E prerequisites**: a live backend + an **authenticated session + seeded data** are needed to
  exercise real flows. If the environment can't provide them (no local backend, no seed/auth), **don't
  fake a pass** — degrade G9 to **contract-level seam verification** (assert the front↔back DTO shapes
  match by reading both sides) and **log the deferral**. Contract verification catches the most common
  multi-stack defect (field/type drift) even without a running system.
- **Reachability precheck — "the record exists but *this* user can't get to it" is a first-class outcome,
  not a skip.** A live backend + auth is not enough: an owner/writer/role-gated feature needs the test user
  to actually own or be permitted to reach the target record, or the detail endpoint returns empty/not-found
  and the affordance never renders — so the flow **cannot be driven live** no matter how healthy the stack
  is. Before driving a flow, check the precondition (can this user reach the record/affordance the change
  touches?). If not: **name it "reachability-blocked"**, degrade that criterion to contract/review-only
  verification, and record *why* (which ownership/role/flag gate blocked it) — carried into sc-ship's claim
  map as a **review-only** label. Do this **once, mechanically**, instead of improvising a "review-verified"
  note by hand every cycle. The blocked state is honest and expected for owner-gated features; hiding it as
  a clean pass is the failure.
- **Device-only UI, no emulator**: when a change's real behavior is visual/native (timer tick, chart/ring
  render, gesture, navigation) with **no front↔back seam**, and no device/emulator is available, automated
  QA = **full-suite regression + integration checks** (real i18n/store/data resolution — not mocks) +
  **typecheck/bundle**. Then **emit a concrete on-device manual checklist** — one observable behavior per fix —
  into the PR and mark it a **pre-merge manual gate**. The checklist IS the honest deferral: don't fake a
  visual pass, and don't silently skip.

## Cut per-cycle spin-up cost (opportunistic, overlay-gated)
In a continuous run, a fresh worktree → dep install → server boot → e2e install *every cycle* dominates
wall-clock. When overlay `env` opts in, reuse instead of re-spinning — but never at the cost of a real
check:
- **Reuse a running dev server** (`env.reuseDevServer` — a bare port, `{port, healthPath}`, or `true` to
  auto-detect): if a server is already healthy, drive QA against it instead of booting a fresh one. Boot
  clean only when the change needs isolation (schema/migration, a server-config or dependency change) or
  the health check fails.
- **Share the dep store across worktrees** (`env.sharedNodeModules`): a pnpm store or a linked
  `node_modules` so each per-stack worktree doesn't re-download the full tree (see PREFLIGHT). This is the
  one knob here that is **destructive on teardown**: a linked `node_modules` is a path by which a
  recursive delete of a worktree reaches into the shared store and wipes it for every other consumer. (A
  pnpm content-addressable store shares by *hardlink* and is not exposed to this — but you rarely know
  from the cycle which form the project used, so the rule applies either way.) Turning this on means
  **stopping to read sc-ship's Cleanup (G13) step 1 and running its link sweep before any worktree is
  deleted** — the rule without its commands is not a procedure.
- **Reuse one e2e install** (`env.reuseE2EInstall`): Playwright browser binaries are cached — reuse a
  single e2e package install rather than `npm ci`-ing it per worktree.

These are **speed knobs, not correctness ones**: if a reused server or its residual state could mask the
change under test, boot clean and say so. Absent the `env` section, always spin up fresh.

## Mobile visual QA — emulator/simulator screenshot loop
Native UI changes **can** be verified automatically when an emulator/simulator is available: drive the
app, capture the screen, and let a vision agent read it — a real "agent sees the UI and iterates" loop,
not just a manual checklist. Two setup traps eat hours if unanticipated — surface them in PREFLIGHT for a
mobile nature:
- **Local dev-client build toolchain pin.** A managed-workflow prebuild can emit a build tool (e.g.
  Gradle) **too new** for the framework's own plugins, which reference an API the newer tool removed → the
  build fails before any screen renders. Pin the build tool to the version the framework supports.
- **Bundler ↔ device networking.** When the dev env and the emulator live in different network namespaces
  (e.g. a Linux dev env + a host-run emulator), the standard `adb reverse`/localhost path can point the
  device at the wrong host and the client gets an empty-stream error. Bind the bundler to all interfaces
  and point the dev client at the dev env's reachable IP directly.
- **Capture**: `adb exec-out screencap -p > shot.png` (binary-safe) → the vision agent reads the PNG.
  Loop: change → reload → capture → read → assess.
- **Auth-gated screens**: get past the gate with the real backend's signup/login to obtain a token — a
  shell can't inject a token into the device's encrypted store. Snapshot the authed state to reuse.
- **Cheaper tier — component isolation (CDD).** Booting the whole app per iteration is the expensive path.
  For component/layout/token regressions, render components **in isolation** (e.g. a Storybook via
  react-native-web) and screenshot them in a **headless browser** — no native build, no emulator, far
  cheaper per shot. Two caveats: (1) it **complements, not replaces** the emulator pass — react-native-web
  drops native-only modules and isn't pixel-identical to native, so whole-app/native visual QA stays an
  occasional top tier; (2) the real token sink is **loop discipline**, not the harness — use the vision loop
  to verify *"does it render / did we break it"*, **not** to iterate subjective aesthetics ("nudge left,
  darker", which doesn't converge and burns tokens). Pin aesthetics in design tokens + acceptance criteria
  up front, where they settle cheaply.
- Still not verifiable this way: camera/scanner, platform health APIs, push, native share/file pickers →
  those go on the on-device manual checklist below. Fall back to that checklist entirely only when **no**
  emulator/simulator can be stood up.

## When to run / skip
- **Run** for real features and any change that crosses a seam.
- **Skip only when `state.size` is `S`** (log the skip reason). A stage does not re-judge triviality for
  itself: PREFLIGHT owns the tier and re-tiering is monotonic upward (§ship-cycle Stage 0.2 — Change-size
  tier), so a run that recorded `M`/`L` cannot skip QA by deciding on its own that it looks isolated.

## Boot smoke (G7b) vs. this stage's bring-up
G7b already ran the eager context-load back in Green (sc-implement). When this stage does a **full
bring-up** (a real boot), that bring-up **re-covers** the same context — so don't add a *third* boot
solely to re-satisfy G7b; note in state that G9's bring-up covered it. G7b stays owned by Green and fires
**even when QA is skipped** (a non-seam framework-wiring change), so a skipped QA never means boot went
unchecked. G9's HTTP bring-up also covers what a `webEnvironment=NONE` context-load can't (web layer,
filters, health endpoint).

## Gate G9 (to advance to `sc-ship`)
- Core flows reproduced; **0 new defects** (new vs `state.baseline`, ignoring `baseline.unrunnableHere`);
  front↔back contracts hold; **every integration/seam suite that *can* run here actually ran (executed
  count > 0) and passed — a compiled-but-unrun or `@Disabled` suite does not satisfy G9** (degrade honestly
  if the env can't run them, don't bank it as passed). A suite in `unrunnableHere` doesn't block this gate
  and doesn't satisfy it either; **if that set is the *only* coverage for the change, G9 is a `degrade`,
  not a `pass`.**
- Set `gates.G9` in state as **`pass` / `degrade` / `fail`, with the reason** — the same three-way shape
  `gates.G7b` already uses (`pass`/`checklist`/`skip`). A `degrade` is **not** a failure: do **not** loop to
  `sc-implement` with a debugger that cannot conjure a database, and do **not** write `pass` because the
  gate had no other value to take. Carry its reason to the pre-merge manual gate, where G12 honors it
  (§sc-ship G12). A gate with no truthful value is how false-green gets written by an honest agent. On a
  genuine `fail`, loop to `sc-implement` with a debugger attached.

## Model routing
qa-tester + verifier run at the **mid** tier.

**Pass `model = state.models['qa']` and `effort = state.effort['qa']` on the qa-tester/verifier calls**
(both resolved at PREFLIGHT) — never the agent type's defaults (Iron Law 6).

**Telemetry**: when you set `gates.G9` in state, append this stage's row to
`state.telemetry.stages['qa']` — the resolved tier, model and effort, plus whatever usage the host
actually exposed (tokens/cost/wall-clock) and `null` for what it didn't. **Never estimate a figure.** The
run's cost readout is assembled from these rows at G13 (§ship-cycle — Cost readout); a stage that writes no
row is simply absent from it, so the readout under-reports rather than lying.
