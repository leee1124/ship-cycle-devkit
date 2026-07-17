# Changelog

## 0.2.22 — Full-context boot/context-load smoke gate for framework-wiring changes (#40)

A change can pass **every** gate — Red-first unit tests (hand-assembled collaborators), integration tests
(sliced context), and multi-lens review (reads code) — and still ship an app that **won't boot**, when the
defect is in framework wiring. None of those gates load the *full* application context. Real field
incident: an **unchanged** broad `@MapperScan` proxied a **new plain interface** as a mapper →
`BindingException` at bean creation → context fails to start; it passed 37 unit tests + a sliced-context IT
+ an opus review. Adds gate **G7b** (docs-only, framework-agnostic):

- **Nature-level trigger, not a per-diff guess.** A `changeNature` entry that declares a project-defined
  `bootCheck` command marks the nature as having a loadable context; G7b (sc-implement, Green) then runs it
  on **every non-inert change** to that nature's production sources. Skip only **provably-inert** diffs
  (docs/comments, tests, non-runtime assets); production resources (`src/main/resources/**`), build/dep
  manifests, and framework config are **non-inert by default**, and **when unsure → boot**. (An earlier
  path-glob "touches wiring" trigger was rejected by the kit's own design critic: it would have *skipped*
  the very incident above — the changed file was an ordinary interface, not a config file.)
- **An outcome floor, not dialable ceremony.** The only thing dialed is whether a nature has a loadable
  context at all — UI-leaf natures declare no `bootCheck` and never boot, so leaf changes pay nothing.
- **Cheap + eager + honest.** Prefer a standing `@SpringBootTest(webEnvironment=NONE)` load (~seconds, often
  already in the suite); it must force **eager** bean creation (lazy-init can false-pass the eager failure).
  A selector matching zero tests is a **misconfig FAIL**, not a pass. It proves the DI graph is
  constructible — the web layer/filters/health stay sc-qa's HTTP bring-up (when QA does a full bring-up it
  re-covers G7b, so no third boot).
- **CI-safety caveat.** Needs a full-context-capable env (a superset of the sliced ITs'). The gate lives in
  the **cycle** (local/pre-PR); never wire an env-dependent boot into a CI path lacking its deps — it
  red-blocks unrelated PRs, and during an outage blocks the very fix that restores the service. When a
  context can't be loaded locally, degrade to a named pre-merge checklist item (surfaced by sc-ship), never
  a silent pass.

Docs-only; framework-agnostic; no behavioral code. Closes #40.

## 0.2.21 — Two silent-failure guards from a real 2-cycle field run (#41)

Field notes from an external user running two ship-cycles concurrently on a Spring Boot + MyBatis repo
surfaced two ways the cycle could *look* green while a floor silently failed. Both fixed as guidance +
overlay wiring (docs-only, framework-agnostic):

- **No false-green from a piped exit code (#41 proposal 3).** `cmd | grep | tail` reports the tail's exit
  status, so a failing build/test — or a `command not found` from a toolchain that never reached `PATH` —
  reads green. Iron Law #2 now forbids judging pass/fail from a piped exit code; sc-implement (G5/G6) and
  sc-ship (G11) require the command's own exit status or the machine-readable report (surefire/JUnit XML,
  runner JSON), never scraped stdout — and note that `set -o pipefail` alone doesn't rescue a `grep`-in-the-
  pipe check (grep exits `1` on no match → a passing build turns false-RED; drop the pipe).
- **Security reviews can't run on a security-refusing model (#41 proposal 2).** Risk-based routing could
  send a security/authz review to a model that refuses security analysis, which then silently no-ops.
  Overlay `modelRouting.securityReviewModel` pins the model the `security`/`authz` review lenses use,
  overriding their tier — sc-review spawns those lenses with it and PREFLIGHT logs `SC-ROUTE-AVOID`. A
  fail-closed floor, since a security review that quietly checks nothing is worse than a loud stop.

Also captured from the same field run: "reviewer != author" adversarial separation and STAY-IN-SCOPE →
file-out-of-scope both earned their keep and are unchanged. Deferred to follow-ups: per-cycle state for
concurrent cycles (#41 proposal 1) and requiring integration tests to *execute*, not just compile (#41
proposal 4).

Docs-only; framework-agnostic; no behavioral code.

## 0.2.20 — Proportional strictness: env graceful-degrade + the outcomes/ceremony bright line

Ran the kit's own design cycle (brainstorm → design → adversarial critic) on "make strictness
risk-proportional." The critic descoped it hard, and correctly: in a docs-only kit the "load-bearing vs
skippable" call is an LLM eyeballing an *unvalidated* config, so a nuanced degrade taxonomy would *reduce*
safety. What survived:
- **One narrow PREFLIGHT carve-out**: a schema-invalid `env` block (a pure cost knob whose documented
  fallback is "spin up fresh") emits `SC-DEGRADE-ENV` and continues instead of aborting the cycle. Every
  other section — and any unparseable file — still fails closed. `env` only, because it can never touch a
  correctness floor.
- **The bright line, stated once** (Lightweight path): *ceremony* (stage count, tier, worktree, lens
  breadth, QA-skip, TDD-harness form) is dialable; *outcomes* (verification ran + read, fresh-eyes review,
  the fail-closed floors, a failing test first) are never dialed. When unsure, it's an outcome.
- **Monotonic risk re-escalation** (PREFLIGHT step 6): the risk label dials ceremony only, never an
  outcome; a later stage that reveals a higher-stakes axis re-escalates — adding ceremony back, never
  removing an outcome.

Explicitly rejected by the cycle: inverting the default to proportional-by-default (it removes the
fail-safe default), a multi-section degrade allowlist, and documenting a risk→lightweight-path dial that
doesn't exist. **strict-by-default is unchanged.**

Docs-only; framework-agnostic; no behavioral code.

## 0.2.19 — Per-cycle env-cost knobs (opportunistic reuse)

In a continuous ship run, every cycle re-pays worktree → dep install → server boot → e2e install; over
many cycles that overhead dominates wall-clock. Adds an optional overlay `env` section and the guidance to
honor it — opt-in, and always subordinate to correctness (closes #22):
- **`env.reuseDevServer`** (a bare port, `{port, healthPath}`, or `true` to auto-detect): sc-qa drives
  against an already-healthy server instead of booting a fresh one — booting clean only when the change
  needs isolation or the health check fails.
- **`env.sharedNodeModules`**: PREFLIGHT shares one dep store (pnpm store / linked `node_modules`) across
  worktrees so each doesn't re-download the full tree.
- **`env.reuseE2EInstall`**: reuse one Playwright/e2e install (browser binaries are cached) instead of
  `npm ci` per worktree.

These are speed knobs, not correctness ones — absent the `env` section, the plugin always spins up fresh.
The plugin is docs-only: it *instructs* the reuse; the actual caching lives in the operator's harness.

Framework-agnostic; docs-only; no behavioral code.

## 0.2.18 — Observability commands (status / resume / ship)

The cycle state file (`.claude/.ship-cycle-state.json`) existed but there was no quick way to inspect a
run mid-flight, resume an interrupted one, or jump to ship once gates pass. Adds a `commands/` surface
(auto-discovered alongside `skills/` — no manifest change) with three user-invokable, read-only-by-default
commands (closes #25):
- **`/ship-cycle-devkit:status`** — print stage, gate table (G1–G13), loop counts, resolved model routing,
  and worktree. Read-only.
- **`/ship-cycle-devkit:resume`** — resume from the last incomplete stage via the ship-cycle PREFLIGHT
  resume path; never restarts completed stages or re-inits state.
- **`/ship-cycle-devkit:ship`** — jump to `sc-ship` only when the required upstream gates (G1–G9) are
  green; refuses and points back to the owning stage otherwise (Iron Law #3).

Note: the `/sc:` short prefix from the issue isn't used — Claude Code derives the command namespace from
the plugin `name`, so commands are `/ship-cycle-devkit:*` (renaming the plugin would break existing
installs). Commands are declarative markdown prompts, not executable code.

Framework-agnostic; declarative commands, no behavioral code.
## 0.2.17 — Audit follow-ups: prompt symmetry, gate & SSOT consistency

Four small consistency fixes from the 0.2.16 audit (closes #32, #33, #34, #35):
- **TDD symmetry in impl prompts** (#32): `impl-web` and `impl-mobile` gained a `## Testing (TDD —
  required)` section — test-first (Red→Green), extract pure logic for render-less UI, no vacuous test —
  matching `impl-backend` and constitution §8 / Iron Law #1.
- **G13 defined** (#33): the gate table listed only G1–G12 while the pipeline row claimed G10–G13. Added
  the G13 row (merged branch deleted local+remote, worktree removed if present, base synced), relabeled
  sc-ship's "Cleanup (Stage 13)" → "Cleanup (G13)" (stages are 0–7; cleanup is a gate, not a 13th stage),
  and wired sc-ship to set `gates.G13 = pass` after cleanup so the gate is actually tracked in state.
- **Loop-cap SSOT** (#34): dropped the duplicated literal "3" from `sc-design` and `sc-review`; both now
  say "respect the orchestrator's loop cap" — the value lives only in `ship-cycle`.
- **impl-mobile parity** (#35): added the no-silent-`catch {}`/log rule (§6, matching `impl-web`) and a
  "consume the actual serialized DTO shape" rule (mirrors the shape-verification language in
  `sc-design`/`sc-audit`; complements `impl-backend`'s "never return entities").

Docs-only; framework-agnostic; no behavioral code.

## 0.2.16 — No-magic-numbers / named-constant coding standard

The kit reached for the narrow design-token/i18n cousins of this rule (no hardcoded colors/spacing/copy)
but never stated the general one, so a literal with domain meaning (a `≥60` deload threshold, a status
string, a `setInterval` period) was authored, reviewed, and shipped with no rule naming it. Added as a
framework-agnostic Clean-Code baseline, language-aware and enforced at review:
- **Constitution §3**: no magic numbers/strings — extract any domain literal to a named constant; a
  closed, related set becomes an `enum` (Java) / a union literal type or an `as const` object (TS —
  **not** `enum`) / `Object.freeze` (JS), with behavior on the set where it has any (an anemic constant
  bag repeats the anemic-model smell, #7). Constants now join the "meaningful names" rule.
- **sc-review quality lens**: magic numbers/strings is now a named anti-pattern — a rule no lens checks is
  dead — including a closed set not modeled as an enum/union/frozen object.
- **impl prompts** (backend/web/mobile): each states the rule in its stack idiom — Java enum-with-behavior;
  TS union / `as const`, **avoiding `enum`** — on top of the existing design/theme-token rules.

Docs-only; framework-agnostic; no behavioral code.

## 0.2.15 — Design-consistency gate: reuse before create

Consistency is decided at design time, not caught at review time — so a crude, uncoordinated surface
(three different empty states, a bespoke spinner where a progress component exists, ad-hoc spacing) is
almost always "invented instead of reused." Framework-agnostic; the overlay supplies *which* tokens and
components exist, the plugin enforces *reuse* of whatever they are.
- **Overlay `design` contract** (`ship-cycle.config` example + schema): declare the project's design
  source of truth — `tokens`, `components`, and an optional design-system `guide`. Optional; omit to have
  the designer inventory the repo ad hoc.
- **sc-design reuse-before-create gate** (UI changes): the design must consume the design source of truth
  and resolve every color/spacing/type-scale/empty-loading-error state/progress indicator/icon from an
  existing token or component. A **new** visual primitive needs a one-line justification of why no
  existing one serves it ("faster to inline it" is not one). Name the canonical pattern per recurring
  surface so the implementer wires the shared one, not a new copy.
- **sc-review designer lens → named anti-patterns** (was a vibe check): hardcoded design values that
  bypass tokens; a reinvented empty/loading/error/card/button where a canonical component exists;
  decorative-not-informative indicators (a fixed spinner where a fill/ring belongs); off-scale type/space;
  the accessibility floor (touch target, labels, contrast, modal focus); emoji-as-icon.
- **Design-consistency floor** (sc-review severity): a change that reinvents an existing
  token/component/pattern is at least a finding even when it "looks fine" in isolation — the cost is
  cumulative fragmentation, paid one diff at a time. Surface it as reuse-or-justify, never a silent pass.

## 0.2.14 — Iron Law mechanization: evidence strength, reachability, model pinning, sibling-PR & artifact guards

Five framework-agnostic hardenings distilled from a long continuous-ship run, each turning an
operator-discipline step into a mechanical one:
- **Evidence *strength* per claim** (`sc-ship` G11): mapping a claim to "evidence" isn't enough — a
  live-driven criterion and a review-only one (live was blocked) read identically unless annotated by hand.
  Tag every claim **live / test / review-only** and surface it in the PR claim map, so a review-only
  fallback can't silently masquerade as a live pass. `review-only` is a named, legitimate outcome — not a
  hidden one.
- **QA reachability precheck** (`sc-qa`): a live backend + auth still can't drive an **owner/role-gated**
  flow when the test user can't reach the target record (detail endpoint returns empty → the affordance
  never renders). Made "reachability-blocked" a first-class outcome — check the precondition, degrade that
  criterion to contract/review-only, record *why*, and carry it into sc-ship's claim map — done once
  mechanically instead of hand-writing a "review-verified" note every cycle.
- **Mechanical model pinning on review lenses** (`sc-review`, Iron Law 6): since lenses are
  `general-purpose` spawns, the review tier lives only in `model=` and one omission silently downgrades a
  top-tier review to a cheap default. Added: read `model = state.models.review` on every spawn (resolve
  once, copy every time), an anti-drift restatement before fan-out, and an **optional** pinned lens-agent
  path that must degrade gracefully to `general-purpose` + `model=` on hosts without custom agent types
  (enforcement without trading portability).
- **Sibling open-PR conflict probe** (`sc-ship` G12): the merge-tree check compares against the base only,
  but two still-open PRs collide with each other on append-only files (i18n `.properties`/bundles/barrels
  where each appends at EOF). Added a heads-up that lists open PRs touching any file in the diff so the
  merge order is a conscious choice, not a merge-time surprise.
- **Artifact-exclusion on commit** (`sc-ship` G12): overlay `commit.excludePaths` lists generated/CI-built
  paths (e.g. a bundle dir a QA step built locally) that sc-ship auto-reverts / never stages, keeping
  commits source-only. Absent the setting, still skip obvious build outputs (`dist/`, `build/`) and flag
  rather than commit blindly.

Docs-only; framework-agnostic; no behavioral code. Adopted from issues #21, #23, #24, #27, #28.

## 0.2.13 — sc-ship: verify the issue-closing token actually landed in the PR body

One framework-agnostic `sc-ship` hardening from a live cycle where a fully-done issue stayed open after
its PR merged:
- **Re-fetch and assert the closing token, don't trust that you wrote it** (`sc-ship` G12 + gate): the
  rule to link the tracked issue with `Closes #NN` already existed, but nothing verified it landed. A PR
  whose body summarized the work in prose (a `#NN —` heading) but omitted the `Closes` keyword merged
  clean and left the finished issue **open** — the host only auto-closes on the `Closes`/`Fixes`/`Resolves`
  keyword, and it must be repeated per issue (`Closes #90, closes #91`, not `Closes #90, #91`). Added: after
  opening the PR, re-fetch the created body and assert the exact intended token for **every** tracked issue
  in state (`Closes` when fully done, `Refs` when partial); a bare mention or title `(#NN)` does not count.
  Missing/keyword-less → patch the body before merge, or `comment + close` if already merged. The gate now
  includes this assertion. Same failure class as the cold lens: the narrative reads complete while the
  machine-readable token silently leaked.

Docs-only; framework-agnostic; no behavioral code.

## 0.2.12 — sc-audit: surface-type drift (phantom fields) + "wired ≠ works" target validation

Two framework-agnostic `sc-audit` hardenings from live parity-migration recon (from #14, #15):
- **Surface-type drift / phantom fields** (Step 3 cross-cutting): cross-reference each surface's
  **self-declared** types against the source-of-truth schema and report fields present in one but not the
  other — **surface-only** = phantom/stale (exists in no backend DTO; renders always-`false`/`undefined`, a
  dead conditional new features inherit), **source-only** = unmodelled. Structural drift the behavioral
  matrix misses — catches "the type is wrong *before* you build on it."
- **"Wired ≠ works"** (Step 1 inventory): in a migration audit, don't treat a legacy source screen as a
  real feature just because it's menu-registered + call-wired. Flag **"possibly non-functional"** when
  handlers are stubs / there's no live data path (no real backend call, hardcoded data, dead submit), and
  **ask the domain owner to confirm it actually functioned** before it becomes a build/parity target —
  rebuilding a never-worked screen is pure waste.

Docs-only; framework-agnostic; no behavioral code. Adopted from issues #14, #15.

## 0.2.11 — lifecycle hardening: plural-case tests, spec-blind cold review, pre-PR merge verification

Three framework-agnostic hardenings distilled from live cycles (consolidated from separate branches):
- **Cover the plural case (N≥2)** (`sc-tdd` + `sc-qa`): a test that exercises **one** item passes while a
  bug that only manifests with **two or more** hides — off-by-one/ordering, batch writes, dedup/merge,
  pagination, and multi-row inserts whose driver returns only one generated key (so an in-memory
  "keys → child rows" link silently cross-wires at ≥2 rows). When the change touches a collection / batch /
  id-key assignment / ordering / any for-each path, write the N≥2 case and **assert the cross-item
  relationship** (row A links to A, B to B), and have `sc-qa` exploration probe the batch case explicitly.
- **Spec-blind "cold" review lens + real-world-state floor** (`sc-review`): a heavy multi-lens review still
  ships bugs an outside reviewer catches first-pass, because every lens is anchored to the author's spec —
  a wrong premise gets rated "as-designed" by all of them. Added an always-on **cold lens** that gets
  **only the diff** (no design doc/canonical) and assumes nothing the author claims; a cross-cutting
  **real-world-state probe** (legacy/pre-existing rows, empty & N≥2, unsaved/no-id-yet, re-run/partial-save);
  and a **data-integrity floor** — a change that can persist wrong/duplicate/lost/orphaned data is at least
  **High**, even if it "matches the spec" or "replicates a legacy quirk" ("the old system did it too" is a
  parity note, not a severity downgrade).
- **Verify clean merge before opening a PR + robust worktree teardown** (`sc-ship` G12 + cleanup): the PR
  stage never checked mergeability — a branch cut before a sibling merged, or one that merely *appends* to
  shared files (i18n bundles, lockfiles), opens **dirty** and only conflicts at merge time. Added a pre-push
  `git merge-tree` conflict probe + post-push `mergeable` poll ("merge base + resolve, re-verify" on
  conflict; re-check open PRs on request). Teardown now uses `git worktree remove --force` + a
  `git worktree prune` fallback (a build tool holding file handles — `node_modules` on Windows — no longer
  aborts cleanup); a failed directory delete is a **warning, not a gate**.

Docs-only; framework-agnostic; no behavioral code. Consolidated from #13, #16, #17.

## 0.2.10 — multi-cycle robustness: test baseline, state lifecycle, axis-split design, scope re-classification

Lessons from running the lifecycle repeatedly on one repo (sequential cycles) and on a change that grew
full-stack at the design gate:
- **Test baseline at PREFLIGHT** (`ship-cycle`): when the base branch already has failing tests, every
  later stage — and every parallel implementer — wastes effort re-deriving "is this my regression or was
  it already red?" (stash-and-compare, over and over). Added: run the suite on the **base commit once**,
  record the pass/fail set in `state.baseline`, and have gates **G6/G9 diff against it** — only a *new*
  failure blocks. `sc-implement` G6 now says the same, so implementers stop re-litigating pre-existing reds.
- **State lifecycle across runs** (`ship-cycle`): a state file left at `stage: complete`/`failed` from a
  finished cycle was being hand-clobbered to start the next one. Added: PREFLIGHT **archives** a finished
  state and initializes fresh; only a mid-pipeline `stage` is a resume candidate. This is what makes
  **sequential cycles** on one repo clean.
- **Split the architect by axis** (`sc-design`): for cross-cutting/full-stack designs, run N architects in
  parallel on **exclusive slices** (each stating its seam contract), then **one** critic reviews the
  **union** — so it catches *inter-axis* contradictions (mismatched seam signatures, one axis's "no schema
  change" vs another's "persist a new field"). The design-stage analogue of `sc-implement`'s partitioning.
- **Scope can be re-classified at the design gate** (`ship-cycle` + `sc-design`): change-nature/model
  routing is **not one-shot**. When design reveals a stack/axis the initial diff didn't show (a
  "frontend-only" change that needs a new backend endpoint), re-run classification, add the implementer
  axis, and route for the true scope — a design-gate scope growth is normal, not a failure.
- **Out-of-scope defect disposition** (Iron Law 5): a real defect found *outside* the current scope (a
  latent bug, dead-code path, data error) → **file it and keep going**; don't fix it in this branch (scope
  creep) and don't silently drop it. "Found, filed, not fixed here."

## 0.2.9 — waved execution: blast-radius control; visual QA: cheaper CDD tier

Refinements to 0.2.8 after review:
- **Atomic contract-change rule needs blast-radius control** (`sc-implement`): with dozens of call sites,
  the naive "each parallel agent runs `tsc` in its loop" backfires in a *shared* working tree — a
  whole-project typecheck sees other agents' half-finished edits and misattributes/"fixes" foreign files.
  Added: land **contract (signature/type) changes + their call sites as a serial micro-wave, verified once**,
  before the parallel leaf waves; and if kept parallel on a shared tree, on barrier failure **bisect errors
  → owning file → re-dispatch only that owner** instead of stalling the wave. In-loop self-verify is only
  safe under worktree isolation.
- **Visual QA has a cheaper tier** (`sc-qa`): component isolation (CDD — a Storybook via react-native-web,
  screenshot in a headless browser) verifies component/layout/token regressions with no native build/
  emulator. Two caveats recorded: it **complements, not replaces** the emulator pass (native fidelity gaps),
  and the real token sink is **loop discipline** — use the vision loop for render/regression verification,
  not subjective aesthetic nudging (pin aesthetics in tokens up front).

## 0.2.8 — mobile visual-QA harness + waved cross-cutting execution

Learned from a real large mobile UI reskin run:
- **Mobile visual QA can be automated** (`sc-qa`): an emulator/simulator screenshot loop ("agent sees the
  UI and iterates") is viable — not just a manual checklist. Two setup traps that eat hours, both with
  generic fixes: a managed prebuild can pin a build tool **too new** for the framework's own plugins (build
  fails before any render), and bundler↔device networking across namespaces sends the device to the wrong
  host (empty-stream error). Capture via `adb exec-out screencap`; get past auth gates with the real
  backend's signup/login.
- **Waved execution for large single-stack cross-cutting changes** (`sc-implement`): worktree-per-stack
  doesn't help when collisions are *within* one stack (a design-system reskin). Serial foundation wave
  (tokens/shared wrappers/i18n) → parallel waves over **exclusive file-ownership partitions** → **atomic
  contract-change rule** (a signature change updates its call sites in the same wave, keeping the barrier
  typecheck green) → resource-aware concurrency (cap agents when a heavy local process is up).
- **Fail-closed hooks block parallel agents** (`sc-design`): a turn-end fail-closed gate (i18n symmetry,
  lint) blocks *parallel* implementers on the shared resource — identify at design time and pre-register/
  freeze it in the serial foundation step.

## 0.2.7 — delegation criteria + high-stakes lightweight review

Learned from a real EAS build-fix run:
- **Delegate vs act inline** (`ship-cycle`, new section): the orchestrator is *not* a pure conductor —
  spawning a subagent isn't free (boot + re-brief + re-read), so a trivial edit is cheaper done inline
  even on the orchestrator's pricier, session-fixed model. Delegate only when it buys **independence**
  (adversarial stages — a reviewer can't be the author), **tier savings on substantial work**,
  **context hygiene** (the orchestrator is long-lived; hand off context-heavy reads to a read-and-discard
  subagent), or **parallelism**. The line is "does delegation buy something", not diff size.
- **Lightweight path drops tiers — except small-but-high-stakes** (`ship-cycle`): trivial work runs
  mid/low, but keep the higher review tier when cost-of-being-wrong is high or verification is expensive
  (build/release config, dependency/lockfile, contracts, data-loss, security). Tier by
  cost-of-being-wrong × verification-difficulty, not diff size — a high-tier review of a 10-line dep bump
  caught a stale-lockfile defect a cheap pass would likely have missed.
- **Lockfile sync** (`sc-implement`): changing a dependency manifest that has a committed lockfile
  requires regenerating the lockfile in the same change — CI/release installs from the lockfile
  (`npm ci`, `--frozen-lockfile`), so a manifest-only edit is inert or re-breaks the build.

## 0.2.6 — model routing, actually enforced

Closes the gap where tier→model routing was *documented* but silently skipped at runtime — a review
meant for the high tier ran on a specialized agent type's cheaper default model, unnoticed.

- **Iron Law 6 (new)**: never spawn a stage agent on a default model. Resolve tier→model at PREFLIGHT and
  pass `model=` explicitly. It names the exact trap: a specialized agent type (`quality-reviewer`,
  `security-reviewer`, `architect`, …) carries its *own* default that silently overrides your tier when
  `model=` is omitted.
- **PREFLIGHT pre-resolves per-stage models** into `state.models` (risk upgrades applied) and **prints
  them** (auditable). This turns "remember to bridge the tierMap" into "copy a concrete value" — the
  difference that makes it actually happen.
- **Every stage skill** now carries a point-of-use line: `Pass model = state.models['<stage>']` at the
  spawn site, not buried in a routing section.
- State schema gains `models`; the tier→model bridge doc spells out the default-model trap and how
  mixed-tier stages (e.g. `sc-ship`) resolve per-role.

## 0.2.5 — state-file handoff between stages

- **State-file handoff rule** (orchestration plumbing, **not an agent**): each stage writes its output
  to a file under the run's artifact dir; the next stage reads it; the orchestrator passes only pointers
  (paths) in the state file, never a full artifact through its own context.
- **Verbatim by construction — zero cost, zero distortion**: files carry artifacts whole. This is
  deliberate — summarizing between stages risks silently dropping an unresolved objection, a gate
  blocker, or failing evidence, and verbatim carrying is a code job, not a model's, so no agent is spent
  on it. (Earlier drafts modeled this as a cheap "relay" agent; a truly-verbatim LLM pass is redundant
  with plain file passing, so it's plumbing, not a role.)
- **Put a model in a handoff only for a trusted transformation** (extract acceptance criteria, reformat
  for the next tool) — then pick the tier that transformation demands, not a blanket cheap summarize.

## 0.2.4 — parity-audit discipline

Adds a new à-la-carte skill, learned from a real cross-platform integration miss:
- **`sc-audit`** (new, not in the default chain): a static **cross-surface parity audit**. Compares every
  consumer surface (web, mobile, CLI, SDK, another service) against a single source-of-truth contract and
  emits a module-by-module gap matrix + cross-cutting risk checks (authz/paywall leak, entity-return,
  data drift, i18n, file/export) + P0/P1/P2 priorities + a **cutover/ship verdict**
  (parallel-run only / cutover-ready / ship-ready).
- **Why it's separate from `sc-design`**: sc-design verifies the contract *for the feature in hand*; an
  entire surface can be built on assumed contracts and stay green until the first real integration, when
  most screens break at once. A dogfood run shipped a whole web app that "deployed" but almost nothing
  worked end-to-end — the class of failure a per-feature guard can't see. sc-audit is the macro sweep;
  run it before a first cross-surface integration or on a large/ahead-of-backend surface.
- **Core rule carried over**: "endpoint exists ≠ integrated" — only ✅ when the surface actually calls it
  with the real serialized shape; check the composition root for which implementation is wired in.
- **Overlay**: new optional `audit` section (`sourceOfTruth` / `surfaces` / `modules` / `reportDir`);
  falls back to `changeNature` globs and logs when defaults are used. Schema + example updated.

## 0.2.3 — second-dogfood feedback (mobile bug-fix cycle)

Learned from a React Native (Expo) bug-fix run on a monorepo:
- **Lens → agent fallback** (`sc-review`): review lens names are *roles*, not fixed agent types. If no
  dedicated reviewer exists (many envs have no `performance-reviewer`/`algorithm-reviewer`), spawn a
  `general-purpose`/`code-reviewer` with the lens's anti-patterns as focus — verify the type exists first,
  never abort on a missing agent. Scale fan-out to the host (sequential on constrained machines).
- **Device-only QA without an emulator** (`sc-qa`): for visual/native changes with no front↔back seam and
  no device available, automated QA = full-suite regression + integration checks + typecheck/bundle, then
  **emit a concrete on-device manual checklist** into the PR as a pre-merge gate. The checklist is the
  honest deferral — don't fake a visual pass or silently skip.
- **No UI/component test harness** (`sc-tdd`): when the stack can't unit-test rendered output (RN without a
  component lib), extract pure logic (formatters, selectors, time/geometry math, i18n) and write Red there;
  thin UI wiring is covered by the designer lens + the on-device checklist, not faked component tests.
- **Overlay commands run from repo root + gitignore run state** (README / example): use root-relative test
  commands (`cd apps/x && ./gradlew …`, `npm run test -w …`, `npx tsc --noEmit -p …`); add
  `.claude/.ship-cycle-state.json` to `.gitignore`.

## 0.2.2 — first-dogfood feedback

Improvements learned from the first real end-to-end run (a web dashboard feature):
- **Verify contracts, never assume** (`sc-design`): read the actual endpoint/entity/serialized response;
  an assumed API shape propagated to the implementer and caused a runtime crash. Now a hard rule.
- **Worktree is conditional** (`ship-cycle`/`sc-implement`): create it only for stack-split/parallel
  work; single-track changes use a plain feature branch (worktree was pure overhead otherwise).
- **Complexity exception to cheap-path-first** (`ship-cycle`): start complex work (novel algorithms,
  intricate SVG/canvas UI) at the higher tier instead of wasting a failed mid-tier attempt.
- **UI-only merges design+implement** (`sc-design`): don't force a separate READ-ONLY architecture doc
  for a widget; keep the critic/accessibility pass.
- **G9 E2E degrades honestly** (`sc-qa`): without a live backend + seeded auth session, degrade to
  contract-level seam verification and log the deferral — never fake a pass.

## 0.2.1 — review discipline (borrowed from Superpowers)

`sc-review` keeps its multi-lens/parallel structure and adds the output discipline from Superpowers'
`requesting-code-review` reviewer:
- **Plan alignment** as a cross-cutting check (does the impl satisfy the acceptance criteria — catch
  "built the wrong thing" at review, not final verify).
- **Production readiness** check for contract/schema/public-surface changes (backward compat, migration, docs).
- Per-lens **output discipline**: mandatory Strengths, actual-severity issues, and a clear merge
  **verdict (Yes/No/With-Fixes)**; no severity inflation; no verdict without reading the code.

## 0.2.0 — composable restructure

Refactored the single monolithic `ship-cycle` skill into an orchestrator + one skill per stage, and
adopted structural patterns from mature frameworks.

### Added
- **Composable stage skills**: `sc-brainstorm`, `sc-design`, `sc-tdd`, `sc-implement`, `sc-review`,
  `sc-qa`, `sc-ship` — each short and focused, usable à la carte. `ship-cycle` is now a thin
  orchestrator that chains them.
- **Dedicated brainstorming stage** (`sc-brainstorm`): refuse to code a vague goal; clarify + propose
  a design + get acceptance first.
- **Full git worktree isolation**: PREFLIGHT creates a feature worktree; `sc-implement` runs
  stack-split implementers in per-worktree isolation for collision-free parallelism.
- **Real state file** (`.claude/.ship-cycle-state.json`): tracks stage, per-gate status, and loop
  counts so "loop cap 3" and resume don't depend on the model's memory.
- **Tier → model bridge**: overlay `modelRouting.tierMap` maps tier names to real model ids; the skill
  passes `model=<resolved>` per `Task`.
- **Overlay JSON Schema** (`docs/ship-cycle.config.schema.json`) + defined precedence for overlapping
  globs (most-specific wins) and malformed-config behavior (stop, don't silent-fallback).

### Fixed
- Dead file references: bundled files are now addressed via `${CLAUDE_PLUGIN_ROOT}`.
- Honest runtime docs: states the specialized-subagent dependency and the stock-Claude-Code fallback.
- Corrected the trigger form to `/ship-cycle-devkit:ship-cycle`.

## 0.1.0 — initial

Portable gated dev-lifecycle plugin: single `ship-cycle` skill, engineering constitution, impl prompt
templates, project overlay, risk-based model routing. Borrowed Iron Laws + Red Flags and a discovery
gate from Superpowers.
