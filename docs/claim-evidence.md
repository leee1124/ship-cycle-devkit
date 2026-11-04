# Claim evidence — load-bearing facts carry a citation

Design and review reports are read by the next stage as fact. A wrong claim about how code behaves (a real
run: "PUSH becomes JUMP_TO" in a library, when it becomes NAVIGATE) flows into the design, the tests and the
implementation unchallenged, because nothing in the report says where it came from. Evidence makes the
claim checkable in one step instead of re-derived.

<!-- claim-evidence-rule -->
**Load-bearing claim** — a factual claim that a decision, a severity or an acceptance criterion depends on:
code behaviour, a library/framework internal, an API contract, a data shape. Remarks nothing depends on
need no citation.

**Evidence** is one of: a repo `path:line`; dependency source (`node_modules/...:line`, a vendored path); an
official doc URL; a command and its output. "I believe", "usually" and recall are not evidence.

**Unevidenced** load-bearing claim: the critic (design) or refuter (review) raises it as an objection; a
review finding resting on one is not kept as Critical/High until it is evidenced.
<!-- /claim-evidence-rule -->

The author attaches the evidence when writing the claim; the reviewer opens the cited line instead of
trusting the sentence. A citation that does not say what the claim says is itself an objection.
