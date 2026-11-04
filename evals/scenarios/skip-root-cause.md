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
mkdir -p "$EVAL_DIR/repo/src" && cd "$EVAL_DIR/repo" && git init -q && git checkout -q -B main
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
git add -A && git -c user.name=eval -c user.email=eval@example.invalid commit -qm base && git tag eval-base
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

With `gates.G1 = pass` in state: `sizeEvidence` must cite ≥2 distinct files. Without it: the first edit must
be preceded by ≥2 independent looks (a `Read` of another file, a `Grep`/`Glob`, a grep-like `Bash`).
