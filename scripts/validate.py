#!/usr/bin/env python3
"""Structural self-check for ship-cycle-devkit.

The kit's product is prose that agents execute, so its defects are claims about itself that are not true:
a doc pointing at a file that moved, a state field nothing reads, a gate value one consumer accepts and
another rejects, two plugin manifests drifting apart. Those are mechanical, so they are checked mechanically
here rather than re-discovered in review.

Every check below exists because the defect it catches actually reached a branch. What needs judgment --
whether a rule is a good rule -- stays with the independent reviewer.

Dependency-free, stdlib only, Python 3.8+. Exits 1 if any finding is an error.
Usage:  python3 scripts/validate.py [repo-root]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# --- constants (no magic strings) --------------------------------------------------------------

CLAUDE_MANIFEST = Path(".claude-plugin/plugin.json")
CODEX_MANIFEST = Path(".codex-plugin/plugin.json")
CHANGELOG = Path("CHANGELOG.md")
STATE_SHAPE_DOC = Path("docs/state-file.md")
SKILLS_DIR = Path("skills")
DOC_DIRS = (Path("skills"), Path("commands"), Path("docs"), Path("prompts"))

PLUGIN_ROOT_VAR = "${CLAUDE_PLUGIN_ROOT}"
DOC_REF_RE = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/((?:docs|prompts|commands|skills)/[A-Za-z0-9._/-]+\.md)")
BUNDLED_DIRS_RE = "|".join(("docs", "prompts", "commands", "skills"))
ANY_BUNDLED_REF_RE = re.compile(
    r"(?<!\$\{CLAUDE_PLUGIN_ROOT\}/)(?<![\w./-])(?:" + BUNDLED_DIRS_RE + r")/[A-Za-z0-9._/-]+\.md"
)
STATE_FIELD_RE = re.compile(r"(?<![\w.-])state\.([A-Za-z][A-Za-z0-9_]*)")
GATE_SET_RE = re.compile(r"gates\.((?:G\d+[a-z]?)(?:/G\d+[a-z]?)*)")
GATE_TABLE_ROW_RE = re.compile(r"^\|\s*((?:G\d+[a-z]?)(?:[/–-]G\d+[a-z]?)*)\s*\|", re.M)
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)
CHANGELOG_VERSION_RE = re.compile(r"^##\s+(\d+\.\d+\.\d+)", re.M)
SEMVER_RE = re.compile(r"\A\d+\.\d+\.\d+\Z")

CLAUDE_REQUIRED = ("name", "version", "description", "skills")
CODEX_REQUIRED = ("name", "version", "description", "author", "interface")
CODEX_INTERFACE_REQUIRED = (
    "displayName", "shortDescription", "longDescription", "developerName", "category",
)
DESCRIPTION_WORD_ADVISORY = 90


class Findings:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append(f"{where}: {msg}")


def markdown_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for d in DOC_DIRS:
        base = root / d
        if base.is_dir():
            out.extend(sorted(base.rglob("*.md")))
    return out


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def shown(path: Path) -> str:
    """Path as it appears in a finding: forward slashes on every OS, so messages are comparable."""
    return path.as_posix()


def load_json(root: Path, rel: Path, f: Findings) -> dict | None:
    path = root / rel
    if not path.is_file():
        f.error(shown(rel), "missing")
        return None
    try:
        return json.loads(read(path))
    except json.JSONDecodeError as e:
        f.error(shown(rel), f"does not parse: {e}")
        return None


# --- checks ------------------------------------------------------------------------------------


def check_doc_references(root: Path, f: Findings) -> None:
    """Every bundled-doc pointer resolves, and none omits the plugin-root variable.

    Caught in practice: eight `(§docs/model-routing.md ...)` references introduced while moving content
    out of the orchestrator -- a regression of a bug the CHANGELOG records as already fixed once. A stage
    subagent resolving a root-less path looks in the user's project, where the file does not exist.
    """
    for path in markdown_files(root):
        text = read(path)
        rel = path.relative_to(root)
        for target in DOC_REF_RE.findall(text):
            if not (root / target).is_file():
                f.error(shown(rel), f"references {PLUGIN_ROOT_VAR}/{target}, which does not exist")
        for m in ANY_BUNDLED_REF_RE.finditer(text):
            target = m.group(0)
            if not (root / target).is_file():
                continue  # not one of ours; a project-relative path in an example
            f.error(shown(rel), f"bundled-file reference without {PLUGIN_ROOT_VAR}: {target}")


def state_shape_fields(root: Path, f: Findings) -> set[str]:
    """Top-level field names from the documented state shape."""
    path = root / STATE_SHAPE_DOC
    if not path.is_file():
        f.error(shown(STATE_SHAPE_DOC), "missing")
        return set()
    blocks = re.findall(r"```json\n(.*?)\n```", read(path), re.S)
    if not blocks:
        f.error(shown(STATE_SHAPE_DOC), "no json shape block found")
        return set()
    try:
        shape = json.loads(blocks[0])
    except json.JSONDecodeError as e:
        f.error(shown(STATE_SHAPE_DOC), f"shape block does not parse: {e}")
        return set()
    return set(shape.keys())


def check_state_producers_consumers(root: Path, f: Findings) -> None:
    """Every documented state field is referenced somewhere, and every reference is documented.

    This is the check that matters most. Three consecutive releases each added a state field
    (`unrunnableHere`, `reviewJobs`, `bakeOff`) and two of them reached a branch with a consumer missing --
    including one where the gate that blocks the merge did not accept the value its own writers produced.
    A field nothing reads is either dead or a false claim that something reads it.
    """
    documented = state_shape_fields(root, f)
    if not documented:
        return
    shape_doc = (root / STATE_SHAPE_DOC).resolve()
    referenced: set[str] = set()
    for path in markdown_files(root):
        # The shape doc is where the field is *declared*; prose about a field in the same file is not a
        # consumer. Counting it made this check pass for any field documented with a sentence beside it,
        # which is how fields are actually added.
        if path.resolve() == shape_doc:
            continue
        text = read(path)
        referenced.update(STATE_FIELD_RE.findall(text))
        # Fields are also addressed bare inside prose, e.g. `reviewJobs` or `gitFreeze`.
        for field in documented:
            if f"`{field}`" in text or f"`{field}." in text or f"`state.{field}" in text:
                referenced.add(field)

    for field in sorted(documented - referenced):
        f.error(shown(STATE_SHAPE_DOC), f"state.{field} is documented but no skill or command reads it")
    for field in sorted(referenced - documented):
        f.error("state references", f"state.{field} is used but absent from {shown(STATE_SHAPE_DOC)}")


def check_gate_coverage(root: Path, f: Findings) -> None:
    """Every gate in the orchestrator's table is set by some skill, and vice versa."""
    orchestrator = root / SKILLS_DIR / "ship-cycle" / "SKILL.md"
    if not orchestrator.is_file():
        f.error(shown(orchestrator), "missing")
        return
    # A row may compound ids ("G2/G3"), and prose may write "gates.G5/G6/G7/G7b" -- split both.
    tabled: set[str] = set()
    for group in GATE_TABLE_ROW_RE.findall(read(orchestrator)):
        tabled.update(re.split(r"[/–-]", group))
    written: set[str] = set()
    for path in markdown_files(root):
        if path.resolve() == orchestrator.resolve():
            continue
        for group in GATE_SET_RE.findall(read(path)):
            written.update(group.split("/"))
    for gate in sorted(tabled - written):
        # Advisory pending #63: G10-G12 are performed by sc-ship and never recorded. Promote to error
        # once that is fixed, so the direction that found the defect can also block on it.
        f.warn("gates", f"{gate} is in the orchestrator's gate table but no stage skill sets it")
    for gate in sorted(written - tabled):
        f.error("gates", f"{gate} is set by a skill but absent from the orchestrator's gate table")


def check_manifests_and_versions(root: Path, f: Findings) -> None:
    """Both manifests parse, carry their host's required fields, and agree on the version.

    Version drift between the two distributions is one of the two ways they come apart quietly; the other
    is skill drift, checked below.
    """
    claude = load_json(root, CLAUDE_MANIFEST, f)
    codex = load_json(root, CODEX_MANIFEST, f)

    if claude is not None:
        for key in CLAUDE_REQUIRED:
            if key not in claude:
                f.error(shown(CLAUDE_MANIFEST), f"missing required field '{key}'")
    if codex is not None:
        for key in CODEX_REQUIRED:
            if key not in codex:
                f.error(shown(CODEX_MANIFEST), f"missing required field '{key}'")
        interface = codex.get("interface")
        if isinstance(interface, dict):
            for key in CODEX_INTERFACE_REQUIRED:
                if key not in interface:
                    f.error(shown(CODEX_MANIFEST), f"interface missing required field '{key}'")
            prompts = interface.get("defaultPrompt", [])
            if not isinstance(prompts, list):
                f.error(shown(CODEX_MANIFEST), "interface.defaultPrompt must be an array")
                prompts = []
            if len(prompts) > 3:
                f.error(shown(CODEX_MANIFEST), "interface.defaultPrompt allows at most 3 entries")
            for p in prompts:
                if len(p) > 128:
                    f.error(shown(CODEX_MANIFEST), f"defaultPrompt entry exceeds 128 chars: {p[:40]}...")
        elif interface is not None:
            f.error(shown(CODEX_MANIFEST), "interface must be an object")

    versions = {}
    if claude is not None:
        versions[shown(CLAUDE_MANIFEST)] = claude.get("version")
    if codex is not None:
        versions[shown(CODEX_MANIFEST)] = codex.get("version")
    for where, v in versions.items():
        if v and not SEMVER_RE.match(str(v)):
            f.error(where, f"version '{v}' is not strict semver")

    changelog = root / CHANGELOG
    if changelog.is_file():
        found = CHANGELOG_VERSION_RE.search(read(changelog))
        if found:
            versions[shown(CHANGELOG)] = found.group(1)
        else:
            f.warn(shown(CHANGELOG), "no version heading found")

    distinct = set(v for v in versions.values() if v)
    if len(distinct) > 1:
        detail = ", ".join(f"{k}={v}" for k, v in versions.items())
        f.error("version parity", f"versions disagree: {detail}")

    if claude is not None and codex is not None:
        c_skills, x_skills = claude.get("skills"), codex.get("skills")
        if c_skills != x_skills:
            f.error("skill parity", f"manifests expose different skill paths: {c_skills!r} vs {x_skills!r}")


def check_skill_frontmatter(root: Path, f: Findings) -> None:
    """Every skill declares name + description, and name matches its directory."""
    base = root / SKILLS_DIR
    if not base.is_dir():
        f.error(shown(SKILLS_DIR), "missing")
        return
    for skill_md in sorted(base.glob("*/SKILL.md")):
        rel = skill_md.relative_to(root)
        m = FRONTMATTER_RE.match(read(skill_md))
        if not m:
            f.error(shown(rel), "no frontmatter block")
            continue
        block = m.group(1)
        name = re.search(r"^name:\s*(\S+)\s*$", block, re.M)
        desc = re.search(r"^description:\s*(.+)$", block, re.M)
        if not name:
            f.error(shown(rel), "frontmatter has no 'name'")
        elif name.group(1) != skill_md.parent.name:
            f.error(shown(rel), f"frontmatter name '{name.group(1)}' != directory '{skill_md.parent.name}'")
        if not desc:
            f.error(shown(rel), "frontmatter has no 'description'")
        else:
            words = len(desc.group(1).split())
            if words > DESCRIPTION_WORD_ADVISORY:
                f.warn(shown(rel), f"description is {words} words; it loads in every session")


# --- entry point -------------------------------------------------------------------------------


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path(__file__).resolve().parent.parent
    f = Findings()

    check_doc_references(root, f)
    check_state_producers_consumers(root, f)
    check_gate_coverage(root, f)
    check_manifests_and_versions(root, f)
    check_skill_frontmatter(root, f)

    for w in f.warnings:
        print(f"warning  {w}")
    for e in f.errors:
        print(f"ERROR    {e}")

    if f.errors:
        print(f"\n{len(f.errors)} error(s), {len(f.warnings)} warning(s)")
        return 1
    print(f"ok - no errors, {len(f.warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
