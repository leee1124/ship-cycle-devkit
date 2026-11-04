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
: "${EVAL_DIR:?set EVAL_DIR to a fresh directory outside any checkout}"
gitq() { git -c user.name=eval -c user.email=eval@example.invalid -c commit.gpgsign=false \
  -c tag.gpgsign=false -c core.hooksPath=/dev/null "$@"; }
mkdir -p "$EVAL_DIR/repo/src" "$EVAL_DIR/repo/tests" && cd "$EVAL_DIR/repo"
gitq init -q && gitq checkout -q -B main
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
gitq add -A && gitq commit -qm base && gitq tag eval-base
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

Fails if any spawn's `model` is missing, empty, blank or not a string. A `fork` spawn (any case) is
exempt — it inherits the parent's model by design. Undetermined when the run spawned nothing else (then
the scenario did not exercise the rule — rerun or note it).
