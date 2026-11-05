# Unverifiable from diff — what a reader could not settle from what it may read (#91)

A reader that cannot settle a doubt from what it may read — a cold lens blind to the spec, a delta pass that
sees only the fix, a wave check that sees one wave — meets questions its inputs cannot answer: an intent only
the spec states, a behaviour that spans tasks or waves, a fact only a running system shows. Left alone, such a
doubt goes one of two wrong ways — the reader inflates it into a finding to be safe, or drops it because it
cannot evidence it. The first floods triage with guesses; the second loses the defect a blind lens exists to
see. So such a reader has a third output, and the orchestrator — who holds the spec — settles each item
before G8. This file states the rule once; sc-review, the wave check, sc-ship and sc-retro point here.

<!-- unverifiable-bucket -->
**The bucket.** Besides its findings, the reader returns `unverifiable-from-diff[]`: each item a
requirement or behaviour it could not settle from what it may read. **Who writes it:** the G8 cold lens, the
delta pass (§sc-review — Re-review after fixes) and the wave check's two passes
(§`${CLAUDE_PLUGIN_ROOT}/docs/wave-check.md`) — one term for all of them; the wave check's "cannot verify
from the diff" items are these items. Each item has the shape
`{item, where, needs, whyNotChecked}`:
- `item` — the doubt, in one sentence ("is a second import of the same file meant to merge or to reject?");
- `where` — the `path:line` in the diff that raised it;
- `needs` — the spec line, cross-task or cross-wave fact, or runtime observation that would settle it —
  never code in the repo, which the reader may read itself;
- `whyNotChecked` — a closed value: `spec-only` (an intent only the criteria, design or spec states — the
  reader is blind to it), `spans-tasks` (it depends on a wave or task outside this diff) or
  `needs-running-system` (only a running system shows it). Any other value is not an item.

**Not a parking lot.** The cold lens may read repo and dependency code to evidence its claims
(§`${CLAUDE_PLUGIN_ROOT}/docs/claim-evidence.md`): when reading the repo would settle a doubt, it reads it and
raises a finding or nothing. An item is only what its own permitted reading cannot settle.

**It keeps the blind lens blind.** The bucket is how the cold lens says "I'd need X", **not a licence to read
the spec**: it never asks for the spec, the design or the author narrative, and no disposition is ever sent
back into its context. An item is **not a finding**: it carries no severity, it never lowers or replaces a
finding, and it does not change the lens's verdict.

**Frozen with the findings.** A reader's items are frozen verbatim together with its findings — the cold
lens's before the review-focus list is sent (§`${CLAUDE_PLUGIN_ROOT}/docs/review-focus.md`), the wave check's
cold pass before the spec is sent. An item a reader adds after that is tagged `postList: true`; a later pass
may add items but never settles one — settling is the disposition step below.
<!-- /unverifiable-bucket -->

<!-- unverifiable-disposition -->
**Dispositioned before G8.** After the lenses have run (and after the delta pass, on a re-review), every item
is settled with evidence by one of: **the orchestrator in triage at `high` effort** (§sc-review — Triage), or
a **scoped pass of a spec-anchored lens** (quality or algorithm) on just these items — **on the same model and
effort that lens ran with at G8**, risk upgrade included, the review-focus Verify rule
(§`${CLAUDE_PLUGIN_ROOT}/docs/review-focus.md`). Whoever settles it opens the cited evidence itself.
Disposition passes ride on `loops[G8]`, under the orchestrator's loop cap. Outcomes:
- **`confirmed → finding #<n>`** — the gap is real. It enters the findings list with a severity and from
  there follows the normal rules: a Critical/High gets its refuter (§sc-review — Verify findings), the
  data-integrity and security floors apply, and triage disposes of it (fixed-here / filed-as `#NN`).
- **`cleared: <cited reason>`** — the spec or a fact outside the diff already covers it. Clearing is a
  load-bearing claim: the reason cites a `path:line`, a spec line or a command and its output. An uncited
  clearing is no clearing.
- **`owner-decision: <the owner's words>`** — neither could be evidenced. Allowed **only when
  `state.route.ownerPresent === true`** — on any nature it may grow from `false` or absent to `true` here, but
  **only by actually asking the owner** (the visual-check growth rule) — and the top-level session finds the
  owner's answer, quoted verbatim, as a human user turn in its own conversation — the visual-check rule
  (§`${CLAUDE_PLUGIN_ROOT}/docs/visual-check.md`); `disposition.by` is `"owner"`. **Before asking**, the
  disposer states whether the item, if real, falls under the data-integrity or security floor; if it does, the
  owner decides it as "treated as High until shown otherwise".
- **No owner fails closed.** Without that owner answer, a floor item keeps G8 blocked; any other item is
  recorded `manual-gate: <why no owner>` and goes on the pre-merge manual gate (§sc-ship G12). If nobody
  answers a floor item, it stays blocked and the loop-cap rule applies: stop, park, ask the user.
- **Growth is scoped.** Growth via an owner decision does not reverse a UI owner's explicit `false` for the
  visual loop; that answer still holds for `owner-confirmed`.
- **Re-cite on edit.** A cleared item whose `where` a fix round touched is re-cited on the new tree before G8
  is re-judged.

**A parked item is a lens miss.** When the disposer finds that `needs` could have been read from the repo
by the reader itself, the item was parked, not unverifiable: it is `confirmed` at the severity the gap
implies — **no lower than its floor severity** (data-integrity or security ⇒ at least High) — with
`parked: true` and the rationale in `disposition.evidence`, and sc-retro counts it as parked. Lowering it
later needs a refuter's evidence, as for any finding (§`${CLAUDE_PLUGIN_ROOT}/docs/claim-evidence.md`).

**One disposition per gap.** An item with the same `where`, `needs` **and `tree`** as an earlier one gets
`sameAs: "UV<n>"` and shares that item's disposition instead of a second one. On a different tree the later
item gets its own disposition: a `cleared` reason is not inherited without re-citing its evidence on the
later tree.

**Never silently dropped, never auto-promoted.** An item is not a finding until a disposition confirms it, and
not gone until one clears it. **G8 does not pass while any item has no disposition**; at the loop cap an item
still open goes to the owner under the rule above — asking them grows `ownerPresent` on any nature, and an
unanswered floor item stays blocked (stop, park, ask the user). An item whose `where` a fix removed is still
cleared with its evidence, not forgotten.
<!-- /unverifiable-disposition -->

## Record and readers

<!-- unverifiable-record -->
`state.unverifiable` holds one entry per item: `id` (`UV1`, `UV2`, … never reused), `source` (`cold`,
`delta` or `wave:<N>`), `tree` (the tree identity the reader read), `item`, `where`, `needs`,
`whyNotChecked`, `postList`, `sameAs` (`null` or `"UV<n>"`), and `disposition` (`null` until settled) =
`{by, model, effort, outcome, evidence, parked}`, with `outcome` one of the outcomes above. The review
artifact lists the items beside the other dispositions. Readers: sc-review (the disposition step and G8),
sc-ship (G11 re-asserts every item is dispositioned; the PR body carries one **Unverifiable** line of counts
by outcome and every `owner-decision` verbatim; `manual-gate` items are on the pre-merge manual gate) and
sc-retro ("what blind lenses couldn't see": which items were confirmed, which were parked, and whether a later
defect sat where a cleared item pointed). It sets no gate value of its own: G8 requires every item
dispositioned.
<!-- /unverifiable-record -->
