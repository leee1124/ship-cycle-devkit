# Design-only route — work that ends in a design document

Some work ends in a design document, not a PR: a data model for another team, an adversarial review of an
existing design, an interface contract between two systems. The default route always runs `sc-review` and
`sc-ship`, and `sc-ship` opens a PR, so this work did not fit: in practice the critic was run by hand as a
"critic-only" sc-design, and later the agent decided on its own to skip the kit because "it is design only" —
a decision the route plan exists to put in front of the user.

<!-- design-only-rule -->
**Chosen at G1, never by the agent alone.** sc-brainstorm proposes it when the criteria end in a document,
not a code change, and the user confirms it with the criteria, like any route. It is recorded as
`state.route.kind = "design-only"` (absent or `"code"` means the default route) and `state.route.designMode`:
`"architect+critic"` (write a design and attack it) or `"critic-only"` (attack an existing design, named by
path in the criteria). **Against "one stage's job → no cycle"**: a request to critique a design takes this
route when the user wants a sign-off record or a hand-off to a later code cycle; otherwise sc-design runs
standalone (§ship-cycle — Route plan).

**Stages and gate values.** `sc-design` runs. The route records `sc-tdd`, `sc-implement`, `sc-review` and
`sc-qa` as `skip: design-only route`; when G3 passes, the orchestrator writes `gates.G4`, `G5`, `G6`, `G7`,
`G7b`, `G8` and `G9` = `n/a: route — design-only route` (one log row each) and hands over from sc-design
**straight to sc-ship** — those stages are never entered, so their own route checks are not consulted. The
critic, a separate agent run until no objection is open, is the independent review. A design-only route that
turns out to need a code change is not stretched to cover it: it ends with the sign-off and hands off (below).

**Critic-only objections.** Reviewing someone else's design, the objection list *is* the deliverable and its
owner may never act on it here. Each objection therefore ends with a disposition in the owner's words, recorded
by sc-design only from the user's own turn: `accepted` (the owner takes it on), `rejected: <reason>`, or
`resolved` when the doc was changed and the critic ruled the fix holds. G3 for critic-only: no objection left
without one of these.

**Floors that still apply**: the branch guard when design docs are written into the repo; claim evidence on
every load-bearing claim about existing code or systems (§`${CLAUDE_PLUGIN_ROOT}/docs/claim-evidence.md`);
the critic run until no objection is `open` (G3); G11's claim map, with design sections and critic rounds as
evidence; the gate log and its archive. **Floors dropped, because they need code**: Red tests (G4), build,
tests, coverage and boot smoke (G5–G7b), the code review lenses (G8), QA and release smoke (G9), and the PR's
merge-tree conflict check — there is no code and no PR for them to apply to. Review focus is still written at
G2, but it is carried **in the design doc, unpinned**, and not mapped at G11 (no tests run here); a hand-off
reads it from there.

**Where the docs live — named at G10, one of three**: (a) outside the repo (a path or link the user gave);
(b) committed and pushed on a kept branch, named in the sign-off; (c) the user wants them merged — then this
route stops at the sign-off and the merge is a normal cycle (docs nature: `sc-tdd` `skip: copy`,
`sc-implement`, `sc-review` and `sc-ship` run, PR as usual). Docs left uncommitted in a worktree are none of
these: G10 does not pass.

**Document sign-off (sc-ship, in place of the PR)**: G10 writes `state.signOff.docs` and `where` (above); G11
maps each acceptance criterion to a doc section or a critic round, and the last critic round has zero `open`
objections; G12 shows the sign-off record to the user — where the docs live, what was reviewed (the design,
or the existing design under critic-only) and by how many critic rounds, zero unresolved objections, the
Gate summary rendered from state and log as for a PR body, and the route line — and passes only on the user's
answer, recorded with their words (`state.signOff.by: "owner"`, `words`, `at`). That replaces G12's whole PR
condition. G13 runs as usual, except: a worktree holding uncommitted sign-off docs is never removed, and a
kept docs branch is not deleted.

**Hand-off to a code cycle.** A later normal cycle may start from a signed-off design: its G1 records
`state.handoff = {from, designDocs, reviewFocus}` (the archived gate log, the doc paths, the focus read from
the doc). It branches from the kept docs branch, or from the base after the docs were merged; its sc-design
reads the carried design as round 1's input instead of writing from scratch, and the carried review focus
seeds `state.reviewFocus`; neither skips that cycle's own critic or gates.
<!-- /design-only-rule -->
