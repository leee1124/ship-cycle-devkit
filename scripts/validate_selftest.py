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
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VALIDATOR = REPO / "scripts" / "validate.py"
COPY_SKIP = {".git", "__pycache__", ".github"}


def run_validator(root: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(VALIDATOR), str(root)],
        capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


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
    sys.exit(main())
