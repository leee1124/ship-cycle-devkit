# Model routing, effort, and the cost readout

PREFLIGHT resolves every stage's model and effort once (§ship-cycle Stage 0.7) and each stage spawns with
the resolved values. This file holds the reasoning behind those choices and the post-run readout; the
orchestrator carries only what it needs at resolve time.

## Assign by cost-of-being-wrong × cost-of-verification, not by role name

- **Base pyramid**: *high* on design and security/quality review; *mid* on implement/QA; *low* on
  docs/style/plumbing. (Inter-stage handoff is not a model step — see the state-file handoff rule.)
- **Risk-gated upgrade**: a high-risk change bumps the *single matching role* to *top* —
  auth/payment → security review, schema/API-contract → design, complex algorithm → algorithm review. Match
  the *kind* of risk rather than always upgrading the same role. Usually 0–1 upgrades per run.
- **Tier → model bridge (required to execute)**: overlay `modelRouting.tierMap`, e.g.
  `{"top":"opus","high":"opus","mid":"sonnet","low":"haiku"}`. PREFLIGHT resolves each stage's tier into
  `state.models` and every agent call passes `model = state.models[<stage>]`. Without a tierMap, tiers are
  advisory only.
- **Bigger levers than tier choice**: prompt caching (cache the repo/diff/design doc), the effort dial, and
  "cheap path first" for implementation — mid tier, verify, escalate only the failing fix. Exception: for
  inherently complex work (novel algorithms, intricate SVG/canvas UI) start at the higher tier, where
  cheap-path-first only buys a wasted failed attempt.

## Why `model=` is passed explicitly

A specialized agent type — `quality-reviewer`, `security-reviewer`, `architect` — carries its **own**
default model that silently overrides your tier when `model=` is omitted. That is precisely how a review
intended for the top tier ends up on a cheap default with nobody noticing. Pre-resolving into
`state.models` at PREFLIGHT turns "remember to bridge the tierMap" into "copy a concrete value".

## Security-refusing-model guard

Some models refuse security analysis, so a security/authz review routed to one silently no-ops: it "ran"
and checked nothing. Overlay `modelRouting.securityReviewModel` pins the model those lenses use, overriding
their tier — set it to the most capable model that will actually *do* security review. It is a fail-closed
floor, not dialable ceremony, and it is opt-in because only the operator knows which model refuses.

## Effort — on the judgment/mechanics axis

Tier says *which model*; effort says *how hard it thinks*. Keying effort to stage names leaks, because the
two most judgment-dense pieces of work in the cycle answer to no stage's name: **root-cause analysis** and
**triage** (which findings are real, which are false positives, which are out of scope). Price the work and
let the size tier scale it — the table lives in the orchestrator, since PREFLIGHT reads it at resolve time.

Two consequences are deliberate:

- **Review effort scales with the size tier** instead of being pinned at the top. Pinning every review at
  maximum is what turns a corroborated one-line fix into a six-figure-token verification pass, so a blanket
  "reviews are always xhigh" rule would leave the actual waste untouched.
- **The edit inherits the tier.** A one-liner whose cause is already pinned is `low`; a multi-file refactor
  *is* design work and is priced as such.

Overlay `modelRouting.effortMap` bridges these levels to whatever the host calls them, exactly as `tierMap`
does for models. Without an `effortMap`, effort levels are advisory only.

**Root-cause analysis and triage are never dialed down** — they sit at `high` on a Tier S change as much as
a Tier L one, because they are outcomes rather than ceremony.

## Cost readout (post-run)

Model routing is this kit's efficiency claim, and enforcement is not measurement: a per-stage tier that is
pinned but never counted leaves the claim unfalsifiable on *your* repo, and leaves `tierMap`/`effortMap`
tunable only by intuition. So the cycle reports what it spent.

- **Accumulate as you go.** When a stage sets its gate in state, it appends to
  `state.telemetry.stages[<stage>]` the resolved tier, model and effort plus whatever usage the host
  exposes — tokens, cost, wall-clock. Each stage skill carries this instruction next to its gate; the
  orchestrator does not write rows on their behalf, because a stage running as a subagent is the only party
  that can see its own usage. `telemetry.upgrades` records which risk-gated upgrades fired.
- **Never invent a number.** Most hosts expose no per-agent token count. Record `null` and print
  `unavailable` for what you cannot measure; the resolved tier/effort per stage is always recordable and is
  itself the useful half. A fabricated cost table is worse than an honest gap — it is the same false-green
  class as a scraped exit code.
- **Emit before anything in G13 deletes anything.** The state file lives in the cycle's working directory,
  which is the worktree itself when PREFLIGHT created one, so removing the worktree destroys `telemetry`
  just as surely as deleting the file. sc-ship emits the readout as the **first** act of G13 and writes it
  to an artifact dir outside the worktree.
- **Read-only.** The readout changes no gate and blocks nothing; it exists so an operator can see whether
  routing paid off here and tune the maps with data instead of an asserted percentage. `/status` prints the
  same table mid-run.

## Exception — small but high-stakes

Keep the higher review tier even for a tiny diff when cost-of-being-wrong is high or verification is
expensive: build/release config, **dependency/lockfile changes**, API/data contracts, data-loss paths,
security. Tier by cost-of-being-wrong × verification-difficulty, not by diff size — a 10-line dependency
bump can silently waste an expensive cloud rebuild, so its review earns the high tier though it looks
trivial. (Real run: a high-tier review of exactly such a bump caught a stale-lockfile defect a cheaper pass
would likely have missed.)
