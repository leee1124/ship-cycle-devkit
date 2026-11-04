# Visual check — the live loop, visual evidence and the accessibility floor (UI natures)

The gates are shaped for logic: a failing test, then green, then a baseline diff. For UI work the meaningful
evidence is the owner looking at the running app on the device they judge on. This file states that rule
once; sc-implement, sc-design, sc-review, sc-qa and sc-ship point here.

A **UI nature** is one whose overlay `changeNature[]` entry declares `visualCheck` (schema:
`${CLAUDE_PLUGIN_ROOT}/docs/ship-cycle.config.schema.json`). A nature reviewed by `designer` without
`visualCheck` still runs the loop with the project's ordinary run command and names the profile it used.

<!-- visual-loop-rule -->
## Live visual loop (inside sc-implement)

1. **Launch the live app, not a release build.** Hot reload needs a dev/debug client connected to the dev
   server; a release-form build installed on the device cannot reload, so build and install the debug
   client first (`visualCheck.devBuild`) when it is not already on the device. That build is heavy work
   (`${CLAUDE_PLUGIN_ROOT}/docs/heavy-work.md`): run it under `env.heavyLock`, and on a small host stop the
   emulator during it. Then start the dev server (`run`) and open the dev client (`open`) on the
   emulator, device or browser.
2. **Show it on the target profile.** Use the first entry of `visualCheck.profiles` — the owner's own
   device profile (resolution, density, font scale, theme) — and name it to the owner. Settings changed to
   reach a profile (`wm size`, `wm density`, font scale) are put back when the loop ends (`restore`).
3. **Ask in plain words what to look at**: the screen, how to reach the state, the one thing that changed,
   the accessibility-floor checks below. Not "does it look good?".
4. **Iterate on feedback without re-entering sc-review.** A tweak is hot-reloaded and shown again; it is
   not a review round and not a `loops` entry. Tests and build (G5–G7) run once the loop settles.
5. **Vague feedback → show, don't ask.** When the owner cannot say what is wrong ("it feels like a log"),
   do not answer with an abstract multiple-choice question: build 2–3 alternative prototypes rendered side
   by side on the running app, below the current version, each labelled `variant A` / `B` / `C`. They are
   temporary and uncommitted. The owner picks one or mixes; productionize only the chosen one and delete
   the rest — a search for the labels finds nothing — before any commit, review or test.
6. **Settled = the owner said so.** Record `state.visualCheck[<nature>]`: `result: "owner-confirmed"`, the
   profile(s), what was checked, the owner's words, and the `tree` it was confirmed on. Then G5–G7, then
   sc-review once on the settled result.
<!-- /visual-loop-rule -->

<!-- visual-evidence-rule -->
## Visual evidence (G9, G11)

- **Primary evidence for a UI nature**: "owner confirmed on `<profile>`: `<what was checked>`". sc-ship G11
  labels it **`live (owner-confirmed)`**. Screenshots are optional — a PR record, not the loop.
  A screenshot-diff against the base runs only when the project declares a harness (`visualCheck.diff`);
  its result is added evidence beside the confirmation, never a replacement for it.
- **No owner present (unattended run).** Fall back to agent capture (`visualCheck.capture`) across every
  profile in the matrix: `result: "agent-captured"`, one capture per profile. G11 labels it
  **`review-only (agent-captured)`** and sc-ship lists each profile on the **"Pre-merge manual gate"** for
  the owner to look at. No capture command either → `result: "unverified: <reason>"`, same gate item.
  Never record `owner-confirmed` without the owner's own words in this run.
- **Stale confirmation.** If a later change (a review fix) touches files matched by that nature after
  `tree`, re-show the changed screens for one confirmation — not a new review — or the entry drops to the
  manual-gate item above.
- **G9.** sc-qa does not repeat the loop: the confirmation covers the screens it names; flows beyond them,
  seams and a release smoke are still QA's.
<!-- /visual-evidence-rule -->

<!-- a11y-floor -->
## Accessibility floor — named checks

Each is a pass/fail line in the loop's checklist (step 3) and in sc-review's `designer` lens:
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
every hook has a plain fallback, and browser-only features degrade on native apps to the live loop.

| stage | design-tool hook | fallback |
|---|---|---|
| sc-brainstorm / sc-design | `shape` — UX plan before code, against the design-system doc | designer prompt + `design.guide` |
| sc-implement live loop | `generate` / `live` — variants to choose from (web) | live loop above, labelled prototypes |
| sc-review designer lens | `critique` + `detect` + `audit` (native variant on iOS/Android) | designer-lens anti-patterns |
| sc-ship | `polish` — a final pass on the settled UI | — |

Inside a cycle the tool is used read-only in review (detectors report, they do not write); it never runs
`init` or `document`, never installs a hook, and never writes the design-system doc. Those are project
setup, outside any cycle.
