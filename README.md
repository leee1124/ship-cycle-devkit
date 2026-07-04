# Ship-Cycle DevKit

A portable [Claude Code](https://code.claude.com) plugin that drives a single goal through a
**gated development lifecycle** — requirements → design → review → test → implement → verify → PR —
enforcing an engineering constitution at each gate, with **risk-based model routing** for token
efficiency.

It is **framework-agnostic**: everything project-specific (monorepo paths, test commands, VCS repo,
i18n layout) lives in a small per-project overlay config. The plugin has **no external dependency** —
it runs on stock Claude Code with the `Task` tool, and opportunistically uses specialized subagent
types if your environment provides them.

## What's inside

| Component | Path | Purpose |
|---|---|---|
| `ship-cycle` skill | `skills/ship-cycle/SKILL.md` | The gated lifecycle state machine + model routing |
| Engineering constitution | `docs/engineering-constitution.md` | The rules the gates enforce (SOLID/OWASP/DDD/TDD/…) |
| Implementation prompt templates | `prompts/impl-{backend,web,mobile}.md` | Stack-specific implementation-agent prompts (adapt to your stack) |
| Overlay config example | `docs/ship-cycle.config.example.json` | The per-project schema |

## Install

```bash
# add this repo as a marketplace, then install
claude plugin marketplace add leee1124/ship-cycle-devkit
claude plugin install ship-cycle-devkit

# team-shared (recorded in the project's .claude/settings.json):
claude plugin install ship-cycle-devkit --scope project
```

Local development / trial without installing:

```bash
claude --plugin-dir /path/to/ship-cycle-devkit
claude plugin validate /path/to/ship-cycle-devkit
```

## Use

Trigger the skill on any goal:

```
/ship-cycle:ship-cycle  add rate limiting to the login endpoint
```
(or say "ship it" / "run the lifecycle" for `{goal}`)

## Project overlay (make it yours)

Copy the example into your repo and edit it — this is the only project-specific file:

```bash
cp docs/ship-cycle.config.example.json <your-repo>/.claude/ship-cycle.config.json
```

It supplies:
- **`vcs`** — provider, `repo`, `defaultBase`, protected branches, optional issue tracker/board.
- **`changeNature`** — path globs → nature, with the `tests`/`build` commands and `reviews` lenses to
  run. This is what routes a `.java` change to JUnit + a security review, a `.tsx` change to Playwright
  + a designer review, etc.
- **`i18n`** — optional path to an i18n-parity config (the i18n hook ships separately).
- **`modelRouting`** — optional overrides of the base pyramid / risk-gated upgrades.

If the overlay is absent, ship-cycle falls back to built-in heuristics and logs that defaults are used.

## Model routing (token efficiency)

Models are assigned by **cost-of-being-wrong × cost-of-verification**, not by role name:

- **Base pyramid**: *high* tier on design & security/quality review, *mid* on implementation/QA,
  *low* on docs/style/plumbing. (~30% cheaper than "everything on the top model" while keeping review
  quality.)
- **Risk-gated upgrade**: only high-risk changes (auth/payment, schema migration, public API contract,
  complex algorithm) bump the *single matching role* to the top tier — matched to the *kind* of risk,
  not always the same role.
- **Bigger levers than tier choice**: prompt caching, an effort dial, and "cheap path first" for
  implementation.

Tier names (top/high/mid/low) map onto whatever model lineup your environment offers.

## Prior art & inspiration

The Claude Code lifecycle/skill space is well populated — see
[Superpowers](https://blog.marcnuri.com/superpowers-claude-code-skills-framework) (Jesse Vincent) and
[claude-code-workflows](https://github.com/shinpr/claude-code-workflows). This kit borrows two of
Superpowers' best patterns: **Iron Laws + Red Flags** (non-negotiable rules with a pre-empted list of
the excuses agents use to skip them) and a **discovery gate** (refuse to code a vague goal).

Where it differs: a **change-nature routing overlay** (one config maps paths → test/review lenses) and
**risk-based model routing** — assigning model tiers by cost-of-being-wrong, with a token-cost rationale
baked into the skill. If you want a mature, batteries-included framework, use Superpowers; this is a
leaner, cost-aware, overlay-driven take.

## License

MIT — see [LICENSE](LICENSE).
