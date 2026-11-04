# Unverifiable from diff — what a blind reader could not settle (#91)

A diff-only reader meets doubts the diff cannot answer: a requirement that lives in unchanged code, a
behaviour that spans tasks or waves, an intent only the spec states. Left alone, such a doubt goes one of two
wrong ways — the lens inflates it into a finding to be safe, or drops it because it cannot evidence it. Both
cost something: the first floods triage with guesses, the second loses the defect a blind lens exists to see.
So a blind reader has a third output, and the orchestrator — who holds the spec — settles each item before
G8. This file states the rule once; sc-review, the wave check, sc-ship and sc-retro point here.

<!-- unverifiable-bucket -->
**The bucket.** Besides its findings, a blind reader returns `unverifiable-from-diff[]`: each item a
requirement or behaviour it could not settle from what it may read. **Who writes it:** the G8 cold lens, the
delta pass (§sc-review — Re-review after fixes) and the wave check's two passes
(§`${CLAUDE_PLUGIN_ROOT}/docs/wave-check.md`) — one term for all of them; the wave check's "cannot verify
from the diff" items are these items. Each item has the shape
`{item, where, needs, whyNotChecked}`:
- `item` — the doubt, in one sentence ("does the import path also reject a null `weight`?");
- `where` — the `path:line` in the diff that raised it;
- `needs` — what unchanged code, spec line or runtime fact would settle it;
- `whyNotChecked` — why this reader could not check it (it is blind to the spec; it spans waves; it needs a
  running system).

**Not a parking lot.** The cold lens may read repo and dependency code to evidence its claims
(§`${CLAUDE_PLUGIN_ROOT}/docs/claim-evidence.md`): when reading the repo would settle a doubt, it reads it and
raises a finding or nothing. An item is only what its own permitted reading cannot settle.

**It keeps the blind lens blind.** The bucket is how the cold lens says "I'd need X", **not a licence to read
the spec**: it never asks for the spec, the design or the author narrative, and no disposition is ever sent
back into its context. An item is **not a finding**: it carries no severity, it never lowers or replaces a
finding, and it does not change the lens's verdict.
<!-- /unverifiable-bucket -->

<!-- unverifiable-disposition -->
**Dispositioned before G8.** After the lenses have run (and after the delta pass, on a re-review), every item
is settled with evidence by one of: **the orchestrator in triage at `high` effort** (§sc-review — Triage), or
a **scoped pass of a spec-anchored lens** (quality or algorithm) on just these items — **on the same model and
effort that lens ran with at G8**, risk upgrade included, the review-focus Verify rule
(§`${CLAUDE_PLUGIN_ROOT}/docs/review-focus.md`). Whoever settles it opens the cited evidence itself. Outcomes:
- **`confirmed → finding #<n>`** — the gap is real. It enters the findings list with a severity and from
  there follows the normal rules: a Critical/High gets its refuter (§sc-review — Verify findings), the
  data-integrity and security floors apply, and triage disposes of it (fixed-here / filed-as `#NN`).
- **`cleared: <cited reason>`** — the unchanged code or the spec already covers it. Clearing is a
  load-bearing claim: the reason cites a `path:line`, a spec line or a command and its output. An uncited
  clearing is no clearing.
- **`owner-decision: <the owner's words>`** — neither could be evidenced. Like an undetermined finding, the
  item exits only as an explicit owner decision recorded in the review artifact.

**Never silently dropped, never auto-promoted.** An item is not a finding until a disposition confirms it,
and not gone until one clears it. **G8 does not pass while any item has no disposition**; an item whose
`where` a fix removed is still cleared with its evidence, not forgotten.
<!-- /unverifiable-disposition -->

## Record and readers

<!-- unverifiable-record -->
`state.unverifiable` holds one entry per item: `id` (`UV1`, `UV2`, … never reused), `source` (`cold`,
`delta` or `wave:<N>`), `tree` (the tree identity the reader read), `item`, `where`, `needs`,
`whyNotChecked`, and `disposition` (`null` until settled) = `{by, model, effort, outcome, evidence}`, with
`outcome` one of the three above. The review artifact lists the items beside the other dispositions.
Readers: sc-review (the disposition step and G8), sc-ship (G11 re-asserts every item is dispositioned; the PR
body carries one **Unverifiable** line of counts by outcome and every `owner-decision` verbatim) and sc-retro
("what blind lenses couldn't see": which items were confirmed, and whether a later defect sat where a cleared
item pointed). It sets no gate value of its own: G8 requires every item dispositioned.
<!-- /unverifiable-record -->
