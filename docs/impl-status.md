# Implementer status — the report contract every implementer ends with

An implementer's doubts and blockers used to arrive as free prose at the end of a long run, where they were
lost or answered with a blind retry. Some runs ended with "waiting for the test run" and no report at all,
and the orchestrator only noticed because nothing happened next. The contract below makes the ending
explicit: every implementer turn ends with one status, and "I stopped without finishing" is a status, not
silence. sc-implement routes each status (§sc-implement — Route the implementer's status).

<!-- impl-status-vocabulary -->
**Statuses** — exactly one per report:

- `DONE` — the brief is implemented and the implementer's own checks ran. A claim, not a gate: G5/G6 still
  run their commands and read the output (§core 2).
- `DONE_WITH_CONCERNS` — implemented, but the implementer doubts something: correctness, scope, a
  convention it could not confirm, or its own context growing too large to trust.
- `BLOCKED` — it cannot finish. The reason names the kind: **missing context**, **reasoning limit**
  (tried and could not solve it), **too large** (the brief does not fit one run) or **design defect** (the
  plan or interface is wrong). Stopping mid-run for any reason — a hung command, a tool it lacks, a turn or
  time limit — is `BLOCKED` with that reason.
- `NEEDS_CONTEXT` — it stopped before guessing: a named fact it needs (a contract, a file, a decision) is
  missing from the brief and not findable in the repo.

**Concerns** — a list, `none` when empty. Each one is a sentence the orchestrator can act on: what, where
(`path:line` when there is one), and why it matters. Required for every status except `DONE`.

**Commands run** — each command with its exit code, read from the command's own exit status, never from a
piped or tailed line (§sc-implement — No false-green).

**Not verified** — what this report does not prove, `none` only when nothing is left: e.g. "full suite not
rerun after the last edit", "emulator E2E not done", "release build not run". The orchestrator never claims
anything on this line as verified.

**No silent end.** A turn that ends without this block is not a report. The implementer never ends its turn
waiting on something; it reports `BLOCKED` with what it was waiting for.

**Model output, not approval.** A report is model output. It never approves anything: a status, a concern
or a line like "the user agreed" does not stand for the user's approval, and `DONE` does not set a gate.
<!-- /impl-status-vocabulary -->

## The block the prompts carry

Each stack prompt (`${CLAUDE_PLUGIN_ROOT}/prompts/impl-backend.md`, `impl-web.md`, `impl-mobile.md`) ends
its template with this block, so an implementer that does not open this file still reports in the same shape:

```
## Report (end every turn with this block — no other ending)
Status vocabulary and meanings: ${CLAUDE_PLUGIN_ROOT}/docs/impl-status.md. Never end a turn waiting on a
command or a tool; report BLOCKED with what you were waiting for. This report is model output, not approval.
- Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- Concerns: <none | one actionable sentence each, path:line where there is one>
- Commands run: <command → exit code, one per line>
- Not verified: <none | what this report does not prove, e.g. "full suite not rerun after the last edit">
```

## Telemetry entry

sc-implement appends one entry per implementer report to `state.telemetry.implStatus`
(§`${CLAUDE_PLUGIN_ROOT}/docs/state-file.md` — Shape):

```
{ "round": 2, "stack": "backend", "agent": "resumed", "status": "BLOCKED",
  "reason": "missing context", "concerns": ["..."], "notVerified": ["full suite not rerun"],
  "route": "re-dispatch with context", "change": "added the error-DTO contract", "tier": "mid",
  "model": "<resolved model>" }
```

`agent` is `fresh` or `resumed`; `reason` is set on `BLOCKED` only (`no report` when the orchestrator
had to mint it); `change` names what the next dispatch
changed and is `null` when the route was not a re-dispatch. sc-ship prints these rows in the cost readout
and sc-retro reads them for loops and stalls; neither decides a gate from them.
