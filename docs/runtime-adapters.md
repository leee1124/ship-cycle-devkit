# Runtime adapters — the same lifecycle on Claude Code and Codex

The lifecycle is host-neutral: gates, tiers, the bright line, the engineering constitution and every stage
skill say the same thing wherever they run. Four things are not neutral — where bundled files live, how a
subagent is spawned, where config and state go, and how the user invokes it.

This file is the intended single home for that difference. It is not yet the only one: §Known gaps lists
the sites still hardcoded to one host, and `scripts/validate.py` does **not** check the invariant, so it is
a review responsibility until the migration lands.

| concern | Claude Code | Codex |
|---|---|---|
| plugin manifest | `.claude-plugin/plugin.json` | `.codex-plugin/plugin.json` |
| bundled-file root | `${CLAUDE_PLUGIN_ROOT}` | the plugin's install directory, resolved by the host |
| project root | `${CLAUDE_PROJECT_DIR}` | the workspace root |
| spawning a role | the `Task` tool with an agent type | a native subagent |
| invocation | `/ship-cycle-devkit:ship-cycle …`, plus `/status`, `/resume`, `/ship` | the `ship-cycle` skill by name; the three observability commands are **not shipped to Codex** (see §Known gaps) |
| overlay config | `.claude/ship-cycle.config.json` | `.codex/ship-cycle.config.json` *(intent — see §Known gaps)* |
| cycle state | `.claude/ship-cycle/<branch-slug>.json` | `.codex/ship-cycle/<branch-slug>.json` *(intent — see §Known gaps)* |

Everything in the skills that reads `${CLAUDE_PLUGIN_ROOT}/docs/…` means "this kit's own `docs/`
directory"; on Codex, resolve it against the plugin's install directory. Nothing in the lifecycle depends
on the literal variable.

## Roles and independence

The stage skills name roles — architect, critic, security-reviewer, executor, judge lens. A role is **a
separate agent that did not author the thing it is looking at**; which agent type provides it is a host
detail. On Claude Code that is a `Task` spawn, using a specialized type where the environment has one and a
`general-purpose` agent briefed with the role's prompt where it does not. On Codex it is a native subagent,
selected from the active role/model catalog.

Two properties survive the translation or the kit is not running:

- **Reviewer ≠ author** (§core 1). A host that cannot give you a second agent cannot run sc-design's critic,
  sc-review's lenses or sc-qa; it can run everything else.
- **The model and effort are passed explicitly** (§core 6), resolved once at PREFLIGHT into `state.models`
  and `state.effort`. Do not hard-code model identifiers in the overlay or the skills: `modelRouting.tierMap`
  maps tiers to whatever the host's current catalog calls them, which is why it is a per-project setting and
  not a constant in this repo.

## Config and state: one convention, two locations

The **file format, the state shape, the slug rule, the gate values and every semantic are identical**. Only
the parent directory differs, and it follows the host you are running under: Codex reads and writes
`.codex/`, Claude Code reads and writes `.claude/`.

**Precedence when both exist** *(intent — §Known gaps)*. Read the directory for the host you are running
under. If it has no overlay
config and the other does, **read the other's config** — overlay config is project policy, it is
host-neutral, and duplicating it is exactly the "duplicate business-specific overlays" the kit avoids. Log
which file was used, so a surprising route is traceable.

**Cycle state never crosses.** `.claude/ship-cycle/` and `.codex/ship-cycle/` are separate, and a cycle
started under one host is resumed under that host. State points at worktrees, review jobs and artifact paths
created by a specific runtime; adopting another host's half-finished cycle would mean inheriting handles it
cannot use. A cycle interrupted on one host and resumed on the other starts a fresh cycle for that branch —
which the branch and its commits already make safe.

Add **both** `.claude/ship-cycle/` and `.codex/ship-cycle/` to `.gitignore`; the overlay config files are
committed.

## Known gaps (0.3.0)

Stated rather than implied, because the table above describes the intended convention and the kit does not
yet execute all of it:

- **The observability commands are Claude-only.** `commands/{status,resume,ship}.md` are declared by the
  Claude manifest, not the Codex one, and implement themselves with Claude's inline `!`-bash reading a
  hardcoded `.claude/ship-cycle/<slug>.json`. Codex gets the stage skills; it does not get `/status`,
  `/resume` or `/ship`.
- **Config and state resolve to `.claude/` in the skills.** PREFLIGHT Stage 0.3 reads the plugin's
  `projectConfig` setting, which only the Claude manifest declares, and about a dozen sites across the
  skills, the commands and the state-shape doc name `.claude/ship-cycle/` directly. The `.codex/` rows in
  the table and the precedence rule above are **design intent, not yet implemented** — and that rule
  currently disagrees with Stage 0.3, which says an absent config falls back to built-in heuristics rather
  than to the other host's file. Stage 0.3 is what executes today.
- Closing these means resolving the host directory once in PREFLIGHT and naming it `<host-dir>/ship-cycle/`
  everywhere else. That is the remainder of #47's deliverables (3) and (4).

## Keeping the two distributions honest

`scripts/validate.py` is the mechanical half: it checks that both manifests parse and carry their required
fields, that their versions match each other and the newest CHANGELOG heading, and that both point at the
same skills directory. Version drift is the way these distributions come apart most quietly, and it is now
a failed check rather than a discovered surprise. Note the narrowness: comparing the two `skills` strings
catches a hand-edited path, not a divergence in the skill *set* — nothing today can produce that, since
both manifests expose one directory.

What the script deliberately does not check is whether the *lifecycle* means the same thing on both hosts —
that is what keeping host-specific detail confined to this file buys. A change that adds a host-specific
rule to a stage skill is the thing to catch in review.
