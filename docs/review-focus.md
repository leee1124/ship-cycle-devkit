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
- `id` — `RF1`…`RF5`, in rank order;
- `input` — the concrete input or state, per feature (a value, a row, a sequence of actions);
- `impliedBy` — the criterion or design line that implies it;
- `uncovered` — why no existing test covers it, cited per §`${CLAUDE_PLUGIN_ROOT}/docs/claim-evidence.md`:
  the test that stops short (`path:line`) or the search that found none (command → no hits);
- `expected` — the behaviour a reasonable user would expect.

**Per feature, never a class.** "Legacy rows", "N≥2", "unsaved id", "re-run", "empty input" as such are not
entries: sc-review's real-world checks already hunt them on every change. An entry names this feature's
instance of one ("an import row from the old app with `weight` null") or none of them. Nor does it restate
an accessibility-floor check (§`${CLAUDE_PLUGIN_ROOT}/docs/visual-check.md` — Accessibility floor): the
designer lens owns those on every UI change.

**An empty list means checked, not skipped.** `reviewFocus: []` is a result — the architect looked and the
criteria imply nothing their tests miss — and the design doc says so in one line. An absent field means
nobody wrote one (§Tier S and route skips).

**Shown, not approved.** The list is in the design doc the user sees at G2/G3, like the design-derived
criteria (§sc-design — Entry-path inventory); there is no separate approval round. The critic may object to
an entry that is a class, an uncited `uncovered`, or a likelier input left off the list.
<!-- /review-focus-rule -->

<!-- review-focus-pin -->
**G4 pins every entry.** sc-tdd treats each entry like an acceptance criterion: a test that encodes
`input` → `expected`, run and seen failing for the right reason (§sc-tdd — Do), recorded as `pinnedBy:
"<test id>"`. Where test-first is the wrong tool for that entry — a layout or copy item, verified by
running the thing — the pin is `pinnedBy: "n/a: <reason>"` naming the execution-based verification that
covers it (which check, on which profile or command). An entry whose test passes before the change is not
pinned: either the claim in `uncovered` was wrong (fix the entry, cite the test that already covers it) or
the test does not exercise the input. G4 does not pass while any entry has no `pinnedBy`.
<!-- /review-focus-pin -->

<!-- review-focus-cold -->
**The cold lens gets the list only after its blind pass.** On the first full review (and a full re-review
of a redesigned change), the cold lens runs exactly as §sc-review states it — diff only, no list. Then:

1. **Freeze.** Its findings are **frozen verbatim** into the review artifact, under the reviewed HEAD sha,
   before the list is sent — the wave check's pattern (§`${CLAUDE_PLUGIN_ROOT}/docs/wave-check.md`).
2. **Compare.** Then send `state.reviewFocus` (entries and pins). For each entry it reports: `raised` —
   whether a frozen finding names that input or failure itself (a finding that only notices the pinning
   test exists does not count); and `pinHolds` — whether the `pinnedBy` test actually drives `input` and
   asserts `expected` through the real construction path, or, for an `n/a` pin, whether the named
   verification covers it. It may add findings; it never edits the frozen list.
3. **Record** `cold = { raised, finding, pinHolds, evidence, tree }` on the entry: `finding` the frozen
   finding it matched or `null`, `evidence` a `path:line` for `pinHolds`, `tree` the reviewed tree
   identity.

**Host without live messaging:** two agents on the same pinned model and effort — the first runs the blind
pass, its frozen findings go to the second with the list (§`${CLAUDE_PLUGIN_ROOT}/docs/runtime-adapters.md`).

**Missed or not covered → items to verify.** Every entry with `raised: false` or `pinHolds: false` is
listed in the sc-review lenses' brief as an item to verify, by the mechanism implementer concerns and
wave-check items use (§sc-review — Triage), and gets a disposition there (fixed-here / filed-as `#NN`). A
missed entry whose pin holds is dispositioned `fixed-here` citing its `pinnedBy`; a pin that does not hold
is a finding — add or fix the test, or file it. The delta pass does not get the list: a fixed-here item is
a prior finding it verifies like any other.
<!-- /review-focus-cold -->

<!-- review-focus-tier -->
**Tier S and route skips.** When sc-design does not run — a route skip or the Tier S collapse — sc-tdd,
which runs for any change with a contract, writes the list itself: **at most two** entries, same shape,
`source: "sc-tdd"`, listed in the G4 report to the user. When sc-tdd is route-skipped too (layout, copy or
config), the field stays **absent**: the cold lens has no compare step and nothing is carried to G8 — its
blind pass and the designer lens still run. A cycle whose route grows sc-design to `run` rewrites the list
there.
<!-- /review-focus-tier -->

## Record and readers

<!-- review-focus-record -->
`state.reviewFocus` holds one entry per item: `id`, `input`, `impliedBy`, `uncovered`, `expected`,
`source` (`sc-design` or `sc-tdd`), `pinnedBy` (written at G4) and `cold` (written at G8, `null` until
then). Readers: sc-tdd (G4 pins), sc-review (the compare step, the brief and G8), sc-ship G11 (each entry
is mapped to its pin's evidence like a criterion) and sc-retro (did the cold lens find what the list named,
and did a later defect sit in an input the list left off). The list sets no gate value of its own: G4
requires every entry pinned, G8 a disposition for every missed or uncovered entry.
<!-- /review-focus-record -->
