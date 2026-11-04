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
GATE_SET_RE = re.compile(r"gates\.((?:G\d+[a-z]?)(?:/G\d+[a-z]?)*)")
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



# --- entry point -------------------------------------------------------------------------------


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
