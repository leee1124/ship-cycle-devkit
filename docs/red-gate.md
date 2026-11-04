# When a gate goes red — reproduce, one hypothesis at a time, and keep the record

The gate table's "On failure" column used to say only "debugger → sc-implement". When the loop cap ran out
it was usually not three different fixes that failed but the same guess tried three times: a fix applied
without reproducing the failure, a rerun until it went green, a resumed session retrying the change the
previous session had already disproved. This file is the protocol every agent sent to fix a red gate
follows. It is stated here once; sc-implement (G5, G6, G7, G7b), sc-qa (G9) and the orchestrator's gate
table point to it.

<!-- red-gate-trigger -->
**When it applies.** A red G5, G6, G7 or G7b in sc-implement, a red wave barrier (its build/typecheck is
G5's build, §sc-implement — waved execution; mapping each error to its owning file is this protocol's
reproduce step at file granularity) and a genuine `fail` at G9 in sc-qa. It binds the build-fixer or
debugger the gate's "On failure" column sends, and every later round on the same failure. An undetermined
check is not red: fix the probe and re-run it (§sc-implement — No false-red); a `degrade` is not red either.
A suite in `baseline.unrunnableHere` never triggers it: it is diffed around, as at G6, neither a regression
nor coverage (§`${CLAUDE_PLUGIN_ROOT}/docs/test-baseline.md`).
A defect goal's root cause is sc-brainstorm's job (§sc-brainstorm — Root-cause analysis); this protocol is
for a gate that this cycle's own change turned red, and uses the same standard — a cause, never a
restatement of the symptom.
<!-- /red-gate-trigger -->

## The protocol

<!-- red-gate-protocol -->
1. **Reproduce first, with the real command.** Rerun the command whose output made the gate red, on the
   current tree, as its own step: record the command, its own exit code (§core 2 — never a piped or tailed
   line) and the tree identity (§`${CLAUDE_PLUGIN_ROOT}/docs/state-file.md` — Tree identity). A full
   suite, a build, an emulator run or a bisection is heavy: run it under overlay `env.heavyLock` with a
   bounded wait (§`${CLAUDE_PLUGIN_ROOT}/docs/heavy-work.md`). Narrow to the failing case once it
   reproduces, and keep the full command for the final re-run. A G9 hand-off from sc-qa (command, exit
   code, tree, error) **is** this step: the fixer re-runs it once to confirm on its own tree, no more.
   **"Could not reproduce" is not fixed.** The red stands: `gates.<G>` keeps its `fail`, and the gate-log
   row reads `fail` with evidence `undetermined: not reproduced in <N> runs` — the log has no
   `undetermined` value (§core 2's third state lives in the evidence, never as a pass). `<N>` is the count
   fixed before the first run (§Flaky and order-dependent failures), applied per tree. It leaves by one
   of three exits, never by a rerun that happens to go green (never retry until green to pass a gate):
   - **(a) Classify and fix.** A case that failed and then passed with no change is classified per
     §Flaky and order-dependent failures, and the cause of the flake is fixed under this protocol.
   - **(b) Recheck on the base commit.** Run that one suite on the base commit (never the working tree).
     It fails the same way there → pre-existing, recorded per
     `${CLAUDE_PLUGIN_ROOT}/docs/test-baseline.md` (a `capturedAt` entry; `flaky` cases stay not exempt
     unless their suite is rechecked, as that doc says).
   - **(c) Not reproducible anywhere.** After the fixed count of runs (§Flaky) on both trees: record the
     runs in `state.debug`, park the cycle and ask the user
     (§`${CLAUDE_PLUGIN_ROOT}/docs/state-file.md` — Parking).
2. **Read the actual error.** The full text of the first failure, from the runner's report where there is
   one (`<failure>` vs `<error>`, `FAILED` vs `ERROR`), not the summary line and not the last error of a
   cascade. N identical infrastructure errors are one broken check.
3. **Compare against a working example.** The same case on the base commit (`state.baseline`, or a
   recheck of that one suite on the base commit — never the working tree), the last tree the gate passed
   on (`state.gateTrees`), a passing sibling test or call site. List the differences; the hypothesis comes
   from one of them.
4. **One hypothesis, with evidence.** State one cause and cite what supports it — a `path:line`, a
   dependency source line, a version-matched doc, or a command and its output
   (§`${CLAUDE_PLUGIN_ROOT}/docs/claim-evidence.md`). Recall is not evidence. **Read `state.debug` first:**
   a hypothesis already `rejected` for this failure is not tried again unless new evidence says why this
   attempt differs, and that evidence is cited. A tree, dependency or environment that changed since the
   rejected entry — cited against that entry's `tree` (a diff, a lockfile line, a probe's output) — is new
   evidence.
5. **One minimal change, then re-run.** Make the smallest change that tests the hypothesis — one change,
   not a bundle — and rerun the reproducing command. The result is `confirmed` (the original failure is
   gone for the stated reason), `rejected` or `undetermined` (the run errored). **Red differently is
   `rejected`** on the original failure: the failure stays the same group until its original error is
   gone, and only then does a new error open a new one.
   **Revert safely — undo this change, not the work around it.** The worktree already holds uncommitted
   work (the implementation, earlier rounds), so a diff taken *before* the change captures that work, and
   reverting it reverts the wrong thing. Instead:
   - **Before the change**, record the tree identity and the pre-change state:
     `base=$(git stash create)` (it writes a commit and prints its sha without touching the worktree or
     the stash list — never run `git stash` itself; empty output means nothing tracked changed, so use
     `HEAD`), and copy every untracked file the change will touch to a scratch dir outside the worktree
     (`stash create` omits untracked files).
   - **After the change**, patch the change itself: `git diff "$base" -- <files> > <scratch>/change.patch`
     for tracked files. Keep the patch outside the worktree — a file in it changes the tree identity.
   - **To undo**, `git apply -R <scratch>/change.patch`; if that fails, and always for an untracked file,
     restore the pre-change copies (a `--no-index` diff of a copy names the scratch path and does not
     apply back); delete a file the change created. Never `git checkout`, `git reset` or `git stash`
     files other agents or the earlier rounds also touch.
   - **Then check** that the tree identity equals the pre-change tree, and record the revert in the entry.
     Changes never pile up.
6. **Record every attempt** as one `state.debug` entry (§The record), confirmed or not, before the next.
7. **Stop guessing before the third blind try.** The counting rides on #87 and adds nothing to it: each
   fix round that ends with its hypotheses rejected is already a fix-round re-dispatch counted against
   `loops[G]` (§sc-implement — Route the implementer's status); hypotheses tested inside one round are
   not loops.
   - **Three rejected hypotheses on the same failure inside a round:** the fixing agent stops and reports
     `BLOCKED` (design defect) — three disproved causes are a design-level signal — unless its evidence
     names a missing fact (then `NEEDS_CONTEXT`) or the environment (then the orchestrator parks and asks
     the user). Routed by the design-defect row to sc-design; it is the round's "further failure", +1 to
     `loops[G]` only because it happened inside the round.
   - **At loop 2 with two rejected hypotheses** — counted as this failure's `rejected` entries across
     all rounds, not within one — prefer sc-design over a third guess.
   - **When the rounds already reached the cap**, the one cap rule decides: stop, park and ask; the user
     decides, with the failure's `state.debug` entries handed over as the evidence.
   This is **not a second cap**: it changes the route, it never stops the cycle by itself, and the one cap
   rule stays the orchestrator's (§ship-cycle — Loop cap). sc-design gets the failure's `state.debug`
   entries as its evidence.

The gate passes only on its own commands, run by the stage that owns it: a `confirmed` entry is a claim,
not a pass, and the full command reruns before the gate is recorded.
<!-- /red-gate-protocol -->

## The record: `state.debug`

<!-- red-gate-record -->
`state.debug` is append-only, one entry per hypothesis tested:

```
{ "gate": "G6", "failure": "RateLimitTest#burst", "round": 2,
  "repro": { "command": "./gradlew test --tests RateLimitTest", "exit": 1 },
  "hypothesis": "the bucket refill reads the wall clock, not the injected Clock",
  "evidence": "src/main/java/RateLimiter.java:41", "change": "use the injected Clock in refill()",
  "result": "rejected", "tree": "<tree id the re-run ran on>",
  "revert": "git apply -R <scratch>/change.patch · tree back to <pre-change tree id>", "at": "<iso>" }
```

- `failure` names the failure so entries group: the failing case id, or for a build the error code plus
  the file, normalised — no line or column, so an edit that shifts lines keeps the same key. "The same
  failure" is the same `gate` and `failure`; a new group opens only once the original error is gone.
- `round` is the `telemetry.implStatus` round that tested it — the round, not a loop: rounds are what
  `loops[G]` counts (§step 7), several entries share one round. `tree` is the tree identity the re-run
  ran on; `result` is `confirmed`, `rejected` or `undetermined`; `revert` records the undo of a rejected
  change.
- **Who writes it.** A red-gate fix brief carries this protocol and the failure's existing entries, and
  requires the report block's `- Hypotheses:` field (§`${CLAUDE_PLUGIN_ROOT}/docs/impl-status.md`), one
  item per hypothesis, fields in this order: `cause · evidence · change · result · tree` (the block's
  placeholder, word for word).
  The field is optional in every other brief. The orchestrator copies each item into `state.debug`. A
  fix-round report missing it is re-asked once as a context fetch (outside `loops[G]`), never routed as
  `BLOCKED` (no report): the rest of the report is a report.
- **Consumers.** sc-implement passes the rejected entries for a failure into every later fix brief for it
  (do not retry); the resume reconcile keeps them (§`${CLAUDE_PLUGIN_ROOT}/docs/state-file.md` — Resume
  reconcile), so the rejected entries survive a restart, so no disproved cause is retried by a resumed
  session or a fresh agent; sc-ship's cost readout prints one line per failure; sc-retro reads them for
  loops. None decides a gate.
<!-- /red-gate-record -->

## Flaky and order-dependent failures

<!-- red-gate-flaky -->
**Retry to classify, never to hide.** Reruns are allowed only to decide which class a failure is in, each
run recorded with its command and exit code, and the count fixed before the first one (3–5 is enough).
"Passed on the third try" is evidence that the case is flaky, not a pass; a gate never passes on the best
of N runs.

- **Classify.** Run the failing case alone, then in the failing order. Alone passes and in order fails →
  **order-dependent** (another test leaves state behind). Flips with nothing changed → **flaky** (timing,
  randomness, an unordered collection, an external dependency). A case that flips here and is not in
  `baseline.flaky` is a finding; a recheck on the base commit that flips the same way shows it pre-existing,
  settled per `${CLAUDE_PLUGIN_ROOT}/docs/test-baseline.md` — not by rerunning.
- **Find the polluter by bisection.** Take the tests that run before the victim in the failing order, run
  the first half plus the victim, keep the half that still fails, repeat: about log2(n) runs. Use the
  runner's own selection and ordering flags (a test-id list, a fixed seed, a disabled random-order
  plugin) rather than a shell glob, so it works on Linux and Windows alike; for leaked files or rows,
  check for the artifact after each run instead of the victim's result. Each run is heavy: under
  `env.heavyLock`, with a bounded wait.
- **Wait for the condition, not for time.** Replace a `sleep` with a wait for the condition itself (the
  row exists, the port answers, the element is shown) with a deadline, failing with a message that names
  the condition. Lengthening a sleep is not a fix; it moves the flake to a slower machine.
- **Isolate shared state.** A per-test temp dir, a fresh database or a rolled-back transaction, reset
  singletons, clock, timezone, locale and environment variables, an ephemeral port. Fix the polluter, not
  the victim.
- **Then guard the boundary.** Once the cause is fixed, a check where the bad value or state entered
  (an assertion, a validation, a teardown) keeps the next change from bringing it back.
<!-- /red-gate-flaky -->
