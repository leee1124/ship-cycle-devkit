# Candidate bake-off — N attempts at the same problem, judged

Every other parallelism in this kit is **partition** parallelism: exclusive, non-competing slices —
worktree-per-stack, file-ownership waves, architects split by axis. Each agent owns a different piece and
the pieces are meant to fit together.

A **bake-off** is the opposite shape: N agents attack the *same* problem independently, a judge panel picks
a winner, and the winner is synthesized with whatever the runners-up got right. It is worth its cost only
where the solution space is genuinely wide and the right approach is honestly unknown — a novel algorithm,
an ambiguous design with no obvious winner. For everything else the single-track pipeline is correct and
several times cheaper.

It is **ceremony**: dialable by size tier and risk, never an outcome (§ship-cycle — the bright line).
Skipping the bake-off never skips the critic, G2/G3, or anything else.

**Design-only, and read-only.** A bake-off produces competing *design docs*, nothing else. It never takes a
worktree and never writes code: Stage 2 is read-only, and creating worktrees here would leak them past a
G13 teardown that only knows about the cycle's own. When the honest comparison needs a *measurement* rather
than an argument — two algorithms whose costs you cannot rank on paper — that is a **spike**, and a spike is
its own cycle with its own branch, not a sub-mode of this one.

## When it earns its cost

All three must hold. Any one missing and you are paying N× for an answer you already had:

1. **The solution space is wide.** More than one defensible approach exists, and they differ in *kind* —
   not "the same design with a different cache size".
2. **You cannot rank them on paper.** If the architect's tradeoff section can already name the winner and
   say why, that *is* the bake-off, done for the price of one agent. Run the bake-off when the honest
   tradeoff section reads "it depends on things we would have to build to find out".
3. **Being wrong is expensive.** The approach is load-bearing — an algorithm the product is built on, a
   boundary that will be hard to move later. A wrong-but-cheap-to-replace choice does not qualify.

**The operator asks for it. There is no automatic trigger, by design.** All three conditions above are
judgments an agent would be making about its own work, so an agent that finds a design hard can satisfy all
three by writing down that it did. Leaving activation with the operator is the only gate that does not
dissolve under self-assessment.

**Tier interaction.** A bake-off multiplies the design stage by N; it belongs on Tier L and needs a stated
reason to appear on Tier M. It never appears on Tier S — a change whose cause is corroborated by two code
sites has no uncertain solution space by construction.

## The stances must actually differ

Fan the *same* spec — identical acceptance criteria, identical constraints — to N candidates, each given a
different **stance** to argue from. Three is the usual number; two is enough when only two approaches are
credible, and above three the judge's job degrades faster than the candidate pool improves.

Default stances, when nothing better fits the problem:

| stance | optimizes for | tends to win when |
|---|---|---|
| **MVP-first** | the shortest path to a working, correct implementation | the requirement is likely to change under you |
| **Risk-first** | the failure modes — data loss, migration reversibility, authz, partial failure | the change is hard to undo |
| **Performance-first** | the cost curve at the size this actually runs at | the workload is known and large |

Pick stances that pull in genuinely different directions for *this* problem. Three variations on one idea
produce three near-identical docs, and the judge then picks between rounding errors while you pay triple.

### Blindness is an input contract, not a prohibition

"Candidates cannot see each other" is worthless as an instruction — a candidate that idly lists the artifact
dir has broken it without meaning to, and the breach leaves no trace. Make it true by construction instead:

- **Spawn all N in a single fan-out, before any of them returns.** A candidate started after a sibling
  finished is an editor of that sibling's doc, not an independent attempt.
- **Give each candidate its own output path and only its own**:
  `<artifact-dir>/bake-off/<stance>/design.md`. The spec, the acceptance criteria and that one path are its
  entire brief.
- **The judge is the first party handed all N paths.** Nothing before the judge has a reason to hold more
  than one.

**Every candidate runs at the same resolved model and effort** — `state.models['design']` and
`state.effort['design']`, passed explicitly on each spawn (§core 6). A stance must never lose because it was
routed to a cheaper model; that would invalidate the comparison the N× spend was for.

## Judge on criteria fixed before the candidates exist

Write the judging criteria, with their weights, **into `state.bakeOff.criteria` and print them, before the
fan-out**. Not "before reading the candidates" — before they are written, when there is nothing to tailor
the criteria to. Criteria recorded afterwards describe the winner you already liked, and the file looks
identical either way, so the ordering has to be a visible step rather than a promise. The judge's first line
restates the criteria it was handed, the same anti-drift trick `sc-review` uses for model pinning.

Good criteria are answerable from the docs and specific to this change: does it satisfy every acceptance
criterion; what does it cost to reverse; where does it fail first under load; how much of it is new surface
to maintain. "Elegance" is not a criterion.

**A panel, not a single judge.** Reuse `sc-review`'s lens machinery: 2–3 lenses drawn from the change's
nature — typically `algorithm` or `quality`, plus `security` when the change touches auth/data, plus the
**cold** lens, which is spec-blind and therefore the one most likely to notice that a candidate answers a
different question than the one asked. Each lens scores every candidate against the same criteria; the
scorecards merge into one ranking, and a disagreement between lenses is itself a finding about the
candidates. One judge is acceptable only when a single lens plainly covers every criterion — say so and
name the lens. Judging is the part of this ceremony that costs 1×, not N×; it is the wrong place to
economize.

- **No judge authored a candidate.** A candidate judging the pool grades its own work, which is the failure
  §core 1 exists to prevent.
- **Score every candidate against every criterion**, and write the losing reason down. The runners-up's
  discarded reasons are half the value of having run it: they are the objections the winner now has to
  survive.
- **A tie is a result.** If two candidates score the same, the honest report is "these are equivalent on
  our criteria" — take the simpler one and record that the tiebreak was simplicity, not a manufactured
  distinction.

## Synthesis is where a bake-off usually goes wrong

The winner is a starting point, not a verdict. Grafting the runners-up's good ideas is the point of running
several — and it is also how you end up with a design that no candidate actually validated, assembled from
parts that each worked in a different context.

So:

- **Name every graft explicitly** in the synthesized doc: what was taken, from which candidate, and why it
  survives outside the design that produced it.
- **Run the synthesized design through the critic as a whole**, not as a diff against the winner. It is new
  work; the critic pass that G3 requires has not happened to *it* yet.
- **Refuse a graft you cannot justify in one line.** Interesting-but-unmotivated pieces are how a design
  acquires surface nobody owns.

**The bake-off runs once.** G3 objections against the synthesized doc are repaired by a **single architect
working on the synthesized doc**, inside the normal design↔review loop and its loop cap. Re-fanning the
candidates is not a repair; it is a new activation decision, priced again, and it would overwrite the
losing-reason record this mode exists to produce.

## Record it

`state.bakeOff` — one bake-off per cycle, at the design stage:

```json
"bakeOff": { "stances": ["mvp-first", "risk-first", "performance-first"],
             "criteria": [{ "name": "reversibility", "weight": "high" }],
             "judgeLenses": ["algorithm", "cold"],
             "candidates": [{ "stance": "risk-first", "docPath": "<path>",
                              "verdict": "winner", "reason": "<why it won or lost>" }],
             "grafts": [{ "from": "mvp-first", "what": "<the piece>", "why": "<one line>" }],
             "converged": false }
```

`/status` prints the stances, whether a winner exists, and `converged`; `/resume` judges the candidates that
exist or re-fans only the missing stances rather than restarting all N.

**When every candidate lands in the same place, record `converged: true`.** It makes a tie honest, and it is
a real finding: this shape of change had one obvious approach and did not need the ceremony. Say so in the
PR summary at G11 — cycle state is deleted at G13, so the PR body is the only place the next person
choosing for a similar change can still read it.

**Cost.** The design stage's telemetry row records `candidates` (the count) and `stances`, so the readout
prints the multiplier next to the `design` row instead of folding an N× stage into a single number
(§`${CLAUDE_PLUGIN_ROOT}/docs/model-routing.md` — Cost readout). Per-candidate token counts are not
recorded: `telemetry.stages` holds one row per stage, and inventing a shape nothing writes would be worse
than an honest count.
