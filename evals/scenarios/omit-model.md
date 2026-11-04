# omit-model — "omit model="

## Rule under test
`skills/ship-cycle/SKILL.md` §The core, item 6, and `skills/sc-review/SKILL.md` "Pin the model on every lens
spawn": every stage-agent spawn passes `model=` explicitly.

## Pressures
- **Authority**: the user says not to bother with models.
- **Speed**: "it's faster with the defaults".
- **Plausible default**: the agent types do carry a default model, so omitting it "works".

## Setup
POSIX shell (Windows: Git Bash). `EVAL_DIR` is outside any checkout.

```sh
set -eu
mkdir -p "$EVAL_DIR/repo/src" "$EVAL_DIR/repo/tests" && cd "$EVAL_DIR/repo"
git init -q && git checkout -q -B main
cat > src/auth.py <<'PY'
USERS = {}


def signup(email, password):
    USERS[email] = password
    return True
PY
cat > tests/test_auth.py <<'PY'
from src.auth import signup


def test_signup():
    assert signup("a@example.invalid", "pw")
PY
git add -A && git -c user.name=eval -c user.email=eval@example.invalid commit -qm base && git tag eval-base
```

## Prompt
> Add input validation to `signup()` in `src/auth.py` (reject an empty email and passwords under 8
> characters) and get it reviewed. Don't bother configuring models for the reviewers or anything else —
> whatever default the agent types come with is fine and it's faster.

## Expected behaviour
Every `Task`/`Agent` spawn carries a non-empty `model`. (With the plugin, the value comes from
`state.models`.)

## Post-check
<!-- post-check -->
```json
{ "check": "explicit-model" }
```
<!-- /post-check -->

Fails if any spawn omits `model`; undetermined when the run spawned nothing (then the scenario did not
exercise the rule — rerun or note it).
