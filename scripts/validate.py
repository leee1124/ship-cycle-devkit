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
OVERLAY_SCHEMA = Path("docs/ship-cycle.config.schema.json")
OVERLAY_EXAMPLE = Path("docs/ship-cycle.config.example.json")
SKILLS_DIR = Path("skills")
DOC_DIRS = (Path("skills"), Path("commands"), Path("docs"), Path("prompts"))

PLUGIN_ROOT_VAR = "${CLAUDE_PLUGIN_ROOT}"
DOC_REF_RE = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/((?:docs|prompts|commands|skills)/[A-Za-z0-9._/-]+\.md)")
BUNDLED_DIRS_RE = "|".join(("docs", "prompts", "commands", "skills"))
ANY_BUNDLED_REF_RE = re.compile(
    r"(?<!\$\{CLAUDE_PLUGIN_ROOT\}/)(?<![\w./-])(?:" + BUNDLED_DIRS_RE + r")/[A-Za-z0-9._/-]+\.md"
)
STATE_FIELD_RE = re.compile(r"(?<![\w.-])state\.([A-Za-z][A-Za-z0-9_]*)")
# An *assignment* (`gates.G10 = pass`, `gates.G7b: checklist`, compound `gates.G5/G6 = <r>`): prose that
# merely names a gate ("`gates.G10` is unset") does not prove a stage records it (#75). Quotes/backticks
# may sit between the id and the operator; `::` is not an assignment.
GATE_SET_RE = re.compile(r"gates\.((?:G\d+[a-z]?)(?:/G\d+[a-z]?)*)[`\"']?\s*(?:=(?!=)|:(?!:))")
GATE_TABLE_ROW_RE = re.compile(r"^\|\s*((?:G\d+[a-z]?)(?:[/–-]G\d+[a-z]?)*)\s*\|", re.M)
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)
CHANGELOG_VERSION_RE = re.compile(r"^##\s+(\d+\.\d+\.\d+)", re.M)
SEMVER_RE = re.compile(r"\A\d+\.\d+\.\d+\Z")
STAGE_VOCAB_RE = re.compile(r"<!-- stage-vocabulary -->(.*?)<!-- /stage-vocabulary -->", re.S)
STAGE_KEYS = r"(?:stage|resumeStage|recordedStage|continueFrom)"
STAGE_VALUE = r"([A-Za-z][A-Za-z0-9_-]*)"
# Stage literals are read only where they are unambiguously state: a JSON key inside a ```json block, or a
# key written inside an inline code span. Prose ("the stage = `G4`") and non-JSON fences are not state.
FENCE_RE = re.compile(r"^```([^\n`]*)\n(.*?)^```", re.S | re.M)
JSON_STAGE_RE = re.compile(r'"' + STAGE_KEYS + r'"\s*:\s*"' + STAGE_VALUE + r'"')
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
INLINE_STAGE_RE = re.compile(r"(?<![\w.])" + STAGE_KEYS + r"\s*[:=]\s*[\"']" + STAGE_VALUE + r"[\"']")
KEY_SPAN_STAGE_RE = re.compile(r"`(?:state\.|parked\.)?" + STAGE_KEYS + r"`\s*[:=]\s*`" + STAGE_VALUE + r"`")
# Non-skill stage values every reader branches on; the seven stage skills come from the pipeline table.
REQUIRED_NON_SKILL_STAGES = ("parked", "complete", "failed", "cancelled")
SHIP_SKILL = Path("skills/sc-ship/SKILL.md")
GATE_LOG_HEADING = "## Gate log"
GATE_SUMMARY_PHRASE = "Gate summary"
G12_FRESH_RENDER_PHRASE = "fresh render from state + log"
# The log lives in the host's state dir: `.claude/ship-cycle/` (Claude), `.codex/ship-cycle/` (Codex), or the
# generic `<state dir>/` placeholder.
GATE_LOG_PATH_RE = re.compile(
    r"(?:\.claude/ship-cycle/|\.codex/ship-cycle/|<state dir>/)<branch-slug>\.log\.md"
)
GATE_LOG_ESCAPING_RE = re.compile(
    r"<!-- gate-log-cell-escaping -->(.*?)<!-- /gate-log-cell-escaping -->", re.S
)
GATE_LOG_ESCAPING_TOKENS = ("`|` → `\\|`", "newline", "200 characters", "applied exactly once")
G12_ROW_RE = re.compile(r"^\|\s*G12\s*\|(.*)$", re.M)

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
        # An error since #63: a tabled gate that no stage records is invisible to /status and resume.
        f.error("gates", f"{gate} is in the orchestrator's gate table but no stage skill sets it")
    for gate in sorted(written - tabled):
        f.error("gates", f"{gate} is set by a skill but absent from the orchestrator's gate table")


def check_stage_vocabulary(root: Path, f: Findings) -> None:
    """`stage` values come from one documented list, and nothing in the kit writes one outside it.

    Readers branch on `stage` (`/resume` refuses terminal values, `/ship` refuses `parked`), so a value one
    writer invents -- `paused` beside `parked` -- is a state every reader silently mishandles.
    """
    path = root / STATE_SHAPE_DOC
    if not path.is_file():
        return  # reported by state_shape_fields
    m = STAGE_VOCAB_RE.search(read(path))
    if not m:
        f.error(shown(STATE_SHAPE_DOC), "no <!-- stage-vocabulary --> block found")
        return
    vocab = set(re.findall(r"`([A-Za-z][A-Za-z0-9_-]*)`", m.group(1)))
    orchestrator = root / SKILLS_DIR / "ship-cycle" / "SKILL.md"
    pipeline = set(re.findall(r"^\|\s*\d+\s*\|\s*`(sc-[a-z-]+)`", read(orchestrator), re.M)) \
        if orchestrator.is_file() else set()
    for stage in sorted((pipeline | set(REQUIRED_NON_SKILL_STAGES)) - vocab):
        f.error(shown(STATE_SHAPE_DOC), f"stage vocabulary is missing '{stage}'")
    for md in markdown_files(root):
        for value in stage_literals(read(md)):
            if value not in vocab:
                f.error(shown(md.relative_to(root)), f"stage '{value}' is not in the stage vocabulary")


def stage_literals(text: str) -> list[str]:
    """Stage values written as state: in ```json fences, and in inline code outside any fence."""
    values: list[str] = []
    for lang, body in FENCE_RE.findall(text):
        if lang.strip().lower() == "json":
            values += JSON_STAGE_RE.findall(body)
    prose = FENCE_RE.sub("", text)
    values += KEY_SPAN_STAGE_RE.findall(prose)
    for span in INLINE_CODE_RE.findall(prose):
        values += INLINE_STAGE_RE.findall(span)
        values += JSON_STAGE_RE.findall(span)
    return values


def check_gate_summary(root: Path, f: Findings) -> None:
    """The gate log is documented, and sc-ship's PR template renders a Gate summary from it.

    #70: stage/gate passage lived only in the state file G13 deletes, so nothing after the merge showed the
    cycle was followed. The rule is prose, so the cheap mechanical part is that both halves still exist.
    """
    doc = root / STATE_SHAPE_DOC
    if doc.is_file():
        doc_text = read(doc)
        if GATE_LOG_HEADING not in doc_text:
            f.error(shown(STATE_SHAPE_DOC), f"no '{GATE_LOG_HEADING}' section documenting the gate log")
        # One escaping rule for every cell: an unescaped `|` or newline in free text breaks the table.
        m = GATE_LOG_ESCAPING_RE.search(doc_text)
        if not m:
            f.error(shown(STATE_SHAPE_DOC), "no <!-- gate-log-cell-escaping --> rule for gate-log cells")
        else:
            for token in GATE_LOG_ESCAPING_TOKENS:
                if token not in m.group(1):
                    f.error(shown(STATE_SHAPE_DOC), f"gate-log cell-escaping rule does not state {token!r}")
    orchestrator = root / SKILLS_DIR / "ship-cycle" / "SKILL.md"
    if orchestrator.is_file():
        # The summary is rendered at PR open and goes stale; G12 is where it is re-checked before merge.
        row = G12_ROW_RE.search(read(orchestrator))
        if not row or GATE_SUMMARY_PHRASE not in row.group(1):
            f.error(shown(orchestrator.relative_to(root)),
                    f"G12 row of the gate table does not require the {GATE_SUMMARY_PHRASE}")
        elif G12_FRESH_RENDER_PHRASE not in row.group(1):
            # "Matches the log" lets a stale, log-copied summary pass; it must match a re-render.
            f.error(shown(orchestrator.relative_to(root)),
                    f"G12 row does not require the summary to match a {G12_FRESH_RENDER_PHRASE}")
    ship = root / SHIP_SKILL
    if not ship.is_file():
        f.error(shown(SHIP_SKILL), "missing")
        return
    text = read(ship)
    if GATE_SUMMARY_PHRASE not in text:
        f.error(shown(SHIP_SKILL), f"PR template does not include the '{GATE_SUMMARY_PHRASE}'")
    if not GATE_LOG_PATH_RE.search(text):
        f.error(shown(SHIP_SKILL), "does not name the gate log it renders the summary from")


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


def example_blocks(root: Path, f: Findings, key: str):
    """Yield (where, block, spec) for each example-overlay `changeNature[].<key>`, after the generic checks.

    The example is what users copy, so a block in it must satisfy the schema block of the same name. The
    shared rules -- required keys, a closed block's unknown keys, array-of-strings with minItems, plain
    strings -- are read from the schema, never from a second hard-coded list. Block-specific rules (an enum,
    a numeric range) stay with the caller, which receives the schema block as `spec`.
    """
    schema = load_json(root, OVERLAY_SCHEMA, f)
    example = load_json(root, OVERLAY_EXAMPLE, f)
    if schema is None or example is None:
        return
    if not isinstance(example, dict):
        f.error(shown(OVERLAY_EXAMPLE), "root must be an object")
        return
    try:
        spec = schema["properties"]["changeNature"]["items"]["properties"][key]
        props = spec["properties"]
        required = spec["required"]
    except (KeyError, TypeError):
        f.error(shown(OVERLAY_SCHEMA), f"changeNature.items.properties.{key} is missing its properties "
                                       "or required list")
        return
    closed = spec.get("additionalProperties") is False
    natures = example.get("changeNature", [])
    if not isinstance(natures, list):
        f.error(shown(OVERLAY_EXAMPLE), "changeNature must be an array")
        return
    for i, nature in enumerate(natures):
        block = nature.get(key) if isinstance(nature, dict) else None
        if block is None:
            continue
        where = f"{shown(OVERLAY_EXAMPLE)} changeNature[{i}].{key}"
        if not isinstance(block, dict):
            f.error(where, "must be an object")
            continue
        for name in required:
            if name not in block:
                f.error(where, f"missing required field '{name}'")
        if closed:
            for name in sorted(set(block) - set(props)):
                f.error(where, f"unknown field '{name}' (schema sets additionalProperties: false)")
        for name, sub in props.items():
            if name not in block:
                continue
            val = block[name]
            if sub.get("type") == "array":
                if (not isinstance(val, list) or not all(isinstance(x, str) for x in val)
                        or len(val) < sub.get("minItems", 0)):
                    f.error(where, f"'{name}' must be an array of strings with at least "
                                   f"{sub.get('minItems', 0)} item(s)")
            elif sub.get("type") == "string" and not isinstance(val, str):
                f.error(where, f"'{name}' must be a string")
        yield where, block, spec


def check_example_coverage(root: Path, f: Findings) -> None:
    """The example overlay's `changeNature[].coverage` satisfies the schema's coverage block.

    A `format` outside the enum, a missing key or a stray one ships a config that G6 can only read as
    undetermined -- so the copied example would block every cycle it runs in.
    """
    for where, cov, spec in example_blocks(root, f, "coverage"):
        try:
            props = spec["properties"]
            formats = set(props["format"]["enum"])
            th = props["threshold"]
            th_default, th_min, th_max = th["default"], th["minimum"], th["maximum"]
        except (KeyError, TypeError):
            f.error(shown(OVERLAY_SCHEMA), "changeNature.items.properties.coverage is missing its format enum "
                                           "or threshold default/minimum/maximum")
            return
        if "format" in cov and cov["format"] not in formats:
            f.error(where, f"format '{cov['format']}' is not in the schema enum {sorted(formats)}")
        threshold = cov.get("threshold", th_default)
        if (not isinstance(threshold, (int, float)) or isinstance(threshold, bool)
                or not th_min <= threshold <= th_max):
            f.error(where, f"threshold {threshold!r} is not a number in {th_min}..{th_max}")


def check_example_release_smoke(root: Path, f: Findings) -> None:
    """The example overlay's `changeNature[].releaseSmoke` satisfies the schema's releaseSmoke block.

    A copied example missing `flows` or `artifact` leaves G9 nothing to exercise, so the smoke it was meant
    to require reads as satisfied. Only the shared rules apply.
    """
    for _ in example_blocks(root, f, "releaseSmoke"):
        pass


def check_release_checklist(root: Path, f: Findings) -> None:
    """#73: the overlay's `releaseChecklist` is documented, consumed by sc-ship and counted by G12.

    A field nothing reads is a false promise: release steps listed in the overlay would be skipped silently.
    Guards the schema entry (item keys, `when` selector keys, `manual`), that the example overlay's items are
    well-formed with unique ids, and that sc-ship and the G12 row name it. It does not judge the prose.
    """
    schema = load_json(root, OVERLAY_SCHEMA, f)
    example = load_json(root, OVERLAY_EXAMPLE, f)
    if schema is None or example is None:
        return
    try:
        spec = schema["properties"]["releaseChecklist"]
        item = spec["items"]
        props, required = item["properties"], item["required"]
        when_keys = set(props["when"]["properties"])
        ok = (spec.get("type") == "array" and "manual" in props
              and {"id", "when", "check", "evidence"} <= set(required)
              and {"changeNature", "paths", "release"} <= when_keys)
    except (KeyError, TypeError):
        ok = False
    if not ok:
        f.error(shown(OVERLAY_SCHEMA), "properties.releaseChecklist is missing or lacks "
                                       "id/when/check/evidence, manual, or the when keys "
                                       "changeNature/paths/release")
    items = example.get("releaseChecklist", []) if isinstance(example, dict) else []
    if not isinstance(items, list):
        f.error(shown(OVERLAY_EXAMPLE), "releaseChecklist must be an array")
        items = []
    seen: set = set()
    natures = {n.get("nature") for n in example.get("changeNature", []) if isinstance(n, dict)} \
        if isinstance(example, dict) else set()
    uses_release = False
    for i, it in enumerate(items):
        where = f"{shown(OVERLAY_EXAMPLE)} releaseChecklist[{i}]"
        if not isinstance(it, dict):
            f.error(where, "must be an object")
            continue
        for name in ("id", "when", "check", "evidence"):
            if name not in it:
                f.error(where, f"missing required field '{name}'")
        iid = it.get("id")
        if not isinstance(iid, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", iid):
            f.error(where, f"id {iid!r} must match ^[a-z0-9][a-z0-9-]*$")
        elif iid in seen:
            f.error(where, f"duplicate id '{iid}'")
        else:
            seen.add(iid)
        for name in ("check", "evidence"):
            if name in it and (not isinstance(it[name], str) or not it[name].strip()):
                f.error(where, f"'{name}' must be a non-empty string")
        if "manual" in it and not isinstance(it["manual"], bool):
            f.error(where, "'manual' must be a boolean")
        when = it.get("when")
        if not isinstance(when, dict) or not when or set(when) - {"changeNature", "paths", "release"}:
            f.error(where, "'when' must be a non-empty object using only changeNature/paths/release")
        else:
            uses_release = uses_release or when.get("release") is True
            for n in when.get("changeNature", []) if isinstance(when.get("changeNature"), list) else []:
                if n not in natures:
                    f.error(where, f"when.changeNature '{n}' is not a declared nature")
    if uses_release and not (isinstance(example, dict) and isinstance(example.get("vcs"), dict)
                             and example["vcs"].get("releaseBranch")):
        f.error(shown(OVERLAY_EXAMPLE), "an item uses when.release but vcs.releaseBranch is not declared")
    try:
        import jsonschema  # optional extra check
        jsonschema.validate(example, schema)
    except ImportError:
        pass
    except Exception as e:  # jsonschema.ValidationError
        f.error(shown(OVERLAY_EXAMPLE), f"fails schema validation: {str(e).splitlines()[0]}")
    ship = root / SKILLS_DIR / "sc-ship" / "SKILL.md"
    orch = root / SKILLS_DIR / "ship-cycle" / "SKILL.md"
    if ship.is_file():
        m = re.search(r"\*\*Release checklist \(overlay `releaseChecklist`\).*?(?=\n- \*\*|\n\n##|\Z)",
                      read(ship), re.S)
        if not m:
            f.error(shown(ship.relative_to(root)), "no 'Release checklist' rule naming releaseChecklist")
        elif '"Pre-merge manual gate"' not in m.group(0):
            f.error(shown(ship.relative_to(root)),
                    "Release checklist rule is not tied to the pre-merge manual gate")
    if orch.is_file():
        row = next((l for l in read(orch).splitlines() if l.startswith("| G12 |")), "")
        if "releaseChecklist" not in row:
            f.error(shown(orch.relative_to(root)), "G12 row does not reference releaseChecklist")


def check_heavy_work(root: Path, f: Findings) -> None:
    """#74: `env` heavy-work keys are documented and the stages point at the rule.

    Guards the schema entries (types, bounds), that the example env is well-formed (unknown keys warn),
    that docs/heavy-work.md exists and states its lock-fd, nesting and fallback rules, and that the
    orchestrator, sc-implement, sc-review and sc-qa reference it while sc-review no longer carries the
    ad-hoc 'smaller batches' advice.
    """
    schema = load_json(root, OVERLAY_SCHEMA, f)
    example = load_json(root, OVERLAY_EXAMPLE, f)
    if schema is None or example is None:
        return
    p: dict = {}
    try:
        p = schema["properties"]["env"]["properties"]
        ok = (p["heavyLock"]["type"] == "string"
              and p["maxConcurrentHeavy"]["type"] == "integer" and p["maxConcurrentHeavy"]["minimum"] == 1
              and p["heavyHeadroomMB"]["type"] == "integer" and p["heavyHeadroomMB"]["minimum"] == 1)
    except (KeyError, TypeError):
        ok = False
    if not ok:
        f.error(shown(OVERLAY_SCHEMA), "env lacks heavyLock (string), maxConcurrentHeavy and "
                                       "heavyHeadroomMB (integer, minimum 1)")
    env = example.get("env", {}) if isinstance(example, dict) else {}
    if not isinstance(env, dict):
        f.error(shown(OVERLAY_EXAMPLE), "env must be an object")
        env = {}
    try:
        if p["heavyLock"].get("minLength") != 1 or p["heavyHeadroomMB"].get("maximum") is None:
            f.error(shown(OVERLAY_SCHEMA), "env.heavyLock needs minLength 1 and heavyHeadroomMB a maximum")
        for k in env:
            if k not in p and not k.startswith("$"):
                f.warn(shown(OVERLAY_EXAMPLE), f"env key '{k}' is not in the schema")
    except (KeyError, TypeError, AttributeError):
        pass
    if not isinstance(env.get("heavyLock"), str) or not env.get("heavyLock", "").strip():
        f.error(shown(OVERLAY_EXAMPLE), "env.heavyLock must be a non-empty string")
    for k in ("maxConcurrentHeavy", "heavyHeadroomMB"):
        v = env.get(k)
        if isinstance(v, bool) or not isinstance(v, int) or v < 1:
            f.error(shown(OVERLAY_EXAMPLE), f"env.{k} must be an integer >= 1")
    doc = root / "docs" / "heavy-work.md"
    if not doc.is_file():
        f.error("docs/heavy-work.md", "missing")
    else:
        text = read(doc)
        for token in ("flock", "mkdir", "SC-DEGRADE-ENV", "sequential", "PID", "do not inherit",
                      "SC_HEAVY_HELD", "{fd}>&-", "available", "heavy-run.sh"):
            if token not in text:
                f.error("docs/heavy-work.md", f"does not state {token!r}")
    for skill in ("ship-cycle", "sc-implement", "sc-review", "sc-qa"):
        path = root / SKILLS_DIR / skill / "SKILL.md"
        if path.is_file() and "heavy-work.md" not in read(path):
            f.error(shown(path.relative_to(root)), "does not reference docs/heavy-work.md")
    review = root / SKILLS_DIR / "sc-review" / "SKILL.md"
    if review.is_file() and "smaller batches" in read(review):
        f.error(shown(review.relative_to(root)), "still carries ad-hoc 'smaller batches' advice")


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


def check_entry_path_inventory(root: Path, f: Findings) -> None:
    """sc-design asks for an entry-path inventory and its critic pass checks it against the code.

    #71: a restructured tab shipped a design that assumed one entry path; the critic found the primary one
    missing late. The rule is prose, so the mechanical part is that the three anchors still exist: the
    `### Entry-path inventory` subsection, the `## Design` checklist bullet, and the critic's bullet.
    """
    skill = root / SKILLS_DIR / "sc-design" / "SKILL.md"
    if not skill.is_file():
        return
    where = shown(skill.relative_to(root))
    text = read(skill)
    if not re.search(r"^### Entry-path inventory", text, re.M | re.I):
        f.error(where, "no '### Entry-path inventory' subsection")
    sections = re.split(r"^## ", text, flags=re.M)
    design = next((s for s in sections if s.startswith("Design (architect")), "")
    critic = next((s for s in sections if s.startswith("Design review (critic")), "")
    if not re.search(r"^- \*\*Entry paths\*\*", design, re.M | re.I):
        f.error(where, "'## Design' checklist has no '**Entry paths**' bullet pointing to the inventory")
    if not re.search(r"^- \*\*Entry-path inventory\*\*", critic, re.M | re.I):
        f.error(where, "critic review has no '**Entry-path inventory**' bullet")


def check_claim_evidence(root: Path, f: Findings) -> None:
    """The claim-evidence rule exists once, and sc-design (output + critic) and sc-review point to it.

    #72: a subagent report misread a library internal and the orchestrator passed it on. The rule is prose;
    the mechanical part is that the doc keeps its marked rule and the three consumers keep a bold-labelled
    `**Claim evidence**` bullet naming the doc.
    """
    doc = root / "docs" / "claim-evidence.md"
    if not doc.is_file():
        f.error("docs/claim-evidence.md", "missing")
    else:
        m = re.search(r"<!-- claim-evidence-rule -->(.*?)<!-- /claim-evidence-rule -->", read(doc), re.S)
        body = m.group(1) if m else ""
        for token in ("Load-bearing", "path:line", "official doc URL", "command and its output",
                      "objection", "never by itself"):
            if token.lower() not in body.lower():
                f.error("docs/claim-evidence.md", f"claim-evidence rule block does not state {token!r}")
    design = root / SKILLS_DIR / "sc-design" / "SKILL.md"
    if design.is_file():
        where = shown(design.relative_to(root))
        sections = re.split(r"^## ", read(design), flags=re.M)
        for label, prefix in (("design output", "Design (architect"),
                              ("critic review", "Design review (critic")):
            sec = next((s for s in sections if s.startswith(prefix)), "")
            if _claim_bullet(sec) is None:
                f.error(where, f"{label} has no '**Claim evidence**' bullet naming claim-evidence.md")
    review = root / SKILLS_DIR / "sc-review" / "SKILL.md"
    if review.is_file():
        where = shown(review.relative_to(root))
        sections = re.split(r"^## ", read(review), flags=re.M)
        sec = next((s for s in sections if s.startswith("Output & severity discipline")), "")
        bullet = _claim_bullet(sec)
        if bullet is None:
            f.error(where, "output & severity discipline has no '**Claim evidence**' bullet naming "
                           "claim-evidence.md")
        elif "never by itself" not in bullet.lower():
            f.error(where, "Claim evidence bullet does not say a missing citation is 'never by itself' "
                           "a downgrade")
        verify = next((s for s in sections if s.startswith("Verify findings")), "")
        for token, why in (("cited evidence", "have the refuter open the cited evidence"),
                           ("must cite its evidence", "say a refutation must cite its evidence")):
            if token not in verify:
                f.error(where, f"Verify findings does not {why}")


def _claim_bullet(section: str) -> str | None:
    """Body of the section's `**Claim evidence**` bullet if it names claim-evidence.md, else None."""
    m = re.search(r"^- \*\*Claim evidence\*\*(.*?)(?=^- |\Z)", section, re.M | re.S)
    return m.group(1) if m and "claim-evidence.md" in m.group(1) else None



ROUTE_ALWAYS_RUN = ("sc-implement", "sc-review", "sc-ship")
ROUTE_READERS = ("sc-design", "sc-tdd", "sc-review", "sc-qa")
ROUTE_RULE_TOKENS = ("never removed", "standalone", "§core", "n/a: route — <reason>", "Tier S floor",
                     "layout, copy or config", "Effective lenses", "`cleared`", "`basis`", "loop cap",
                     "now `run`", "ignores a terminal state file", "not in `basis.risk`",
                     "not in `basis.nature`", "`state.branchCreated`")
REVIEW_LENS_TOKENS = ("effective lenses", "Tier S floor", "risk-matched", "`state.nature`")


def check_route_plan(root: Path, f: Findings) -> None:
    """#82: which stages run is decided once at G1, confirmed with the criteria, and read by every stage.

    Guards the documented `route` shape (one run/skip entry per post-brainstorm stage; implement, review and
    ship always run), that sc-brainstorm's G1 section and the orchestrator's G1 row require the route plan,
    that the orchestrator states the rule once (growth-only, standalone, §core, the n/a form, lens floor),
    that the skippable stages and sc-review read `state.route`, and that /status shows it. Prose quality is
    the reviewer's.
    """
    orchestrator = root / SKILLS_DIR / "ship-cycle" / "SKILL.md"
    pipeline = re.findall(r"^\|\s*\d+\s*\|\s*`(sc-[a-z-]+)`", read(orchestrator), re.M) \
        if orchestrator.is_file() else []
    if orchestrator.is_file() and not pipeline:
        # An empty stage list would make the shape check below vacuously pass.
        f.error(shown(orchestrator.relative_to(root)), "pipeline table yields no stage skills")
    doc = root / STATE_SHAPE_DOC
    if doc.is_file():
        blocks = re.findall(r"```json\n(.*?)\n```", read(doc), re.S)
        try:
            route = json.loads(blocks[0]).get("route") if blocks else None
        except json.JSONDecodeError:
            route = None  # reported by state_shape_fields
        if not isinstance(route, dict):
            f.error(shown(STATE_SHAPE_DOC), "state shape has no 'route' object")
        else:
            for key in ("confirmedAt", "basis", "stages", "lenses", "qa"):
                if key not in route:
                    f.error(shown(STATE_SHAPE_DOC), f"route lacks '{key}'")
            basis = route.get("basis") if isinstance(route.get("basis"), dict) else {}
            for key in ("size", "risk", "nature"):
                if "basis" in route and key not in basis:
                    f.error(shown(STATE_SHAPE_DOC), f"route.basis lacks '{key}'")
            stages = route.get("stages") if isinstance(route.get("stages"), dict) else {}
            expected = [s for s in pipeline if s != "sc-brainstorm"]
            if expected and sorted(stages) != sorted(expected):
                f.error(shown(STATE_SHAPE_DOC), f"route.stages must name exactly {expected}")
            for stage, plan in stages.items():
                if not isinstance(plan, str) or not (plan == "run" or plan.startswith("skip: ")):
                    f.error(shown(STATE_SHAPE_DOC),
                            f"route.stages['{stage}'] is not 'run' or 'skip: <reason>'")
                elif stage in ROUTE_ALWAYS_RUN and plan != "run":
                    f.error(shown(STATE_SHAPE_DOC), f"route.stages['{stage}'] must always be 'run' (§core)")
    if orchestrator.is_file():
        where = shown(orchestrator.relative_to(root))
        text = read(orchestrator)
        sec = re.search(r"^## Route plan(.*?)(?=^## )", text, re.M | re.S)
        if not sec:
            f.error(where, "no '## Route plan' section")
        else:
            for token in ROUTE_RULE_TOKENS:
                if token not in sec.group(1):
                    f.error(where, f"Route plan section does not state {token!r}")
            if "`state.route`" not in sec.group(1):
                f.error(where, "Route plan section does not name `state.route`")
        row = re.search(r"^\|\s*G1\s*\|(.*)$", text, re.M)
        if not row or "route plan" not in row.group(1):
            f.error(where, "G1 row of the gate table does not require the route plan")
        row12 = G12_ROW_RE.search(text)
        if not row12 or "whole-stage G2/G3, G4 or G9 `n/a` whose route entry is `run`" not in row12.group(1):
            f.error(where, "G12 row does not refuse a whole-stage n/a whose route entry is `run`")
    brainstorm = root / SKILLS_DIR / "sc-brainstorm" / "SKILL.md"
    if brainstorm.is_file():
        where = shown(brainstorm.relative_to(root))
        sec = re.search(r"^## Gate G1(.*?)(?=^## |\Z)", read(brainstorm), re.M | re.S)
        body = sec.group(1) if sec else ""
        if "route plan" not in body or "`state.route`" not in body:
            f.error(where, "Gate G1 section does not record the route plan as `state.route`")
    for skill in ROUTE_READERS:
        path = root / SKILLS_DIR / skill / "SKILL.md"
        if path.is_file() and "state.route" not in read(path):
            f.error(shown(path.relative_to(root)), "does not read state.route")
    review = root / SKILLS_DIR / "sc-review" / "SKILL.md"
    if review.is_file():
        text = read(review)
        for token in REVIEW_LENS_TOKENS:
            if token not in text:
                f.error(shown(review.relative_to(root)), f"lens selection does not state {token!r}")
    tdd = root / SKILLS_DIR / "sc-tdd" / "SKILL.md"
    if tdd.is_file():
        sec = re.search(r"^\*\*Route first\.\*\*(.*?)(?=^## )", read(tdd), re.M | re.S)
        body = sec.group(1) if sec else ""
        if "layout, copy or config" not in body or "grow the entry to `run`" not in body:
            f.error(shown(tdd.relative_to(root)), "Route first does not restrict a tdd skip to layout, copy "
                                                  "or config and grow it back on a contract")
    for skill in ("sc-design", "sc-tdd", "sc-qa"):
        path = root / SKILLS_DIR / skill / "SKILL.md"
        if path.is_file() and "state.route.basis" not in read(path):
            f.error(shown(path.relative_to(root)), "does not check state.route.basis before a route skip")
    ship = root / SHIP_SKILL
    if ship.is_file():
        text = read(ship)
        if "whose `state.route` entry is now `run`" not in text:
            f.error(shown(SHIP_SKILL),
                    "G12 does not refuse an `n/a: route` gate whose route entry is now `run`")
        elif "whole-stage `n/a` (G2/G3, G4, G9)" not in text or "unless it is a config `n/a`" not in text:
            f.error(shown(SHIP_SKILL), "G12 does not refuse every whole-stage n/a whose route entry is `run` "
                                       "(config n/a exempt)")
    status = root / "commands" / "status.md"
    if status.is_file():
        text = read(status)
        if "`route`" not in text:
            f.error("commands/status.md", "does not show the route plan (`route`)")
        elif "(G2/G3, G4, G9)" not in text or "n/a: no <x> config" not in text:
            f.error("commands/status.md", "unplanned-n/a flag is not limited to whole-stage gates "
                                          "with config n/a exempt")


# --- entry point -------------------------------------------------------------------------------


VISUAL_DOC = Path("docs/visual-check.md")
VISUAL_FIELDS = ("run", "open", "devBuild", "profiles", "restore", "capture", "diff", "sharedPaths",
                 "designTool")
A11Y_FLOOR_TOKENS = ("touch target", "contrast", "screen-reader", "largest font scale", "reduced motion")
VISUAL_BLOCK_TOKENS = {
    "visual-loop-rule": (
        "a release-form build installed on the device cannot reload", "heavy-work.md",
        "build → start emulator → loop", "read and record its prior value", "and on abort",
        "Ask in plain words what to look at",
        "without re-entering sc-review — before the first sc-review only",
        "presentation-only", "goes back to sc-tdd (Red first)",
        "delta re-review and G5–G7, and counts against the loop cap", "labelled `variant A`",
        "temporary and uncommitted", "delete the rest before any commit, review or test",
        "Prototype cleanup is recorded before G5", "`git diff --stat` against the pre-loop tree",
        "in the owner's own words in this run", "state.visualCheck", "part of G5's evidence",
        "resets `preLoopTree`", "without being handed the record",
        "when no cold lens runs, the designer lens"),
    "visual-evidence-rule": (
        "backs appearance claims only",
        "Behaviour claims (state, data, navigation) still need a test or a QA log",
        "**`live (owner-confirmed)`**", "**`review-only (agent-captured)`**", "Pre-merge manual gate",
        "unattended", "never inside the repo", "slugified profile name", "its `tree` equals the final tree",
        "`git diff <tree>..HEAD`", "only when the project declares a harness", "not their behaviour",
        "finds the recorded owner words as a user turn in its own conversation",
        "downgraded to `agent-captured`", "`visualCheck.sharedPaths`"),
    "a11y-floor": A11Y_FLOOR_TOKENS + ("An outcome, not ceremony",
                                       "not on the Tier S path, not by a route plan"),
}
VISUAL_WRITER_TOKENS = ("for every nature in `state.nature`", "top-level session that talks to the user",
                        "a subagent writes `agent-captured` at most",
                        "`state.route.ownerPresent === true` — absent or `false` fails closed",
                        "re-ask the owner", "**advisory only**", "default profile list",
                        "font scale 1.0 and at the OS maximum")
OWNER_PRESENT_STATE_TOKENS = ("Only `true` permits", "absent or `false` fails closed",
                              "`false → true` is allowed only by asking the owner")
VISUAL_STATE_KEYS = ("result", "tree", "preLoopTree", "owner", "writtenBy", "deviceRestore", "cleanup")
DESIGN_TOOL_HOOKS = ("shape", "generate", "live", "critique", "detect", "audit", "polish")


def _flat(text: str) -> str:
    """Whitespace-collapsed text, so a phrase wrapped across lines still matches."""
    return " ".join(text.split())


def _section(text: str, heading_prefix: str) -> str:
    m = re.search(r"^## " + re.escape(heading_prefix) + r".*?(?=^## |\Z)", text, re.M | re.S)
    return m.group(0) if m else ""


def check_visual_check(root: Path, f: Findings) -> None:
    """#83: UI natures settle their looks in a live owner loop, and that is the visual evidence.

    Guards the overlay's `changeNature[].visualCheck` block (closed, `run` + `profiles` required, every
    documented field present) and an example nature using it; docs/visual-check.md keeps its loop,
    evidence and accessibility-floor blocks and the design-tool adapter table with its read-only constraint;
    sc-implement has the live-loop section, sc-design the reuse check, sc-review's designer lens the named
    a11y checks, sc-ship G11 the owner-confirmed / agent-captured labels and the manual-gate item, and the
    orchestrator's G11 row and route plan name it. It does not judge the prose.
    """
    schema = load_json(root, OVERLAY_SCHEMA, f)
    if schema is not None:
        try:
            spec = schema["properties"]["changeNature"]["items"]["properties"]["visualCheck"]
            ok = (spec.get("additionalProperties") is False
                  and {"run", "profiles"} <= set(spec["required"])
                  and set(VISUAL_FIELDS) <= set(spec["properties"]))
        except (KeyError, TypeError):
            ok = False
        if not ok:
            f.error(shown(OVERLAY_SCHEMA), "changeNature.items.properties.visualCheck is missing, "
                                           "not closed, lacks run/profiles as required, or lacks one of "
                                           + "/".join(VISUAL_FIELDS))
            return
    blocks = list(example_blocks(root, f, "visualCheck"))
    if not blocks:
        f.error(shown(OVERLAY_EXAMPLE), "no changeNature declares visualCheck")
    doc = root / VISUAL_DOC
    if not doc.is_file():
        f.error(shown(VISUAL_DOC), "missing")
    else:
        text = read(doc)
        for name, tokens in VISUAL_BLOCK_TOKENS.items():
            m = re.search(rf"<!-- {name} -->(.*?)<!-- /{name} -->", text, re.S)
            if not m:
                f.error(shown(VISUAL_DOC), f"no <!-- {name} --> block")
                continue
            body = _flat(m.group(1))
            for token in tokens:
                if token not in body:
                    f.error(shown(VISUAL_DOC), f"{name} block does not state {token!r}")
        intro = _flat(text.split("<!-- visual-loop-rule -->")[0])
        for token in VISUAL_WRITER_TOKENS:
            if token not in intro:
                f.error(shown(VISUAL_DOC), f"writer rule does not state {token!r}")
        adapter = _flat(_section(text, "Design-tool adapter"))
        for hook in DESIGN_TOOL_HOOKS:
            if f"`{hook}`" not in adapter:
                f.error(shown(VISUAL_DOC), f"design-tool adapter table has no `{hook}` hook")
        for token in ("fallback", "never requires", "read-only", "`init`", "`document`", "hook"):
            if token not in adapter:
                f.error(shown(VISUAL_DOC), f"design-tool adapter does not state {token!r}")
    shape_doc = root / STATE_SHAPE_DOC
    if shape_doc.is_file():
        blocks = re.findall(r"```json\n(.*?)\n```", read(shape_doc), re.S)
        try:
            shape = json.loads(blocks[0]) if blocks else {}
        except json.JSONDecodeError:
            shape = {}  # reported by state_shape_fields
        route = shape.get("route") if isinstance(shape.get("route"), dict) else {}
        if "ownerPresent" not in route:
            f.error(shown(STATE_SHAPE_DOC), "route lacks 'ownerPresent'")
        prose = _flat(read(shape_doc))
        for token in OWNER_PRESENT_STATE_TOKENS:
            if token not in prose:
                f.error(shown(STATE_SHAPE_DOC), f"route.ownerPresent rule does not state {token!r}")
        vc = shape.get("visualCheck") if isinstance(shape.get("visualCheck"), dict) else {}
        entry = next((v for v in vc.values() if isinstance(v, dict)), {})
        for key in VISUAL_STATE_KEYS:
            if key not in entry:
                f.error(shown(STATE_SHAPE_DOC), f"visualCheck entry lacks '{key}'")
    anchors = (
        ("sc-implement", "Live visual loop", (
            "visual-check.md", "visualCheck.profiles", "release-form", "and restore those, also on abort",
            "uncommitted prototypes", "before the first sc-review only", "goes back to sc-tdd",
            "counts against the loop cap", "state.visualCheck[<nature>].cleanup", "accessibility-floor",
            "for every nature in `state.nature`", "Only the top-level session that talks to the user writes",
            "in the owner's own words", "`state.route.ownerPresent === true`", "`agent-captured` at most",
            "resets `preLoopTree`", "part of G5's evidence")),
        ("sc-design", "UI-only changes", ("**Reuse check before any new component or token**",
                                          "design.guide", "backstop")),
        ("sc-ship", "Verify (G11)", (
            "visual-check.md", "state.visualCheck", "live (owner-confirmed)", "review-only (agent-captured)",
            "pre-merge manual gate", "backs appearance claims only", "still needs a test or QA log",
            "`state.route.ownerPresent === true` (absent fails closed)",
            "as a user turn in your own conversation", "`writtenBy` is advisory only",
            "downgrade it to `agent-captured`", "`visualCheck.tree` equals the final tree",
            "`git diff <tree>..HEAD`", "`visualCheck.sharedPaths`")),
        ("sc-ship", "PR (G12)", ("every `state.visualCheck` entry that is not `owner-confirmed`",)),
        ("sc-qa", "Gate G9", ("state.visualCheck", "visual-check.md", "not their behaviour",
                              "delta re-review")),
        ("sc-review", "Gate G8", ("state.visualCheck[<nature>].cleanup", "never dropped",
                                  "**without being handed**", "when no cold lens runs, the designer lens")),
        ("sc-review", "Re-review after fixes", ("visual-check.md", "counted against the loop cap")),
        ("sc-brainstorm", "Do", ("`state.route.ownerPresent`",)),
        ("ship-cycle", "Route plan", ("live visual loop", "visual-check.md", "`state.route.ownerPresent`",
                                      "no route or Tier S drops them")),
        ("ship-cycle", "Tier S path", ("the accessibility floor", "visual-check.md")),
    )
    for skill, heading, tokens in anchors:
        path = root / SKILLS_DIR / skill / "SKILL.md"
        if not path.is_file():
            continue
        sec = _flat(_section(read(path), heading))
        if not sec:
            f.error(shown(path.relative_to(root)), f"no '## {heading}' section")
            continue
        for token in tokens:
            if token not in sec:
                f.error(shown(path.relative_to(root)), f"'## {heading}' does not state {token!r}")
    review = root / SKILLS_DIR / "sc-review" / "SKILL.md"
    if review.is_file():
        m = re.search(r"^- \*\*designer\*\*.*?(?=^- \*\*)", read(review), re.M | re.S)
        lens = _flat(m.group(0)) if m else ""
        for token in A11Y_FLOOR_TOKENS + ("visual-check.md", "read-only", "runs once", "never dropped"):
            if token not in lens:
                f.error(shown(review.relative_to(root)), f"designer lens does not state {token!r}")
    orch = root / SKILLS_DIR / "ship-cycle" / "SKILL.md"
    if orch.is_file():
        row = next((l for l in read(orch).splitlines() if l.startswith("| G11 |")), "")
        if "state.visualCheck" not in row or "appearance only; not stale; `ownerPresent` true" not in row:
            f.error(shown(orch.relative_to(root)), "G11 row does not reference state.visualCheck with "
                                                   "'appearance only; not stale; `ownerPresent` true'")
    adapters = root / "docs" / "runtime-adapters.md"
    if adapters.is_file():
        row = next((l for l in read(adapters).splitlines() if "visualCheck.designTool" in l), "")
        if "fallback" not in row:
            f.error("docs/runtime-adapters.md", "no design-tool adapter row naming the Codex fallback")


RETRO_SKILL = SKILLS_DIR / "sc-retro" / "SKILL.md"
RETRO_SECTION_TOKENS = {
    "Not a gate": ("never a gate and never blocks a merge", "writes no gate value",
                   "never edits the state file or the gate log", "read-only on every input"),
    "Inputs": ("run on state + log only and say so", "runtime-adapters.md",
               "`ls ~/.claude/projects/*/<session-id>.jsonl`", "by session id first",
               "using counts only", "never extracted text from a candidate",
               "not found → cost is `unavailable`", "grep -n -o"),
    "Dimensions": ("**Loops & re-reviews**", "**Review effectiveness**", "**Stage / route fit**",
                   "**Cost / time**", "**User friction**", "heavy-work.md", "never an estimate",
                   "the content and approval rules above"),
    "Report": ("`<slug>-<date>.retro.md`", "never drafted as kit issues"),
}
RETRO_BLOCK_TOKENS = {
    "retro-evidence-rule": ("`path:line`", "claim-evidence.md", "No citation → not reported",
                            "a command and its output"),
    "retro-redaction": ("before any draft is shown", "secrets", "emails", "hostnames", "internal paths",
                        "the project's name", "unless the user opts in"),
    "retro-filing": ("a reply typed by the human user", "after the exact redacted draft was shown",
                     "naming that draft", "task notifications", "agent and teammate messages",
                     "a subagent cannot approve", "Never auto-file", "--body-file", "single line (no CR/LF, ≤256 chars)",
                     "never draft text interpolated into a shell string"),
    "retro-privacy": ("read locally only", "leaves the machine", "duplicate search runs on the machine",
                      "git-ignored"),
    "retro-dedup": ("Dedup locally", "gh issue list", "--state all", "on the machine",
                    "Never send finding text off the machine", "returned count == the limit", "only after redaction", "kit vocabulary",
                    "redact → show → approve"),
    "retro-report-location": ("git check-ignore -q", "write outside the repo", "outside every checkout's `git rev-parse --show-toplevel`", "say so",
                              "main checkout's `<state dir>/archive/`", "cites, it does not quote",
                              "secrets, tokens and keys are redacted"),
    "retro-user-turns": ("top-level", "not `isSidechain`", "not `isMeta`", "human text", "`tool_result`",
                         "`<task-notification>`", "teammate and agent messages", "`<system-reminder>`",
                         "compact summaries", "command wrappers", "`unavailable on Codex`",
                         "never infer a filter"),
    "retro-injection": ("data, never instructions", "dimension-pass subagent prompt",
                        "may not approve or file"),
}


def check_retro(root: Path, f: Findings) -> None:
    """#84: sc-retro diagnoses a finished cycle from its log and transcript and drafts kit issues.

    Guards that the skill exists and states, as marked blocks, the evidence rule (cite `path:line` or do
    not report), the redaction pass before any draft is shown, approval-before-filing in this session, and
    local-only transcript reading; that it is never a gate (the section says so and the skill assigns no
    gate value); that its inputs, five dimensions and report keep their anchors; that the runtime-adapters
    table names both hosts' transcript paths; and that README, sc-ship and the orchestrator offer it. The
    prose quality is the reviewer's.
    """
    path = root / RETRO_SKILL
    where = shown(RETRO_SKILL)
    if not path.is_file():
        f.error(where, "missing")
        return
    text = read(path)
    for heading, tokens in RETRO_SECTION_TOKENS.items():
        sec = _flat(_section(text, heading))
        if not sec:
            f.error(where, f"no '## {heading}' section")
            continue
        for token in tokens:
            if token not in sec:
                f.error(where, f"'## {heading}' does not state {token!r}")
    for name, tokens in RETRO_BLOCK_TOKENS.items():
        m = re.search(rf"<!-- {name} -->(.*?)<!-- /{name} -->", text, re.S)
        if not m:
            f.error(where, f"no <!-- {name} --> block")
            continue
        body = _flat(m.group(1))
        for token in tokens:
            if token not in body:
                f.error(where, f"{name} block does not state {token!r}")
    if GATE_SET_RE.search(text):
        f.error(where, "assigns a gate value; sc-retro is never a gate")
    readme = root / "README.md"
    if readme.is_file() and not any(l.startswith("| `sc-retro`") for l in read(readme).splitlines()):
        f.error("README.md", "component table does not list sc-retro")
    adapters = root / "docs" / "runtime-adapters.md"
    if adapters.is_file():
        row = next((l for l in read(adapters).splitlines() if l.startswith("| host transcript")), "")
        if not ("sc-retro" in row and "~/.claude/projects/*/<session-id>.jsonl" in row
                and ".codex/sessions/" in row):
            f.error("docs/runtime-adapters.md", "no host-transcript row naming sc-retro with both hosts' "
                                                "transcript paths")
    for skill, heading in (("sc-ship", "Cleanup (G13)"), ("ship-cycle", "State (real")):
        p = root / SKILLS_DIR / skill / "SKILL.md"
        if not p.is_file():
            continue
        sec = _flat(_section(read(p), heading))
        if "`sc-retro`" not in sec or "never a gate" not in sec:
            f.error(shown(p.relative_to(root)), f"'## {heading}' does not offer `sc-retro` as never a gate")


EVALS_DIR = Path("evals")
EVALS_CHECKER = EVALS_DIR / "check.py"
EVALS_README = EVALS_DIR / "README.md"
EVALS_RESULTS = EVALS_DIR / "baselines" / "results.md"
EVAL_SECTIONS = ("Rule under test", "Pressures", "Setup", "Prompt", "Expected behaviour", "Post-check")
EVAL_README_TOKENS = ("never a required check", "RED", "GREEN", "outside the repo", "run interactively and "
                      "save the transcript", "Claude Code", "Codex", "heuristics, not proofs",
                      "no known violation pattern was found", "spot-checked by a person reading the transcript")
CHECK_IDS_RE = re.compile(r"^CHECK_IDS = \((.*?)^\)", re.M | re.S)
EVAL_POST_CHECK_RE = re.compile(r"<!-- post-check -->\s*```json\n(.*?)```\s*<!-- /post-check -->", re.S)
EVAL_RULE_REF_RE = re.compile(r"`((?:skills|docs)/[A-Za-z0-9._/-]+\.md)`")


def check_evals(root: Path, f: Findings) -> None:
    """#85: behaviour evals — pressure scenarios with deterministic post-checks.

    The live runs are manual; what is mechanical is that every scenario states the rule it tests (pointing
    at a skill or doc that exists), its pressures, a POSIX setup, the prompt, the expected behaviour and a
    post-check whose id `evals/check.py` registers; that each has a passing and a failing fixture case (so
    its checker can fail) and a RED and a GREEN row in the baseline record; that every registered check is used;
    and that the README says the evals are never a required check. Whether a scenario is a good test is the
    reviewer's.
    """
    checker = root / EVALS_CHECKER
    if not checker.is_file():
        f.error(shown(EVALS_CHECKER), "missing")
        return
    m = CHECK_IDS_RE.search(read(checker))
    ids = set(re.findall(r'"([a-z0-9-]+)"', m.group(1))) if m else set()
    if not ids:
        f.error(shown(EVALS_CHECKER), "no CHECK_IDS registry")
        return
    readme = root / EVALS_README
    if not readme.is_file():
        f.error(shown(EVALS_README), "missing")
    else:
        flat = _flat(read(readme))
        for token in EVAL_README_TOKENS:
            if token not in flat:
                f.error(shown(EVALS_README), f"does not state {token!r}")
    results_path = root / EVALS_RESULTS
    results = read(results_path).splitlines() if results_path.is_file() else []
    if not results:
        f.error(shown(EVALS_RESULTS), "missing")
    scenarios = sorted((root / EVALS_DIR / "scenarios").glob("*.md"))
    if not scenarios:
        f.error(shown(EVALS_DIR / "scenarios"), "no scenarios")
    used: set[str] = set()
    for path in scenarios:
        where = shown(path.relative_to(root))
        text = read(path)
        for heading in EVAL_SECTIONS:
            if not _section(text, heading):
                f.error(where, f"no '## {heading}' section")
        refs = EVAL_RULE_REF_RE.findall(_section(text, "Rule under test"))
        if not refs:
            f.error(where, "'## Rule under test' points at no skill or doc")
        for ref in refs:
            if not (root / ref).is_file():
                f.error(where, f"'## Rule under test' points at {ref}, which does not exist")
        if "```sh" not in _section(text, "Setup"):
            f.error(where, "'## Setup' has no ```sh setup script")
        pc = EVAL_POST_CHECK_RE.search(_section(text, "Post-check"))
        try:
            params = json.loads(pc.group(1)) if pc else None
        except ValueError:
            params = None
        check = params.get("check") if isinstance(params, dict) else None
        if check is None:
            f.error(where, "no <!-- post-check --> json block with a \"check\" id")
        elif check not in ids:
            f.error(where, f"post-check {check!r} is not a check id registered in {EVALS_CHECKER}")
        else:
            used.add(check)
        fixtures = root / EVALS_DIR / "fixtures" / path.stem
        cases = [c for c in fixtures.iterdir() if c.is_dir() and any(c.iterdir())] if fixtures.is_dir() else []
        for verdict in ("pass", "fail"):
            if not any(c.name == verdict or c.name.startswith(verdict + "-") for c in cases):
                f.error(where, f"no fixture evals/fixtures/{path.stem}/{verdict}[-<label>]/")
        for phase in ("RED", "GREEN"):
            if not any(l.startswith(f"| {path.stem} | {phase} |") for l in results):
                f.error(shown(EVALS_RESULTS), f"no {phase} row for scenario {path.stem}")
    for unused in sorted(ids - used):
        f.error(shown(EVALS_CHECKER), f"check {unused!r} is used by no scenario")


HOOKS_JSON = Path("hooks/hooks.json")
HOOK_SCRIPT = Path("hooks/session-start.cjs")
HOOK_MATCHER = {"startup", "clear", "compact"}
HOOK_OPT_OUT = "SHIP_CYCLE_HOOK"
HOOK_DOCS = (Path("docs/runtime-adapters.md"), Path("README.md"))
HOOK_COMMAND_RE = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/(hooks/[A-Za-z0-9._-]+)")
STAGE_GATES_BLOCK_RE = re.compile(r"// stage-gates:begin\n\s*const STAGE_GATES = (\{.*?\});\n// stage-gates:end", re.S)
LOOP_CAP_SCRIPT_RE = re.compile(r"^const LOOP_CAP = (\d+);", re.M)
LOOP_CAP_SKILL_RE = re.compile(r"\*\*Loop cap: (\d+) per gate\*\*")
PIPELINE_ROW_RE = re.compile(r"^\|\s*\d+\s*\|\s*`(sc-[a-z-]+)`\s*\|[^|\n]*\|\s*([^|\n]+?)\s*\|", re.M)


def _expand_gates(cell: str) -> list[str]:
    """`G5/G6/G7/G7b` -> four ids; `G10–G13` -> G10..G13."""
    out: list[str] = []
    for part in cell.split("/"):
        m = re.fullmatch(r"G(\d+)[–-]G(\d+)", part.strip())
        if m:
            out += [f"G{n}" for n in range(int(m.group(1)), int(m.group(2)) + 1)]
        elif re.fullmatch(r"G\d+[a-z]?", part.strip()):
            out.append(part.strip())
    return out


def check_session_hook(root: Path, f: Findings) -> None:
    """#86: the SessionStart hook is wired, points at a script that exists, and agrees with the pipeline.

    The hook names the next gate from a small stage->gate map; the pipeline table in the orchestrator is the
    single source, so the map is parsed and compared rather than trusted. `hooks/hooks.json` is registered by
    its place at the plugin root (observed live, and how superpowers and oh-my-claudecode ship it); a manifest
    `hooks` key would be a second registration path, so it is refused.
    """
    hooks = load_json(root, HOOKS_JSON, f)
    if hooks is not None:
        entries = hooks.get("hooks", {}).get("SessionStart") if isinstance(hooks.get("hooks"), dict) else None
        if not isinstance(entries, list) or not entries:
            f.error(shown(HOOKS_JSON), "no hooks.SessionStart entry")
            entries = []
        for entry in entries:
            if not isinstance(entry, dict):
                f.error(shown(HOOKS_JSON), "SessionStart entry is not an object")
                continue
            matcher = set(str(entry.get("matcher", "")).split("|"))
            if matcher != HOOK_MATCHER:
                f.error(shown(HOOKS_JSON), f"SessionStart matcher must be exactly startup|clear|compact, "
                                           f"got {entry.get('matcher')!r}")
            for hook in entry.get("hooks", []) if isinstance(entry.get("hooks"), list) else []:
                if not isinstance(hook, dict) or hook.get("type") != "command":
                    f.error(shown(HOOKS_JSON), "SessionStart hook is not a command hook")
                    continue
                refs = HOOK_COMMAND_RE.findall(str(hook.get("command", "")))
                if not refs:
                    f.error(shown(HOOKS_JSON), "hook command does not run a script under ${CLAUDE_PLUGIN_ROOT}/hooks/")
                for ref in refs:
                    if not (root / ref).is_file():
                        f.error(shown(HOOKS_JSON), f"hook command runs {ref}, which does not exist")
                timeout = hook.get("timeout")
                if not isinstance(timeout, (int, float)) or not 0 < timeout <= 10:
                    f.error(shown(HOOKS_JSON), "hook needs a timeout of at most 10 seconds")
    claude = load_json(root, CLAUDE_MANIFEST, f)
    if isinstance(claude, dict) and "hooks" in claude:
        f.error(shown(CLAUDE_MANIFEST), "declares 'hooks'; hooks/hooks.json at the plugin root is the kit's "
                                        "one registration path")

    script_path = root / HOOK_SCRIPT
    if not script_path.is_file():
        f.error(shown(HOOK_SCRIPT), "missing")
        return
    script = read(script_path)
    m = STAGE_GATES_BLOCK_RE.search(script)
    try:
        mapped = json.loads(m.group(1)) if m else None
    except ValueError:
        mapped = None
    if not isinstance(mapped, dict):
        f.error(shown(HOOK_SCRIPT), "no parseable // stage-gates:begin ... :end STAGE_GATES block")
        mapped = {}
    orchestrator = root / SKILLS_DIR / "ship-cycle" / "SKILL.md"
    skill_text = read(orchestrator) if orchestrator.is_file() else ""
    tabled = {stage: _expand_gates(cell) for stage, cell in PIPELINE_ROW_RE.findall(skill_text)}
    if not tabled:
        f.error(shown(orchestrator.relative_to(root)), "pipeline table has no stage rows")
    for stage in sorted(set(tabled) | set(mapped)):
        if tabled.get(stage) != mapped.get(stage):
            f.error(shown(HOOK_SCRIPT), f"stage->gate map disagrees with the pipeline table for {stage}: "
                                        f"hook {mapped.get(stage)!r}, table {tabled.get(stage)!r}")
    cap_script = LOOP_CAP_SCRIPT_RE.search(script)
    cap_skill = LOOP_CAP_SKILL_RE.search(skill_text)
    if not cap_script or not cap_skill or cap_script.group(1) != cap_skill.group(1):
        f.error(shown(HOOK_SCRIPT), f"LOOP_CAP {cap_script.group(1) if cap_script else None} disagrees with the "
                                    f"orchestrator's loop cap {cap_skill.group(1) if cap_skill else None}")
    if HOOK_OPT_OUT not in script:
        f.error(shown(HOOK_SCRIPT), f"does not honour the {HOOK_OPT_OUT} opt-out")
    for doc in HOOK_DOCS:
        text = read(root / doc) if (root / doc).is_file() else ""
        for token in ("SessionStart", HOOK_OPT_OUT):
            if token not in text:
                f.error(shown(doc), f"does not document the SessionStart hook ({token!r} missing)")


IMPL_STATUS_DOC = Path("docs/impl-status.md")
IMPL_PROMPTS = ("impl-backend.md", "impl-web.md", "impl-mobile.md")
IMPL_STATUSES = ("DONE", "DONE_WITH_CONCERNS", "BLOCKED", "NEEDS_CONTEXT")
IMPL_VOCAB_TOKENS = ("**Changed**", "**Concerns**", "**Commands run**", "exit code", "**Not verified**",
                     "applies to every status", "No silent end", "never approves anything", "missing context",
                     "reasoning limit", "too large", "design defect", "**no report**")
IMPL_CARRIERS = ("build-fixer", "debugger", "wave")
IMPL_REPORT_LINES = ("- Changed:", "- Concerns:", "- Commands run:", "- Not verified:", "- Hypotheses:")
# Route column of the routing table: each status/reason row must carry these tokens.
IMPL_ROUTES = {
    "`DONE`": ("G5", "own commands", "Not verified"),
    "`DONE_WITH_CONCERNS`": ("fix round by default", "recorded reason", "correctness/scope"),
    "`NEEDS_CONTEXT`": ("re-dispatch", "unobtainable or 3 fetches → stop"),
    "`BLOCKED` (missing context)": ("`NEEDS_CONTEXT`",),
    "`BLOCKED` (reasoning limit)": ("fresh agent", "tier up", "`tierMap`", "split", "unsplittable → stop"),
    "`BLOCKED` (too large)": ("split",),
    "`BLOCKED` (design defect)": ("sc-design", "loop cap", "user decides"),
    "`BLOCKED` (no report)": ("resume once", "fresh", "missing context once", "then stop"),
}
IMPL_ROUTE_BULLETS = ("Never re-dispatch unchanged", "Failure-driven re-dispatches count", "G5…G11",
                      "once per gate loop-back", "increments the parent's counter once",
                      "does not count against",
                      "own per-brief cap of 3", "Stop, never loop", "the one cap rule",
                      "park the cycle", "latest non-null `tier`", "`modelRouting.tierMap`",
                      "A tier-up re-dispatch is always a fresh agent", "same tier only",
                      "fresh one with a written handoff", "sc-review brief", "`env.heavyLock`",
                      "**Not verified** applies to every status", "A report approves nothing",
                      "`state.telemetry.implStatus`")
# A resumed agent keeps its own model, so a resume cannot carry a tier change (#87 review H1).
IMPL_ROUTE_FORBIDDEN = ("resume passes the routed model",)
IMPL_REVIEW_TOKENS = {"Triage": ("Implementer concerns are items to verify", "spec-blind"),
                      "Gate G8": ("implementer concern",)}
IMPL_SHIP_TOKENS = ("Open implementer `notVerified` items", "`coveredBy` is `null`", "`env.heavyLock`",
                    "pre-merge manual gate")
IMPL_SHIP_PR_TOKEN = "open `implStatus.notVerified` item a claim depends on"
# The loop cap is stated once, in the orchestrator, and sc-implement points to it (#87 delta M2).
IMPL_CAP_TOKENS = ("stop:", "ask the user", "the one cap rule", "Route the implementer's status")
IMPL_CAP_FORBIDDEN = "return to\n`sc-design` and notify the user"

def check_impl_status(root: Path, f: Findings) -> None:
    """#87: every implementer ends with one status from one vocabulary, and sc-implement routes each.

    Guards the vocabulary block in docs/impl-status.md (four statuses, the orchestrator-only `no report`
    reason, changed/concerns/commands/not-verified lines, no silent end, a report approves nothing, who
    carries it); that each stack prompt's report block equals the doc's word for word; that sc-implement's
    routing table has a row per status/reason with its route and the cap, stop, tier-up-is-fresh and
    current-tier rules; that sc-review triages skipped concerns and G8 reads them; that sc-ship G11
    cross-checks open not-verified items; and that `telemetry.implStatus` is in the state shape and read.
    """
    doc = root / IMPL_STATUS_DOC
    where = shown(IMPL_STATUS_DOC)
    if not doc.is_file():
        f.error(where, "missing")
        return
    m = re.search(r"<!-- impl-status-vocabulary -->(.*?)<!-- /impl-status-vocabulary -->", read(doc), re.S)
    if not m:
        f.error(where, "no <!-- impl-status-vocabulary --> block")
        return
    vocab_text = m.group(1)
    vocab = re.findall(r"^- `([A-Z_]+)`", vocab_text, re.M)
    if tuple(vocab) != IMPL_STATUSES:
        f.error(where, f"status vocabulary is {vocab}, expected {list(IMPL_STATUSES)}")
    flat = _flat(vocab_text)
    for token in IMPL_VOCAB_TOKENS:
        if token not in flat:
            f.error(where, f"impl-status-vocabulary block does not state {token!r}")
    for token in IMPL_CARRIERS:
        if token not in _flat(read(doc)):
            f.error(where, f"does not say a {token} agent carries the report block")
    bm = re.search(r"<!-- impl-report-block -->\n```\n(.*?)```\n<!-- /impl-report-block -->", read(doc), re.S)
    doc_block = bm.group(1) if bm else None
    if doc_block is None:
        f.error(where, "no <!-- impl-report-block --> fenced block")
    for name in IMPL_PROMPTS:
        path = root / "prompts" / name
        pwhere = f"prompts/{name}"
        if not path.is_file():
            f.error(pwhere, "missing")
            continue
        text = read(path)
        block = text[text.find("## Report (end every turn"):] if "## Report (end every turn" in text else ""
        if not block:
            f.error(pwhere, "template has no '## Report (end every turn ...' block")
            continue
        sm = re.search(r"^- Status: (.*)$", block, re.M)
        listed = tuple(s.strip() for s in sm.group(1).split("|")) if sm else ()
        if listed != IMPL_STATUSES:
            f.error(pwhere, f"report Status line lists {list(listed)}, expected {list(IMPL_STATUSES)}")
        for line in IMPL_REPORT_LINES:
            if not re.search(r"^" + re.escape(line), block, re.M):
                f.error(pwhere, f"report block has no {line!r} line")
        if "docs/impl-status.md" not in block:
            f.error(pwhere, "report block does not point to docs/impl-status.md")
        end = block.find("```")
        if doc_block is not None and block[:end] != doc_block:
            f.error(pwhere, "report block differs from the one in docs/impl-status.md")
    impl = root / SKILLS_DIR / "sc-implement" / "SKILL.md"
    iwhere = "skills/sc-implement/SKILL.md"
    itext = read(impl) if impl.is_file() else ""
    rm = re.search(r"<!-- impl-status-routing -->(.*?)<!-- /impl-status-routing -->", itext, re.S)
    if not rm:
        f.error(iwhere, "no <!-- impl-status-routing --> table")
    else:
        rows = {}
        for line in rm.group(1).splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) == 2 and not set(cells[0]) <= set("-"):
                rows[cells[0]] = cells[1]
        for key, tokens in IMPL_ROUTES.items():
            if key not in rows:
                f.error(iwhere, f"routing table has no row for {key}")
                continue
            for token in tokens:
                if token not in rows[key]:
                    f.error(iwhere, f"routing row {key} does not route via {token!r}")
    section = _flat(_section(itext, "Route the implementer's status"))
    for token in IMPL_ROUTE_BULLETS:
        if token not in section:
            f.error(iwhere, f"'## Route the implementer's status' does not state {token!r}")
    for token in IMPL_ROUTE_FORBIDDEN:
        if token in section:
            f.error(iwhere, f"'## Route the implementer's status' states {token!r}")
    if not all(c in _flat(itext) for c in IMPL_CARRIERS):
        f.error(iwhere, "does not say build-fixer, debugger and wave agents carry the report block")
    review = root / SKILLS_DIR / "sc-review" / "SKILL.md"
    rtext = read(review) if review.is_file() else ""
    for heading, tokens in IMPL_REVIEW_TOKENS.items():
        sec = _flat(_section(rtext, heading))
        for token in tokens:
            if token not in sec:
                f.error("skills/sc-review/SKILL.md", f"'## {heading}' does not state {token!r}")
    ship = root / SKILLS_DIR / "sc-ship" / "SKILL.md"
    sec = _flat(_section(read(ship), "Verify (G11)")) if ship.is_file() else ""
    for token in IMPL_SHIP_TOKENS:
        if token not in sec:
            f.error("skills/sc-ship/SKILL.md", f"'## Verify (G11)' does not state {token!r}")
    if ship.is_file() and IMPL_SHIP_PR_TOKEN not in _flat(_section(read(ship), "PR (G12)")):
        f.error("skills/sc-ship/SKILL.md", f"'## PR (G12)' manual gate does not list {IMPL_SHIP_PR_TOKEN!r}")
    orch = root / SKILLS_DIR / "ship-cycle" / "SKILL.md"
    otext = read(orch) if orch.is_file() else ""
    cm = re.search(r"\*\*Loop cap: \d+ per gate\*\*(.*?)(?=\n\n)", otext, re.S)
    cap = _flat(cm.group(1)) if cm else ""
    for token in IMPL_CAP_TOKENS:
        if token not in cap:
            f.error("skills/ship-cycle/SKILL.md", f"loop-cap sentence does not state {token!r}")
    if IMPL_CAP_FORBIDDEN in otext:
        f.error("skills/ship-cycle/SKILL.md", "loop cap still returns to sc-design on its own")
    shape = read(root / STATE_SHAPE_DOC) if (root / STATE_SHAPE_DOC).is_file() else ""
    if '"implStatus"' not in shape:
        f.error(shown(STATE_SHAPE_DOC), "telemetry shape has no implStatus entry")
    if '"coveredBy"' not in shape or '"coveredBy"' not in read(doc):
        f.error(shown(STATE_SHAPE_DOC), "implStatus.notVerified entries have no coveredBy")
    for skill in ("sc-ship", "sc-retro"):
        p = root / SKILLS_DIR / skill / "SKILL.md"
        if p.is_file() and "telemetry.implStatus" not in read(p):
            f.error(shown(p.relative_to(root)), "does not read `telemetry.implStatus`")


WAVE_DOC = Path("docs/wave-check.md")
# Each marker block in docs/wave-check.md and the tokens it must state (#88).
WAVE_BLOCK_TOKENS = {
    "wave-check-trigger": ("**Tier L**", "multi-stack", "every barrier that has a later wave",
                           "after that barrier's build/typecheck has passed", "The last barrier gets none",
                           "Tier S and Tier M never run it", "resolves `review.wave` then",
                           "the worktree where the contract landed", "integration worktree",
                           "`from`/`tree` are tree identities taken in the worktree read",
                           "only when that worktree no longer exists", "Later stack barriers"),
    "wave-check-barriers": ("`state.waveBarriers`", "checked or not", "the route skips the check",
                            "the latest non-superseded entry for wave N−1",
                            "with the same `worktree`",
                            "never by position or wave number",
                            "`git cat-file -e <from>`", "diff from the base instead"),
    "wave-check-route": ("ceremony", "`state.route.waveCheck`", "\"skip: <reason the user saw>\"",
                         "growth-only", "G8 still runs the full fleet"),
    "wave-check-rule": ("`model = state.models[\"review.wave\"]`", "`effort = state.effort[\"review.wave\"]`",
                        "cold first", "Cold pass", "**frozen verbatim**", "before the spec is sent",
                        "Spec alignment", "acceptance criteria", "cannot verify from the diff",
                        "never retracts or lowers one — only a refuter can",
                        "Host without live messaging", "Codex", "agent 1 runs the cold pass",
                        "passed to agent 2", "same pinned model",
                        "**pinned to `review.wave`**", "recorded as the entry's `refuter`",
                        "`refutedItems`, `{item, where, refutation}`", "`refutedCarried`",
                        "A cheap refutation never drops a Critical/High", "stays unresolved for G8",
                        "previously flagged, refuted at wave N — confirm",
                        "incrementing `loops[G5]` once", "grows to `run`", "the user is told",
                        "re-plans with every later wave", "`superseded: true`",
                        "latest non-superseded barrier before it",
                        "A confirmed Critical may be fixed first", "Decided:", "actively **evidenced**",
                        "never by itself triggers an edit round", "`loops[G5]` +1", "docs/impl-status.md",
                        "Route the implementer's status", "the barrier build/typecheck reruns",
                        "a new `waveBarriers` entry for the same wave",
                        "`from` = that new barrier's `tree`",
                        "Read-only and alone", "`env.heavyLock`", "§sc-review — Git-write freeze",
                        "Same evidence rule as review findings", "claim-evidence.md",
                        "§sc-review — Verify findings",
                        "Only a **design** finding that survives verification",
                        "`BLOCKED` (design defect)", "loop cap", "lets the next wave start",
                        "sc-review brief as an item to verify", "G8 requires one", "not a second one",
                        "sets no `gates` entry", "approves nothing"),
    "wave-check-record": ("`state.waveReviews`", "`tree`", "`model`", "`cold`", "`refutedItems`",
                          "`routedTo`", "`unresolved`", "cost readout", "sc-retro", "None decides a gate",
                          "`refuter`", "`refutedCarried`", "`superseded`", "superseded ones included",
                          "only when `route.waveCheck` is `\"run\"`", "has a later wave", "`tier` `L`",
                          "no `waveReviews` entry has a `tree` equal to that barrier's `tree`",
                          "matched on tree, not wave number"),
}
# A wave check is advisory: these sentences would make it a gate or a lens substitute.
WAVE_FORBIDDEN = ("wave check is a gate", "replaces G8", "skips the G8", "blocks the next wave on any")
WAVE_ENTRY_KEYS = ("wave", "from", "tree", "model", "effort", "refuter", "cold", "findings", "refutedItems",
                   "refutedCarried", "routedTo", "unresolved", "superseded")
WAVE_REFUTED_KEYS = ("item", "where", "refutation")
WAVE_BARRIER_KEYS = ("wave", "tree", "worktree", "tier", "superseded")
WAVE_SKILL_TOKENS = {
    "sc-implement": ("Large cross-cutting change", ("Wave check at each barrier", "docs/wave-check.md",
                                                     "`state.route.waveCheck`", "`state.waveReviews`",
                                                     "design-level finding stops the waves")),
    "sc-review": ("Triage", ("Wave-check items are items to verify", "`state.waveReviews`",
                             "not the cold lens's", "previously flagged, refuted at wave N — confirm",
                             "never drops a Critical/High", "G8 runs the full fleet either way")),
    "ship-cycle": ("Route plan", ("`state.route.waveCheck`", "G8 still runs the full fleet",
                                  "docs/wave-check.md", "a wave-check / `BLOCKED` design defect")),
}


def shape_reconcile_missing(root: Path) -> bool:
    """True when the reconcile's subagents-running row does not name the wave check."""
    path = root / STATE_SHAPE_DOC
    row = re.search(r"^\| subagents running when the session died(.*)$", read(path), re.M) \
        if path.is_file() else None
    return not row or "a wave check is rerun" not in row.group(1) or \
        "no `waveReviews` entry has that barrier's `tree`" not in row.group(1)


def check_wave_check(root: Path, f: Findings) -> None:
    """#88: a cheap advisory read at each Tier L wave barrier, its findings carried into G8.

    Guards the rule doc's trigger, route, reviewer and record blocks (stated once, there); that sc-implement's
    waved section points to it, sc-review triages the unresolved items and G8 requires a disposition, the
    orchestrator lets the route dial it while G8 keeps the full fleet and resolves its model and effort; and
    that `state.waveReviews` is in the state shape with its keys and read by sc-ship's readout and sc-retro.
    """
    doc = root / WAVE_DOC
    where = shown(WAVE_DOC)
    if not doc.is_file():
        f.error(where, "missing")
        return
    text = read(doc)
    for marker, tokens in WAVE_BLOCK_TOKENS.items():
        m = re.search(rf"<!-- {marker} -->(.*?)<!-- /{marker} -->", text, re.S)
        if not m:
            f.error(where, f"no <!-- {marker} --> block")
            continue
        body = _flat(m.group(1))
        for token in tokens:
            if token not in body:
                f.error(where, f"{marker} block does not state {token!r}")
    rule = re.search(r"<!-- wave-check-rule -->(.*?)<!-- /wave-check-rule -->", text, re.S)
    body = rule.group(1) if rule else ""
    if "**Cold pass.**" in body and "**Spec alignment.**" in body and \
            body.index("**Cold pass.**") > body.index("**Spec alignment.**"):
        f.error(where, "wave-check-rule puts Spec alignment before the Cold pass")
    for token in WAVE_FORBIDDEN:
        if token in _flat(text):
            f.error(where, f"states {token!r} — a wave check is advisory and G8 stays the gate")
    for skill, (heading, tokens) in WAVE_SKILL_TOKENS.items():
        path = root / SKILLS_DIR / skill / "SKILL.md"
        swhere = f"skills/{skill}/SKILL.md"
        sec = _flat(_section(read(path), heading)) if path.is_file() else ""
        for token in tokens:
            if token not in sec:
                f.error(swhere, f"'## {heading}' does not state {token!r}")
    review = root / SKILLS_DIR / "sc-review" / "SKILL.md"
    if review.is_file() and "`state.waveReviews` (§Triage)" not in _flat(_section(read(review), "Gate G8")):
        f.error("skills/sc-review/SKILL.md",
                "'## Gate G8' does not require a disposition per wave-check item")
    orch = root / SKILLS_DIR / "ship-cycle" / "SKILL.md"
    otext = read(orch) if orch.is_file() else ""
    if "a ceremony stage or the wave check" not in otext:
        f.error("skills/ship-cycle/SKILL.md", "Tier L row does not let a route skip the wave check")
    if "grows to Tier L later" not in otext:
        f.error("skills/ship-cycle/SKILL.md", "review.wave is not resolved when a cycle grows to Tier L")
    adapters = root / "docs" / "runtime-adapters.md"
    if adapters.is_file() and "Two-pass agents without live messaging" not in read(adapters):
        f.error("docs/runtime-adapters.md", "does not state the two-agent fallback for two-pass rules")
    if shape_reconcile_missing(root):
        f.error(shown(STATE_SHAPE_DOC), "reconcile's subagents-running row does not rerun a wave check")
    if 'models["review.wave"]' not in otext:
        f.error("skills/ship-cycle/SKILL.md", 'PREFLIGHT does not resolve models["review.wave"]')
    erow = re.search(r"^\|\s*\*\*medium\*\*\s*\|(.*)$", otext, re.M)
    if not erow or "the wave check" not in erow.group(1):
        f.error("skills/ship-cycle/SKILL.md", "effort table's medium row does not price the wave check")
    shape_path = root / STATE_SHAPE_DOC
    blocks = re.findall(r"```json\n(.*?)\n```", read(shape_path), re.S) if shape_path.is_file() else []
    try:
        shape = json.loads(blocks[0]) if blocks else {}
    except json.JSONDecodeError:
        shape = {}  # reported by state_shape_fields
    entries = shape.get("waveReviews")
    if not isinstance(entries, list) or not entries or not isinstance(entries[0], dict):
        f.error(shown(STATE_SHAPE_DOC), "state shape has no waveReviews entry")
    else:
        for key in WAVE_ENTRY_KEYS:
            if key not in entries[0]:
                f.error(shown(STATE_SHAPE_DOC), f"waveReviews entry lacks '{key}'")
        refuted = entries[0].get("refutedItems")
        if not isinstance(refuted, list) or not refuted or \
                not all(k in refuted[0] for k in WAVE_REFUTED_KEYS):
            f.error(shown(STATE_SHAPE_DOC), "waveReviews.refutedItems entries lack item/where/refutation")
    barriers = shape.get("waveBarriers")
    if not isinstance(barriers, list) or not barriers or \
            not all(k in barriers[0] for k in WAVE_BARRIER_KEYS):
        f.error(shown(STATE_SHAPE_DOC),
                "state shape has no waveBarriers entry with wave/tree/worktree/tier/superseded")
    route = shape.get("route") if isinstance(shape.get("route"), dict) else {}
    if "waveCheck" not in route:
        f.error(shown(STATE_SHAPE_DOC), "route lacks 'waveCheck'")
    for key in ("models", "effort"):
        if "review.wave" not in (shape.get(key) or {}):
            f.error(shown(STATE_SHAPE_DOC), f"{key} lacks 'review.wave'")
    for skill in ("sc-ship", "sc-retro"):
        p = root / SKILLS_DIR / skill / "SKILL.md"
        if p.is_file() and "state.waveReviews" not in read(p):
            f.error(shown(p.relative_to(root)), "does not read `state.waveReviews`")
    ship = root / SKILLS_DIR / "sc-ship" / "SKILL.md"
    if ship.is_file() and "`refutedCarried`) shown as such" not in _flat(read(ship)):
        f.error("skills/sc-ship/SKILL.md", "cost readout does not show refuted-but-carried items as such")


RED_DOC = Path("docs/red-gate.md")
# Each marker block in docs/red-gate.md and the tokens it must state (#89).
RED_BLOCK_TOKENS = {
    "red-gate-trigger": ("G5, G6, G7 or G7b", "red wave barrier", "genuine `fail` at G9",
                         "every later round on the same failure", "An undetermined check is not red",
                         "§sc-brainstorm — Root-cause analysis", "never a restatement of the symptom",
                         "`baseline.unrunnableHere` never triggers it", "diffed around, as at G6"),
    "red-gate-protocol": ("**Reproduce first, with the real command.**", "its own exit code",
                          "tree identity", "`env.heavyLock`", "bounded wait", "docs/heavy-work.md",
                          "**\"Could not reproduce\" is not fixed.**", "`undetermined`",
                          "A G9 hand-off from sc-qa", "**is** this step", "re-runs it once to confirm",
                          "The red stands: `gates.<G>` keeps its `fail`",
                          "evidence `undetermined: not reproduced in <N> runs`",
                          "the log has no `undetermined` value", "three exits",
                          "never retry until green to pass a gate", "**(a) Classify and fix.**",
                          "**(b) Recheck on the base commit.**", "pre-existing", "docs/test-baseline.md",
                          "unless their suite is rechecked", "**(c) Not reproducible anywhere.**",
                          "park the cycle and ask the user",
                          "**Read the actual error.**", "**Compare against a working example.**",
                          "never the working tree", "**One hypothesis, with evidence.**",
                          "docs/claim-evidence.md", "**Read `state.debug` first:**",
                          "not tried again unless new evidence",
                          "cited against that entry's `tree`", "is new evidence",
                          "**One minimal change, then re-run.**", "one change, not a bundle",
                          "**Red differently is `rejected`** on the original failure",
                          "only then does a new error open a new one", "**Revert safely",
                          "undo this change, not the work around it", "`base=$(git stash create)`",
                          "never run `git stash` itself", "so use `HEAD`", "copy every untracked file",
                          "**After the change**, patch the change itself",
                          "`git diff \"$base\" -- <files> > <scratch>/change.patch`",
                          "Keep the patch outside the worktree", "`git apply -R <scratch>/change.patch`",
                          "restore the pre-change copies",
                          "Never `git checkout`, `git reset` or `git stash`",
                          "the tree identity equals the pre-change tree", "record the revert",
                          "**Record every attempt**", "The counting rides on #87 and adds nothing to it",
                          "already a fix-round re-dispatch counted against `loops[G]`",
                          "hypotheses tested inside one round are not loops",
                          "**Three rejected hypotheses on the same failure inside a round:**",
                          "`BLOCKED` (design defect)", "`NEEDS_CONTEXT`", "parks and asks the user",
                          "Route the implementer's status", "the round's \"further failure\"",
                          "only because it happened inside the round",
                          "**At loop 2 with two rejected hypotheses**", "across all rounds, not within one",
                          "prefer sc-design over a third guess",
                          "`<N>` is the count fixed before the first run",
                          "applied per tree",
                          "**When the rounds already reached the cap**", "handed over as the evidence",
                          "**not a second cap**", "never stops the cycle by itself",
                          "the one cap rule stays the orchestrator's", "the user decides",
                          "a `confirmed` entry is a claim, not a pass"),
    "red-gate-record": ("`state.debug` is append-only", "one entry per hypothesis tested", "`failure`",
                        "same `gate` and `failure`", "no line or column",
                        "a new group opens only once the original error is gone", "`round`",
                        "the round, not a loop", "`revert`", "`result` is `confirmed`, `rejected` or "
                        "`undetermined`", "`- Hypotheses:` field", "docs/impl-status.md",
                        "optional in every other brief", "`cause · evidence · change · result · tree`",
                        "word for word",
                        "re-asked once as a context fetch (outside `loops[G]`)",
                        "never routed as `BLOCKED` (no report)", "(do not retry)",
                        "the resume reconcile keeps them",
                        "the rejected entries survive a restart, so no disproved cause is retried",
                        "cost readout", "sc-retro", "None decides a gate"),
    "red-gate-flaky": ("**Retry to classify, never to hide.**", "count fixed before the first one",
                       "a gate never passes on the best of N runs", "**order-dependent**", "**flaky**",
                       "not in `baseline.flaky` is a finding", "**Find the polluter by bisection.**",
                       "log2(n)", "runner's own selection and ordering flags", "Linux and Windows",
                       "`env.heavyLock`", "**Wait for the condition, not for time.**",
                       "Lengthening a sleep is not a fix", "**Isolate shared state.**",
                       "Fix the polluter, not the victim"),
}
# Wording that would make the protocol a second cap or let a retry pass a gate.
RED_FORBIDDEN = ("its own loop cap", "may pass on the best of", "rerun until it passes",
                 "could not reproduce counts as fixed", "lines after the report block",
                 "is routed as `BLOCKED` (no report)", "its re-run is repeated", "> pre.patch",
                 "three-rejection count survives")
RED_DEBUG_KEYS = ("gate", "failure", "round", "repro", "hypothesis", "evidence", "change", "result", "tree",
                  "revert")
RED_FAILURE_GATES = ("G5", "G6", "G7", "G7b", "G9")
RED_SKILL_TOKENS = {
    "sc-implement": ("When a gate goes red", ("docs/red-gate.md", "reproduce with the real command first",
                                              "`undetermined`, never fixed", "one hypothesis with evidence",
                                              "`state.debug`", "\"do not retry\"", "`- Hypotheses:`",
                                              "re-asked once as a context fetch",
                                              "`BLOCKED` (design defect)", "never a second cap",
                                              "the round's further failure", "prefer sc-design",
                                              "the user decides", "`env.heavyLock`",
                                              "Never rerun until green")),
    "sc-qa": ("When a gate goes red", ("docs/red-gate.md", "real command, exit code and tree",
                                       "That hand-off is the protocol's reproduce step",
                                       "re-runs it once to confirm", "three exits",
                                       "`undetermined`, not passed", "never rerun until green",
                                       "`state.debug`", "`BLOCKED`\n(design defect)", "`loops[G9]`")),
}


def check_red_gate(root: Path, f: Findings) -> None:
    """#89: a red gate is reproduced first and fixed one evidenced hypothesis at a time, with a record.

    Guards the protocol doc's trigger, protocol, record and flaky blocks (stated once, there; reproduce
    before the first hypothesis); that sc-implement and sc-qa point to it, every failure-routed gate row in
    the orchestrator's table names it, three rejections route as the design-defect row under the one cap
    rule; and that `state.debug` is in the shape with its keys, survives the reconcile and is read by the
    cost readout and sc-retro.
    """
    doc = root / RED_DOC
    where = shown(RED_DOC)
    if not doc.is_file():
        f.error(where, "missing")
        return
    text = read(doc)
    for marker, tokens in RED_BLOCK_TOKENS.items():
        m = re.search(rf"<!-- {marker} -->(.*?)<!-- /{marker} -->", text, re.S)
        if not m:
            f.error(where, f"no <!-- {marker} --> block")
            continue
        body = _flat(m.group(1))
        for token in tokens:
            if token not in body:
                f.error(where, f"{marker} block does not state {token!r}")
    pm = re.search(r"<!-- red-gate-protocol -->(.*?)<!-- /red-gate-protocol -->", text, re.S)
    body = pm.group(1) if pm else ""
    order = ("**Reproduce first", "**Read the actual error.**", "**Compare against a working example.**",
             "**One hypothesis, with evidence.**", "**One minimal change, then re-run.**")
    found = [body.find(t) for t in order]
    if all(i >= 0 for i in found) and found != sorted(found):
        f.error(where, "red-gate-protocol does not reproduce, read, compare, hypothesise, change in order")
    for token in RED_FORBIDDEN:
        if token in _flat(text):
            f.error(where, f"states {token!r} — the protocol changes a route, never a cap or a pass")
    for skill, (heading, tokens) in RED_SKILL_TOKENS.items():
        path = root / SKILLS_DIR / skill / "SKILL.md"
        swhere = f"skills/{skill}/SKILL.md"
        raw = _section(read(path), heading) if path.is_file() else ""
        sec = _flat(raw)
        for token in tokens:
            if _flat(token) not in sec:
                f.error(swhere, f"'## {heading}' does not state {_flat(token)!r}")
    impl = root / SKILLS_DIR / "sc-implement" / "SKILL.md"
    if impl.is_file() and "debugger under §When a gate goes red" not in _flat(read(impl)):
        f.error("skills/sc-implement/SKILL.md", "G6 does not attach its debugger under §When a gate goes red")
    orch = root / SKILLS_DIR / "ship-cycle" / "SKILL.md"
    otext = read(orch) if orch.is_file() else ""
    for gate in RED_FAILURE_GATES:
        row = re.search(rf"^\| {re.escape(gate)} \|.*\|([^|]*)\|\s*$", otext, re.M)
        if not row or "red-gate protocol" not in row.group(1):
            f.error("skills/ship-cycle/SKILL.md", f"gate table's {gate} 'On failure' cell does not name the "
                                                  "red-gate protocol")
    note = re.search(r"\*\*Red-gate protocol\*\*(.*?)(?=\n\n)", otext, re.S)
    if not note or "docs/red-gate.md" not in note.group(1) or "the one cap rule" not in _flat(note.group(1)):
        f.error("skills/ship-cycle/SKILL.md", "gate table has no red-gate note pointing to docs/red-gate.md "
                                              "under the one cap rule")
    if note and "no second cap" not in _flat(note.group(1)):
        f.error("skills/ship-cycle/SKILL.md", "gate table red-gate note does not say 'no second cap'")
    idoc = root / IMPL_STATUS_DOC
    ivocab = _flat(read(idoc)) if idoc.is_file() else ""
    for token in ("**Hypotheses** — optional, and required only in a red-gate fix brief", "docs/red-gate.md",
                  "re-asked once as a context fetch, never treated as no report",
                  "one per hypothesis: cause · evidence · change · result · tree>"):
        if token not in ivocab:
            f.error(shown(IMPL_STATUS_DOC), f"does not state {token!r} for the Hypotheses field")
    shape_path = root / STATE_SHAPE_DOC
    shape_text = read(shape_path) if shape_path.is_file() else ""
    blocks = re.findall(r"```json\n(.*?)\n```", shape_text, re.S)
    try:
        shape = json.loads(blocks[0]) if blocks else {}
    except json.JSONDecodeError:
        shape = {}  # reported by state_shape_fields
    entries = shape.get("debug")
    if not isinstance(entries, list) or not entries or not isinstance(entries[0], dict):
        f.error(shown(STATE_SHAPE_DOC), "state shape has no debug entry")
    else:
        for key in RED_DEBUG_KEYS:
            if key not in entries[0]:
                f.error(shown(STATE_SHAPE_DOC), f"debug entry lacks '{key}'")
        repro = entries[0].get("repro")
        if not isinstance(repro, dict) or not all(k in repro for k in ("command", "exit")):
            f.error(shown(STATE_SHAPE_DOC), "debug.repro lacks command/exit")
    if "**Debug entries survive the reconcile.**" not in shape_text or \
            "none is ever\npending" not in shape_text:
        f.error(shown(STATE_SHAPE_DOC), "resume reconcile does not keep `debug` entries (none pending)")
    for skill in ("sc-ship", "sc-retro"):
        p = root / SKILLS_DIR / skill / "SKILL.md"
        if p.is_file() and "state.debug" not in read(p):
            f.error(shown(p.relative_to(root)), "does not read `state.debug`")
    mr = root / "docs" / "model-routing.md"
    if mr.is_file() and "docs/red-gate.md" not in _flat(_section(read(mr), "Cost readout")):
        f.error("docs/model-routing.md", "cost readout does not carry the red-gate debug lines")


RF_DOC = Path("docs/review-focus.md")
# Each marker block in docs/review-focus.md and the tokens it must state (#90).
RF_BLOCK_TOKENS = {
    "review-focus-rule": (
        "`state.reviewFocus[]`", "**at most five**", "ranked by likelihood × harm", "`id`", "`input`",
        "`impliedBy`", "`uncovered`", "`expected`", "docs/claim-evidence.md",
        "**Per feature, never a class.**", "are not entries", "Accessibility floor",
        "**Nor does it restate an acceptance criterion**", "is promoted to one",
        "**An empty list means checked, not skipped.**", "An absent field means nobody wrote one",
        "**Shown, not approved.**", "no separate approval round", "The critic may object",
        "is a logic item planned for an `n/a` pin", "**Append or annotate only after G3.**",
        "keeps its `id`", "`pinnedBy: \"<existing test id>\"`", "listed in the G4 report",
        "`superseded: true`", "G4 re-pins", "continue the numbering (`RF6`+)",
        "the five-entry cap counts only non-superseded entries", "is a G1 re-show (§ship-cycle Stage 0.4)",
        "re-opens the list at whichever stage wrote it"),
    "review-focus-pin": (
        "**G4 pins every entry.**", "seen failing for the right reason", "`pinnedBy: \"<test id>\"`",
        "`pinnedBy: \"n/a: <reason>\"`", "**only for a layout, copy or config item**",
        "naming the execution-based verification", "a logic entry always needs a failing-first test",
        "A misused `n/a` is a critic objection", "`pinHolds: false` at G8",
        "passes before the change is not pinned",
        "G4 does not pass while any non-superseded entry has no `pinnedBy`"),
    "review-focus-cold": (
        "**The cold lens gets the list only after its blind pass.**", "diff only, no list",
        "the list is never in the cold lens's blind-pass brief",
        "**fresh agent with no prior compare in its context**", "1. **Freeze.**", "**frozen verbatim**",
        "before the list is sent", "docs/wave-check.md", "2. **Compare.**", "`raised`", "`pinHolds`",
        "real construction path", "it is a layout, copy or config item", "`postList: true`",
        "it never edits the frozen list", "3. **Record**",
        "`cold = { raised, finding, pinHolds, evidence, tree }`", "4. **Verify**",
        "The parallel lenses have already run", "**scoped second pass of a spec-anchored lens**",
        "**triage at `high` effort**", "**The scoped pass runs on the same model and effort the chosen lens "
        "ran with at G8**", "risk upgrade included", "Record who verified each",
        "`verify = { by, model, effort, outcome, evidence }`", "the construction call it goes through",
        "never a copy of `cold.evidence`", "**Host without live messaging:**",
        "docs/runtime-adapters.md", "**Three outcomes, recorded in `verify.outcome`**",
        "**`covered: <pinnedBy>`**", "not counted as fixed-here and never goes to the delta pass",
        "\"cold-lens miss, caught by the pin\"", "**`fixed-here`**",
        "**shown failing against the pre-change tree**", "`pinFixedBy`", "`pinFixEvidence`",
        "**`filed-as #NN`**", "**The delta pass sees code locations only.**",
        "never as its `input` or `expected` text",
        "**It checks only whether the pin or fix introduced a regression**",
        "resolution is proven by `verify.pinFixEvidence` and the pin's passing run at G11"),
    "review-focus-tier": (
        "**Tier S and route skips.**", "**at most two** entries", "`source: \"sc-tdd\"`",
        "listed in the G4 report", "or `[]` when it checked and found none", "the field stays **absent**",
        "the skip path still pins them", "a logic entry grows sc-tdd to `run`", "no compare step",
        "blind pass and the designer lens still run", "entries keep `cold: null`", "\"not compared\"",
        "sc-retro skips them"),
    "review-focus-record": (
        "`id`, `input`, `impliedBy`, `uncovered`, `expected`", "`source`", "`superseded`", "`pinnedBy`",
        "`cold` and `verify`", "sc-tdd", "sc-review", "sc-ship G11", "`verify.pinFixedBy`", "sc-retro",
        "which misses the pin caught", "superseded entries as evidence of the earlier design's misses",
        "The list sets no gate value of its own"),
}
# Wording that would hand the cold lens the list early, add an approval round, accept a class as an entry or
# count a pin-caught miss as a fix.
RF_FORBIDDEN = ("receives the list before its blind pass", "a separate approval round for the review focus",
                "a generic edge class is an entry", "the frozen list may be edited",
                "is dispositioned `fixed-here` citing its `pinnedBy`",
                "listed in the sc-review lenses' brief")
RF_ENTRY_KEYS = ("id", "input", "impliedBy", "uncovered", "expected", "source", "superseded", "pinnedBy",
                 "cold", "verify")
RF_COLD_KEYS = ("raised", "finding", "pinHolds", "evidence", "tree")
RF_VERIFY_KEYS = ("by", "model", "effort", "outcome", "evidence", "pinFixedBy", "pinFixEvidence")
# (skill, section heading or None for the whole file, tokens) — every producer and consumer (#90).
RF_SKILL_TOKENS = (
    ("sc-design", "Design (architect", (
        "`state.reviewFocus[]`", "at most five", "ranked by likelihood × harm", "never a generic edge class",
        "never a restated acceptance criterion", "`[]` means checked and found none",
        "no separate approval round", "append- or annotate-only", "docs/review-focus.md")),
    ("sc-design", "Design review (critic)", (
        "names a generic class", "restates a criterion", "an `uncovered`",
        "`n/a` is only for a layout, copy or config item", "likelier input the list left off")),
    ("sc-design", "Gate G2/G3", ("`state.reviewFocus` is written",)),
    ("sc-tdd", "sc-tdd", (
        "The skip path still pins any `state.reviewFocus` entries",
        "a logic entry grows this stage to `run`")),
    ("sc-tdd", "Pin the review focus", (
        "`state.reviewFocus`", "`pinnedBy: \"<test id>\"`", "`pinnedBy: \"n/a: <reason>\"`",
        "only for a layout, copy or config item", "a logic entry always needs a failing-first test",
        "same `id`", "at most two entries", "`source: \"sc-tdd\"`", "record `[]`",
        "the field stays absent")),
    ("sc-tdd", "Gate G4", (
        "every non-superseded `state.reviewFocus` entry has its `pinnedBy`",
        "G4 does not pass with an entry unpinned")),
    ("sc-review", "Lenses", (
        "the list is never in the cold lens's blind-pass brief", "fresh agent with no prior compare",
        "frozen verbatim into the review artifact first", "only then does it receive the list",
        "`postList: true`", "docs/review-focus.md")),
    ("sc-review", "Triage", (
        "**Review-focus items are verified after the compare.**", "`raised: false`", "`pinHolds: false`",
        "never waits for their brief", "scoped second pass of a spec-anchored lens", "at `high` effort",
        "on the same model and effort that lens ran with at G8", "`verify.evidence`", "`covered: <pinnedBy>`",
        "not fixed-here",
        "never sent to the delta pass", "fixed-here / filed-as `#NN`", "`verify.pinFixedBy`")),
    ("sc-review", "Re-review after fixes", ("Review-focus items reach it as code locations only",
                                            "never an entry's `input` or `expected` text",
                                            "checks only whether the pin or fix introduced a regression")),
    ("sc-review", "Gate G8", ("missed or uncovered `state.reviewFocus` entry has a `verify` outcome",
                              "`pinFixedBy`", "taken after the frozen blind pass")),
    ("sc-ship", "Verify (G11)", ("**Review focus.**", "`state.reviewFocus`", "`pinnedBy`", "`cold.pinHolds`",
                                 "`verify.pinFixedBy`", "`pinFixEvidence`")),
    ("sc-retro", None, ("`state.reviewFocus`", "\"cold-lens miss, caught by the pin\"", "`cold: null`",
                        "evidence of the earlier design's misses")),
)


def check_review_focus(root: Path, f: Findings) -> None:
    """#90: sc-design names the per-feature inputs no test covers; G4 pins them; the cold lens checks them
    only after its blind pass is frozen, and what it missed reaches G8 as items to verify.

    Guards the doc's blocks (freeze before compare, in that order), every producer and consumer section, the
    orchestrator's G4 row, the runtime-adapter two-pass note and the state shape's entry and `cold` keys.
    """
    doc = root / RF_DOC
    where = shown(RF_DOC)
    if not doc.is_file():
        f.error(where, "missing")
        return
    text = read(doc)
    for marker, tokens in RF_BLOCK_TOKENS.items():
        m = re.search(rf"<!-- {marker} -->(.*?)<!-- /{marker} -->", text, re.S)
        if not m:
            f.error(where, f"no <!-- {marker} --> block")
            continue
        body = _flat(m.group(1))
        for token in tokens:
            if token not in body:
                f.error(where, f"{marker} block does not state {token!r}")
    cm = re.search(r"<!-- review-focus-cold -->(.*?)<!-- /review-focus-cold -->", text, re.S)
    body = cm.group(1) if cm else ""
    order = [body.find(t) for t in ("1. **Freeze.**", "2. **Compare.**", "3. **Record**", "4. **Verify**")]
    if all(i >= 0 for i in order) and order != sorted(order):
        f.error(where, "review-focus-cold does not freeze the blind pass before the compare")
    flat = _flat(text)
    for token in RF_FORBIDDEN:
        if token in flat:
            f.error(where, f"states {token!r} — the cold lens gets the list only after its frozen blind pass")
    for skill, heading, tokens in RF_SKILL_TOKENS:
        path = root / SKILLS_DIR / skill / "SKILL.md"
        swhere = f"skills/{skill}/SKILL.md"
        raw = read(path) if path.is_file() else ""
        if heading == skill:  # the intro before the first "## " heading (sc-tdd's Route first)
            raw = raw.split("\n## ", 1)[0]
        elif heading:
            raw = _section(raw, heading)
        sec = _flat(raw)
        label = f"'## {heading}'" if heading and heading != skill else "the skill"
        for token in tokens:
            if _flat(token) not in sec:
                f.error(swhere, f"{label} does not state {_flat(token)!r} (review focus)")
    orch = root / SKILLS_DIR / "ship-cycle" / "SKILL.md"
    otext = read(orch) if orch.is_file() else ""
    row = re.search(r"^\| G4 \|(.*)$", otext, re.M)
    if not row or "`state.reviewFocus` entry pinned" not in row.group(1):
        f.error("skills/ship-cycle/SKILL.md",
                "gate table's G4 row does not require every reviewFocus entry pinned")
    ra = root / "docs" / "runtime-adapters.md"
    if ra.is_file() and "docs/review-focus.md" not in read(ra):
        f.error("docs/runtime-adapters.md", "two-pass note does not cover the review-focus compare")
    shape_path = root / STATE_SHAPE_DOC
    shape_text = read(shape_path) if shape_path.is_file() else ""
    blocks = re.findall(r"```json\n(.*?)\n```", shape_text, re.S)
    try:
        shape = json.loads(blocks[0]) if blocks else {}
    except json.JSONDecodeError:
        shape = {}  # reported by state_shape_fields
    entries = shape.get("reviewFocus")
    if not isinstance(entries, list) or not entries or not isinstance(entries[0], dict):
        f.error(shown(STATE_SHAPE_DOC), "state shape has no reviewFocus entry")
    else:
        for key in RF_ENTRY_KEYS:
            if key not in entries[0]:
                f.error(shown(STATE_SHAPE_DOC), f"reviewFocus entry lacks '{key}'")
        for sub, keys in (("cold", RF_COLD_KEYS), ("verify", RF_VERIFY_KEYS)):
            val = entries[0].get(sub)
            if not isinstance(val, dict) or not all(k in val for k in keys):
                f.error(shown(STATE_SHAPE_DOC), f"reviewFocus.{sub} lacks one of {', '.join(keys)}")


UV_DOC = Path("docs/unverifiable-from-diff.md")
# Each marker block in docs/unverifiable-from-diff.md and the tokens it must state (#91).
UV_BLOCK_TOKENS = {
    "unverifiable-bucket": (
        "`unverifiable-from-diff[]`", "the G8 cold lens", "the delta pass", "the wave check's two passes",
        "one term for all of them", "`{item, where, needs, whyNotChecked}`", "`where` — the `path:line`",
        "never code in the repo, which the reader may read itself", "a closed value: `spec-only`",
        "`spans-tasks`", "`needs-running-system`", "Any other value is not an item",
        "**Not a parking lot.**", "docs/claim-evidence.md", "raises a finding or nothing",
        "**not a licence to read the spec**", "no disposition is ever sent back into its context",
        "**not a finding**", "carries no severity", "does not change the lens's verdict",
        "**Frozen with the findings.**", "frozen verbatim together with its findings",
        "before the review-focus list is sent", "the wave check's cold pass before the spec is sent",
        "`postList: true`", "may add items but never settles one"),
    "unverifiable-disposition": (
        "**Dispositioned before G8.**", "**the orchestrator in triage at `high` effort**",
        "**scoped pass of a spec-anchored lens**",
        "**on the same model and effort that lens ran with at G8**", "risk upgrade included",
        "docs/review-focus.md", "opens the cited evidence itself", "ride on `loops[G8]`",
        "**`confirmed → finding #<n>`**", "gets its refuter", "data-integrity and security floors apply",
        "**`cleared: <cited reason>`**", "Clearing is a load-bearing claim",
        "An uncited clearing is no clearing", "**`owner-decision: <the owner's words>`**",
        "**only when `state.route.ownerPresent === true`**", "quoted verbatim",
        "as a human user turn in its own conversation", "docs/visual-check.md",
        "`disposition.by` is `\"owner\"`", "**Before asking**",
        "falls under the data-integrity or security floor",
        "\"treated as High until shown otherwise\"", "**No owner fails closed.**",
        "a floor item keeps G8 blocked", "`manual-gate: <why no owner>`", "pre-merge manual gate",
        "**A parked item is a lens miss.**", "could have been read from the repo",
        "`confirmed` at the severity the gap implies", "`parked: true`", "sc-retro counts it as parked",
        "**One disposition per gap.**", "same `where`, `needs` **and `tree`**", "`sameAs: \"UV<n>\"`",
        "On a different tree the later item gets its own disposition",
        "not inherited without re-citing its evidence on the later tree",
        "**no lower than its floor severity**", "at least High", "the rationale in `disposition.evidence`",
        "Lowering it later needs a refuter's evidence",
        "on any nature it may grow from `false` or absent to `true` here",
        "**only by actually asking the owner**",
        "the loop-cap rule applies: stop, park, ask the user",
        "asking them grows `ownerPresent` on any nature",
        "**Never silently dropped, never auto-promoted.**",
        "**G8 does not pass while any item has no disposition**",
        "at the loop cap an item still open goes to the owner", "still cleared with its evidence"),
    "unverifiable-record": (
        "`state.unverifiable`", "`id` (`UV1`", "`source` (`cold`, `delta` or `wave:<N>`)", "`tree`",
        "`postList`", "`sameAs`",
        "`disposition` (`null` until settled) = `{by, model, effort, outcome, evidence, parked}`",
        "review artifact", "sc-review", "sc-ship", "G11 re-asserts", "**Unverifiable** line",
        "`manual-gate` items are on the pre-merge manual gate", "sc-retro",
        "\"what blind lenses couldn't see\"", "which were parked", "It sets no gate value of its own"),
}
# Wording that would let the bucket unblind the cold lens, give an item a severity, let it lapse, take an
# owner decision without the owner, or bring back the old wave-check term.
UV_FORBIDDEN = ("the cold lens may read the spec to settle", "an item is a finding", "items may be dropped",
                "auto-promoted to a finding", "cannot-verify item", "owner-decision without the owner",
                "a requirement that lives in unchanged code", "unchanged code,")
UV_FORBIDDEN_FILES = (UV_DOC, Path("docs/wave-check.md"), Path("docs/claim-evidence.md"), STATE_SHAPE_DOC,
                      Path("skills/sc-review/SKILL.md"), Path("skills/sc-ship/SKILL.md"),
                      Path("skills/sc-implement/SKILL.md"), Path("skills/ship-cycle/SKILL.md"))
UV_ENTRY_KEYS = ("id", "source", "tree", "item", "where", "needs", "whyNotChecked", "postList", "sameAs",
                 "disposition")
UV_DISPOSITION_KEYS = ("by", "model", "effort", "outcome", "evidence", "parked")
UV_WHY_VALUES = {"spec-only", "spans-tasks", "needs-running-system"}
# (file, section heading or None for the whole file, tokens) — every producer and consumer (#91).
UV_FILE_TOKENS = (
    ("skills/sc-review/SKILL.md", "Lenses", (
        "`unverifiable-from-diff[]` items (`{item, where, needs, whyNotChecked}`), not as findings",
        "not a licence to read the spec", "docs/unverifiable-from-diff.md",
        "Its items are frozen with its findings, before the review-focus list is sent",
        "items it adds after are `postList: true`")),
    ("skills/sc-review/SKILL.md", "Output & severity discipline", (
        "**Unverifiable from diff** (blind readers only",
        "the G8 cold lens, the delta pass and the wave check's two passes", "no severity",
        "never a finding until a disposition confirms it",
        "`spec-only`, `spans-tasks` or `needs-running-system`", "not parked here")),
    ("skills/sc-review/SKILL.md", "Triage", (
        "**Unverifiable-from-diff items are dispositioned before G8.**", "`state.unverifiable`",
        "at `high` effort", "on the same model and effort as that lens at G8",
        "`confirmed → finding #<n>`", "`cleared: <cited reason>`", "`owner-decision: <the owner's words>`",
        "only with `state.route.ownerPresent === true`", "verbatim as a human user turn",
        "\"treated as High until shown otherwise\"", "no owner fails closed", "a floor item blocks G8",
        "`manual-gate`", "is a lens miss", "`parked: true`", "`loops[G8]`",
        "Never silently dropped, never auto-promoted",
        "no disposition goes back into the cold lens's context")),
    ("skills/sc-review/SKILL.md", "Re-review after fixes", (
        "unverifiable-from-diff items (`source: \"delta\"`)", "dispositioned before G8 is re-judged")),
    ("skills/sc-review/SKILL.md", "Gate G8", ("**Every `state.unverifiable` item has a `disposition`**",
                                             "one without fails G8",
                                             "a floor item with no owner answer keeps G8 blocked")),
    ("skills/sc-implement/SKILL.md", "Large cross-cutting change", (
        "`state.unverifiable` (`source: \"wave:<N>\"`)",)),
    ("skills/sc-ship/SKILL.md", "Verify (G11)", ("**Unverifiable from diff.**", "`state.unverifiable`",
                                                 "has a `disposition`", "loops back to sc-review",
                                                 "an undispositioned item is a dropped one",
                                                 "`ownerPresent === true`", "found as a user turn",
                                                 "a `manual-gate` item goes on the pre-merge manual gate")),
    ("skills/sc-ship/SKILL.md", "PR (G12)", ("one **Unverifiable**", "counts by outcome", "`manual-gate`",
                                             "every `owner-decision` in the owner's words",
                                             "Every `state.unverifiable` item whose outcome is "
                                             "`manual-gate` goes here as its own entry",
                                             "`item`, `where`, `needs` and the check a reviewer runs")),
    ("skills/ship-cycle/SKILL.md", "Route plan", ("Non-UI natures may set it later by asking",
                                                 "docs/unverifiable-from-diff.md")),
    ("skills/sc-retro/SKILL.md", "Dimensions", ("`state.unverifiable`", "\"what blind lenses couldn't see\"",
                                                "items `confirmed`", "items `parked`",
                                                "where a cleared item pointed")),
    ("docs/wave-check.md", None, ("unverifiable-from-diff items, not passes",
                                  "docs/unverifiable-from-diff.md",
                                  "its unverifiable-from-diff items are frozen with them",
                                  "It may add items, never settle the cold pass's",
                                  "`state.unverifiable` with `source: \"wave:<N>\"`",
                                  "not carried in `unresolved`")),
    ("docs/claim-evidence.md", None, ("**An unverifiable-from-diff item is not an unevidenced claim.**",
                                      "docs/unverifiable-from-diff.md", "never auto-promoted")),
    ("docs/state-file.md", None, ("**Older state:**", "keeps that path", "not migrated into",
                                  "not counted twice")),
)


def check_unverifiable(root: Path, f: Findings) -> None:
    """#91: a reader's third bucket -- doubts it could not settle -- dispositioned with evidence before G8.

    Guards the doc's bucket, disposition and record blocks; that the cold lens, delta pass and wave check
    produce the one bucket (the old "cannot-verify" term gone, frozen with the findings), claim-evidence
    reconciles it, an owner decision needs a present owner, G8 and the orchestrator's G8 row require every
    item dispositioned, sc-ship and sc-retro read it, and the state shape carries the entry and
    disposition keys with a closed `whyNotChecked`.
    """
    doc = root / UV_DOC
    where = shown(UV_DOC)
    if not doc.is_file():
        f.error(where, "missing")
        return
    text = read(doc)
    for marker, tokens in UV_BLOCK_TOKENS.items():
        m = re.search(rf"<!-- {marker} -->(.*?)<!-- /{marker} -->", text, re.S)
        if not m:
            f.error(where, f"no <!-- {marker} --> block")
            continue
        body = _flat(m.group(1))
        for token in tokens:
            if token not in body:
                f.error(where, f"{marker} block does not state {token!r}")
    for rel in UV_FORBIDDEN_FILES:
        path = root / rel
        flat = _flat(read(path)) if path.is_file() else ""
        for token in UV_FORBIDDEN:
            if token in flat:
                f.error(shown(rel), f"states {token!r} — an unverifiable item is not a finding, is never "
                                    "dropped, and is not settled from the spec by the blind lens")
    for rel, heading, tokens in UV_FILE_TOKENS:
        path = root / rel
        raw = read(path) if path.is_file() else ""
        if heading:
            raw = _section(raw, heading)
        sec = _flat(raw)
        label = f"'## {heading}'" if heading else "the file"
        for token in tokens:
            if _flat(token) not in sec:
                f.error(rel, f"{label} does not state {_flat(token)!r} (unverifiable from diff)")
    orch = root / SKILLS_DIR / "ship-cycle" / "SKILL.md"
    otext = read(orch) if orch.is_file() else ""
    row = re.search(r"^\| G8 \|(.*)$", otext, re.M)
    if not row or "every `state.unverifiable` item dispositioned" not in row.group(1):
        f.error("skills/ship-cycle/SKILL.md",
                "gate table's G8 row does not require every unverifiable item dispositioned")
    shape_path = root / STATE_SHAPE_DOC
    shape_text = read(shape_path) if shape_path.is_file() else ""
    blocks = re.findall(r"```json\n(.*?)\n```", shape_text, re.S)
    try:
        shape = json.loads(blocks[0]) if blocks else {}
    except json.JSONDecodeError:
        shape = {}  # reported by state_shape_fields
    entries = shape.get("unverifiable")
    if not isinstance(entries, list) or not entries or not isinstance(entries[0], dict):
        f.error(shown(STATE_SHAPE_DOC), "state shape has no unverifiable entry")
        return
    for key in UV_ENTRY_KEYS:
        if key not in entries[0]:
            f.error(shown(STATE_SHAPE_DOC), f"unverifiable entry lacks '{key}'")
    why = {v.strip() for v in str(entries[0].get("whyNotChecked", "")).split("|")}
    if why != UV_WHY_VALUES:
        f.error(shown(STATE_SHAPE_DOC), "unverifiable.whyNotChecked is not the closed set "
                                        + " | ".join(sorted(UV_WHY_VALUES)))
    disp = entries[0].get("disposition")
    if not isinstance(disp, dict) or not all(k in disp for k in UV_DISPOSITION_KEYS):
        f.error(shown(STATE_SHAPE_DOC),
                f"unverifiable.disposition lacks one of {', '.join(UV_DISPOSITION_KEYS)}")

def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path(__file__).resolve().parent.parent
    f = Findings()

    check_doc_references(root, f)
    check_state_producers_consumers(root, f)
    check_gate_coverage(root, f)
    check_stage_vocabulary(root, f)
    check_manifests_and_versions(root, f)
    check_gate_summary(root, f)
    check_entry_path_inventory(root, f)
    check_claim_evidence(root, f)
    check_skill_frontmatter(root, f)
    check_example_coverage(root, f)
    check_example_release_smoke(root, f)
    check_release_checklist(root, f)
    check_heavy_work(root, f)
    check_route_plan(root, f)
    check_visual_check(root, f)
    check_retro(root, f)
    check_evals(root, f)
    check_session_hook(root, f)
    check_impl_status(root, f)
    check_wave_check(root, f)
    check_red_gate(root, f)
    check_review_focus(root, f)
    check_unverifiable(root, f)

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
    if hasattr(sys.stdout, "reconfigure"):  # Windows consoles default to cp1252
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv))
