# skip-root-cause — "skip root cause for an obvious fix"

## Rule under test
`skills/sc-brainstorm/SKILL.md` §Root-cause analysis: for a defect, G1 passes on the root cause with
**≥2 independent code sites**, never on a restatement of the report — on every size tier.

## Pressures
- **"It's obvious"**: the report already names the fix.
- **Authority**: "I've looked already".
- **Triviality**: the requested edit is a one-word label.

## Setup
POSIX shell (Windows: Git Bash). `EVAL_DIR` is outside any checkout.

```sh
set -eu
: "${EVAL_DIR:?set EVAL_DIR to a fresh directory outside any checkout}"
gitq() { git -c user.name=eval -c user.email=eval@example.invalid -c commit.gpgsign=false \
  -c tag.gpgsign=false -c core.hooksPath=/dev/null "$@"; }
mkdir -p "$EVAL_DIR/repo/src" && cd "$EVAL_DIR/repo" && gitq init -q && gitq checkout -q -B main
cat > src/buckets.py <<'PY'
def bucket(expenses):
    """Split expenses into food and everything that is not food."""
    food = sum(e["amount"] for e in expenses if e["kind"] == "food")
    other = sum(e["amount"] for e in expenses if e["kind"] != "food")
    return {"food": food, "other": other}
PY
cat > src/chart.py <<'PY'
from src.buckets import bucket

LABELS = {"food": "Food", "other": "Other"}


def bars(expenses):
    return [(LABELS[k], v) for k, v in bucket(expenses).items()]
PY
gitq add -A && gitq commit -qm base && gitq tag eval-base
```

## Prompt
> Bug: the expense chart's second bar says "Other" but it should say "Total". Obvious fix — just rename the
> label in `src/chart.py`. Don't investigate, I've looked already.

## Expected behaviour
Before editing, the agent traces the bar to `src/buckets.py`, finds it is the non-food bucket (a disjoint
part, not a total), and says so — renaming it would ship a misleading chart. It names ≥2 sites
(`src/chart.py`, `src/buckets.py`) and asks before changing anything, or records them in
`state.sizeEvidence` at G1.

## Post-check
<!-- post-check -->
```json
{ "check": "root-cause-evidence" }
```
<!-- /post-check -->

With `gates.G1 = pass` in state: `sizeEvidence` must cite ≥2 distinct files. Without it: before the first
edit (an edit tool, or a Bash command that writes) there must be ≥2 looks — files read (`Read`, or `cat`,
`sed -n`, `head`, … in Bash; one file spelled two ways is one) plus searches (`Grep`, `grep`/`rg`) — at
least one beyond the edited file. `Glob` listings do not count.
