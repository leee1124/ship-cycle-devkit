# Cross-artifact check — one decision, every place it is written

A decision often has to land in several artifacts at once: the requirements, the design notes, a generated
table or column comment, the Q&A record, the README, an i18n string. A delegated agent that syncs them and
reports "done" can leave wording in some of them that says the opposite (a real run: a rule stated one way in
the design notes and the reverse in a table comment). Nothing downstream re-reads all of them together, so
the contradiction ships unless the stage that made the change checks before it reports done.

<!-- cross-artifact-rule -->
**Trigger.** The stage changed a fact — a decision, a rule, a name, a limit, a default — and **more than one
artifact in scope states it**, whether the stage edited them all, delegated the edits, or edited one while
another still states the old version. A fact stated in one artifact only, or edits that change no stated fact
(formatting, a typo), do not trigger it. The stage records its decision either way: an entry with `result`
`clear`, `blocked` or `n/a: <reason>` (`n/a: one artifact states it`, `n/a: no stated fact changed`). **No
entry is not a pass** — the gate reads the entry, so a skipped check and an untriggered one never look alike.

**The check**, before the stage reports done:
1. **List each changed decision as a short claim** — one line, in the form the artifacts should agree with
   ("refresh tokens are deleted on password reset", not "token handling updated").
2. **Grep every artifact in scope for the terms of each claim** — the claim's nouns, the old wording it
   replaced, and the identifiers it names. Scope is every file the stage changed **plus** every artifact of
   the same kinds the cycle owns (design doc, criteria, Q&A record, docs globs, generated comments, i18n),
   on the **integrated tree** when implementers worked in separate worktrees — a stale copy sits exactly
   where nobody edited, and a cross-stack contradiction shows only on the union.
3. **Report each hit** as `consistent`, `contradicting` or `stale` (says the old decision), with
   `path:line`. A hit the check cannot judge from the text is `contradicting` until shown otherwise.

**A `contradicting` or `stale` hit blocks the stage**, the same as an unresolved critic objection. The
writer (or the stage's implementer) fixes it, and the check runs again — a hit is dispositioned `fixed` only
when the re-run reads it `consistent`. A hit in an artifact the cycle does not own (another team's doc the
grep reached) may instead be `filed: #NN` with a link. The entry is `clear` when no hit is left without a
disposition. Re-runs inside the stage count against nothing; a gate that fails on a blocked entry loops as
that gate does.

**Not by the writer.** The check is run by an agent other than the one that wrote the change — a separate
agent, or the orchestrator checking a delegated writer — and the entry records both (`writtenBy`,
`checkedBy`). A separate pass by the same agent is not independent and does not count. A writer's "all
synced" report is a claim under test, not evidence. On a host with no second agent
(§`${CLAUDE_PLUGIN_ROOT}/docs/runtime-adapters.md`), the owner checks the hit list instead and the entry
records their words (`checkedBy: "owner"`); with no owner either, the gate goes to the pre-merge manual gate.

**An outcome, not ceremony.** Tier S does not drop it (§ship-cycle — the bright line); only who runs it
scales.
<!-- /cross-artifact-rule -->

## Where it runs

| stage | before | scope it owns |
|---|---|---|
| sc-design | G2/G3, after the critic's last round | design notes, acceptance criteria and the Q&A record from G1, entry-path criteria |
| sc-implement | G5, on the integrated tree | generated table/column comments, schema docs, i18n strings, code comments the change restates — and G1's criteria and Q&A record when sc-design did not run |
| sc-ship | G10 | README, CHANGELOG, API docs, user-facing docs |

- **sc-design**: a fix after G3 passed re-opens the critic for a round (delta) before the gate holds again.
- **sc-ship G10**: the grep still covers every artifact in scope, but G10 may only edit inside the docs globs.
  A blocking hit outside them (a comment, an i18n string, a schema doc) routes back to sc-implement, which
  fixes it, re-runs its own check at G5 and re-records the tree (§`${CLAUDE_PLUGIN_ROOT}/docs/state-file.md`
  — Tree identity).

## Record

Each run appends to `state.crossArtifact` (shape: `${CLAUDE_PLUGIN_ROOT}/docs/state-file.md`) and one gate-log
row with `gate` = `cross-artifact` (evidence `<stage> · <result> · <n> claims · tree <prefix>`) — like a
`route` row it is not a gate, so the Gate summary and the reconcile skip it.
The entry holds the stage, the claims, the scope it grepped, every hit with its verdict, `path:line` and
disposition, `writtenBy`, `checkedBy`, the `tree` it read (§Tree identity) and the result. A gate reads the
latest entry for its stage: it needs `clear` or `n/a: <reason>` **taken on the tree the gate passes on** — an
entry from another tree is no entry.
