# Test baseline and the `unrunnableHere` category

PREFLIGHT (§ship-cycle Stage 0.5) records the base commit's pass/fail set so G6/G9 can tell a regression
from a pre-existing red mechanically. This file holds the rules for the third category — suites that
neither pass nor fail because the environment cannot start them.

## Why a third category exists

Pass/fail is binary and some suites are neither: an integration/DDL/DB-gated suite this environment cannot
start at all (no database reachable, a service absent, a sandbox policy refusing the connection), verified
elsewhere against a real dependency. It is not a failure to diff against, and counting it as passed is
forbidden — so without a category for it, a large part of a suite ends up with **no truthful status**, which
is how "can't run it here" quietly becomes either a fake pass or a fake regression.

Record it instead:

```json
"unrunnableHere": [{ "suite": "...", "reason": "...", "startupError": "...", "probe": "...",
                     "capturedAt": "preflight" }]
```

`failing` is per-case; `unrunnableHere` is per-suite — a suite that could not start has no cases to
enumerate.

## The boundary is where the suite stops

- **Unrunnable-here** — the suite **could not start** because a **dependency** is missing.
- **`failing`** — the suite **starts and fails**.
- **FAIL / deferral** — the suite starts and **skips itself**: `@Disabled`, zero executed, DDL/seed/auth
  not provisioned.

This category is **not a laundering route for a disabled test**; it exists only for a dependency the
environment refuses to provide.

Runners blur the line: a context-init failure is commonly reported as an *error on every test method*
(reads like `failing`), and a container-gated suite as *skipped* (reads like a deferral). **When the report
is ambiguous it is not unrunnable-here** — record it under whichever stricter category the runner named, and
say in one line why.

## Two pieces of evidence, and the dependency probe is the weaker one

- **`startupError`** — the **suite's own attempted run** in this baseline, terminating with an
  initialization error **before executing any test**. Paste the error line.
- **`probe`** — the dependency command and what it returned (`connection refused`, `no such host`, a policy
  denial).

Only `startupError` says *this suite* could not start; `probe` says the environment is missing something,
and **one probe never licenses quarantining a second suite**. **Either piece missing ⇒ not
unrunnable-here.**

Where the nature declares overlay `envProbe`, run it: a **passing** `envProbe` is a hard bar — nothing under
that nature may be quarantined for that dependency.

Be honest about what this buys. Both pieces are self-reported prose that nothing validates; they are
friction, not proof. What actually holds the category shut is the next two rules.

## Pre-committed: fixed at PREFLIGHT, and it may only shrink

It is classified **against the base commit, before this change exists**.

- Moving a suite **out** (it became runnable) is free and always welcome.
- **There is no path that adds a suite mid-cycle.** A suite that ran at PREFLIGHT and won't run now is a
  **finding** — attach a debugger; it is an environment regression this change may have caused.
- A suite **not in the baseline run at all** (written this cycle by sc-tdd, or never selected by the
  nature's `tests` command) may only **inherit** an existing entry, and only when it is gated by the **same
  dependency whose probe already failed at PREFLIGHT** — recorded with
  `inheritedFrom: "<the PREFLIGHT entry>"`.

Any other growth means re-running the baseline step against the base commit from the top, never editing the
set in place.

## It never satisfies anything

G6/G9 stop treating these suites as regressions; they do **not** start treating them as coverage. sc-ship
maps every acceptance criterion whose only coverage is an unrunnable-here suite to
`review-only (ci-deferred)` (§sc-ship G11) and surfaces it on the pre-merge manual gate (§sc-ship G12).

## Tier S

The baseline is skipped only on the Tier S path, and a skipped baseline means `unrunnableHere` is **absent,
not empty** — there is no pre-committed set for it to be pre-committed against. A Tier S run that meets a
suite it cannot start re-tiers upward to M (monotonic) and captures the baseline against the base commit; it
never mints a quarantine mid-cycle.
