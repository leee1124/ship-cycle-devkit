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
