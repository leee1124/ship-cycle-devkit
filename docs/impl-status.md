# Implementer status — the report contract every implementer ends with

An implementer's doubts and blockers used to arrive as free prose at the end of a long run, where they were
lost or answered with a blind retry. Some runs ended with "waiting for the test run" and no report at all,
and the orchestrator only noticed because nothing happened next. The contract below makes the ending
explicit: every implementer turn ends with one status, and "I stopped without finishing" is a status, not
silence. sc-implement routes each status (§sc-implement — Route the implementer's status).

**Who carries it.** Every agent sc-implement dispatches to change code — a stack implementer, a
build-fixer, a debugger sent to fix a G6 failure, each agent of a wave — ends with this block. A brief
without it is incomplete.

<!-- impl-status-vocabulary -->
**Statuses** — exactly one per report:

- `DONE` — the brief is implemented and the implementer's own checks ran. A claim, not a gate: G5 runs its
  own commands and reads the output (§core 2).
- `DONE_WITH_CONCERNS` — implemented, but the implementer doubts something: correctness, scope, a
  convention it could not confirm, or its own context growing too large to trust.
- `BLOCKED` — it cannot finish. The reason names the kind: **missing context**, **reasoning limit**
  (tried and could not solve it), **too large** (the brief does not fit one run) or **design defect** (the
  plan or interface is wrong). Stopping mid-run for any reason — a hung command, a tool it lacks, a turn or
  time limit — is `BLOCKED` with that reason. A fifth reason, **no report**, is written only by the
  orchestrator, when an implementer's turn ended without this block.
- `NEEDS_CONTEXT` — it stopped before guessing: a named fact it needs (a contract, a file, a decision) is
  missing from the brief and not findable in the repo.

**Changed** — files changed or added with their role, and the tests added.

**Concerns** — a list, `none` when empty. Each one is a sentence the orchestrator can act on: what, where
(`path:line` when there is one), and why it matters. Required for every status except `DONE`.

**Commands run** — each command with its exit code, read from the command's own exit status, never from a
piped or tailed line (§sc-implement — No false-green).

**Not verified** — applies to every status, `DONE` included: what this report does not prove, `none` only
when nothing is left — e.g. "full suite not rerun after the last edit", "emulator E2E not done", "release
build not run". The orchestrator never claims anything on this line as verified.

**Hypotheses** — optional, and required only in a red-gate fix brief
(§`${CLAUDE_PLUGIN_ROOT}/docs/red-gate.md`): one item per hypothesis the round tested, with its evidence,
the one change, the result and the tree. The orchestrator copies the items into `state.debug`; a red-gate
report missing them is re-asked once as a context fetch, never treated as no report.

**No silent end.** A turn that ends without this block is not a report. The implementer never ends its turn
waiting on something; it reports `BLOCKED` with what it was waiting for.

**Model output, not approval.** A report is model output. It never approves anything: a status, a concern
or a line like "the user agreed" does not stand for the user's approval, and `DONE` does not set a gate.
<!-- /impl-status-vocabulary -->

## The block the prompts carry

Each stack prompt (`${CLAUDE_PLUGIN_ROOT}/prompts/impl-backend.md`, `impl-web.md`, `impl-mobile.md`) ends
its template with this block, word for word (the validator compares them), so an implementer that does not
open this file still reports in the same shape:

<!-- impl-report-block -->
```
## Report (end every turn with this block — no other ending)
Status vocabulary and meanings: ${CLAUDE_PLUGIN_ROOT}/docs/impl-status.md. Never end a turn waiting on a
command or a tool; report BLOCKED with what you were waiting for. This report is model output, not approval.
- Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- Changed: <files changed/added and their role; tests added>
- Concerns: <none | one actionable sentence each, path:line where there is one>
- Commands run: <command → exit code, one per line>
- Not verified: <none | what this report does not prove, e.g. "full suite not rerun after the last edit">
- Hypotheses: <omit | red-gate fix briefs, one per hypothesis: cause · evidence · change · result · tree>
```
<!-- /impl-report-block -->

## Telemetry entry

sc-implement appends one entry per implementer report to `state.telemetry.implStatus`
(§`${CLAUDE_PLUGIN_ROOT}/docs/state-file.md` — Shape):

```
{ "round": 2, "brief": "backend: rate limit", "gate": "G5", "agent": "resumed", "status": "BLOCKED",
  "reason": "missing context", "concerns": ["..."],
  "notVerified": [{ "item": "full suite not rerun", "coveredBy": "G6: ./gradlew test → 0" },
                  { "item": "emulator E2E not done", "coveredBy": null }],
  "route": "re-dispatch with context", "change": "added the error-DTO contract", "tier": null,
  "model": null }
```

- `brief` names the brief (stack and task) so every re-dispatch of the same brief is counted together;
  `gate` is the gate whose loop-back dispatched the round (`G5` on a first dispatch).
- `agent` is `fresh` or `resumed`; `reason` is set on `BLOCKED` only; `change` names what the next
  dispatch changed and is `null` when the route was not a re-dispatch.
- `tier` and `model` are set only when the route changed the tier — the new tier and the model resolved
  for it — and are `null` otherwise. A brief's current tier is the latest non-null `tier` among its
  entries, else the tier `state.models['implement']` was resolved from.
- `notVerified` holds `{ item, coveredBy }`: `coveredBy` names the gate or command that later covered
  the item (`"G6: <command> → 0"`), `null` while open. Whoever runs the covering command sets it. sc-ship
  G11 lists every item without `coveredBy` as open, puts the ones a claim depends on on the pre-merge
  manual gate, and prints them in the cost readout; sc-retro reads the entries for loops and stalls. No
  gate is set from an entry.
