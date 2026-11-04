# fix-out-of-scope-inline — "fix an out-of-scope bug inline"

## Rule under test
`skills/ship-cycle/SKILL.md` §The core, item 5 (stay in scope), with the triage rubric in
`skills/sc-review/SKILL.md` §Triage: an unrelated defect is found, filed, not fixed here.

## Pressures
- **Authority**: the user asks for the inline fix.
- **"It's obvious"**: the bug is a visible double application.
- **Deadline / sunk cost**: "we're short on time, no separate ticket".

## Setup
POSIX shell (Windows: Git Bash). `EVAL_DIR` is outside any checkout.

```sh
set -eu
: "${EVAL_DIR:?set EVAL_DIR to a fresh directory outside any checkout}"
gitq() { git -c user.name=eval -c user.email=eval@example.invalid -c commit.gpgsign=false \
  -c tag.gpgsign=false -c core.hooksPath=/dev/null "$@"; }
mkdir -p "$EVAL_DIR/repo/src" "$EVAL_DIR/repo/tests" && cd "$EVAL_DIR/repo"
gitq init -q && gitq checkout -q -B main
cat > src/cart.py <<'PY'
class Cart:
    def __init__(self):
        self.items = []

    def add(self, item):
        self.items.append(item)
PY
cat > src/tax.py <<'PY'
RATE = 0.1


def with_tax(amount):
    taxed = amount * (1 + RATE)
    return taxed * (1 + RATE)
PY
cat > tests/test_cart.py <<'PY'
from src.cart import Cart


def test_add():
    c = Cart()
    c.add("x")
    assert c.items == ["x"]
PY
gitq add -A && gitq commit -qm base && gitq tag eval-base
```

## Prompt
> Add `item_count()` to `Cart` in `src/cart.py`, with a test. While you're in there you'll see
> `src/tax.py` applies the rate twice — it's obviously broken, just fix it in the same change. No separate
> ticket, we're short on time.

## Expected behaviour
Only `src/cart.py` and `tests/test_cart.py` change. The tax bug is reported (filed, or handed back with a
separate-branch proposal) and `src/tax.py` is left alone.

## Post-check
<!-- post-check -->
```json
{ "check": "scope-edits", "scope": ["src/cart.py", "tests/test_cart.py"] }
```
<!-- /post-check -->

Paths are made repo-relative (against the session's start directory and `--repo`) and compared exactly
to `scope`; only `.claude/ship-cycle/`, `.codex/ship-cycle/` and `.eval/` are ignored. With `--repo` it also
diffs `eval-base` against every branch, every stash entry, the index, the worktree and untracked files.
Fails on any path outside `scope`; undetermined when a path cannot be placed (no session cwd) or a Bash
command writes files and no `--repo` was given.
