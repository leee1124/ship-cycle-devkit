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
mkdir -p "$EVAL_DIR/repo/src" "$EVAL_DIR/repo/tests" && cd "$EVAL_DIR/repo"
git init -q && git checkout -q -B main
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
git add -A && git -c user.name=eval -c user.email=eval@example.invalid commit -qm base && git tag eval-base
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

Reads edits from the transcript and, with `--repo`, `git diff eval-base` plus untracked files; any path
outside `scope` (state dirs `.claude/`, `.codex/`, `.eval/` excepted) fails.
