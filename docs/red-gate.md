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
   reproduces, and keep the full command for the final re-run.
   **"Could not reproduce" is not fixed.** It is `undetermined`: the gate stays not-passed, the red is
   withheld, not cleared. A case that failed and then passed with no change is classified by §Flaky and
   order-dependent failures and, like `baseline.flaky`, is not exempt
   (§`${CLAUDE_PLUGIN_ROOT}/docs/test-baseline.md`). Never retry until green to pass a gate.
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
   attempt differs, and that evidence is cited.
5. **One minimal change, then re-run.** Make the smallest change that tests the hypothesis — one change,
   not a bundle — and rerun the reproducing command. The result is `confirmed` (the failure is gone for
   the stated reason), `rejected` (still red, or red differently) or `undetermined` (the run errored).
   A rejected change is reverted before the next hypothesis, so changes do not pile up.
6. **Record every attempt** as one `state.debug` entry (§The record), confirmed or not, before the next.
7. **Three rejected hypotheses on the same failure: stop guessing.** The fixing agent stops and reports
   `BLOCKED` (design defect) — three disproved causes are a design-level signal — unless its evidence
   names a missing fact (then `NEEDS_CONTEXT`) or the environment (then the orchestrator parks and asks the
   user). The report is routed by §sc-implement — Route the implementer's status: the design-defect row
   goes to sc-design and counts toward `loops[G]` once, like any design defect (#87). This is **not a
   second cap**: it changes the route, it never stops the cycle by itself, and the one cap rule stays the
   orchestrator's (§ship-cycle — Loop cap) — at the cap the user decides. sc-design gets the failure's
   `state.debug` entries as its evidence.

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
  "result": "rejected", "tree": "<tree id the re-run ran on>", "at": "<iso>" }
```

- `failure` names the failure so entries group: the failing case id, or the first error line for a build.
  "The same failure" is the same `gate` and `failure`; a new error after a change is a new failure.
- `round` is the `telemetry.implStatus` round that tested it; `tree` is the tree identity the re-run ran
  on; `result` is `confirmed`, `rejected` or `undetermined`.
- **Who writes it.** A fix brief carries this protocol and the failure's existing entries, and asks for
  one line per hypothesis after the report block:
  `- Hypothesis: <cause> · evidence: <cite> · change: <change> · result: <result> · tree: <id>`.
  The orchestrator copies each line into `state.debug`. A fix-round report without them is incomplete
  and is routed as `BLOCKED` (no report): nothing shows which causes were tested.
- **Consumers.** sc-implement passes the rejected entries for a failure into every later fix brief for it
  (do not retry); the resume reconcile keeps them (§`${CLAUDE_PLUGIN_ROOT}/docs/state-file.md` — Resume
  reconcile), so a resumed session or
  a fresh agent does not retry a disproved cause and the three-rejection count survives a restart;
  sc-ship's cost readout prints one line per failure; sc-retro reads them for loops. None decides a gate.
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
