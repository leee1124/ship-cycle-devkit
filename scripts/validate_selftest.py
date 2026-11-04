#!/usr/bin/env python3
"""Self-test for scripts/validate.py.

A checker that cannot fail is indistinguishable from one that does not check -- the same false-green the kit
warns about at §core 2. So each check is exercised against a deliberately broken copy of the repo and must
report the error, and against the real repo and must not.

Dependency-free, stdlib only, and path-safe on Windows and Unix (including paths containing spaces).
Usage:  python3 scripts/validate_selftest.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VALIDATOR = REPO / "scripts" / "validate.py"
HOOK_TEST = REPO / "scripts" / "hook_test.py"
COPY_SKIP = {".git", "__pycache__", ".github"}


def run_validator(root: Path) -> tuple[int, str]:
    # UTF-8 both ways: messages carry non-ASCII (→, —) and a Windows console defaults to cp1252.
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, str(VALIDATOR), str(root)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )
    return proc.returncode, proc.stdout + proc.stderr


def run_eval_checker(root: Path) -> tuple[int, str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, str(root / "evals" / "check.py"), "selftest"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )
    return proc.returncode, proc.stdout + proc.stderr


def run_hook_test(hook: Path) -> tuple[int, str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, str(HOOK_TEST), str(hook)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )
    return proc.returncode, proc.stdout + proc.stderr


# Broken copies of the SessionStart hook its behaviour test must reject (#86): (name, old, new, expected).
HOOK_MUTATIONS = [
    ("hook echoes the park reason", '"; the park reason is recorded there"',
     '"; reason: " + state.parked.reason', "echoed state free text"),
    ("hook lets an error escape", "} catch (_) {\n  out = null;\n}", "} finally {}", "exit 1"),
    ("hook ignores the opt-out", "if (OFF_VALUES.has(off)) return null;", "", "expected silence"),
    ("hook prints any branch name", "const named = BRANCH_RE.test(branch);", "const named = true;",
     "[tag-character branch is never echoed]"),
    ("hook ignores the stdin cwd", "try { start = stdinCwd(); }", "try { start = null; }",
     "[cwd taken from stdin JSON]"),
    ("hook names the last gate when all are recorded",
     'const gateText = gate ? `next gate ${gate}` : "stage gates recorded - advance per the pipeline";',
     'const gateText = `next gate ${gate || "G13"}`;', "[combined n/a gate key: every stage gate recorded]"),
]
# POSIX only: the FIFO cases that catch it are skipped on Windows.
if os.name != "nt":
    HOOK_MUTATIONS.append(("hook reads a FIFO",
                           "if (!st || st === STOP || !st.isFile() || st.size > max) return null;",
                           "if (!st || st === STOP) return null;", "[FIFO as HEAD is never read (POSIX)]"))
    HOOK_MUTATIONS.append(("hook reads stdin until it closes",
                           'input = JSON.parse(Buffer.concat(chunks).toString("utf8"));\n      break;',
                           'input = JSON.parse(Buffer.concat(chunks).toString("utf8"));',
                           "[stdin complete but never closed does not stall]"))


def fresh_copy(dest: Path) -> Path:
    shutil.copytree(REPO, dest, ignore=shutil.ignore_patterns(*COPY_SKIP))
    return dest


def bump_codex_version(root: Path) -> None:
    """Give the Codex manifest a different (still valid) version from the Claude one."""
    path = root / ".codex-plugin" / "plugin.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    major, minor, patch = (int(p) for p in data["version"].split("."))
    data["version"] = f"{major}.{minor}.{patch + 1}"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _codex(root: Path) -> tuple[Path, dict]:
    path = root / ".codex-plugin" / "plugin.json"
    return path, json.loads(path.read_text(encoding="utf-8"))


def _write_codex(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def drop_interface_key(root: Path, key: str) -> None:
    path, data = _codex(root)
    data["interface"].pop(key, None)
    _write_codex(path, data)


def set_interface_key(root: Path, key: str, value: object) -> None:
    path, data = _codex(root)
    data["interface"][key] = value
    _write_codex(path, data)


def set_manifest_key(root: Path, key: str, value: object) -> None:
    path, data = _codex(root)
    data[key] = value
    _write_codex(path, data)


def mutate(path: Path, old: str, new: str, count: int = 1) -> None:
    """Replace the first `count` occurrences of `old` (`count=-1`: every one)."""
    text = path.read_text(encoding="utf-8")
    assert old in text, f"self-test fixture is stale: {old[:50]!r} not in {path.name}"
    path.write_text(text.replace(old, new, count), encoding="utf-8")


def swap_red_steps(root: Path) -> None:
    """Move the hypothesis step above the read-the-error step in docs/red-gate.md."""
    path = root / "docs" / "red-gate.md"
    text = path.read_text(encoding="utf-8")
    read_at = text.index("2. **Read the actual error.**")
    hyp_at = text.index("4. **One hypothesis, with evidence.**")
    path.write_text(text.replace("**Read the actual error.**", "@@R@@", 1)
                    .replace("**One hypothesis, with evidence.**", "**Read the actual error.**", 1)
                    .replace("@@R@@", "**One hypothesis, with evidence.**", 1), encoding="utf-8")
    assert read_at < hyp_at


def swap_wave_passes(root: Path) -> None:
    """Move the Spec alignment step above the Cold pass in docs/wave-check.md."""
    path = root / "docs" / "wave-check.md"
    text = path.read_text(encoding="utf-8")
    cold = text.index("1. **Cold pass.**")
    spec = text.index("2. **Spec alignment.**")
    end = text.index("**Host without live messaging**")
    path.write_text(text[:cold] + text[spec:end] + text[cold:spec] + text[end:], encoding="utf-8")


def swap_focus_steps(root: Path) -> None:
    """Move the Compare step above the Freeze step in docs/review-focus.md."""
    path = root / "docs" / "review-focus.md"
    text = path.read_text(encoding="utf-8")
    freeze = text.index("1. **Freeze.**")
    compare = text.index("2. **Compare.**")
    end = text.index("3. **Record**")
    path.write_text(text[:freeze] + text[compare:end] + text[freeze:compare] + text[end:], encoding="utf-8")


# (name, mutate_fn, substring that must appear in the output)
CASES = [
    (
        "dangling doc reference",
        lambda r: mutate(
            r / "skills" / "ship-cycle" / "SKILL.md",
            "${CLAUDE_PLUGIN_ROOT}/docs/state-file.md",
            "${CLAUDE_PLUGIN_ROOT}/docs/does-not-exist.md",
        ),
        "does not exist",
    ),
    (
        "bundled-doc reference missing the plugin root",
        lambda r: mutate(
            r / "skills" / "sc-design" / "SKILL.md",
            "`${CLAUDE_PLUGIN_ROOT}/docs/bake-off.md`",
            "(§docs/bake-off.md",
        ),
        "without ${CLAUDE_PLUGIN_ROOT}",
    ),
    (
        "state field documented but unread",
        lambda r: mutate(
            r / "docs" / "state-file.md",
            '"nature": ["backend"],',
            '"orphanField": true, "nature": ["backend"],',
        ),
        "no skill or command reads it",
    ),
    (
        "state field used but undocumented",
        lambda r: mutate(
            r / "skills" / "sc-qa" / "SKILL.md",
            "## Model routing",
            "Read `state.inventedField` first.\n\n## Model routing",
        ),
        "absent from docs/state-file.md",
    ),
    (
        "version drift between the two manifests",
        lambda r: bump_codex_version(r),
        "versions disagree",
    ),
    (
        "changelog version disagrees with the manifests",
        lambda r: mutate(r / "CHANGELOG.md", "## 0.", "## 99.99.99 — drift\n\n## 0."),
        "versions disagree",
    ),
    (
        "skill frontmatter name does not match its directory",
        lambda r: mutate(r / "skills" / "sc-tdd" / "SKILL.md", "name: sc-tdd", "name: sc-wrong"),
        "!= directory",
    ),
    (
        "state field documented WITH prose beside it, but no real consumer",
        lambda r: (
            mutate(
                r / "docs" / "state-file.md",
                '"nature": ["backend"],',
                '"ghostField": true, "nature": ["backend"],',
            ),
            mutate(
                r / "docs" / "state-file.md",
                "## The slug",
                "`ghostField` records whether the ghost is present.\n\n## The slug",
            ),
        ),
        "no skill or command reads it",
    ),
    (
        "empty codex manifest",
        lambda r: (r / ".codex-plugin" / "plugin.json").write_text("{}\n", encoding="utf-8"),
        "missing required field",
    ),
    (
        "codex interface missing a required sub-field",
        lambda r: drop_interface_key(r, "category"),
        "interface missing required field 'category'",
    ),
    (
        "defaultPrompt is a string, not an array",
        lambda r: set_interface_key(r, "defaultPrompt", "just one prompt"),
        "must be an array",
    ),
    (
        "non-semver version",
        lambda r: set_manifest_key(r, "version", "1.2"),
        "not strict semver",
    ),
    (
        "bundled reference in backticks without the plugin root",
        lambda r: mutate(
            r / "skills" / "sc-qa" / "SKILL.md",
            "## Model routing",
            "See `docs/state-file.md` for the shape.\n\n## Model routing",
        ),
        "without ${CLAUDE_PLUGIN_ROOT}",
    ),
    (
        "gate in the table that no skill sets",
        lambda r: mutate(
            r / "skills" / "sc-ship" / "SKILL.md",
            "`gates.G10 = pass`",
            "the docs gate",
        ),
        "in the orchestrator's gate table but no stage skill sets it",
    ),
    (
        "gate only mentioned in prose, never assigned (#75)",
        lambda r: mutate(
            r / "skills" / "sc-ship" / "SKILL.md",
            "`gates.G10 = pass`",
            "`gates.G10` is unset",
        ),
        "in the orchestrator's gate table but no stage skill sets it",
    ),
    (
        "gate set by a skill but absent from the gate table",
        lambda r: mutate(
            r / "skills" / "sc-qa" / "SKILL.md",
            "## Model routing",
            "Set `gates.G99 = pass`.\n\n## Model routing",
        ),
        "absent from the orchestrator's gate table",
    ),
    (
        "stage literal outside the documented vocabulary",
        lambda r: mutate(
            r / "skills" / "sc-qa" / "SKILL.md",
            "## Model routing",
            'Set `stage: "paused"` while waiting.\n\n## Model routing',
        ),
        "is not in the stage vocabulary",
    ),
    (
        "stage vocabulary drops parked",
        lambda r: mutate(r / "docs" / "state-file.md", "`sc-ship`, `parked`,", "`sc-ship`,"),
        "stage vocabulary is missing 'parked'",
    ),
    (
        "bogus resumeStage in a json block",
        lambda r: mutate(
            r / "docs" / "state-file.md",
            '"resumeStage": "sc-brainstorm"',
            '"resumeStage": "sc-waiting"',
        ),
        "stage 'sc-waiting' is not in the stage vocabulary",
    ),
    (
        "stage vocabulary drops a pipeline stage",
        lambda r: mutate(r / "docs" / "state-file.md", "`sc-review`, `sc-qa`, `sc-ship`", "`sc-review`, `sc-ship`"),
        "stage vocabulary is missing 'sc-qa'",
    ),
    (
        "stage vocabulary anchor removed",
        lambda r: mutate(r / "docs" / "state-file.md", "<!-- stage-vocabulary -->", "<!-- stage list -->"),
        "no <!-- stage-vocabulary --> block found",
    ),
    (
        "example overlay coverage format outside the schema enum",
        lambda r: mutate(
            r / "docs" / "ship-cycle.config.example.json",
            '"format": "jacoco"',
            '"format": "xml"',
        ),
        "is not in the schema enum",
    ),
    (
        "example overlay coverage missing a required key",
        lambda r: mutate(
            r / "docs" / "ship-cycle.config.example.json",
            '"reportPath": "apps/backend/build/reports/jacoco/test/jacocoTestReport.xml",',
            "",
        ),
        "missing required field 'reportPath'",
    ),
    (
        "example overlay releaseSmoke missing its flows",
        lambda r: mutate(
            r / "docs" / "ship-cycle.config.example.json",
            '"flows": ["sign-in (email)", "sign-in (third-party SDK)", "start and finish a workout"],',
            "",
        ),
        "missing required field 'flows'",
    ),
    (
        "example overlay releaseSmoke artifact is not a command list",
        lambda r: mutate(
            r / "docs" / "ship-cycle.config.example.json",
            '"artifact": ["cd apps/mobile/android && ./gradlew assembleRelease"],',
            '"artifact": "cd apps/mobile/android && ./gradlew assembleRelease",',
        ),
        "'artifact' must be an array of strings",
    ),
    (
        "G12 row drops releaseChecklist",
        lambda r: mutate(r / "skills" / "ship-cycle" / "SKILL.md",
                         "every matched overlay `releaseChecklist` item", "every item"),
        "G12 row does not reference releaseChecklist",
    ),
    (
        "sc-ship loses its Release checklist rule",
        lambda r: mutate(r / "skills" / "sc-ship" / "SKILL.md", "**Release checklist (overlay",
                         "**Release list (overlay"),
        "no 'Release checklist' rule naming releaseChecklist",
    ),
    (
        "sc-ship Release checklist drops the manual gate",
        lambda r: mutate(r / "skills" / "sc-ship" / "SKILL.md", "list it under **\"Pre-merge manual gate\"**",
                         "mention it"),
        "not tied to the pre-merge manual gate",
    ),
    (
        "schema releaseChecklist loses the manual field",
        lambda r: mutate(r / "docs" / "ship-cycle.config.schema.json", '"manual": {', '"manualx": {'),
        "properties.releaseChecklist is missing or lacks",
    ),
    (
        "example overlay releaseChecklist item missing its evidence",
        lambda r: mutate(
            r / "docs" / "ship-cycle.config.example.json",
            '"evidence": "exit 0: versionCode/versionName are higher than the last released values"',
            '"x": 1',
        ),
        "missing required field 'evidence'",
    ),
    (
        "example overlay releaseChecklist duplicate id",
        lambda r: mutate(r / "docs" / "ship-cycle.config.example.json", '"id": "oauth-release-key-hash"',
                         '"id": "mobile-version-bump"'),
        "duplicate id",
    ),
    (
        "example overlay releaseChecklist bad when key",
        lambda r: mutate(r / "docs" / "ship-cycle.config.example.json", '"paths": ["apps/mobile/android',
                         '"path": ["apps/mobile/android'),
        "'when' must be a non-empty object",
    ),
    (
        "schema env loses heavyLock",
        lambda r: mutate(r / "docs" / "ship-cycle.config.schema.json", '"heavyLock": {', '"heavyLockx": {'),
        "env lacks heavyLock",
    ),
    (
        "schema maxConcurrentHeavy loses its minimum 1",
        lambda r: mutate(
            r / "docs" / "ship-cycle.config.schema.json",
            '"minimum": 1,\n          "description": "Heavy jobs allowed',
            '"minimum": 0,\n          "description": "Heavy jobs allowed'),
        "env lacks heavyLock (string)",
    ),
    (
        "schema heavyHeadroomMB loses its maximum",
        lambda r: mutate(r / "docs" / "ship-cycle.config.schema.json", '"maximum": 1048576,', ""),
        "needs minLength 1 and heavyHeadroomMB a maximum",
    ),
    (
        "heavy-work doc drops the nesting guard",
        lambda r: mutate(r / "docs" / "heavy-work.md", "SC_HEAVY_HELD", "SC_X", count=-1),
        "does not state 'SC_HEAVY_HELD'",
    ),
    (
        "example env maxConcurrentHeavy is zero",
        lambda r: mutate(r / "docs" / "ship-cycle.config.example.json", '"maxConcurrentHeavy": 1',
                         '"maxConcurrentHeavy": 0'),
        "env.maxConcurrentHeavy must be an integer >= 1",
    ),
    (
        "heavy-work doc drops the no-flock fallback",
        lambda r: mutate(r / "docs" / "heavy-work.md", "mkdir", "makedir", count=-1),
        "does not state 'mkdir'",
    ),
    (
        "heavy-work doc drops the fd-closing wrapper",
        lambda r: mutate(r / "docs" / "heavy-work.md", "{fd}>&-", "", count=-1),
        "does not state '{fd}>&-'",
    ),
    (
        "schema env has no properties (no crash)",
        lambda r: mutate(r / "docs" / "ship-cycle.config.schema.json", '"env": {\n      "type": "object",\n      "properties": {',
                         '"env": {\n      "type": "object",\n      "propertiesx": {'),
        "env lacks heavyLock",
    ),
    (
        "sc-qa stops referencing heavy-work",
        lambda r: mutate(r / "skills" / "sc-qa" / "SKILL.md", "docs/heavy-work.md", "docs/other.md"),
        "does not reference docs/heavy-work.md",
    ),
    (
        "sc-review regains smaller-batches advice",
        lambda r: mutate(r / "skills" / "sc-review" / "SKILL.md", "Lenses are read-only, so",
                         "Run in smaller batches; lenses are read-only, so"),
        "ad-hoc 'smaller batches'",
    ),
    (
        "example overlay uses when.release without vcs.releaseBranch",
        lambda r: mutate(r / "docs" / "ship-cycle.config.example.json", '"releaseBranch": "main",', ""),
        "vcs.releaseBranch is not declared",
    ),
    (
        "sc-ship PR template drops the Gate summary",
        lambda r: mutate(r / "skills" / "sc-ship" / "SKILL.md", "Gate summary", "Summary", count=-1),
        "does not include the 'Gate summary'",
    ),
    (
        "state-file.md loses its Gate log section",
        lambda r: mutate(r / "docs" / "state-file.md", "## Gate log", "## History"),
        "no '## Gate log' section",
    ),
    (
        "gate-log cell-escaping rule drops the length cap",
        lambda r: mutate(r / "docs" / "state-file.md", "**200 characters**", "a reasonable length"),
        "does not state '200 characters'",
    ),
    (
        "G12 row no longer requires the Gate summary",
        lambda r: mutate(
            r / "skills" / "ship-cycle" / "SKILL.md",
            "; PR body's **Gate summary** matches a fresh render from state + log,"
            " re-checked right before merge",
            "",
        ),
        "G12 row of the gate table does not require the Gate summary",
    ),
    (
        "G12 row weakened to 'matches the gate log'",
        lambda r: mutate(
            r / "skills" / "ship-cycle" / "SKILL.md",
            "matches a fresh render from state + log",
            "matches the gate log",
        ),
        "does not require the summary to match a fresh render",
    ),
    (
        "gate-log escaping no longer says it is applied once",
        lambda r: mutate(r / "docs" / "state-file.md", "applied exactly once", "applied everywhere"),
        "does not state 'applied exactly once'",
    ),
    (
        "sc-ship names no gate-log path",
        lambda r: mutate(r / "skills" / "sc-ship" / "SKILL.md", "<branch-slug>.log.md", "the log", count=-1),
        "does not name the gate log",
    ),
    (
        "sc-design loses the Entry-path inventory subsection",
        lambda r: mutate(r / "skills" / "sc-design" / "SKILL.md", "### Entry-path inventory", "### Entry points"),
        "no '### Entry-path inventory' subsection",
    ),
    (
        "sc-design Design checklist drops the Entry paths bullet",
        lambda r: mutate(r / "skills" / "sc-design" / "SKILL.md", "- **Entry paths**", "- Entry paths"),
        "no '**Entry paths**' bullet",
    ),
    (
        "sc-design critic stops checking the entry-path inventory",
        lambda r: mutate(
            r / "skills" / "sc-design" / "SKILL.md",
            "- **Entry-path inventory** (when",
            "- Entry-path inventory (when",
        ),
        "critic review has no '**Entry-path inventory**' bullet",
    ),
    (
        "claim-evidence doc loses its rule block",
        lambda r: mutate(r / "docs" / "claim-evidence.md", "path:line", "a location", count=-1),
        "does not state 'path:line'",
    ),
    (
        "sc-design output drops the Claim evidence bullet",
        lambda r: mutate(
            r / "skills" / "sc-design" / "SKILL.md", "- **Claim evidence**: each", "- Claim evidence: each"
        ),
        "design output has no '**Claim evidence**' bullet",
    ),
    (
        "sc-design critic drops the Claim evidence bullet",
        lambda r: mutate(
            r / "skills" / "sc-design" / "SKILL.md", "- **Claim evidence**: every", "- Claim evidence: every"
        ),
        "critic review has no '**Claim evidence**' bullet",
    ),
    (
        "claim-evidence rule loses the never-downgrade-for-missing-citation sentence",
        lambda r: mutate(r / "docs" / "claim-evidence.md", "never by itself", "sometimes"),
        "does not state 'never by itself'",
    ),
    (
        "sc-review Claim evidence bullet allows downgrade",
        lambda r: mutate(
            r / "skills" / "sc-review" / "SKILL.md", "never by itself grounds", "grounds"
        ),
        "'never by itself' a downgrade",
    ),
    (
        "sc-review refuter stops opening the cited evidence",
        lambda r: mutate(
            r / "skills" / "sc-review" / "SKILL.md", "opens the cited evidence", "reads the finding"
        ),
        "refuter open the cited evidence",
    ),
    (
        "sc-review refutation no longer has to cite evidence",
        lambda r: mutate(
            r / "skills" / "sc-review" / "SKILL.md", "must cite its evidence", "may be asserted"
        ),
        "say a refutation must cite its evidence",
    ),
    (
        "sc-review output discipline drops the Claim evidence bullet",
        lambda r: mutate(
            r / "skills" / "sc-review" / "SKILL.md", "- **Claim evidence** —", "- Claim evidence —"
        ),
        "output & severity discipline has no '**Claim evidence**' bullet",
    ),
    (
        "route plan: sc-brainstorm G1 no longer records it",
        lambda r: mutate(
            r / "skills" / "sc-brainstorm" / "SKILL.md",
            "the route plan as `state.route` with its `confirmedAt`",
            "the plan with its `confirmedAt`",
        ),
        "Gate G1 section does not record the route plan",
    ),
    (
        "route plan: G1 gate row stops requiring it",
        lambda r: mutate(
            r / "skills" / "ship-cycle" / "SKILL.md",
            "acceptance criteria stated verifiably + **route plan**, user-agreed together",
            "acceptance criteria stated verifiably + user-agreed",
        ),
        "G1 row of the gate table does not require the route plan",
    ),
    (
        "route plan: the orchestrator section is gone",
        lambda r: mutate(
            r / "skills" / "ship-cycle" / "SKILL.md",
            "## Route plan — which stages run, decided at G1",
            "## Stage choice",
        ),
        "no '## Route plan' section",
    ),
    (
        "route plan: the rule loses growth-only",
        lambda r: mutate(r / "skills" / "ship-cycle" / "SKILL.md", "never removed", "sometimes removed"),
        "Route plan section does not state 'never removed'",
    ),
    (
        "route plan: sc-qa re-derives its skip instead of reading state.route",
        lambda r: mutate(
            r / "skills" / "sc-qa" / "SKILL.md", "state.route", "the plan", count=-1
        ),
        "skills/sc-qa/SKILL.md: does not read state.route",
    ),
    (
        "route plan: the documented shape lets review be skipped",
        lambda r: mutate(
            r / "docs" / "state-file.md", '"sc-review": "run"', '"sc-review": "skip: small diff"'
        ),
        "route.stages['sc-review'] must always be 'run'",
    ),
    (
        "route plan: a stage value that is neither run nor skip",
        lambda r: mutate(r / "docs" / "state-file.md", '"sc-tdd": "run"', '"sc-tdd": "maybe"'),
        "route.stages['sc-tdd'] is not 'run' or 'skip: <reason>'",
    ),
    (
        "route plan: /status does not show it",
        lambda r: mutate(r / "commands" / "status.md", "`route`", "the plan", count=-1),
        "does not show the route plan",
    ),
    (
        "route plan: the rule no longer limits a tdd skip to layout/copy/config",
        lambda r: mutate(r / "skills" / "ship-cycle" / "SKILL.md", "layout, copy or config", "small"),
        "Route plan section does not state 'layout, copy or config'",
    ),
    (
        "route plan: the rule drops the standalone terminal-state clause",
        lambda r: mutate(
            r / "skills" / "ship-cycle" / "SKILL.md", "ignores a terminal state file", "reads the state file"
        ),
        "Route plan section does not state 'ignores a terminal state file'",
    ),
    (
        "route plan: sc-tdd honours a skip even when the change has a contract",
        lambda r: mutate(r / "skills" / "sc-tdd" / "SKILL.md", "grow the entry to `run`", "note it"),
        "Route first does not restrict a tdd skip",
    ),
    (
        "route plan: sc-review lens set loses the risk-matched term",
        lambda r: mutate(r / "skills" / "sc-review" / "SKILL.md", "risk-matched", "matching"),
        "lens selection does not state 'risk-matched'",
    ),
    (
        "route plan: sc-design skips without checking the basis",
        lambda r: mutate(r / "skills" / "sc-design" / "SKILL.md", "state.route.basis", "the plan"),
        "skills/sc-design/SKILL.md: does not check state.route.basis",
    ),
    (
        "route plan: G12 accepts a route n/a whose stage grew back",
        lambda r: mutate(
            r / "skills" / "sc-ship" / "SKILL.md", "whose `state.route` entry is now `run`", "that is stale"
        ),
        "G12 does not refuse an `n/a: route` gate",
    ),
    (
        "route plan: /status flags every n/a, config ones included",
        lambda r: mutate(r / "commands" / "status.md", "(G2/G3, G4, G9)", "(any)"),
        "unplanned-n/a flag is not limited to whole-stage gates",
    ),
    (
        "route plan: the documented shape has no basis",
        lambda r: mutate(
            r / "docs" / "state-file.md", '"basis": { "size"', '"basisGone": { "size"'
        ),
        "route lacks 'basis'",
    ),
    (
        "route plan: the pipeline table yields no stages",
        lambda r: mutate(r / "skills" / "ship-cycle" / "SKILL.md", "| `sc-", "| sc-", count=-1),
        "pipeline table yields no stage skills",
    ),
    (
        "route plan: G12 row accepts any whole-stage n/a",
        lambda r: mutate(
            r / "skills" / "ship-cycle" / "SKILL.md",
            "whole-stage G2/G3, G4 or G9 `n/a` whose route entry is `run`", "stale route n/a",
        ),
        "G12 row does not refuse a whole-stage n/a",
    ),
    (
        "route plan: sc-ship G12 refuses only n/a: route, not unplanned whole-stage n/a",
        lambda r: mutate(
            r / "skills" / "sc-ship" / "SKILL.md", "whole-stage `n/a` (G2/G3, G4, G9)", "`n/a: route` gate"
        ),
        "G12 does not refuse every whole-stage n/a",
    ),
    (
        "route plan: basis has no nature",
        lambda r: mutate(
            r / "docs" / "state-file.md", '"nature": ["backend"] },', '"natureGone": ["backend"] },'
        ),
        "route.basis lacks 'nature'",
    ),
    (
        "route plan: cancel cleanup deletes a branch PREFLIGHT did not create",
        lambda r: mutate(r / "skills" / "ship-cycle" / "SKILL.md", "(`state.branchCreated`) ", ""),
        "Route plan section does not state '`state.branchCreated`'",
    ),
    (
        "visualCheck schema stops requiring profiles",
        lambda r: mutate(
            r / "docs" / "ship-cycle.config.schema.json",
            '"required": ["run", "profiles"]',
            '"required": ["run"]',
        ),
        "visualCheck is missing",
    ),
    (
        "visualCheck schema block opened",
        lambda r: mutate(
            r / "docs" / "ship-cycle.config.schema.json",
            '"required": ["run", "profiles"],\n            "additionalProperties": false',
            '"required": ["run", "profiles"],\n            "additionalProperties": true',
        ),
        "visualCheck is missing",
    ),
    (
        "no example nature declares visualCheck",
        lambda r: mutate(
            r / "docs" / "ship-cycle.config.example.json",
            '"visualCheck": {',
            '"visualCheckOff": {',
            count=-1,
        ),
        "no changeNature declares visualCheck",
    ),
    (
        "example visualCheck loses profiles",
        lambda r: mutate(
            r / "docs" / "ship-cycle.config.example.json",
            '"profiles": ["desktop',
            '"profilez": ["desktop',
        ),
        "missing required field 'profiles'",
    ),
    (
        "live loop drops the dev-build-not-release rule",
        lambda r: mutate(r / "docs" / "visual-check.md", "release-form", "release", count=-1),
        "does not state 'a release-form build installed on the device cannot reload'",
    ),
    (
        "live loop drops labelled prototypes",
        lambda r: mutate(r / "docs" / "visual-check.md", "`variant A`", "`option`", count=-1),
        "does not state 'labelled `variant A`'",
    ),
    (
        "visual evidence drops the unattended fallback",
        lambda r: mutate(r / "docs" / "visual-check.md", "agent-captured", "captured", count=-1),
        "does not state '**`review-only (agent-captured)`**'",
    ),
    (
        "a11y floor drops reduced motion",
        lambda r: mutate(r / "docs" / "visual-check.md", "**reduced motion**", "**motion**"),
        "a11y-floor block does not state 'reduced motion'",
    ),
    (
        "design-tool adapter drops read-only",
        lambda r: mutate(r / "docs" / "visual-check.md", "used read-only in review", "used in review"),
        "design-tool adapter does not state 'read-only'",
    ),
    (
        "design-tool adapter drops the polish hook",
        lambda r: mutate(r / "docs" / "visual-check.md", "`polish` —", "polish —"),
        "no `polish` hook",
    ),
    (
        "sc-implement loses the live visual loop",
        lambda r: mutate(
            r / "skills" / "sc-implement" / "SKILL.md",
            "## Live visual loop (UI natures)",
            "## Visual notes",
        ),
        "no '## Live visual loop' section",
    ),
    (
        "live loop re-enters review per tweak",
        lambda r: mutate(
            r / "skills" / "sc-implement" / "SKILL.md",
            "**before the first sc-review only**",
            "**always**",
        ),
        "does not state 'before the first sc-review only'",
    ),
    (
        "sc-design loses the early reuse check",
        lambda r: mutate(
            r / "skills" / "sc-design" / "SKILL.md",
            "**Reuse check before any new component or token**",
            "**Reuse**",
        ),
        "does not state '**Reuse check before any new component or token**'",
    ),
    (
        "designer lens drops the largest font scale",
        lambda r: mutate(r / "skills" / "sc-review" / "SKILL.md", "largest font scale", "big fonts"),
        "designer lens does not state 'largest font scale'",
    ),
    (
        "sc-ship G11 drops the owner-confirmed label",
        lambda r: mutate(r / "skills" / "sc-ship" / "SKILL.md", "**`live (owner-confirmed)`**", "**`live`**"),
        "does not state 'live (owner-confirmed)'",
    ),
    (
        "pre-merge gate drops unconfirmed visual checks",
        lambda r: mutate(
            r / "skills" / "sc-ship" / "SKILL.md",
            "every `state.visualCheck` entry that is not",
            "every visual entry that is not",
        ),
        "'## PR (G12)' does not state 'every `state.visualCheck` entry",
    ),
    (
        "G11 row drops visualCheck",
        lambda r: mutate(
            r / "skills" / "ship-cycle" / "SKILL.md",
            "a UI nature's looks → `state.visualCheck`",
            "a UI nature's looks",
        ),
        "G11 row does not reference state.visualCheck",
    ),
    (
        "route plan stops naming the live visual loop",
        lambda r: mutate(r / "skills" / "ship-cycle" / "SKILL.md", "**live visual loop**", "**loop**"),
        "'## Route plan' does not state 'live visual loop'",
    ),
    (
        'stale rule drops the tree comparison',
        lambda r: mutate(
            r / "docs" / "visual-check.md",
            'its `tree` equals the final tree',
            'it looks recent',
        ),
        "does not state 'its `tree` equals the final tree'",
    ),
    (
        'sc-ship G11 stops checking the confirmation tree',
        lambda r: mutate(
            r / "skills" / "sc-ship" / "SKILL.md",
            '`visualCheck.tree` equals the final tree',
            'the confirmation is recent',
        ),
        "does not state '`visualCheck.tree` equals the final tree'",
    ),
    (
        "loop drops the owner's own words",
        lambda r: mutate(
            r / "docs" / "visual-check.md",
            "in the owner's own words in this run",
            'when it looks settled',
        ),
        'does not state "in the owner\'s own words in this run"',
    ),
    (
        'subagent may write owner-confirmed',
        lambda r: mutate(
            r / "docs" / "visual-check.md",
            '`agent-captured` at most.',
            'anything.',
        ),
        "writer rule does not state 'a subagent writes `agent-captured` at most'",
    ),
    (
        'state shape drops route.ownerPresent',
        lambda r: mutate(
            r / "docs" / "state-file.md",
            '"ownerPresent": true',
            '"ownerSeen": true',
        ),
        "route lacks 'ownerPresent'",
    ),
    (
        'sc-ship G11 accepts owner-confirmed without the owner',
        lambda r: mutate(
            r / "skills" / "sc-ship" / "SKILL.md",
            '`state.route.ownerPresent === true` (absent fails closed)',
            '`state.route.ownerPresent` is not `false`',
        ),
        "does not state '`state.route.ownerPresent === true` (absent fails closed)'",
    ),
    (
        'tweaks may change behaviour',
        lambda r: mutate(
            r / "docs" / "visual-check.md",
            'change goes back to',
            'change is fine, see',
        ),
        "does not state 'goes back to sc-tdd (Red first)'",
    ),
    (
        'owner confirmation backs behaviour claims',
        lambda r: mutate(
            r / "docs" / "visual-check.md",
            'backs appearance claims only',
            'backs every claim',
        ),
        "does not state 'backs appearance claims only'",
    ),
    (
        'state shape drops the prototype cleanup record',
        lambda r: mutate(
            r / "docs" / "state-file.md",
            '"cleanup": {',
            '"tidy": {',
        ),
        "visualCheck entry lacks 'cleanup'",
    ),
    (
        'G8 stops verifying prototype cleanup',
        lambda r: mutate(
            r / "skills" / "sc-review" / "SKILL.md",
            '**without being handed** `state.visualCheck[<nature>].cleanup`',
            'with `state.visualCheck[<nature>].cleanup`',
        ),
        "'## Gate G8' does not state '**without being handed**'",
    ),
    (
        'restore loses the abort path',
        lambda r: mutate(
            r / "docs" / "visual-check.md",
            'and on abort',
            'eventually',
        ),
        "does not state 'and on abort'",
    ),
    (
        'a11y floor becomes dialable',
        lambda r: mutate(
            r / "docs" / "visual-check.md",
            'not on the Tier S path, not by a route plan',
            'unless trivial',
        ),
        "does not state 'not on the Tier S path, not by a route plan'",
    ),
    (
        'Tier S bright line drops the accessibility floor',
        lambda r: mutate(
            r / "skills" / "ship-cycle" / "SKILL.md",
            'the accessibility floor —',
            'polish —',
        ),
        "'## Tier S path' does not state 'the accessibility floor'",
    ),
    (
        'runtime adapters drop the design-tool row',
        lambda r: mutate(
            r / "docs" / "runtime-adapters.md",
            '| design-tool adapter (`visualCheck.designTool`)',
            '| design tool',
        ),
        'no design-tool adapter row',
    ),
    (
        'absent ownerPresent no longer fails closed',
        lambda r: mutate(
            r / "docs" / "visual-check.md",
            '— absent or `false` fails closed;',
            '— unless `false`;',
        ),
        "does not state '`state.route.ownerPresent === true` — absent or `false` fails closed'",
    ),
    (
        'state-file drops the absent-fails-closed rule',
        lambda r: mutate(
            r / "docs" / "state-file.md",
            'absent or `false` fails closed',
            '`false` blocks',
        ),
        "route.ownerPresent rule does not state 'absent or `false` fails closed'",
    ),
    (
        'state-file lets ownerPresent flip without asking',
        lambda r: mutate(
            r / "docs" / "state-file.md",
            '`false → true` is allowed only by asking the owner',
            'it may change freely',
        ),
        "does not state '`false → true` is allowed only by asking the owner'",
    ),
    (
        'writtenBy treated as proof',
        lambda r: mutate(
            r / "docs" / "visual-check.md",
            '`writtenBy` is **advisory only**',
            '`writtenBy` is **proof**',
        ),
        "writer rule does not state '**advisory only**'",
    ),
    (
        'G11 trusts the recorded owner words',
        lambda r: mutate(
            r / "skills" / "sc-ship" / "SKILL.md",
            'find the recorded owner words as a user turn in your own conversation',
            'read the recorded owner words',
        ),
        "does not state 'as a user turn in your own conversation'",
    ),
    (
        'G11 no longer downgrades unverified owner words',
        lambda r: mutate(
            r / "docs" / "visual-check.md",
            'otherwise the entry is downgraded to',
            'otherwise keep it',
        ),
        "does not state 'downgraded to `agent-captured`'",
    ),
    (
        'cold lens is handed the cleanup record',
        lambda r: mutate(
            r / "docs" / "visual-check.md",
            'without being handed the record',
            'with the record',
        ),
        "does not state 'without being handed the record'",
    ),
    (
        'variant re-show keeps the old preLoopTree',
        lambda r: mutate(
            r / "docs" / "visual-check.md",
            'resets `preLoopTree` when it starts',
            'keeps `preLoopTree`',
        ),
        "does not state 'resets `preLoopTree`'",
    ),
    (
        'schema drops visualCheck.sharedPaths',
        lambda r: mutate(
            r / "docs" / "ship-cycle.config.schema.json",
            '"sharedPaths": {',
            '"sharedPathz": {',
        ),
        'visualCheck is missing',
    ),
    (
        'G11 row drops its three conditions',
        lambda r: mutate(
            r / "skills" / "ship-cycle" / "SKILL.md",
            'appearance only; not stale; `ownerPresent` true',
            'appearance',
        ),
        'G11 row does not reference state.visualCheck with',
    ),
    (
        'default profiles not concrete',
        lambda r: mutate(
            r / "docs" / "visual-check.md",
            'font scale 1.0 and at the OS maximum',
            'a few sizes',
        ),
        "does not state 'font scale 1.0 and at the OS maximum'",
    ),
    (
        "sc-retro skill missing",
        lambda r: shutil.rmtree(r / "skills" / "sc-retro"),
        "skills/sc-retro/SKILL.md: missing",
    ),
    (
        "sc-retro reports findings without a citation",
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            "**No citation → not reported**",
            "**A citation is preferred**",
        ),
        "retro-evidence-rule block does not state 'No citation → not reported'",
    ),
    (
        "sc-retro shows drafts before redacting",
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            "**Redaction pass, before any draft is shown.**",
            "**Redaction pass, before filing.**",
        ),
        "retro-redaction block does not state 'before any draft is shown'",
    ),
    (
        "sc-retro keeps the project name by default",
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            "unless the user opts in",
            "where helpful",
        ),
        "retro-redaction block does not state 'unless the user opts in'",
    ),
    (
        "sc-retro lets a subagent approve filing",
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            "a subagent cannot approve",
            "a subagent may approve",
        ),
        "retro-filing block does not state 'a subagent cannot approve'",
    ),
    (
        "sc-retro auto-files issues",
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            "Never auto-file, ",
            "",
        ),
        "retro-filing block does not state 'Never auto-file'",
    ),
    (
        "sc-retro sends transcripts off the machine",
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            "Transcripts are read locally only.",
            "Transcripts may be uploaded.",
        ),
        "retro-privacy block does not state 'read locally only'",
    ),
    (
        "sc-retro becomes a gate",
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            "## Model routing",
            "A clean retro sets `gates.G13 = pass`.\n\n## Model routing",
        ),
        "assigns a gate value; sc-retro is never a gate",
    ),
    (
        "sc-retro blocks a merge",
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            "never a gate and never blocks a merge",
            "a gate before merge",
        ),
        "'## Not a gate' does not state 'never a gate and never blocks a merge'",
    ),
    (
        "sc-retro drafts project-specific findings as kit issues",
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            "never drafted as kit\nissues",
            "drafted too",
        ),
        "'## Report' does not state 'never drafted as kit issues'",
    ),
    (
        "sc-retro drops a dimension",
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            "**User friction**",
            "**Other**",
        ),
        "'## Dimensions' does not state '**User friction**'",
    ),
    (
        "sc-retro needs a transcript to run",
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            "run on state + log only and say so",
            "stop",
        ),
        "'## Inputs' does not state 'run on state + log only and say so'",
    ),
    (
        "runtime-adapters loses the Codex transcript path",
        lambda r: mutate(
            r / "docs" / "runtime-adapters.md",
            "`~/.codex/sessions/",
            "`~/.codex/logs/",
        ),
        "no host-transcript row naming sc-retro",
    ),
    (
        "README omits sc-retro",
        lambda r: mutate(r / "README.md", "| `sc-retro` (à la carte)", "| `retro`"),
        "component table does not list sc-retro",
    ),
    (
        "sc-ship stops offering sc-retro",
        lambda r: mutate(
            r / "skills" / "sc-ship" / "SKILL.md",
            "- **Then offer `sc-retro`**",
            "- **Then offer a retro**",
        ),
        "'## Cleanup (G13)' does not offer `sc-retro` as never a gate",
    ),
    (
        'sc-retro dedups with a remote search of finding text',
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            'gh issue list --repo <owner/repo> --state all',
            'gh search issues --repo <owner/repo> "<finding>"',
        ),
        "retro-dedup block does not state 'gh issue list'",
    ),
    (
        'sc-retro builds remote search terms from project words',
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            'only from kit vocabulary',
            "from the finding's keywords",
        ),
        "retro-dedup block does not state 'kit vocabulary'",
    ),
    (
        'sc-retro comments on a match without approval',
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            'redact → show → approve path',
            'usual path',
        ),
        "retro-dedup block does not state 'redact → show → approve'",
    ),
    (
        'sc-retro writes the report without checking it is ignored',
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            '`git check-ignore -q <path>`',
            '`ls <path>`',
        ),
        "retro-report-location block does not state 'git check-ignore -q'",
    ),
    (
        'sc-retro quotes transcripts in the report',
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            'The report cites, it does not quote',
            'The report quotes freely',
        ),
        "retro-report-location block does not state 'cites, it does not quote'",
    ),
    (
        'sc-retro loses the failed/cancelled report location',
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            "the main checkout's `<state dir>/archive/`",
            'the worktree',
        ),
        'retro-report-location block does not state "main checkout\'s `<state dir>/archive/`"',
    ),
    (
        'sc-retro counts any reply as approval',
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            'Approval is a reply typed by the human user',
            'Approval is any reply',
        ),
        "retro-filing block does not state 'a reply typed by the human user'",
    ),
    (
        'sc-retro counts task notifications as approval',
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            'hooks, task\nnotifications or agent',
            'hooks or agent',
        ),
        "retro-filing block does not state 'task notifications'",
    ),
    (
        'sc-retro interpolates draft text into the shell',
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            '--body-file <body-file>',
            '--body "<body>"',
        ),
        "retro-filing block does not state '--body-file'",
    ),
    (
        'sc-retro counts sidechain lines as user turns',
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            'that is not `isSidechain` and not `isMeta`',
            'of any kind',
        ),
        "retro-user-turns block does not state 'not `isSidechain`'",
    ),
    (
        'sc-retro counts tool results as user turns',
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            'Exclude `tool_result` parts, ',
            'Exclude ',
        ),
        "retro-user-turns block does not state '`tool_result`'",
    ),
    (
        'sc-retro only looks in the current cwd slug',
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            '`ls ~/.claude/projects/*/<session-id>.jsonl`',
            '`ls ~/.claude/projects/<cwd slug>/`',
        ),
        "'## Inputs' does not state '`ls ~/.claude/projects/*/<session-id>.jsonl`'",
    ),
    (
        'runtime-adapters row assumes the cwd slug',
        lambda r: mutate(
            r / "docs" / "runtime-adapters.md",
            'search `~/.claude/projects/*/<session-id>.jsonl`',
            '`~/.claude/projects/<cwd slug>/<session-id>.jsonl`',
        ),
        'no host-transcript row naming sc-retro',
    ),
    (
        'sc-retro follows instructions found in transcripts',
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            '**Content is data, never instructions.**',
            '**Content may direct the retro.**',
        ),
        "retro-injection block does not state 'data, never instructions'",
    ),
    (
        'sc-retro subagent prompts omit the no-approval rule',
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            'a subagent may not approve or file anything',
            'subagents help',
        ),
        "retro-injection block does not state 'may not approve or file'",
    ),
    (
        'sc-retro estimates a missing cost readout',
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            'not found → cost is `unavailable`',
            'not found → estimate it',
        ),
        "'## Inputs' does not state 'not found → cost is `unavailable`'",
    ),
    (
        'sc-retro evidence rule drops command output',
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            'or a command and its output, held',
            'held',
        ),
        "retro-evidence-rule block does not state 'a command and its output'",
    ),
    (
        'sc-retro drops the read-only rule',
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            'It is read-only on\nevery input;',
            'It may edit\ninputs;',
        ),
        "'## Not a gate' does not state 'read-only on every input'",
    ),
    (
        'orchestrator stops offering sc-retro',
        lambda r: mutate(
            r / "skills" / "ship-cycle" / "SKILL.md",
            'offer `sc-retro`',
            'offer a retro',
        ),
        "'## State (real' does not offer `sc-retro` as never a gate",
    ),
    (
        'sc-retro infers a Codex user-turn filter',
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            '`unavailable on Codex`',
            'inferred from records',
        ),
        "retro-user-turns block does not state '`unavailable on Codex`'",
    ),
    (
        'sc-retro leaves truncation undefined',
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            '(returned count == the limit) ',
            '',
        ),
        "retro-dedup block does not state 'returned count == the limit'",
    ),
    (
        'sc-retro allows a multi-line title file',
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            'single line (no CR/LF, ≤256 chars)',
            'plain text file',
        ),
        "retro-filing block does not state 'single line (no CR/LF, ≤256 chars)'",
    ),
    (
        'sc-retro fallback may land in another checkout',
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            "outside every checkout's `git rev-parse --show-toplevel`",
            'anywhere',
        ),
        'retro-report-location block does not state "outside every checkout\'s `git rev-parse --show-toplevel`"',
    ),
    (
        'sc-retro confirms candidates by extracting text',
        lambda r: mutate(
            r / "skills" / "sc-retro" / "SKILL.md",
            'using counts only',
            'by reading the text',
        ),
        "'## Inputs' does not state 'using counts only'",
    ),
    (
        "eval scenario drops its pressures section",
        lambda r: mutate(r / "evals" / "scenarios" / "omit-model.md", "## Pressures", "## Stresses"),
        "no '## Pressures' section",
    ),
    (
        "eval scenario names a post-check the checker does not register",
        lambda r: mutate(r / "evals" / "scenarios" / "omit-model.md", '"check": "explicit-model"',
                         '"check": "model-pinned"'),
        "is not a check id registered",
    ),
    (
        "eval scenario points its rule at a skill that does not exist",
        lambda r: mutate(r / "evals" / "scenarios" / "skip-root-cause.md", "`skills/sc-brainstorm/SKILL.md`",
                         "`skills/sc-discover/SKILL.md`"),
        "which does not exist",
    ),
    (
        "eval scenario setup is not a shell script",
        lambda r: mutate(r / "evals" / "scenarios" / "commit-protected-branch.md", "```sh", "```text"),
        "has no ```sh setup script",
    ),
    (
        "eval scenario loses its failing fixture",
        lambda r: [shutil.rmtree(c) for c in (r / "evals" / "fixtures" / "omit-model").glob("fail*")],
        "no fixture evals/fixtures/omit-model/fail[-<label>]/",
    ),
    (
        "eval baseline record drops a GREEN row",
        lambda r: mutate(r / "evals" / "baselines" / "results.md", "| piped-tail-green | GREEN |",
                         "| piped-tail-green | LATER |"),
        "no GREEN row for scenario piped-tail-green",
    ),
    (
        "eval checker registers a check no scenario uses",
        lambda r: mutate(r / "evals" / "check.py", '    "defect-filed",\n)',
                         '    "defect-filed",\n    "orphan-check",\n)'),
        "'orphan-check' is used by no scenario",
    ),
    (
        "eval README stops saying the evals are never a required check",
        lambda r: mutate(r / "evals" / "README.md", "never a required check", "an optional check", count=-1),
        "does not state 'never a required check'",
    ),
    (
        "hook's stage->gate map drifts from the pipeline table",
        lambda r: mutate(r / "hooks" / "session-start.cjs", '"sc-review": ["G8"]', '"sc-review": ["G9"]'),
        "stage->gate map disagrees with the pipeline table for sc-review",
    ),
    (
        "hook's loop cap drifts from the orchestrator's",
        lambda r: mutate(r / "hooks" / "session-start.cjs", "const LOOP_CAP = 3;", "const LOOP_CAP = 4;"),
        "LOOP_CAP 4 disagrees",
    ),
    (
        "SessionStart matcher drops compact",
        lambda r: mutate(r / "hooks" / "hooks.json", '"startup|clear|compact"', '"startup|clear"'),
        "matcher must be exactly startup|clear|compact",
    ),
    (
        "hook command points at a script that does not exist",
        lambda r: mutate(r / "hooks" / "hooks.json", "session-start.cjs", "session-start.js"),
        "hooks/session-start.js, which does not exist",
    ),
    (
        "Claude manifest declares the auto-discovered hooks file",
        lambda r: mutate(r / ".claude-plugin" / "plugin.json", '"skills": "./skills/",',
                         '"skills": "./skills/",\n  "hooks": "./hooks/hooks.json",'),
        "declares 'hooks'",
    ),
    (
        "runtime-adapters stops documenting the hook opt-out",
        lambda r: mutate(r / "docs" / "runtime-adapters.md", "SHIP_CYCLE_HOOK", "THE_HOOK_VAR", count=-1),
        "('SHIP_CYCLE_HOOK' missing)",
    ),
    (
        "impl-status doc missing",
        lambda r: (r / "docs" / "impl-status.md").unlink(),
        "docs/impl-status.md: missing",
    ),
    (
        "impl-status vocabulary drops NEEDS_CONTEXT",
        lambda r: mutate(r / "docs" / "impl-status.md", "- `NEEDS_CONTEXT` — it stopped", "- it stopped"),
        "status vocabulary is",
    ),
    (
        "impl-status vocabulary drops the no-silent-end rule",
        lambda r: mutate(r / "docs" / "impl-status.md", "**No silent end.**", "**Endings.**"),
        "does not state 'No silent end'",
    ),
    (
        "impl-status vocabulary lets a report approve",
        lambda r: mutate(r / "docs" / "impl-status.md", "It never approves anything", "It may approve"),
        "does not state 'never approves anything'",
    ),
    (
        "a stack prompt drops a status",
        lambda r: mutate(r / "prompts" / "impl-web.md", "BLOCKED | NEEDS_CONTEXT", "BLOCKED"),
        "prompts/impl-web.md: report Status line lists",
    ),
    (
        "a stack prompt invents a status",
        lambda r: mutate(r / "prompts" / "impl-mobile.md", "| NEEDS_CONTEXT", "| NEEDS_CONTEXT | PARTIAL"),
        "prompts/impl-mobile.md: report Status line lists",
    ),
    (
        "a stack prompt drops the not-verified line",
        lambda r: mutate(r / "prompts" / "impl-backend.md", "- Not verified:", "- Notes:"),
        "report block has no '- Not verified:' line",
    ),
    (
        "a stack prompt drops the concerns line",
        lambda r: mutate(r / "prompts" / "impl-backend.md", "- Concerns:", "- Remarks:"),
        "report block has no '- Concerns:' line",
    ),
    (
        "a stack prompt loses the report block",
        lambda r: mutate(r / "prompts" / "impl-web.md", "## Report (end every turn", "## Wrap-up (end"),
        "template has no '## Report (end every turn ...' block",
    ),
    (
        "sc-implement routing table loses the design-defect row",
        lambda r: mutate(
            r / "skills" / "sc-implement" / "SKILL.md",
            "| `BLOCKED` (design defect) | → sc-design; counts toward the loop cap; at the cap the user "
                         "decides |\n",
            "",
        ),
        "routing table has no row for `BLOCKED` (design defect)",
    ),
    (
        "design defect stops counting toward the loop cap",
        lambda r: mutate(r / "skills" / "sc-implement" / "SKILL.md",
                         "→ sc-design; counts toward the loop cap;", "→ sc-design;"),
        "does not route via 'loop cap'",
    ),
    (
        "reasoning limit names a model instead of the tierMap",
        lambda r: mutate(r / "skills" / "sc-implement" / "SKILL.md",
                         "fresh agent one tier up via `tierMap`", "fresh agent one tier up on opus"),
        "does not route via '`tierMap`'",
    ),
    (
        "sc-implement allows an unchanged re-dispatch",
        lambda r: mutate(r / "skills" / "sc-implement" / "SKILL.md",
                         "**Never re-dispatch unchanged.**", "**Re-dispatch freely.**"),
        "does not state 'Never re-dispatch unchanged'",
    ),
    (
        "sc-implement drops the fresh-agent handoff",
        lambda r: mutate(r / "skills" / "sc-implement" / "SKILL.md",
                         "dispatch a fresh one with a written handoff", "keep resuming it"),
        "does not state 'fresh one with a written handoff'",
    ),
    (
        "state shape drops telemetry.implStatus",
        lambda r: mutate(r / "docs" / "state-file.md", '"implStatus"', '"implReports"'),
        "telemetry shape has no implStatus entry",
    ),
    (
        "sc-ship stops printing implStatus",
        lambda r: mutate(r / "skills" / "sc-ship" / "SKILL.md", "telemetry.implStatus", "telemetry.impl",
                         count=-1),
        "skills/sc-ship/SKILL.md: does not read `telemetry.implStatus`",
    ),
    (
        "a stack prompt's report block drifts from the doc's",
        lambda r: mutate(
            r / "prompts" / "impl-web.md",
            "- Changed: <files changed/added and their role; tests added>",
            "- Changed: <files>",
        ),
        "prompts/impl-web.md: report block differs from the one in docs/impl-status.md",
    ),
    (
        "a stack prompt drops the changed line",
        lambda r: mutate(r / "prompts" / "impl-mobile.md", "- Changed:", "- Files:"),
        "report block has no '- Changed:' line",
    ),
    (
        "impl-status stops applying Not verified to every status",
        lambda r: mutate(r / "docs" / "impl-status.md", "applies to every status, `DONE` included",
                         "applies to blocked reports"),
        "does not state 'applies to every status'",
    ),
    (
        "impl-status stops naming build-fixer as a carrier",
        lambda r: mutate(r / "docs" / "impl-status.md", "a stack implementer, a\nbuild-fixer, a debugger",
                         "a stack implementer, a\nfixer, a debugger"),
        "does not say a build-fixer agent carries the report block",
    ),
    (
        "DONE_WITH_CONCERNS skips the fix round without a recorded correctness reason",
        lambda r: mutate(
            r / "skills" / "sc-implement" / "SKILL.md",
            "skip only with a recorded reason it is not correctness/scope",
            "skip it when it looks minor",
        ),
        "does not route via 'correctness/scope'",
    ),
    (
        "a resume carries a tier change",
        lambda r: mutate(
            r / "skills" / "sc-implement" / "SKILL.md",
            "- **A tier-up re-dispatch is always a fresh agent**",
            "- A resume passes the routed model too.\n- **A tier-up re-dispatch is always a fresh agent**",
        ),
        "states 'resume passes the routed model'",
    ),
    (
        "a tier-up may resume the old agent",
        lambda r: mutate(
            r / "skills" / "sc-implement" / "SKILL.md",
            "**A tier-up re-dispatch is always a fresh agent**",
            "**A tier-up may resume**",
        ),
        "does not state 'A tier-up re-dispatch is always a fresh agent'",
    ),
    (
        "failure-driven re-dispatches stop counting toward the cap",
        lambda r: mutate(
            r / "skills" / "sc-implement" / "SKILL.md",
            "**Failure-driven re-dispatches count.**",
            "**Re-dispatches.**",
        ),
        "does not state 'Failure-driven re-dispatches count'",
    ),
    (
        "sc-implement drops the terminal stop route",
        lambda r: mutate(
            r / "skills" / "sc-implement" / "SKILL.md",
            "**Stop, never loop.**",
            "**When stuck.**",
        ),
        "does not state 'Stop, never loop'",
    ),
    (
        "tier-up steps from the PREFLIGHT base",
        lambda r: mutate(
            r / "skills" / "sc-implement" / "SKILL.md",
            "the\n  latest non-null `tier` in its",
            "the\n  PREFLIGHT tier, not its",
        ),
        "does not state 'latest non-null `tier`'",
    ),
    (
        "no-report route loops instead of stopping",
        lambda r: mutate(
            r / "skills" / "sc-implement" / "SKILL.md",
            "unknown → missing context once, then stop",
            "unknown → resume again",
        ),
        "does not route via 'missing context once'",
    ),
    (
        "design defect at the cap gets another sc-design round",
        lambda r: mutate(
            r / "skills" / "sc-implement" / "SKILL.md",
            "; at the cap the user decides |",
            "; at the cap re-design |",
        ),
        "does not route via 'user decides'",
    ),
    (
        "sc-review drops implementer concerns from triage",
        lambda r: mutate(
            r / "skills" / "sc-review" / "SKILL.md",
            "**Implementer concerns are items to verify.**",
            "**Concerns.**",
        ),
        "'## Triage' does not state 'Implementer concerns are items to verify'",
    ),
    (
        "G8 stops reading implementer concerns",
        lambda r: mutate(r / "skills" / "sc-review" / "SKILL.md",
                         "- **Every implementer concern handed to review has a disposition**",
                         "- **Concerns may be noted**"),
        "'## Gate G8' does not state 'implementer concern'",
    ),
    (
        "sc-ship G11 ignores open notVerified items",
        lambda r: mutate(r / "skills" / "sc-ship" / "SKILL.md", "**Open implementer `notVerified` items.**",
                         "**Implementer notes.**"),
        "'## Verify (G11)' does not state 'Open implementer `notVerified` items'",
    ),
    (
        "a loop-back's implement round counts twice",
        lambda r: mutate(r / "skills" / "sc-implement" / "SKILL.md", "once per gate loop-back", "every time"),
        "does not state 'once per gate loop-back'",
    ),
    (
        "a split counts once per child",
        lambda r: mutate(r / "skills" / "sc-implement" / "SKILL.md",
                         "A split increments the parent's counter once, not per child.",
                         "Each child of a split counts."),
        "does not state \"increments the parent's counter once\"",
    ),
    (
        "context fetches lose their own cap",
        lambda r: mutate(r / "skills" / "sc-implement" / "SKILL.md", "own per-brief cap of 3", "no cap"),
        "does not state 'own per-brief cap of 3'",
    ),
    (
        "NEEDS_CONTEXT row loses the fetch cap",
        lambda r: mutate(r / "skills" / "sc-implement" / "SKILL.md", "unobtainable or 3 fetches → stop",
                         "unobtainable → stop"),
        "does not route via 'unobtainable or 3 fetches → stop'",
    ),
    (
        "orchestrator loop cap returns to sc-design on its own again",
        lambda r: mutate(r / "skills" / "ship-cycle" / "SKILL.md",
                         "beyond that, stop:\npark the cycle and ask the user, who decides the next step, "
                         "`sc-design` included",
                         "beyond that, return to\n`sc-design` and notify the user"),
        "loop cap still returns to sc-design on its own",
    ),
    (
        "orchestrator loop cap stops pointing to sc-implement",
        lambda r: mutate(r / "skills" / "ship-cycle" / "SKILL.md",
                         "(§sc-implement — Route the implementer's status)", "(§sc-implement)"),
        "loop-cap sentence does not state \"Route the implementer's status\"",
    ),
    (
        "G12 manual gate omits open notVerified items",
        lambda r: mutate(r / "skills" / "sc-ship" / "SKILL.md",
                         "every open `implStatus.notVerified` item a claim depends on",
                         "every open implementer item"),
        "manual gate does not list",
    ),
    (
        "notVerified entries lose coveredBy",
        lambda r: mutate(r / "docs" / "state-file.md", '"coveredBy"', '"by"'),
        "implStatus.notVerified entries have no coveredBy",
    ),
    (
        "G11 stops treating null coveredBy as open",
        lambda r: mutate(r / "skills" / "sc-ship" / "SKILL.md", "`coveredBy` is `null`",
                         "`coveredBy` is unset"),
        "does not state '`coveredBy` is `null`'",
    ),
    # The wave check (#88).
    (
        "wave-check doc missing",
        lambda r: (r / "docs" / "wave-check.md").unlink(),
        "docs/wave-check.md: missing",
    ),
    (
        "wave check runs on Tier M too",
        lambda r: mutate(r / "docs" / "wave-check.md", "Tier S and Tier M never run it",
                         "Tier S never runs it"),
        "wave-check-trigger block does not state 'Tier S and Tier M never run it'",
    ),
    (
        "wave check reads a red barrier",
        lambda r: mutate(r / "docs" / "wave-check.md", "after that barrier's build/typecheck has passed",
                         "at that barrier"),
        "does not state \"after that barrier's build/typecheck has passed\"",
    ),
    (
        "wave check spec-alignment runs before the cold pass",
        lambda r: mutate(r / "docs" / "wave-check.md", "list before\n   the spec is sent",
                         "list with\n   the spec"),
        "wave-check-rule block does not state 'before the spec is sent'",
    ),
    (
        "wave check reviewer model not pinned",
        lambda r: mutate(r / "docs" / "wave-check.md", '`model = state.models["review.wave"]`',
                         "a cheap model"),
        "wave-check-rule block does not state",
    ),
    (
        "wave check stops the waves on any finding",
        lambda r: mutate(r / "docs" / "wave-check.md", "Only a **design** finding that survives verification",
                         "Any finding"),
        "does not state 'Only a **design** finding that survives verification'",
    ),
    (
        "wave check invents a second carry mechanism",
        lambda r: mutate(r / "docs" / "wave-check.md", "not a second one", "a mechanism of its own"),
        "wave-check-rule block does not state 'not a second one'",
    ),
    (
        "wave check heavy run escapes the lock",
        lambda r: mutate(r / "docs" / "wave-check.md", "goes under overlay `env.heavyLock`",
                         "runs directly"),
        "wave-check-rule block does not state '`env.heavyLock`'",
    ),
    (
        "wave check becomes a gate",
        lambda r: mutate(r / "docs" / "wave-check.md", "It does not\nreplace G8:",
                         "The wave check is a gate and it does not\nreplace G8:"),
        "a wave check is advisory and G8 stays the gate",
    ),
    (
        "wave check route skip drops the G8 fleet",
        lambda r: mutate(r / "docs" / "wave-check.md", "G8 still runs the full fleet",
                         "G8 runs fewer lenses"),
        "wave-check-route block does not state 'G8 still runs the full fleet'",
    ),
    (
        "sc-implement waved section loses the wave check",
        lambda r: mutate(r / "skills" / "sc-implement" / "SKILL.md",
                         "**Wave check at each barrier (Tier L).**", "**Barrier note.**"),
        "'## Large cross-cutting change' does not state 'Wave check at each barrier'",
    ),
    (
        "sc-review brief drops wave-check items",
        lambda r: mutate(r / "skills" / "sc-review" / "SKILL.md",
                         "**Wave-check items are items to verify, too.**", "**Wave notes.**"),
        "'## Triage' does not state 'Wave-check items are items to verify'",
    ),
    (
        "G8 stops requiring wave-check dispositions",
        lambda r: mutate(r / "skills" / "sc-review" / "SKILL.md",
                         "The same holds for every unresolved wave-check item in "
                         "`state.waveReviews` (§Triage).",
                         "Wave checks are advisory."),
        "does not require a disposition per wave-check item",
    ),
    (
        "route plan no longer dials the wave check",
        lambda r: mutate(r / "skills" / "ship-cycle" / "SKILL.md",
                         "`state.route.waveCheck` is `\"run\"` by default",
                         "the wave check is on by default"),
        "'## Route plan' does not state '`state.route.waveCheck`'",
    ),
    (
        "PREFLIGHT stops resolving the wave reviewer model",
        lambda r: mutate(r / "skills" / "ship-cycle" / "SKILL.md", 'as `models["review.wave"]` and',
                         "as a model and"),
        'PREFLIGHT does not resolve models["review.wave"]',
    ),
    (
        "effort table drops the wave check",
        lambda r: mutate(r / "skills" / "ship-cycle" / "SKILL.md",
                         "Tier S review; the wave check (§sc-implement);", "Tier S review;"),
        "medium row does not price the wave check",
    ),
    (
        "waveReviews entry loses its tree",
        lambda r: mutate(r / "docs" / "state-file.md", '"tree": "<tree id of this barrier>", ', ""),
        "waveReviews entry lacks 'tree'",
    ),
    (
        "route shape loses waveCheck",
        lambda r: mutate(r / "docs" / "state-file.md", '"waveCheck": "run", ', ""),
        "route lacks 'waveCheck'",
    ),
    (
        "sc-ship readout stops printing waveReviews",
        lambda r: mutate(r / "skills" / "sc-ship" / "SKILL.md", "one line per `state.waveReviews` entry",
                         "one line per wave check"),
        "skills/sc-ship/SKILL.md: does not read `state.waveReviews`",
    ),
    (
        "sc-retro stops reading waveReviews",
        lambda r: mutate(r / "skills" / "sc-retro" / "SKILL.md", "Read\n   `state.waveReviews`",
                         "Read\n   the wave checks"),
        "skills/sc-retro/SKILL.md: does not read `state.waveReviews`",
    ),
    (
        "wave check spec pass listed before the cold pass",
        lambda r: swap_wave_passes(r),
        "wave-check-rule puts Spec alignment before the Cold pass",
    ),
    (
        "wave check cold findings not frozen",
        lambda r: mutate(r / "docs" / "wave-check.md", "**frozen verbatim**", "noted"),
        "wave-check-rule block does not state '**frozen verbatim**'",
    ),
    (
        "wave check spec pass may retract cold findings",
        lambda r: mutate(r / "docs" / "wave-check.md", "never retracts or lowers one — only a refuter can",
                         "may retract one"),
        "does not state 'never retracts or lowers one — only a refuter can'",
    ),
    (
        "wave check cheap refutation drops a Critical",
        lambda r: mutate(r / "docs" / "wave-check.md", "**A cheap refutation never drops a Critical/High.**",
                         "**Refutations drop findings.**"),
        "does not state 'A cheap refutation never drops a Critical/High'",
    ),
    (
        "wave check loses the host fallback",
        lambda r: mutate(r / "docs" / "wave-check.md", "**Host without live messaging**", "**Other hosts**"),
        "wave-check-rule block does not state 'Host without live messaging'",
    ),
    (
        "wave check design stop no longer counts loops[G5]",
        lambda r: mutate(r / "docs" / "wave-check.md", "incrementing `loops[G5]`\n  once", "counting"),
        "does not state 'incrementing `loops[G5]` once'",
    ),
    (
        "wave check re-plan loses its new from",
        lambda r: mutate(r / "docs" / "wave-check.md", "latest non-superseded barrier\n  before it",
                         "previous barrier"),
        "does not state 'latest non-superseded barrier before it'",
    ),
    (
        "wave check multi-stack worktree unstated",
        lambda r: mutate(r / "docs" / "wave-check.md", "the worktree where the contract landed",
                         "some worktree"),
        "does not state 'the worktree where the contract landed'",
    ),
    (
        "unchecked barriers not recorded",
        lambda r: mutate(r / "docs" / "wave-check.md", "recorded, checked or not.**",
                         "recorded when checked.**"),
        "wave-check-barriers block does not state 'checked or not'",
    ),
    (
        "pruned from tree has no fallback",
        lambda r: mutate(r / "docs" / "wave-check.md", "diff from the\nbase instead", "stop"),
        "wave-check-barriers block does not state 'diff from the base instead'",
    ),
    (
        "waveBarriers shape loses its worktree",
        lambda r: mutate(r / "docs" / "state-file.md", '"worktree": "<path the barrier was taken in>"',
                         '"where": "<path>"'),
        "state shape has no waveBarriers entry with wave/tree/worktree",
    ),
    (
        "refutedItems lose their refutation",
        lambda r: mutate(r / "docs" / "state-file.md",
                         '"refutation": "<evidence: path:line or command → output>"', '"why": "<x>"'),
        "waveReviews.refutedItems entries lack item/where/refutation",
    ),
    (
        "reconcile stops rerunning a dead wave check",
        lambda r: mutate(r / "docs" / "state-file.md", "a wave check is rerun — cheap and idempotent",
                         "a wave check is dropped"),
        "reconcile's subagents-running row does not rerun a wave check",
    ),
    (
        "sc-review brief drops refuted wave items",
        lambda r: mutate(r / "skills" / "sc-review" / "SKILL.md",
                         '"previously flagged, refuted at wave N — confirm"', "refuted"),
        "'## Triage' does not state 'previously flagged, refuted at wave N — confirm'",
    ),
    (
        "growth-only sources omit the wave-check design defect",
        lambda r: mutate(r / "skills" / "ship-cycle" / "SKILL.md",
                         "a wave-check /\n  `BLOCKED` design defect", "a design defect"),
        "'## Route plan' does not state 'a wave-check / `BLOCKED` design defect'",
    ),
    (
        "Tier L row no longer names the wave check as skippable",
        lambda r: mutate(r / "skills" / "ship-cycle" / "SKILL.md", "a ceremony stage or the wave check",
                         "a ceremony stage"),
        "Tier L row does not let a route skip the wave check",
    ),
    (
        "review.wave not resolved on growth to Tier L",
        lambda r: mutate(r / "skills" / "ship-cycle" / "SKILL.md", "grows to Tier L later", "is Tier L"),
        "review.wave is not resolved when a cycle grows to Tier L",
    ),
    (
        "runtime-adapters loses the two-agent fallback",
        lambda r: mutate(r / "docs" / "runtime-adapters.md", "**Two-pass agents without live messaging.**",
                         "**Two passes.**"),
        "does not state the two-agent fallback for two-pass rules",
    ),
    (
        "barrier lookup by position, not latest non-superseded entry",
        lambda r: mutate(r / "docs" / "wave-check.md", "**the latest non-superseded\nentry for wave N−1 with the same `worktree`**",
                         "**the previous entry**"),
        "does not state 'the latest non-superseded entry for wave N−1'",
    ),
    (
        "waveBarriers shape loses superseded",
        lambda r: mutate(r / "docs" / "state-file.md", '"tier": "L", "superseded": false,',
                         '"tier": "L",'),
        "state shape has no waveBarriers entry with wave/tree/worktree/tier/superseded",
    ),
    (
        "waveReviews entry loses superseded",
        lambda r: mutate(r / "docs" / "state-file.md", '"routedTo": null, "superseded": false,',
                         '"routedTo": null,'),
        "waveReviews entry lacks 'superseded'",
    ),
    (
        "wave refuter not pinned",
        lambda r: mutate(r / "docs" / "wave-check.md", "**pinned to `review.wave`** too", "on any model"),
        "does not state '**pinned to `review.wave`**'",
    ),
    (
        "waveReviews entry loses its refuter",
        lambda r: mutate(r / "docs" / "state-file.md",
                         '\n                    "refuter": { "model": "sonnet", "effort": "medium" },', ""),
        "waveReviews entry lacks 'refuter'",
    ),
    (
        "Critical fix on a merely unrefuted finding",
        lambda r: mutate(r / "docs" / "wave-check.md", "actively\n  **evidenced**", "did not\n  refute"),
        "does not state 'actively **evidenced**'",
    ),
    (
        "Critical fix skips the impl-status report",
        lambda r: mutate(r / "docs" / "wave-check.md",
                         "the report block of\n  `${CLAUDE_PLUGIN_ROOT}/docs/impl-status.md`", "a summary"),
        "does not state 'docs/impl-status.md'",
    ),
    (
        "Critical fix does not count loops[G5]",
        lambda r: mutate(r / "docs" / "wave-check.md", "(`loops[G5]` +1, a fix round", "(a fix round"),
        "does not state '`loops[G5]` +1'",
    ),
    (
        "Critical fix skips the barrier rerun",
        lambda r: mutate(r / "docs" / "wave-check.md", "the barrier build/typecheck reruns;", "then"),
        "does not state 'the barrier build/typecheck reruns'",
    ),
    (
        "reconcile matches the wave number, not the tree",
        lambda r: mutate(r / "docs" / "wave-check.md", "matched on tree, not wave number", "matched by wave"),
        "does not state 'matched on tree, not wave number'",
    ),
    (
        "reconcile row reruns any barrier",
        lambda r: mutate(r / "docs" / "state-file.md", "and no `waveReviews` entry has that barrier's `tree`",
                         "and the check is missing"),
        "reconcile's subagents-running row does not rerun a wave check",
    ),
    (
        "readout hides refuted-but-carried items",
        lambda r: mutate(r / "skills" / "sc-ship" / "SKILL.md", "(`refutedCarried`) shown as such",
                         "(`refutedCarried`)"),
        "cost readout does not show refuted-but-carried items as such",
    ),
    (
        "multi-stack later barriers unstated",
        lambda r: mutate(r / "docs" / "wave-check.md", "Later stack barriers:", "Also:"),
        "does not state 'Later stack barriers'",
    ),
    # The red-gate protocol (#89).
    (
        "red-gate doc missing",
        lambda r: (r / "docs" / "red-gate.md").unlink(),
        "docs/red-gate.md: missing",
    ),
    (
        "red gate fixes before reproducing",
        lambda r: mutate(r / "docs" / "red-gate.md",
                         "**Reproduce first, with the real command.**", "**Fix it.**"),
        "does not state '**Reproduce first, with the real command.**'",
    ),
    (
        "could-not-reproduce counts as fixed",
        lambda r: mutate(r / "docs" / "red-gate.md",
                         "**\"Could not reproduce\" is not fixed.**", "**Could not reproduce is fine.**"),
        "does not state '**\"Could not reproduce\" is not fixed.**'",
    ),
    (
        "repro exit code read from a pipe",
        lambda r: mutate(r / "docs" / "red-gate.md", "its own exit code", "the exit code"),
        "red-gate-protocol block does not state 'its own exit code'",
    ),
    (
        "repro runs escape the lock",
        lambda r: mutate(r / "docs" / "red-gate.md",
                         "under overlay `env.heavyLock` with a\n   bounded wait", "freely"),
        "red-gate-protocol block does not state '`env.heavyLock`'",
    ),
    (
        "hypothesis without evidence",
        lambda r: mutate(r / "docs" / "red-gate.md", "(§`${CLAUDE_PLUGIN_ROOT}/docs/claim-evidence.md`)", ""),
        "red-gate-protocol block does not state 'docs/claim-evidence.md'",
    ),
    (
        "rejected hypothesis retried",
        lambda r: mutate(r / "docs" / "red-gate.md",
                         "not tried again unless new evidence", "tried again unless new evidence"),
        "does not state 'not tried again unless new evidence'",
    ),
    (
        "several changes at once",
        lambda r: mutate(r / "docs" / "red-gate.md", "one change,\n   not a bundle", "a few changes"),
        "does not state 'one change, not a bundle'",
    ),
    (
        "three rejections become a second cap",
        lambda r: mutate(r / "docs" / "red-gate.md",
                         "This is **not a second cap**", "This has its own loop cap"),
        "states 'its own loop cap'",
    ),
    (
        "three rejections not routed as design defect",
        lambda r: mutate(r / "docs" / "red-gate.md",
                         "reports\n     `BLOCKED` (design defect)", "reports\n     failure"),
        "red-gate-protocol block does not state '`BLOCKED` (design defect)'",
    ),
    (
        "three rejections not counted",
        lambda r: mutate(r / "docs" / "red-gate.md", "already a fix-round re-dispatch counted against",
                         "free, not counted against"),
        "does not state 'already a fix-round re-dispatch counted against `loops[G]`'",
    ),
    (
        "protocol hypothesises before reading the error",
        lambda r: swap_red_steps(r),
        "red-gate-protocol does not reproduce, read, compare, hypothesise, change in order",
    ),
    (
        "flaky retried until green",
        lambda r: mutate(r / "docs" / "red-gate.md",
                         "**Retry to classify, never to hide.**", "**Retry until it is green.**"),
        "does not state '**Retry to classify, never to hide.**'",
    ),
    (
        "gate passes on best of N",
        lambda r: mutate(r / "docs" / "red-gate.md",
                         "a gate never passes on the best\nof N runs",
                         "a gate may pass on the best of N runs"),
        "states 'may pass on the best of'",
    ),
    (
        "polluter bisection unix-only",
        lambda r: mutate(r / "docs" / "red-gate.md", "so it works on Linux and Windows alike", "with find"),
        "does not state 'Linux and Windows'",
    ),
    (
        "sleep instead of condition",
        lambda r: mutate(r / "docs" / "red-gate.md",
                         "**Wait for the condition, not for time.**", "**Add a sleep.**"),
        "does not state '**Wait for the condition, not for time.**'",
    ),
    (
        "sc-implement loses the red-gate section",
        lambda r: mutate(r / "skills" / "sc-implement" / "SKILL.md", "## When a gate goes red", "## Red"),
        "'## When a gate goes red' does not state",
    ),
    (
        "sc-implement fix briefs drop the record",
        lambda r: mutate(r / "skills" / "sc-implement" / "SKILL.md",
                         'rejected ones marked "do not retry"', ""),
        "does not state '\"do not retry\"'",
    ),
    (
        "G6 debugger without the protocol",
        lambda r: mutate(r / "skills" / "sc-implement" / "SKILL.md",
                         "debugger under §When a gate goes red", "debugger"),
        "G6 does not attach its debugger under §When a gate goes red",
    ),
    (
        "sc-qa flaky flow counted as passed",
        lambda r: mutate(r / "skills" / "sc-qa" / "SKILL.md", "is `undetermined`, not passed", "passed"),
        "skills/sc-qa/SKILL.md: '## When a gate goes red' does not state '`undetermined`, not passed'",
    ),
    (
        "gate table G6 drops the protocol",
        lambda r: mutate(r / "skills" / "ship-cycle" / "SKILL.md",
                         "debugger → sc-implement, red-gate protocol", "debugger → sc-implement"),
        "G6 'On failure' cell does not name the red-gate protocol",
    ),
    (
        "gate table G9 drops the protocol",
        lambda r: mutate(r / "skills" / "ship-cycle" / "SKILL.md",
                         "| → sc-implement, red-gate protocol |", "| → sc-implement |"),
        "G9 'On failure' cell does not name the red-gate protocol",
    ),
    (
        "gate table red-gate note loses the cap rule",
        lambda r: mutate(r / "skills" / "ship-cycle" / "SKILL.md", "under the one cap rule\n(§", "\n(§"),
        "gate table has no red-gate note",
    ),
    (
        "debug entry loses its tree",
        lambda r: mutate(r / "docs" / "state-file.md",
                         '\n              "tree": "<tree id the re-run ran on>",', ''),
        "debug entry lacks 'tree'",
    ),
    (
        "debug entry loses its repro exit",
        lambda r: mutate(r / "docs" / "state-file.md",
                         '"repro": { "command": "<the gate\'s real command>", "exit": 1 }',
                         '"repro": { "command": "x" }'),
        "debug.repro lacks command/exit",
    ),
    (
        "reconcile drops debug entries",
        lambda r: mutate(r / "docs" / "state-file.md",
                         "**Debug entries survive the reconcile.**", "**Debug entries.**"),
        "resume reconcile does not keep `debug` entries",
    ),
    (
        "sc-ship readout stops printing debug",
        lambda r: mutate(r / "skills" / "sc-ship" / "SKILL.md",
                         "one line per failure in `state.debug`", "one line per failure"),
        "skills/sc-ship/SKILL.md: does not read `state.debug`",
    ),
    (
        "sc-retro stops reading debug",
        lambda r: mutate(r / "skills" / "sc-retro" / "SKILL.md",
                         "Read `state.debug` (or", "Read the debug log (or"),
        "skills/sc-retro/SKILL.md: does not read `state.debug`",
    ),
    (
        "third rejection always +1 even at the cap",
        lambda r: mutate(r / "docs" / "red-gate.md",
                         "**When the rounds already reached the cap**", "**Always**"),
        "does not state '**When the rounds already reached the cap**'",
    ),
    (
        "loop 2 keeps guessing",
        lambda r: mutate(r / "docs" / "red-gate.md",
                         "prefer sc-design over a third guess", "try a third guess"),
        "prefer sc-design over a third guess",
    ),
    (
        "hypotheses outside the report block",
        lambda r: mutate(r / "docs" / "red-gate.md",
                         "requires the report block's `- Hypotheses:` field",
                         "asks for lines after the report block"),
        "states 'lines after the report block'",
    ),
    (
        "missing hypotheses treated as no report",
        lambda r: mutate(r / "docs" / "red-gate.md",
                         "never routed as\n  `BLOCKED` (no report)", "is routed as `BLOCKED` (no report)"),
        "is routed as `BLOCKED` (no report)",
    ),
    (
        "prompt drops the Hypotheses field",
        lambda r: mutate(r / "prompts" / "impl-web.md", "- Hypotheses: <omit", "- Notes: <omit"),
        "report block has no '- Hypotheses:' line",
    ),
    (
        "impl-status loses the Hypotheses rule",
        lambda r: mutate(r / "docs" / "impl-status.md", "never treated as no report", "routed as no report"),
        "for the Hypotheses field",
    ),
    (
        "could-not-reproduce has no base recheck exit",
        lambda r: mutate(r / "docs" / "red-gate.md", "**(b) Recheck on the base commit.**", "**(b) Wait.**"),
        "does not state '**(b) Recheck on the base commit.**'",
    ),
    (
        "could-not-reproduce loops forever",
        lambda r: mutate(r / "docs" / "red-gate.md", "**(c) Not reproducible anywhere.**", "**(c) Retry.**"),
        "does not state '**(c) Not reproducible anywhere.**'",
    ),
    (
        "flaky exemption clause dropped",
        lambda r: mutate(r / "docs" / "red-gate.md", "unless their suite is rechecked", "always"),
        "does not state 'unless their suite is rechecked'",
    ),
    (
        "undetermined written as a gate value",
        lambda r: mutate(r / "docs" / "red-gate.md",
                         "the log has no\n   `undetermined` value", "the log records\n   `undetermined`"),
        "does not state 'the log has no `undetermined` value'",
    ),
    (
        "revert by checkout",
        lambda r: mutate(r / "docs" / "red-gate.md",
                         "Never `git checkout`, `git reset` or `git stash`", "Use `git checkout` on"),
        "does not state 'Never `git checkout`, `git reset` or `git stash`'",
    ),
    (
        "revert not checked against the pre-change tree",
        lambda r: mutate(r / "docs" / "red-gate.md",
                         "the tree identity equals the pre-change tree", "check"),
        "does not state 'the tree identity equals the pre-change tree'",
    ),
    (
        "red differently opens a new group",
        lambda r: mutate(r / "docs" / "red-gate.md",
                         "**Red differently is\n   `rejected`** on the original failure",
                         "**Red differently is a new failure**"),
        "does not state '**Red differently is `rejected`** on the original failure'",
    ),
    (
        "build failure key keeps line numbers",
        lambda r: mutate(r / "docs" / "red-gate.md", "no line or column", "with line and column"),
        "does not state 'no line or column'",
    ),
    (
        "pending entries re-run on resume",
        lambda r: mutate(r / "docs" / "state-file.md", "none is ever\npending", "its re-run is repeated"),
        "resume reconcile does not keep `debug` entries (none pending)",
    ),
    (
        "changed tree not new evidence",
        lambda r: mutate(r / "docs" / "red-gate.md", "cited against that entry's `tree`", "cited"),
        'does not state "cited against that entry\'s `tree`"',
    ),
    (
        "QA hand-off re-reproduced from scratch",
        lambda r: mutate(r / "skills" / "sc-qa" / "SKILL.md",
                         "That hand-off is the protocol's reproduce step", "Then reproduce again"),
        'does not state "That hand-off is the protocol\'s reproduce step"',
    ),
    (
        "unrunnableHere triggers the protocol",
        lambda r: mutate(r / "docs" / "red-gate.md",
                         "`baseline.unrunnableHere` never triggers it",
                         "`baseline.unrunnableHere` triggers it too"),
        "does not state '`baseline.unrunnableHere` never triggers it'",
    ),
    (
        "debug entry loses its revert",
        lambda r: mutate(r / "docs" / "state-file.md",
                         '"revert": "git apply -R <scratch>/change.patch', '"undo": "x'),
        "debug entry lacks 'revert'",
    ),
    (
        "revert diffs before the change",
        lambda r: mutate(r / "docs" / "red-gate.md",
                         "`base=$(git stash create)`", "`git diff -- <files> > pre.patch`"),
        "states '> pre.patch'",
    ),
    (
        "revert runs git stash",
        lambda r: mutate(r / "docs" / "red-gate.md", "never run `git stash` itself", "run `git stash`"),
        "does not state 'never run `git stash` itself'",
    ),
    (
        "revert patch is not the change itself",
        lambda r: mutate(r / "docs" / "red-gate.md", "patch the change itself", "patch the worktree"),
        "does not state '**After the change**, patch the change itself'",
    ),
    (
        "revert drops untracked copies",
        lambda r: mutate(r / "docs" / "red-gate.md", "copy every untracked file", "skip untracked files"),
        "does not state 'copy every untracked file'",
    ),
    (
        "loop-2 count within one round",
        lambda r: mutate(r / "docs" / "red-gate.md",
                         "across\n     all rounds, not within one", "within\n     the round"),
        "does not state 'across all rounds, not within one'",
    ),
    (
        "restart wording counts toward a cap",
        lambda r: mutate(r / "docs" / "red-gate.md",
                         "the rejected entries survive a restart, so no disproved cause is retried",
                         "the three-rejection count survives a restart"),
        "states 'three-rejection count survives'",
    ),
    (
        "Hypotheses item format diverges",
        lambda r: mutate(r / "docs" / "red-gate.md",
                         "`cause · evidence · change · result · tree`", "`cause: evidence`"),
        "does not state '`cause · evidence · change · result · tree`'",
    ),
    (
        "N not applied per tree",
        lambda r: mutate(r / "docs" / "red-gate.md", "applied per tree", "overall"),
        "does not state 'applied per tree'",
    ),
    # The review focus (#90).
    (
        'review-focus doc missing',
        lambda r: (r / "docs" / "review-focus.md").unlink(),
        'docs/review-focus.md: missing',
    ),
    (
        'review focus not capped at five',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         '**at most five**',
                         '**up to ten**'),
        "does not state '**at most five**'",
    ),
    (
        'review focus not ranked',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         'ranked\nby likelihood × harm',
                         'in any order'),
        "does not state 'ranked by likelihood × harm'",
    ),
    (
        'review focus accepts a generic class',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         '**Per feature, never a class.**',
                         '**Classes.**'),
        "does not state '**Per feature, never a class.**'",
    ),
    (
        'review focus duplicates the a11y floor',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         'Nor does it restate\nan accessibility-floor check '
                         '(§`${CLAUDE_PLUGIN_ROOT}/docs/visual-check.md` — Accessibility floor)',
                         'It may restate a check'),
        "does not state 'Accessibility floor'",
    ),
    (
        'review focus restates a criterion',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         '**Nor does it restate an acceptance criterion**',
                         '**It may restate a criterion**'),
        "does not state '**Nor does it restate an acceptance criterion**'",
    ),
    (
        'empty review focus reads as skipped',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         '**An empty list means checked, not skipped.**',
                         '**Empty.**'),
        "does not state '**An empty list means checked, not skipped.**'",
    ),
    (
        'review focus gets an approval round',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         'there is no separate approval round',
                         'the user approves it'),
        "does not state 'no separate approval round'",
    ),
    (
        'review focus rewritten after G3',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         '**Append or annotate only after G3.**',
                         '**Edit freely.**'),
        "does not state '**Append or annotate only after G3.**'",
    ),
    (
        'corrected entry loses its id',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         'keeps its `id`',
                         'gets a new id'),
        "does not state 'keeps its `id`'",
    ),
    (
        'rewrite does not supersede old entries',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         '`superseded: true`',
                         'deleted', count=-1),
        "does not state '`superseded: true`'",
    ),
    (
        'n/a pin allowed for logic',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         '**only for a layout, copy or config item**',
                         'for any item'),
        "does not state '**only for a layout, copy or config item**'",
    ),
    (
        'logic entry need not fail first',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         'a logic\nentry always needs a failing-first test',
                         'any test will do'),
        "does not state 'a logic entry always needs a failing-first test'",
    ),
    (
        'misused n/a not caught',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         'A misused `n/a` is a critic objection',
                         'A misused `n/a` is fine'),
        "does not state 'A misused `n/a` is a critic objection'",
    ),
    (
        'review focus pin need not fail first',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         'An entry whose test passes before the change is not pinned',
                         'Any test pins it'),
        "does not state 'passes before the change is not pinned'",
    ),
    (
        'G4 passes with an unpinned entry',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         'G4 does not pass\nwhile any non-superseded entry has no `pinnedBy`.',
                         ''),
        "does not state 'G4 does not pass while any non-superseded entry has no `pinnedBy`'",
    ),
    (
        'cold lens compares before it freezes',
        lambda r: swap_focus_steps(r),
        'review-focus-cold does not freeze the blind pass before the compare',
    ),
    (
        'list leaks into the blind brief',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         "the list is\nnever in the cold lens's blind-pass brief",
                         'the list may help'),
        'does not state "the list is never in the cold lens\'s blind-pass brief"',
    ),
    (
        'blind pass reuses the compare agent',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         '**fresh\nagent with no prior compare in its context**',
                         'the same agent'),
        "does not state '**fresh agent with no prior compare in its context**'",
    ),
    (
        'cold findings not frozen verbatim',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         '**frozen verbatim**',
                         '**noted**'),
        "does not state '**frozen verbatim**'",
    ),
    (
        'cold lens gets the list early',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         'it never edits the frozen list.',
                         'it never edits the frozen list. It receives the list before its blind pass.'),
        "states 'receives the list before its blind pass'",
    ),
    (
        'pin judged without the real construction path',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         'through the real construction path',
                         'somehow'),
        "does not state 'real construction path'",
    ),
    (
        'post-list findings not tagged',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         '`postList: true`',
                         'as usual'),
        "does not state '`postList: true`'",
    ),
    (
        "misses wait for the lenses' brief",
        lambda r: mutate(r / "docs" / "review-focus.md",
                         '**scoped second pass of a spec-anchored lens**',
                         "item in the lenses' brief"),
        "does not state '**scoped second pass of a spec-anchored lens**'",
    ),
    (
        'verifier not recorded',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         '`verify = { by, model, effort, outcome,\n   evidence }`',
                         'nothing'),
        "does not state '`verify = { by, model, effort, outcome, evidence }`'",
    ),
    (
        'pin-caught miss counted as fixed-here',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         '**`covered: <pinnedBy>`**',
                         '**`fixed-here` (pin)**'),
        "does not state '**`covered: <pinnedBy>`**'",
    ),
    (
        'covered entry sent to the delta pass',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         'not counted as fixed-here and never goes to the delta pass',
                         'sent to the delta pass'),
        "does not state 'not counted as fixed-here and never goes to the delta pass'",
    ),
    (
        'old fixed-here wording returns',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         '- **`filed-as #NN`**',
                         '- A missed entry whose pin holds is dispositioned '
                         '`fixed-here` citing its `pinnedBy`.\n- **`filed-as #NN`**'),
        "states 'is dispositioned `fixed-here` citing its `pinnedBy`'",
    ),
    (
        'fixed pin never shown failing',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         '**shown failing\n  against the pre-change tree**',
                         'rerun'),
        "does not state '**shown failing against the pre-change tree**'",
    ),
    (
        'delta pass gets input text',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         'never as its `input` or `expected` text',
                         'with its full text'),
        "does not state 'never as its `input` or `expected` text'",
    ),
    (
        'tier S review focus uncapped',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         '**at most two** entries',
                         'any number of entries'),
        "does not state '**at most two** entries'",
    ),
    (
        'sc-tdd cannot record an empty list',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         'or `[]` when it checked and found none',
                         ''),
        "does not state 'or `[]` when it checked and found none'",
    ),
    (
        'route-skipped review focus not absent',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         'the field stays **absent**',
                         'the field is `[]`'),
        "does not state 'the field stays **absent**'",
    ),
    (
        'no-cold-lens entries not marked',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         'entries keep\n`cold: null`',
                         'entries are dropped'),
        "does not state 'entries keep `cold: null`'",
    ),
    (
        'review focus record loses a reader',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         'and sc-retro (did the cold lens',
                         'and nobody (did the cold lens'),
        "review-focus-record block does not state 'sc-retro'",
    ),
    (
        'sc-design loses the review-focus bullet',
        lambda r: mutate(r / "skills" / "sc-design" / "SKILL.md",
                         'never a generic edge class',
                         'any edge class'),
        "'## Design (architect' does not state 'never a generic edge class' (review focus)",
    ),
    (
        'sc-design critic ignores the review focus',
        lambda r: mutate(r / "skills" / "sc-design" / "SKILL.md",
                         'likelier input the list left off',
                         'missing input'),
        "does not state 'likelier input the list left off' (review focus)",
    ),
    (
        'G2 does not require the review focus',
        lambda r: mutate(r / "skills" / "sc-design" / "SKILL.md",
                         ', and `state.reviewFocus` is written (`[]` when checked and empty).',
                         '.'),
        "'## Gate G2/G3' does not state '`state.reviewFocus` is written' (review focus)",
    ),
    (
        'sc-tdd route skip drops the pins',
        lambda r: mutate(r / "skills" / "sc-tdd" / "SKILL.md",
                         'The skip path still pins any `state.reviewFocus` entries',
                         'The skip path ignores entries'),
        "the skill does not state 'The skip path still pins any `state.reviewFocus` entries' (review focus)",
    ),
    (
        'sc-tdd loses the pin section',
        lambda r: mutate(r / "skills" / "sc-tdd" / "SKILL.md",
                         '## Pin the review focus',
                         '## Pin things'),
        "'## Pin the review focus' does not state",
    ),
    (
        'sc-tdd G4 does not require pins',
        lambda r: mutate(r / "skills" / "sc-tdd" / "SKILL.md",
                         'G4 does not pass with an entry unpinned.',
                         ''),
        "'## Gate G4' does not state 'G4 does not pass with an entry unpinned' (review focus)",
    ),
    (
        'sc-review cold brief carries the list',
        lambda r: mutate(r / "skills" / "sc-review" / "SKILL.md",
                         "the list is never in the cold lens's blind-pass brief",
                         'the list may be in the brief'),
        '\'## Lenses\' does not state "the list is never in the cold lens\'s blind-pass brief" (review focus)',
    ),
    (
        'sc-review cold lens gets the list unfrozen',
        lambda r: mutate(r / "skills" / "sc-review" / "SKILL.md",
                         'frozen verbatim into the review artifact first',
                         'noted'),
        "'## Lenses' does not state 'frozen verbatim into the review artifact first' (review focus)",
    ),
    (
        'sc-review triage drops the verify step',
        lambda r: mutate(r / "skills" / "sc-review" / "SKILL.md",
                         '**Review-focus items are verified after the compare.**',
                         '**Review focus.**'),
        "'## Triage' does not state '**Review-focus items are verified after the compare.**' (review focus)",
    ),
    (
        'sc-review delta pass gets input text',
        lambda r: mutate(r / "skills" / "sc-review" / "SKILL.md",
                         'Review-focus items reach it as code locations only',
                         'Review-focus items reach it'),
        "'## Re-review after fixes' does not state 'Review-focus items reach it as code locations only' (review focus)",
    ),
    (
        'G8 ignores review-focus outcomes',
        lambda r: mutate(r / "skills" / "sc-review" / "SKILL.md",
                         'missed or uncovered `state.reviewFocus` entry has a `verify` outcome',
                         'item'),
        "'## Gate G8' does not state 'missed or uncovered "
        "`state.reviewFocus` entry has a `verify` outcome' (review focus)",
    ),
    (
        'G11 does not map the review focus',
        lambda r: mutate(r / "skills" / "sc-ship" / "SKILL.md",
                         '**Review focus.** Each `state.reviewFocus` entry',
                         '**Extras.** Each entry'),
        "'## Verify (G11)' does not state '**Review focus.**' (review focus)",
    ),
    (
        'G11 accepts a fixed pin without evidence',
        lambda r: mutate(r / "skills" / "sc-ship" / "SKILL.md",
                         'and its `pinFixEvidence`',
                         ''),
        "'## Verify (G11)' does not state '`pinFixEvidence`' (review focus)",
    ),
    (
        'sc-retro does not count pin-caught misses',
        lambda r: mutate(r / "skills" / "sc-retro" / "SKILL.md",
                         '"cold-lens miss, caught by the pin"',
                         'a miss'),
        'the skill does not state \'"cold-lens miss, caught by the pin"\' (review focus)',
    ),
    (
        'G4 row does not require pins',
        lambda r: mutate(r / "skills" / "ship-cycle" / "SKILL.md",
                         '; every `state.reviewFocus` entry pinned (test or named `n/a`)',
                         ''),
        "gate table's G4 row does not require every reviewFocus entry pinned",
    ),
    (
        'runtime adapters miss the review-focus two-pass',
        lambda r: mutate(r / "docs" / "runtime-adapters.md",
                         '§`${CLAUDE_PLUGIN_ROOT}/docs/review-focus.md`',
                         '§sc-review'),
        'two-pass note does not cover the review-focus compare',
    ),
    (
        'state shape reviewFocus lacks pinnedBy',
        lambda r: mutate(r / "docs" / "state-file.md",
                         '"pinnedBy": "<test id, seen failing first>',
                         '"pinned": "<test id, seen failing first>'),
        "reviewFocus entry lacks 'pinnedBy'",
    ),
    (
        'state shape reviewFocus.cold lacks raised',
        lambda r: mutate(r / "docs" / "state-file.md",
                         '"cold": { "raised": false,',
                         '"cold": {'),
        'reviewFocus.cold lacks one of',
    ),
    (
        'state shape reviewFocus.verify lacks by',
        lambda r: mutate(r / "docs" / "state-file.md",
                         '"verify": { "by": "quality lens (scoped)",',
                         '"verify": {'),
        'reviewFocus.verify lacks one of',
    ),
    (
        'ids restart after a rewrite',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         'continue the numbering (`RF6`+)',
                         'restart at `RF1`'),
        "does not state 'continue the numbering (`RF6`+)'",
    ),
    (
        'cap counts superseded entries',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         'the five-entry\n  cap counts only non-superseded entries',
                         'the cap counts every entry'),
        "does not state 'the five-entry cap counts only non-superseded entries'",
    ),
    (
        'promotion skips the G1 re-show',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         'is a G1 re-show (§ship-cycle Stage 0.4)',
                         'is silent'),
        "does not state 'is a G1 re-show (§ship-cycle Stage 0.4)'",
    ),
    (
        'scope growth re-opens only at sc-design',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         're-opens the list at whichever stage wrote it',
                         're-opens the list at sc-design'),
        "does not state 're-opens the list at whichever stage wrote it'",
    ),
    (
        'scoped verify pass on another model',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         '**The scoped\n   pass runs on the same model and effort the chosen lens ran with at G8**',
                         'The scoped pass runs cheaper'),
        "does not state '**The scoped pass runs on the same model and effort the chosen lens ran with at G8**'",
    ),
    (
        'verifier copies the cold evidence',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         'never a copy of `cold.evidence`',
                         'a copy of `cold.evidence` will do'),
        "does not state 'never a copy of `cold.evidence`'",
    ),
    (
        'delta pass judges resolution',
        lambda r: mutate(r / "docs" / "review-focus.md",
                         '**It checks only\nwhether the pin or fix introduced a regression**',
                         'It judges the fix'),
        "does not state '**It checks only whether the pin or fix introduced a regression**'",
    ),
    (
        'sc-review triage verify pass unpinned',
        lambda r: mutate(r / "skills" / "sc-review" / "SKILL.md",
                         'on the same model and effort that lens ran with at G8',
                         'on any model'),
        "'## Triage' does not state 'on the same model and effort that lens ran with at G8' (review focus)",
    ),
    (
        'sc-review delta pass judges review-focus resolution',
        lambda r: mutate(r / "skills" / "sc-review" / "SKILL.md",
                         'For these the delta pass checks only whether the pin or fix introduced a\n  regression',
                         'For these the delta pass judges the fix'),
        "does not state 'checks only whether the pin or fix introduced a regression' (review focus)",
    ),
    (
        'sc-retro ignores superseded entries',
        lambda r: mutate(r / "skills" / "sc-retro" / "SKILL.md",
                         "`superseded` entries as evidence of the earlier design's misses; ",
                         ''),
        'the skill does not state "evidence of the earlier design\'s misses" (review focus)',
    ),
    (
        'state shape reviewFocus.verify lacks evidence',
        lambda r: mutate(r / "docs" / "state-file.md",
                         '"evidence": "<assertion path:line> · <construction call path:line>",',
                         ''),
        'reviewFocus.verify lacks one of',
    ),
]


# Mutations the validator must NOT flag: prose and non-JSON fences are not state.
PASSING_CASES = [
    (
        "prose 'the stage = `G4`' and a bash fence are not stage literals",
        lambda r: mutate(
            r / "skills" / "sc-qa" / "SKILL.md",
            "## Model routing",
            'When the stage = `G4`, stop.\n\n```bash\nstage="whatever"\n```\n\n## Model routing',
        ),
    ),
    (
        "sc-ship names the gate log by its Codex state dir",
        lambda r: mutate(
            r / "skills" / "sc-ship" / "SKILL.md",
            "<state dir>/<branch-slug>.log.md",
            ".codex/ship-cycle/<branch-slug>.log.md",
            count=-1,
        ),
    ),
]


def main() -> int:
    failures: list[str] = []

    code, out = run_validator(REPO)
    if code != 0:
        failures.append(f"the real repo does not pass its own validator:\n{out}")

    # The eval post-checks (#85): every fixture gives its expected verdict, and swapping every scenario's
    # failing case into its passing slot makes the checker's own self-test fail for each scenario --
    # otherwise "selftest ok" would prove nothing.
    code, out = run_eval_checker(REPO)
    if code != 0:
        failures.append(f"evals/check.py selftest fails on the real repo:\n{out}")
    else:
        print("ok   eval post-checks give every fixture its expected verdict")
    with tempfile.TemporaryDirectory(prefix="scdk self test ") as tmp:
        root = fresh_copy(Path(tmp) / "repo copy")
        swapped = []
        for scenario in sorted(p for p in (root / "evals" / "fixtures").iterdir() if p.is_dir()):
            if (scenario / "fail").is_dir() and (scenario / "pass").is_dir():
                shutil.rmtree(scenario / "pass")
                shutil.copytree(scenario / "fail", scenario / "pass")
                swapped.append(scenario.name)
        code, out = run_eval_checker(root)
        missed = [s for s in swapped if f"FAIL {s}/pass:" not in out]
        if code == 0 or missed or not swapped:
            failures.append(f"[eval checker] swapped fixtures not all caught (missed {missed}):\n{out}")
        else:
            print(f"ok   eval checker selftest fails on each of {len(swapped)} swapped fixtures")

    # The SessionStart hook (#86): its behaviour test passes on the real script and fails on each broken copy.
    code, out = run_hook_test(REPO / "hooks" / "session-start.cjs")
    skipped = out.startswith("skip")
    if code != 0:
        failures.append(f"scripts/hook_test.py fails on the real hook:\n{out}")
    elif skipped:
        print(out.strip())
    else:
        print("ok   SessionStart hook behaviour test passes on the real hook")
        for name, old, new, expected in HOOK_MUTATIONS:
            with tempfile.TemporaryDirectory(prefix="scdk self test ") as tmp:
                hook = Path(tmp) / "hook copy" / "session-start.cjs"
                hook.parent.mkdir()
                shutil.copy2(REPO / "hooks" / "session-start.cjs", hook)
                mutate(hook, old, new)
                code, out = run_hook_test(hook)
                if code == 0:
                    failures.append(f"[{name}] hook test passed a broken hook")
                elif expected not in out:
                    failures.append(f"[{name}] expected {expected!r} in hook test output, got:\n{out}")
                else:
                    print(f"ok   {name}")

    for name, mutation, expected in CASES:
        with tempfile.TemporaryDirectory(prefix="scdk self test ") as tmp:
            root = fresh_copy(Path(tmp) / "repo copy")
            mutation(root)
            code, out = run_validator(root)
            if code == 0:
                failures.append(f"[{name}] validator passed a repo that should fail")
            elif expected not in out:
                failures.append(f"[{name}] expected {expected!r} in output, got:\n{out}")
            else:
                print(f"ok   {name}")

    for name, mutation in PASSING_CASES:
        with tempfile.TemporaryDirectory(prefix="scdk self test ") as tmp:
            root = fresh_copy(Path(tmp) / "repo copy")
            mutation(root)
            code, out = run_validator(root)
            if code != 0:
                failures.append(f"[{name}] validator flagged a repo that should pass:\n{out}")
            else:
                print(f"ok   {name}")

    if failures:
        print("\n".join(f"FAIL {f}" for f in failures))
        return 1
    print(f"\nok - {len(CASES)} checks each fail on a broken repo and pass on the real one;"
          f" {len(PASSING_CASES)} must-pass mutation(s) pass")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):  # Windows consoles default to cp1252
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
