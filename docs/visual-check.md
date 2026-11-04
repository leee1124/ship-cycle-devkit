# Visual check — the live loop, visual evidence and the accessibility floor (UI natures)

The gates are shaped for logic: a failing test, then green, then a baseline diff. For UI work the meaningful
evidence of *appearance* is the owner looking at the running app on the device they judge on. This file
states that rule once; sc-implement, sc-design, sc-review, sc-qa and sc-ship point here. Tables and JSON
one-liners here are exempt from the 110-column prose limit.

A **UI nature** is one whose overlay `changeNature[]` entry declares `visualCheck` (schema:
`${CLAUDE_PLUGIN_ROOT}/docs/ship-cycle.config.schema.json`), or one reviewed by `designer` without it. The
latter runs the loop with the project's ordinary run command and the **default profile list**: the
platform's common phone (or desktop viewport) at font scale 1.0 and at the largest scale, light and dark.

**Who writes `state.visualCheck[<nature>]`**: sc-implement, for every nature in `state.nature` — the loop
outcome for a UI nature, `"n/a"` for any other. Only the **top-level session that talks to the user** may
write `owner-confirmed`, and only when `state.route.ownerPresent` is not `false`; a subagent writes
`agent-captured` at most. With `ownerPresent: false`, an `owner-confirmed` entry is invalid and G11
rejects it.

<!-- visual-loop-rule -->
## Live visual loop (inside sc-implement)

1. **Launch the live app, not a release build.** Hot reload needs a dev/debug client connected to the dev
   server; a release-form build installed on the device cannot reload, so build and install the debug
   client first (`visualCheck.devBuild`) when it is not already on the device. That build is heavy work
   (`${CLAUDE_PLUGIN_ROOT}/docs/heavy-work.md`), under `env.heavyLock`. On a small host the sequence is
   **build → start emulator → loop**: the emulator stays stopped while the build runs.
2. **Show it on the target profile.** Use the first entry of `visualCheck.profiles` — the owner's own
   device profile (resolution, density, font scale, theme) — and name it to the owner. **Before changing a
   device setting** to reach a profile, read and record its prior value in
   `state.visualCheck[<nature>].deviceRestore` (e.g. `settings get system font_scale`, `wm size`,
   `wm density`); when the loop ends — and on abort — put those recorded values back
   (`visualCheck.restore` names the commands).
3. **Ask in plain words what to look at**: the screen, how to reach the state, the one thing that changed,
   the accessibility-floor checks below. Not "does it look good?".
4. **Iterate without re-entering sc-review — before the first sc-review only.** A tweak is
   presentation-only — styles, layout, copy, tokens, assets — hot-reloaded and shown again; it is not a
   review round and not a `loops` entry. **Any behaviour, state, data or navigation change goes back to
   sc-tdd (Red first).** After the first sc-review has run, every edit — a tweak during a re-show, or
   during G9/G11 — goes through sc-review's delta re-review and G5–G7, and counts against the loop cap.
5. **Vague feedback → show, don't ask.** When the owner cannot say what is wrong ("it feels like a log"),
   do not answer with an abstract multiple-choice question: build 2–3 alternative prototypes rendered side
   by side on the running app, below the current version, each labelled `variant A` / `B` / `C`. They are
   temporary and uncommitted. The owner picks one or mixes; productionize only the chosen one and delete
   the rest before any commit, review or test.
6. **Prototype cleanup is recorded before G5** in `state.visualCheck[<nature>].cleanup`: a search for the
   variant labels finds nothing, and `git diff --stat` against the pre-loop tree (`preLoopTree`) lists no
   file only a losing variant used. The cold lens checks it at G8.
7. **Settled = the owner said so, in the owner's own words in this run.** Record `result:
   "owner-confirmed"`, the profile(s), what was checked, the owner's words, and the `tree` it was
   confirmed on. Then G5–G7, then sc-review once on the settled result.
<!-- /visual-loop-rule -->

<!-- visual-evidence-rule -->
## Visual evidence (G9, G11)

- **Owner confirmation backs appearance claims only.** "Owner confirmed on `<profile>`: `<what was
  checked>`" is the primary evidence for how the screens look; sc-ship G11 labels it
  **`live (owner-confirmed)`**. Behaviour claims (state, data, navigation) still need a test or a QA log.
  Screenshots are optional — a PR record, not the loop. A screenshot-diff against the base runs only when
  the project declares a harness (`visualCheck.diff`); it is added evidence, never a replacement.
- **No owner present (unattended run).** Fall back to agent capture (`visualCheck.capture`) across every
  profile in the matrix: `result: "agent-captured"`, one capture per profile, written to the state or
  scratch dir (never inside the repo) under a slugified profile name. G11 labels it
  **`review-only (agent-captured)`** and sc-ship lists each profile on the **"Pre-merge manual gate"**.
  No capture command either → `result: "unverified: <reason>"`, same gate item.
- **Stale, defined mechanically.** G11 accepts the entry only if its `tree` equals the final tree, or
  `git diff <tree>..HEAD` restricted to the nature's `match` globs ∪ the declared design paths
  (`design.tokens`, `design.components`, shared theme, i18n) is empty. Otherwise re-show the changed
  screens (an edit then follows step 4's post-review rule) or the entry drops to the manual-gate item above.
- **G9.** sc-qa does not repeat the loop: the confirmation covers the appearance of the screens it names,
  not their behaviour; flows, seams and a release smoke are still QA's.
<!-- /visual-evidence-rule -->

<!-- a11y-floor -->
## Accessibility floor — named checks

**An outcome, not ceremony**: for a UI nature the designer lens (or, at the least, this checklist) is never
dropped — not on the Tier S path, not by a route plan. Each is a pass/fail line in the loop's checklist
(step 3) and in sc-review's `designer` lens:
- **touch target** at or above the platform minimum (44 pt iOS, 48 dp Android, 24 px web);
- **contrast**: text 4.5:1 (3:1 large text), non-text controls and states 3:1, in every theme in the matrix;
- **screen-reader labels/roles**: every control has a label, a role and its state; reading order follows
  the visual order; modals trap focus;
- **largest font scale** in `profiles`: nothing clipped, truncated or overlapping;
- **reduced motion**: with the OS setting on, nothing non-essential animates.
A failed check is a finding; one that blocks use (an unlabelled control, an unreachable target) is High.
<!-- /a11y-floor -->

## Design-tool adapter (optional)

`visualCheck.designTool` names an installed design skill (e.g. *impeccable*). The kit never requires one;
every hook has a plain fallback, and browser-only features degrade on native apps to the live loop. The
adapter is Claude Code only for now; on Codex the fallbacks apply
(`${CLAUDE_PLUGIN_ROOT}/docs/runtime-adapters.md`).

| stage | design-tool hook | fallback |
|---|---|---|
| sc-brainstorm / sc-design | `shape` — UX plan before code, against the design-system doc | designer prompt + `design.guide` |
| sc-implement live loop | `generate` / `live` — variants to choose from (web) | live loop above, labelled prototypes |
| sc-review designer lens | `critique` + `detect` + `audit` (native variant on iOS/Android) | designer-lens anti-patterns |
| sc-ship | `polish` — a final pass on the settled UI | — |

Inside a cycle the tool is used read-only in review (detectors report, they do not write); it never runs
`init` or `document`, never installs a hook, and never writes the design-system doc. Those are project
setup, outside any cycle.
