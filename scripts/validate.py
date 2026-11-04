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
