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
  `node_modules` so each per-stack worktree doesn't re-download the full tree (see PREFLIGHT).
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
- **Skip** for trivial/isolated changes (log the skip reason).

## Gate G9 (to advance to `sc-ship`)
- Core flows reproduced; **0 new defects**; front↔back contracts hold. On failure, loop to
  `sc-implement` with a debugger attached. Set `gates.G9` in state.

## Model routing
qa-tester + verifier run at the **mid** tier.

**Pass `model = state.models['qa']` on the qa-tester/verifier calls** (resolved at PREFLIGHT) — never the
agent type's default model (Iron Law 6).
