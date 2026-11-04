# RED/GREEN results per rule

One row per run. **RED** = without the plugin, **GREEN** = with it (`evals/README.md` §Method). Rows start
as "not yet run"; never fill one in without a run behind it. The transcript column is a location on the
operator's machine — transcripts are never committed. `check.py`'s verdict is a heuristic: a result counts
only once a person has read the transcript and agrees, and **checked by** names that person.

Template for a new row:

`| <scenario> | RED or GREEN | <YYYY-MM-DD> | <host + version> | <model> | <plugin version or "none"> | <pass / fail / undetermined> | <transcript path outside the repo> | <who read the transcript> | <one-line note> |`

| scenario | phase | date | host | model | plugin version | result | transcript location | checked by | note |
|---|---|---|---|---|---|---|---|---|---|
| skip-review-one-liner | RED | — | — | — | none | not yet run | — | — | — |
| skip-review-one-liner | GREEN | — | — | — | — | not yet run | — | — | — |
| piped-tail-green | RED | — | — | — | none | not yet run | — | — | — |
| piped-tail-green | GREEN | — | — | — | — | not yet run | — | — | — |
| fix-out-of-scope-inline | RED | — | — | — | none | not yet run | — | — | — |
| fix-out-of-scope-inline | GREEN | — | — | — | — | not yet run | — | — | — |
| omit-model | RED | — | — | — | none | not yet run | — | — | — |
| omit-model | GREEN | — | — | — | — | not yet run | — | — | — |
| skip-root-cause | RED | — | — | — | none | not yet run | — | — | — |
| skip-root-cause | GREEN | — | — | — | — | not yet run | — | — | — |
| unstartable-suite-passed | RED | — | — | — | none | not yet run | — | — | — |
| unstartable-suite-passed | GREEN | — | — | — | — | not yet run | — | — | — |
| commit-protected-branch | RED | — | — | — | none | not yet run | — | — | — |
| commit-protected-branch | GREEN | — | — | — | — | not yet run | — | — | — |
| found-defect-not-filed | RED | — | — | — | none | not yet run | — | — | — |
| found-defect-not-filed | GREEN | — | — | — | — | not yet run | — | — | — |
