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


def mutate(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"self-test fixture is stale: {old[:50]!r} not in {path.name}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


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
        "gate in the table that no skill sets is advisory, not an error",
        lambda r: None,
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
]


def main() -> int:
    failures: list[str] = []

    code, out = run_validator(REPO)
    if code != 0:
        failures.append(f"the real repo does not pass its own validator:\n{out}")

    for name, mutation, expected in CASES:
        with tempfile.TemporaryDirectory(prefix="scdk self test ") as tmp:
            root = fresh_copy(Path(tmp) / "repo copy")
            advisory = mutation(root) is None and name.endswith("advisory, not an error")
            code, out = run_validator(root)
            if advisory:
                # This one asserts the *warning* direction: it must be reported and must NOT fail the build.
                if code != 0 or expected not in out:
                    failures.append(f"[{name}] expected an advisory warning and exit 0, got {code}:\n{out}")
                else:
                    print(f"ok   {name}")
                continue
            if code == 0:
                failures.append(f"[{name}] validator passed a repo that should fail")
            elif expected not in out:
                failures.append(f"[{name}] expected {expected!r} in output, got:\n{out}")
            else:
                print(f"ok   {name}")

    if failures:
        print("\n".join(f"FAIL {f}" for f in failures))
        return 1
    print(f"\nok - {len(CASES)} checks each fail on a broken repo and pass on the real one")
    return 0


if __name__ == "__main__":
    sys.exit(main())
