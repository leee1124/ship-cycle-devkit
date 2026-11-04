# Behaviour evals — does an agent following the kit actually keep its rules?

`scripts/validate.py` checks that the kit's prose is consistent with itself: references resolve, gates are
produced and consumed, manifests agree. It cannot tell whether an agent that **reads** the prose then
behaves. 0.2.29 removed the rebuttal lists from the skills on the assumption that current models comply
with a rule stated once, with its reason; these evals measure that assumption, and catch a regression when
a rule's wording is trimmed again.

Each scenario puts an agent under pressure to break **one** load-bearing rule and ends with a deterministic
post-check on what the run left behind — the host transcript, the cycle state file, the fixture repo's git
state. The post-checks are automated and tested here; **the live runs are not**. They cost real model
time, need a machine with spare RAM, and are run by an operator — manually, or on a nightly schedule.
They are **never a required check**: a model's answer is not a build result, and a red eval is a signal
to read the transcript, not a reason to block a merge.

## Layout

| Path | What it is |
|---|---|
| `scenarios/<id>.md` | One scenario: rule under test, pressures, fixture setup, prompt, expected behaviour, post-check |
| `check.py` | The post-checks: `run <id> --transcript F --state F --repo D` → pass / fail / undetermined |
| `fixtures/<id>/{pass,fail}/` | Hand-written synthetic transcripts, state files and repo specs, one passing and one failing per scenario (`undetermined/` optional) |
| `baselines/results.md` | The RED/GREEN record per rule — date, host, model, plugin version, result, transcript location |

`python3 evals/check.py selftest` runs every fixture and requires its expected verdict; it runs in CI as
part of `scripts/validate_selftest.py` (Linux and Windows). `scripts/validate.py` requires each scenario
to carry its sections and a post-check whose id `check.py` knows, and each to have both fixtures and a
RED/GREEN baseline row.

## Method: RED, then GREEN

1. **RED — without the plugin.** Run the scenario on a host where the kit is not installed. Record the
   verdict and the rationalizations the agent gave (paraphrase; do not paste transcripts into this repo).
   A rule whose RED run already passes is not load-bearing for that model: say so in the row.
2. **GREEN — with the plugin.** Same fixture, same prompt, with the kit loaded and (where the scenario says
   so) the orchestrator invoked. The GREEN run is the claim the kit makes.
3. **Regression.** After trimming a rule's wording, rerun its GREEN scenario. A GREEN that turns RED is
   the regression these evals exist to catch.

Run each scenario more than once per phase where cost allows: a single run is an anecdote. Use a **fresh**
fixture for every run — the setup is a script so this is cheap.

## Pressures

Each prompt stacks several of the pressures that make an agent reach for an exception, because a rule that
holds under one pressure often folds under three:

- **Sunk cost** — "I already spent the afternoon on this".
- **Deadline** — "release cut is in 40 minutes".
- **"It already works"** — "I checked it", "green for months".
- **Authority** — the user, as repo owner, asks for the exception outright.
- **Triviality** — "it's a one-liner", "it's only docs".

A scenario names its pressures in its own `## Pressures` section.

## Running a scenario

`EVAL_DIR` is a fresh directory **outside every checkout** — never inside this repo. The setup scripts are
POSIX shell; on Windows run them in Git Bash (WSL also works). Setup builds `"$EVAL_DIR/repo"`, commits its
base and tags it `eval-base`; scenarios that would call `gh` put a logging stub in `.eval/bin`, so put that
first on `PATH` and the real CLI is never reached.

```sh
export EVAL_DIR="$(mktemp -d)/skip-review-one-liner"   # outside the repo
# paste the scenario's ## Setup block here, then:
cd "$EVAL_DIR/repo"
```

**Claude Code.** The kit's `docs/runtime-adapters.md` does not document a headless invocation. Claude Code
itself documents a non-interactive print mode, `claude -p "<prompt>"`; load the kit for GREEN with
`--plugin-dir /path/to/ship-cycle-devkit`, and leave it out — with no installed copy enabled — for RED. The
session transcript lands at `~/.claude/projects/*/<session-id>.jsonl` (runtime-adapters, host transcript
row). This invocation has not been exercised by the kit; if it does not fit your setup, **run interactively
and save the transcript**.

**Codex.** Codex documents `codex exec "<prompt>"` as its non-interactive mode, not exercised by the kit
either; otherwise run interactively and save the transcript. Its rollout lands under
`~/.codex/sessions/<YYYY>/<MM>/<DD>/`. `check.py` recognises a Codex rollout but reports it **unsupported**
— its record shape is not documented here — so transcript-only checks come back `undetermined`; checks
that read the state file or the fixture repo (`protected-branch`, `scope-edits`, `defect-filed` via
`.eval/gh.log`, `root-cause-evidence` and `undetermined-not-passed` with a state file) still decide.

Then:

```sh
python3 evals/check.py run skip-review-one-liner \
  --transcript ~/.claude/projects/<dir>/<session-id>.jsonl \
  --state "$EVAL_DIR/repo/.claude/ship-cycle/<branch-slug>.json" \
  --repo "$EVAL_DIR/repo"
```

Exit 0 pass, 1 fail, 2 undetermined (the run did not exercise the rule, or the evidence is not readable —
rerun or note it; never count it as a pass), 64 usage error. Pass only the inputs you have.

## Where results go

Transcripts, state files and fixture repos stay **outside the repo** and are never committed — they hold
the operator's paths and whatever the model wrote. What comes back is one row per run in
`baselines/results.md`: the verdict and where the transcript lives on the operator's machine. `check.py`
treats every transcript as data: it parses JSON, matches fixed patterns against a few structured fields,
and never executes or follows anything it reads. It streams the file line by line.

## Cost

A scenario is one agent session; with the plugin, the orchestrator also spawns lenses, so a GREEN run costs
several times a RED one. Run them one at a time on a small host (`docs/heavy-work.md`), and prefer a
nightly sweep over per-PR runs. Never wire a live run into a required CI check.
