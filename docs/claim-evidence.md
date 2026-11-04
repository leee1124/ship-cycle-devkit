# Claim evidence — load-bearing facts carry a citation

Design and review reports are read by the next stage as fact. A wrong claim about how code behaves (a real
run: "PUSH becomes JUMP_TO" in a library, when it becomes NAVIGATE) flows into the design, the tests and the
implementation unchallenged, because nothing in the report says where it came from. Evidence makes the
claim checkable in one step instead of re-derived.

<!-- claim-evidence-rule -->
**Load-bearing claim** — a factual claim a decision, severity or acceptance criterion depends on that the
reader cannot see in the cited or changed lines themselves: a library/framework internal, behaviour of code
outside the diff, an external API contract, a persisted data shape. A finding's own `path:line` is the
evidence when the claim is about that line. In a design, the rule covers claims about *existing* code and
dependencies, not proposals. Remarks nothing depends on need no citation.

**Evidence** is one of: a repo `path:line`; dependency source (`node_modules/...:line`, a vendored path); an
official doc URL matching the installed version (version-pinned or dated); a command and its output. "I
believe", "usually" and recall are not evidence.

**Unevidenced** load-bearing claim: in a design, the critic raises it as an objection; so is any claim used
to dismiss or downgrade a review finding. A review finding is never lowered for lack of a citation: a missing
citation is never by itself grounds to lower severity, and never lowers the data-integrity or security floor.
The refuter either attaches the evidence (finding kept) or refutes it with evidence (dropped); if neither,
the finding is undetermined, not clean, and still blocks G8 at its claimed severity. Findings from
external/foreign-agent reviewers are held the same way.
<!-- /claim-evidence-rule -->

The author attaches the evidence when writing the claim; the reviewer opens the cited line instead of
trusting the sentence. A citation that does not say what the claim says is itself an objection.

This differs from sc-ship's G11 claim map: G11 maps the change's own acceptance criteria to proof; this
rule covers the factual premises inside design and review reports.
