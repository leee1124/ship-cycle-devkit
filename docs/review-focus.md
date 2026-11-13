# Review focus — the inputs the spec implies and no test exercises (#90)

A spec says what the software must do, not everything it will meet, and its silence on an input is not
permission for that input to break the program. Users break software exactly there: the second program with
no start date, the import file saved by the old app, the name that is all emoji. The kit's generic edge
classes (legacy rows, N≥2, unsaved id, re-run — §sc-review — Every review checks) name *kinds* of state;
they cannot name this feature's inputs. So the one stage that has the spec, the design and the existing
tests in front of it writes those inputs down once, the tests pin them, and the cold lens — after its own
blind pass — checks what it missed. This file states the rule once; sc-design, sc-tdd, sc-review, sc-ship
and sc-retro point here.

<!-- review-focus-rule -->
**What sc-design writes.** With the design, the architect writes `state.reviewFocus[]`: **at most five**
inputs or failure modes the acceptance criteria or the design imply but no existing test exercises, ranked
by likelihood × harm, most likely to bite a person first. Each entry:
- `id` — `RF1`, `RF2`, … in rank order; later entries continue the numbering (`RF6`+), and the five-entry
  cap counts only non-superseded entries;
- `input` — the concrete input or state, per feature (a value, a row, a sequence of actions);
- `impliedBy` — the criterion or design line that implies it;
- `uncovered` — why no existing test covers it, cited per §`${CLAUDE_PLUGIN_ROOT}/docs/claim-evidence.md`:
  the test that stops short (`path:line`) or the search that found none (command → no hits);
- `expected` — the behaviour a reasonable user would expect.

**Per feature, never a class.** "Legacy rows", "N≥2", "unsaved id", "re-run", "empty input" as such are not
entries: sc-review's real-world checks already hunt them on every change. An entry names this feature's
instance of one ("an import row from the old app with `weight` null") or none of them. Nor does it restate
an accessibility-floor check (§`${CLAUDE_PLUGIN_ROOT}/docs/visual-check.md` — Accessibility floor): the
designer lens owns those on every UI change. **Nor does it restate an acceptance criterion**: an input a
criterion already names is that criterion's test; one that should be a criterion is promoted to one
(`design-derived`, §sc-design — Entry-path inventory), not listed here.

**An empty list means checked, not skipped.** `reviewFocus: []` is a result — the architect looked and the
criteria imply nothing their tests miss — and the design doc says so in one line. An absent field means
nobody wrote one (§Tier S and route skips).

**Shown, not approved.** The list is in the design doc the user sees at G2/G3, like the design-derived
criteria (§sc-design — Entry-path inventory); there is no separate approval round. The critic may object to
an entry that is a class, restates a criterion, has an uncited `uncovered`, is a logic item planned for an
`n/a` pin, or leaves a likelier input off the list.

**Append or annotate only after G3.** Entries are never silently rewritten once G3 passed. A **corrected**
entry (its `uncovered` was wrong — a test already drives the input) keeps its `id`, gets
`pinnedBy: "<existing test id>"` and is listed in the G4 report. A design **rewrite** (sc-design re-run)
marks the old entries `superseded: true` and appends the new ones, which G4 re-pins. Promoting an entry
to a criterion after G3 is a G1 re-show (§ship-cycle Stage 0.4); the entry is marked `superseded: true`.
Scope growth (§ship-cycle Stage 0.4) re-opens the list at whichever stage wrote it.
<!-- /review-focus-rule -->

<!-- review-focus-pin -->
**G4 pins every entry.** sc-tdd treats each entry like an acceptance criterion: a test that encodes
`input` → `expected`, run and seen failing for the right reason (§sc-tdd — Do), recorded as `pinnedBy:
"<test id>"`. `pinnedBy: "n/a: <reason>"` is allowed **only for a layout, copy or config item** (§core 3),
naming the execution-based verification that covers it (which check, on which profile or command); a logic
entry always needs a failing-first test. A misused `n/a` is a critic objection at design and `pinHolds:
false` at G8. An entry whose test passes before the change is not pinned: either `uncovered` was wrong
(correct the entry, §Append or annotate only) or the test does not exercise the input. G4 does not pass
while any non-superseded entry has no `pinnedBy`.
<!-- /review-focus-pin -->

<!-- review-focus-cold -->
**The cold lens gets the list only after its blind pass.** On the first full review (and a full re-review
of a redesigned change), the cold lens runs exactly as §sc-review states it — diff only, no list: the list is
never in the cold lens's blind-pass brief. Every blind pass, the one after a redesign included, is a **fresh
agent with no prior compare in its context**. Then:

1. **Freeze.** Its findings are **frozen verbatim** into the review artifact, under the reviewed HEAD sha,
   before the list is sent — the wave check's pattern (§`${CLAUDE_PLUGIN_ROOT}/docs/wave-check.md`).
2. **Compare.** Then send `state.reviewFocus` (non-superseded entries and pins). For each entry it
   reports: `raised` — whether a frozen finding names that input or failure itself (a finding that only
   notices the pinning test exists does not count); and `pinHolds` — whether the `pinnedBy` test actually
   drives `input` and asserts `expected` through the real construction path, or, for an `n/a` pin, whether
   it is a layout, copy or config item and the named verification covers it. Findings it adds now are
   tagged `postList: true`; it never edits the frozen list.
3. **Record** `cold = { raised, finding, pinHolds, evidence, tree }` on the entry: `finding` the frozen
   finding it matched or `null`, `evidence` a `path:line` for `pinHolds`, `tree` the reviewed tree
   identity.
4. **Verify** every entry with `raised: false` or `pinHolds: false`. The parallel lenses have already run,
   so these never wait for their brief: a **scoped second pass of a spec-anchored lens** (quality or
   algorithm) on just these items, or **triage at `high` effort** verifying them directly. **The scoped
   pass runs on the same model and effort the chosen lens ran with at G8**, risk upgrade included
   (§sc-review — Model routing). Record who verified each as `verify = { by, model, effort, outcome,
   evidence }`: `evidence` is the `path:line` of the assertion and of the construction call it goes through,
   which the verifier opens itself — never a copy of `cold.evidence`.

**Host without live messaging:** two agents on the same pinned model and effort — the first runs the blind
pass, its frozen findings go to the second with the list (§`${CLAUDE_PLUGIN_ROOT}/docs/runtime-adapters.md`).

**Three outcomes, recorded in `verify.outcome`** and in the review artifact beside the other dispositions
(§sc-review — Triage):
- **`covered: <pinnedBy>`** — the cold lens missed it, but the pin holds and drives the input. Verified, not
  fixed: it is not counted as fixed-here and never goes to the delta pass. sc-retro counts it as
  "cold-lens miss, caught by the pin".
- **`fixed-here`** — the pin did not hold; it is a finding, and the fixed or new pin must be **shown failing
  against the pre-change tree** (or with the guarded line reverted): record `pinFixedBy` (the test id) and
  `pinFixEvidence` (command → failing output) in `verify`.
- **`filed-as #NN`** — out of scope by §sc-review — Triage, listed as open.

**The delta pass sees code locations only.** A fixed-here item reaches the delta pass as the `path:line` of
its pin or fix, never as its `input` or `expected` text — the delta pass is a cold lens too. **It checks only
whether the pin or fix introduced a regression**; resolution is proven by `verify.pinFixEvidence` and the
pin's passing run at G11, not by the delta lens.
<!-- /review-focus-cold -->

<!-- review-focus-tier -->
**Design-only route.** The list is written at G2 into the design doc, unpinned, and is not mapped at G11 —
no tests run on that route (`${CLAUDE_PLUGIN_ROOT}/docs/design-only-route.md`).

**Tier S and route skips.** When sc-design does not run — a route skip or the Tier S collapse — sc-tdd,
which runs for any change with a contract, writes the list itself: **at most two** entries, same shape,
`source: "sc-tdd"`, listed in the G4 report to the user, or `[]` when it checked and found none. When sc-tdd
is route-skipped too (layout, copy or config), the field stays **absent** unless entries already exist —
then the skip path still pins them (`n/a` only for layout, copy or config) and a logic entry grows sc-tdd to
`run`. Absent: the cold lens has no compare step and nothing is carried to G8 — its blind pass and the
designer lens still run. When no cold lens runs at all (a trivial Tier S change), entries keep
`cold: null`, the review artifact notes "not compared", and sc-retro skips them. A cycle whose route grows
sc-design to `run` appends to the list there (§Append or annotate only).
<!-- /review-focus-tier -->

## Record and readers

<!-- review-focus-record -->
`state.reviewFocus` holds one entry per item: `id`, `input`, `impliedBy`, `uncovered`, `expected`, `source`
(`sc-design` or `sc-tdd`), `superseded`, `pinnedBy` (written at G4), `cold` and `verify` (written at G8,
`null` until then — and `cold` stays `null` when no cold lens ran). Readers: sc-tdd (G4 pins), sc-review (the
compare, the verify step and G8), sc-ship G11 (each entry is mapped to its pin's evidence like a criterion; a
`fixed-here` entry needs `verify.pinFixedBy` with its failing-first evidence) and sc-retro (did the cold lens
find what the list named, which misses the pin caught, superseded entries as evidence of the earlier design's
misses, and did a later defect sit in an input the list left off). The list sets no gate value of its own: G4
requires every entry pinned, G8 a `verify` outcome for every missed or uncovered entry.
<!-- /review-focus-record -->
