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
| heavy-job lock | `flock` / `mkdir` on `env.heavyLock` (see `heavy-work.md`) | same; use a workspace or `$TMPDIR` path if `/tmp` is sandboxed |
| cycle state | `.claude/ship-cycle/<branch-slug>.json` | `.codex/ship-cycle/<branch-slug>.json` *(intent — see §Known gaps)* |
| design-tool adapter (`visualCheck.designTool`) | an installed design skill hooked into UI stages (`visual-check.md`) | not wired: the plain fallbacks apply |
| session-start reminder (#86) | `hooks/hooks.json` → `SessionStart` (`startup\|clear\|compact`) runs `hooks/session-start.cjs` | not wired by the plugin — see §Session-start hook |
| host transcript (read by `sc-retro`) | search `~/.claude/projects/*/<session-id>.jsonl` (the cwd slug can change on a directory rename), subagents in `<session-id>/subagents/` | `~/.codex/sessions/<YYYY>/<MM>/<DD>/rollout-<time>-<id>.jsonl` (under `$CODEX_HOME` if set) |

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

## Session-start hook

A long cycle crosses a compaction or a `/clear`, and the state-file discipline
(§`${CLAUDE_PLUGIN_ROOT}/docs/state-file.md`) breaks silently there: the new context does not know a cycle
is mid-flight. The hook restates the facts so the session reads the state file instead of guessing.

**What it does.** On `SessionStart` with source `startup`, `clear` or `compact`, `hooks/session-start.cjs`
takes the session's working directory from the `cwd` field of the hook's stdin JSON (a bounded read of at
most 64 KiB, skipped when stdin is a terminal and under `--host codex`; the value must be an absolute,
existing directory and not UNC-style) and falls back to its own working directory. The read **relies on
the host closing stdin or completing the JSON value**: it stops at the first chunk that parses, so a host
that writes the JSON and keeps the pipe open does not stall it, but a host that writes nothing and never
closes stdin would hold it until the hook's 5 s timeout. From there it finds the repo top, reads the branch
from the HEAD file (a `.git` directory, or a worktree's `.git` file and its `gitdir:`; no `git` process),
derives the slug exactly as (§`${CLAUDE_PLUGIN_ROOT}/docs/state-file.md` — The slug) does, and reads
`.claude/ship-cycle/<slug>.json` under the repo top. When the stage is mid-pipeline or `parked`, it prints
three lines:

```text
ship-cycle: active cycle on branch `feat/x` - stage sc-review, next gate G8, loops G8=1/3.
State: .claude/ship-cycle/feat-x.json (gate log beside it).
Run /ship-cycle-devkit:resume's reconcile before acting.
```

A parked file says ``parked cycle on branch `<branch>` since <date> - resume stage <s>, next gate <G>`` and
that the park reason is in the file. The next gate is the first gate of the stage (from the pipeline table in
`${CLAUDE_PLUGIN_ROOT}/skills/ship-cycle/SKILL.md`, which the script mirrors and `scripts/validate.py`
compares) not yet recorded — `pass`, `checklist`, `degrade` and any `n/a…` count as recorded, and `G2`, `G3`
or `G2/G3` covers the one design gate. When every gate of the stage is recorded it says
`stage gates recorded - advance per the pipeline` instead. Loops show each recorded count against the loop cap.

**Silent** for: no repo, detached HEAD, no state file, a terminal or unknown stage, malformed or oversized
JSON, a file whose `branch` names another branch (§state-file.md — Collision guard), and any error at all —
it always exits 0 and writes nothing but the context. **It is built not to stall a session start**: `.git`, a
worktree's `.git` file, HEAD and the state file are read only when they are regular files under a size
cap (4 KiB; 1 MiB for the state), so a FIFO or device is never opened; UNC-style `gitdir:` and stdin `cwd`
values (`\\…` or `//…`) are not followed; stdin is read as above; and an error other than "not found"
while looking for `.git` (a symlink loop, a permission error) stops the search instead of walking
further up. A mounted network drive under an ordinary path is still read like any directory.

**Nothing from the repo reaches the model as free text.** The state file and the branch name can be written by
anyone with repo access, so the hook prints only whitelisted values: stage names and `G<n>` keys from fixed
vocabularies, integer counts, an ISO date, and the branch only when it matches `^[A-Za-z0-9._/-]{1,80}$` — and
then as quoted data, ``on branch `<branch>` ``. A branch outside that set is not printed, and neither is the
state path built from it — the lines say `(state file for the current branch)` and `the state file beside the
gate log in .claude/ship-cycle/`. `goal`, `parked.reason` and gate `n/a` reasons are never echoed. A branch
name inside the whitelist is still the user's own text — it can spell words, never sentences with spaces or
punctuation beyond `._/-`.

**Output form.** Claude Code gets `{"hookSpecificOutput": {"hookEventName": "SessionStart",
"additionalContext": "…"}}`, ASCII-escaped — the form superpowers' `hooks/session-start` emits for Claude
Code, and the one a live `claude --plugin-dir` session was observed to receive as context. Only that one
form is emitted; superpowers' own comment is the reason it emits a single field per host.

**Runtime: Node.** The script is one dependency-free CommonJS file run as
`node "${CLAUDE_PLUGIN_ROOT}/hooks/session-start.cjs"`. Node starts in ~30 ms with no shell fork, behaves
the same on Linux, macOS and Windows, and is present wherever Claude Code was installed through npm. A
POSIX-sh version would need Git Bash on Windows and a `.cmd` polyglot launcher (what superpowers ships)
plus JSON escaping by hand. The cost of the choice: a Claude Code install without `node` on PATH (the
native installer does not need one) gets a non-blocking "hook error" line at session start.

**Opt-out.** Set `SHIP_CYCLE_HOOK=off` (also `0`, `false`, `no`, `disabled`) in the environment or in the
`env` block of `.claude/settings.json` / `~/.claude/settings.json`; the script then exits silently. That
switch is read by the script, so it **cannot** silence the spawn error when `node` itself is missing —
there, `"disableAllHooks": true` in settings (every hook, this one included) or disabling the plugin is
the way out.

**Registration.** `hooks/hooks.json` sits at the plugin root and the manifest does not name it: a live
`claude --plugin-dir` session ran it that way, and superpowers and oh-my-claudecode ship their hooks the
same way. The validator keeps that single registration path (it refuses a `hooks` key in the manifest).

**Codex — known gap.** The Codex manifest declares no hooks, so nothing runs there by default. The script
has a Codex mode (`--host codex`: reads `.codex/ship-cycle/`, prints plain text), and a user who wires a
`SessionStart` command hook in their Codex hooks config to
`node <plugin dir>/hooks/session-start.cjs --host codex` gets the same lines. That wiring, Codex's matcher
values and whether its plain stdout becomes model context are **not verified** against a real Codex
install; until they are, a Codex session after compaction relies on the orchestrator's own resume path
(§`${CLAUDE_PLUGIN_ROOT}/docs/state-file.md` — Resume and selection).

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
