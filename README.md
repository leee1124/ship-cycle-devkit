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

Composable skills — a thin orchestrator that chains one short skill per stage (each usable à la carte):

| Component | Path | Purpose |
|---|---|---|
| `ship-cycle` (orchestrator) | `skills/ship-cycle/` | PREFLIGHT + worktree + routing + state + gate chaining + model routing + state-file handoff between stages |
| `sc-brainstorm` | `skills/sc-brainstorm/` | Discovery: clarify a vague goal, propose a design, get acceptance |
| `sc-design` | `skills/sc-design/` | Architect design + adversarial critic review |
| `sc-tdd` | `skills/sc-tdd/` | Write failing tests first (Red) |
| `sc-implement` | `skills/sc-implement/` | Green + build, in git worktree isolation (parallel stacks) |
| `sc-review` | `skills/sc-review/` | Multi-lens parallel review (security/quality/perf/algorithm/designer) |
| `sc-qa` | `skills/sc-qa/` | Integration/E2E + front↔back seam contracts |
| `sc-ship` | `skills/sc-ship/` | Docs + evidence verify + PR + branch/worktree cleanup |
| `sc-audit` (à la carte) | `skills/sc-audit/` | Cross-surface parity audit: gap matrix + risks + cutover/ship verdict (not in the default chain) |
| Engineering constitution | `docs/engineering-constitution.md` | The rules the gates enforce (SOLID/OWASP/DDD/TDD/…) |
| Impl prompt templates | `prompts/impl-{backend,web,mobile}.md` | Stack-specific implementation prompts (adapt to your stack) |
| Overlay config + schema | `docs/ship-cycle.config.{example,schema}.json` | The per-project config and its JSON Schema |
| Observability commands | `commands/` | User-invokable `/status` · `/resume` · `/ship` slash commands (read-only by default) |

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
/ship-cycle-devkit:ship-cycle  add rate limiting to the login endpoint
```
(or say "ship it" / "run the lifecycle" for `{goal}`)

### Observability commands

User-invokable slash commands for inspecting or steering an in-flight run (read the cycle's state file at
`.claude/ship-cycle/<branch-slug>.json`, keyed by the current branch — run them from the cycle's own
working directory; they resolve the branch with `git branch --show-current`, which needs **git ≥ 2.22**):

- `/ship-cycle-devkit:status` — print the current stage, gate table (G1–G13), loop counts, **size tier**,
  resolved model **and effort** routing, the **cost so far**, in-flight **review jobs** and any **git-write
  freeze**, and the worktree. Read-only.
- `/ship-cycle-devkit:resume` — resume an interrupted run from its last incomplete stage (doesn't restart
  completed stages).
- `/ship-cycle-devkit:ship` — jump to the ship stage when the required upstream gates (G1–G9) are green;
  refuses if any gate is unmet.

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
- **`audit`** — optional inputs for the à-la-carte `sc-audit` skill: the `sourceOfTruth` contract, the
  consumer `surfaces` checked against it, domain `modules`, and `reportDir`. Omit to derive from `changeNature`.
- **`externalReviewers`** — optional out-of-process review agents (a different model or CLI entirely). A
  `changeNature[].reviews` entry of the form **`external:<name>`** adds one as an **async review job**:
  freeze → snapshot → release → launch → poll → judge on completion, with the cycle free to suspend and
  resume in between. You supply the commands; the kit never hard-codes a vendor. The `external:` prefix is
  what keeps a foreign reviewer an *additional* lens rather than a replacement — it can never occupy a
  built-in lens's slot, so one named `cold` cannot silently retire the in-session cold lens.
- **`modelRouting`** — optional overrides of the base pyramid / risk-gated upgrades.
- **`env`** — optional per-cycle cost knobs for continuous runs: reuse a running dev server, share
  `node_modules` across worktrees, reuse one e2e install. Opt-in; correctness always wins (boots clean
  when a change needs isolation). Sharing `node_modules` links each worktree into one store, so teardown
  **sweeps for links and unlinks before it deletes** (sc-ship G13) — a delete that resolves the link would
  destroy the shared install.

If the overlay is absent, ship-cycle falls back to built-in heuristics and logs that defaults are used.

> **Commands run from the repo root.** `changeNature[].tests`/`build` execute at the repository root, so use
> root-relative forms — `cd apps/api && ./gradlew test`, `npm run test -w apps/web`, `npx tsc --noEmit -p apps/mobile` —
> not a bare `./gradlew` that assumes a subdir cwd. Run the observability commands and stages from **the
> cycle's own working directory** (its worktree if one was created, else the main checkout): the per-branch
> state file lives there and is keyed from that cwd's current branch.
> **Gitignore the run state.** Add the directory `.claude/ship-cycle/` to your `.gitignore` — it holds the
> per-cycle, per-branch run state, not meant to be committed (the overlay config
> `.claude/ship-cycle.config.json` *is*).

## Model routing (token efficiency)

Models are assigned by **cost-of-being-wrong × cost-of-verification**, not by role name:

- **Base pyramid**: *high* tier on design & security/quality review, *mid* on implementation/QA,
  *low* on docs/style/plumbing. (~30% cheaper than "everything on the top model" while keeping review
  quality.)
- **Risk-gated upgrade**: only high-risk changes (auth/payment, schema migration, public API contract,
  complex algorithm) bump the *single matching role* to the top tier — matched to the *kind* of risk,
  not always the same role.
- **Effort is priced on the judgment/mechanics axis, not on stage names.** The two most judgment-dense
  pieces of work answer to no stage's name — **root-cause analysis** and **triage** — so they sit at `high`
  on every change, while setup, discovery, commit/push/PR and running tests sit at `low`. Review effort
  **scales with the size tier** rather than being pinned at the top; the edit inherits the tier.
- **Bigger levers than tier choice**: prompt caching, the effort dial, and "cheap path first" for
  implementation.
- **Enforced, not just documented**: PREFLIGHT pre-resolves each stage's tier into a concrete model
  (`state.models`) and its effort into `state.effort`, and every stage passes both explicitly. Iron Law 6
  forbids spawning on an agent type's default — a specialized type (`quality-reviewer`, …) otherwise
  silently overrides your tier.
- **Measured, not just asserted**: every run ends with a **cost readout** — per-stage tier/model/effort plus
  whatever usage your host exposes, the run total, and which risk upgrades fired. So the efficiency claim
  above is checkable on *your* repo, and `tierMap`/`effortMap` are tunable with data instead of intuition.
  What the host doesn't expose is printed `unavailable`; nothing is estimated.

Tier names (top/high/mid/low) map onto whatever model lineup your environment offers, via `tierMap`;
effort levels (xhigh/high/medium/low) map through `effortMap` the same way.

## Right-sizing & pruning

Two rules that keep the kit from bloating — and from being trimmed into uselessness.

**Size before ceremony.** PREFLIGHT picks a **change-size tier (S/M/L)** up front and records it in state;
every later stage reads it. **Tier S** — a one-liner whose cause is already corroborated by ≥2 independent
code sites — takes no worktree, no verification fleet (bar one refuter on a surviving Critical/High), the
security lens plus one nature-matched lens, and the low tiers. **Tier L** gets the full set. The security
lens is never one of the things a tier drops — it is a fail-closed floor. The tier dials *ceremony* (stage
count, model tier and effort, lens breadth, agent count); it never dials an *outcome*. Re-tiering is
monotonic **upward**: a change that turns out bigger adds the
ceremony back, and never drops a stage it already owes. Root-cause analysis, finding triage and the pre-PR
conflict check are outcomes — they are the cheapest stages in the pipeline and the first a right-sizing
pass reaches for, and cutting them is how you ship a misdiagnosed request confidently.

**"Simplify" means delete what the model already knows — not reduce line count.** Two very different kinds
of rule accumulate in files like these, and a blunt prune deletes the wrong one:

| prunable | load-bearing |
|---|---|
| Restatements of Clean Code / SOLID, "don't swallow exceptions", "use parameterized queries", "prefer meaningful names" — a competent model applies these unprompted | Toolchain absolute paths that aren't on `PATH`, wrapper scripts, runner flags a symlink/junction layout requires, build-artifact rebuild steps, dual-build dependency drift, VCS footguns (`git -C`, never `cd`; stage explicit files, never `-A`; a teardown that follows a `node_modules` junction and wipes the shared store) |

Everything in the right-hand column exists because of an incident that actually happened, and none of it is
inferable from general engineering knowledge. In a framework-agnostic kit the split generalizes cleanly:
**generic principles are prunable; overlay- and environment-supplied facts are load-bearing.** The same
test applies to your own `CLAUDE.md`/`AGENTS.md`.

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
