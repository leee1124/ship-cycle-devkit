# Test baseline: its source, and the `unrunnableHere` category

PREFLIGHT (§ship-cycle Stage 0.5) records the base commit's pass/fail set so G6/G9 can tell a regression
from a pre-existing red mechanically. This file holds where that set may come from (`baseline.source`) and
the rules for the third category — suites that neither pass nor fail because the environment cannot start
them.

## Where the baseline comes from: `baseline.source`

Running a nature's full suite on the base commit can take an hour on a constrained host, under a test lock
other work is queued behind. The base commit has usually been tested already — by CI, on the commit itself.
Re-running it locally buys little, and without a documented alternative operators substitute "the base
branch is CI-green" by hand, which is the same claim with nothing recorded. So the baseline has three
sources, and the state says which one it is:

```json
"baseline": { "capturedOn": "<base-sha>", "source": "ci",
              "run": { "ref": "<CI run id or URL>", "commit": "<base-sha>", "job": "<job/check name>",
                       "report": "<artifact the failing set was read from>", "rechecked": [] },
              "failing": ["suiteA#case"] }
```

- **`local`** (absent `source` means `local` — a baseline recorded before this field existed): the suite
  ran here, on the base commit. Unchanged.
- **`ci`**: the base commit's CI run for the same suite, **with its machine-readable report** (JUnit XML,
  runner JSON — whatever the runner emits). PREFLIGHT reads the report and fills `failing` per case exactly
  as a local run would, so G6/G9 still diff mechanically. No local execution.
- **`ci-status-only`**: the run exists and **succeeded**, but its report is unavailable (not uploaded,
  expired, unreadable). `failing` is **absent** — there is no per-case set to diff against.

Any CI host qualifies — the rules ask only for what every host exposes. A run is usable when:

- its commit is **exactly** `capturedOn`. A run on the branch tip, a merge commit or the previous commit is
  evidence about a different tree;
- it **completed** — not queued, running or cancelled. Use the latest completed attempt; a case that
  failed and passed on an automatic retry is recorded as failing, since the retry hid it;
- its job runs **the same selection** as the nature's `tests` command. Suites the job does not run are not
  baselined by it: capture them locally, or they fall under the `ci-status-only` rule below;
- for `ci`, the report shows an **executed count > 0** for each suite it covers (§core 2 — a report of a
  skipped suite is not a green one).

Record the run in `baseline.run` (`ref`, `commit`, `job`, and `report` when there is one) so the claim can
be checked later. Overlay `changeNature[].ciBaseline` names the job and the report artifact per nature, so
PREFLIGHT does not have to guess which of a dozen checks ran the suite; without it, find the job and say in
one line why it is the right one.

### The rule for `ci-status-only`: any failure in a touched suite blocks

A green status says the suite passed somewhere; it does not say which cases ran or which were already red,
so there is nothing to subtract. Under `ci-status-only`, **every failure G6/G9 sees in a suite this cycle
runs blocks** — "it was probably already red" is exactly the claim the source cannot support. To exempt a
red that really is pre-existing, run *that suite* on the base commit (never the working tree) and add its
result; that suite's entry is then local evidence (below).

A red run without a report is not a baseline at all: it says *something* failed, not what. Capture locally.

### The trade-off, and the recheck that settles it

CI ran on CI's machine. A test that fails only here — a locale, a timezone, a path separator, a slower disk
— is absent from a CI baseline and shows up at G6 as a regression the change did not cause. That is the
price, and it is paid in the safe direction: the CI source can produce a **false regression**, never a
false green. The remedy is the same targeted step as above — run that one suite against the base commit
locally, add its failures to `failing`, and list the suite in `baseline.run.rechecked`. That is still
evidence about the base commit, recorded as such. Re-running a suite against the *changed* tree and calling
the result baseline is not.

A CI baseline is evidence about the base commit, **not about this environment**: it cannot populate
`unrunnableHere`, which needs this environment's own startup error. If the nature's `envProbe` fails, the
suites gated by it still need their own local startup attempt (cheap — it stops before any test runs) to
be quarantined. And on a cycle whose suites are short, the local source is still the default; the CI
sources exist for the suites where a local run is the bottleneck.

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
