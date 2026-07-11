# Mobile Implementation-Agent Prompt (React Native / Expo example)

Template for a **mobile-only** implementation agent, separate from backend/web. Fill in `{…}` and hand
to `executor`/`designer`. Never touch backend or web. Adapt the stack line to your project.

## Stack (example)
Expo (Managed) / React Native / Expo Router / TypeScript / a persisted state store / an i18n lib /
a chart lib + react-native-svg.

## Template
```
Implement {feature/goal} in the mobile app ({mobilePath}). Work on the current branch {branch} (do not
switch branches). Do not touch backend/web — separate agents own those.

## Acceptance criteria
{Verifiable criteria. e.g. on a specific screen, specific data/interaction works}

## Design rules (required)
- **No emoji → vector icons**: use the platform vector-icon set (e.g. @expo/vector-icons — bundled,
  free). Replace emoji/text icons (▼▶›‹✓○ …) in tab bar/buttons/arrows.
- **Theme tokens**: use colors/spacing/typography tokens from a theme module. No raw-px magic numbers
  or hardcoded colors → add tokens/semantic tokens.
- **No magic numbers/strings in logic**: beyond theme tokens, extract domain literals (thresholds, status
  strings, intervals) into named constants; a closed set → a union literal type or an `as const` object,
  **not a TS `enum`**.
- **Component reuse**: reuse Card/Button/Badge/etc.; avoid one-off inline styles.
- **State design**: empty/loading/error. Center empty states with flex, not magic padding. No silent
  `catch {}` — surface a retryable error state and log (constitution #6).

## Accessibility
- Every interactive element gets `accessibilityLabel`/`accessibilityRole`/`accessibilityState`
  (toggle = switch+checked, selectable card = selected). Icon-only touchables must have a label.
- Touch targets **≥44pt**. WCAG contrast in light/dark (small text 4.5:1).
- Self-check with an a11y lint plugin (free, static).

## i18n
- Add new keys **symmetrically across all configured locales/namespaces** (a parity check may enforce).
- **No hardcoded copy**; don't assemble translations via `t('k').replace(...)` (breaks in other locales).
- **Correct domain units**: use the right unit noun per concept (don't reuse an unrelated unit).

## RN pitfalls (found in real audits — avoid)
- Don't fake a circular progress bar with CSS `transform: rotate` + `transformOrigin` (unsupported in
  RN, breaks on Android) → use react-native-svg / a chart lib.
- Live elapsed time etc.: `useEffect` + `setInterval` + cleanup (avoid render-time freeze bugs).
- Prefer `expo-haptics` over `Vibration`.
- Cards that look tappable must have a real onPress, or drop the Touchable.
- Don't overlay differently-scaled data on one Y axis.

## Data
- Use the repository pattern (Local/Api/OfflineFirst — check the wiring in index). Persist stores.
- Consume the API's **actual serialized DTO shape** (real field names/types) via the repository — never a
  guessed shape; if the backend returns a raw entity, flag it (constitution #6).

## Testing (TDD — required)
- Tests come first (Red), then implementation (Green). For UI with no render harness, extract pure logic
  (formatters, selectors/reducers, i18n resolution, time/geometry math) into testable modules and write
  the failing tests there; thin view wiring is covered by the designer lens + sc-qa. If a change has no
  extractable logic, say so explicitly and route verification to review/QA — don't write a vacuous test.

## Done criteria
- `tsc`/lint green (incl. a11y lint), no console/type errors. (Release artifact build is via EAS.)
- Report changed/new files & roles and how you verified. **Do NOT commit/PR**. Read the real target
  screens/components/theme first and match conventions.
```

## Notes
- UI change → include a **designer review** (strict). Visual pass via device screenshot → a vision
  agent, or Maestro (free CLI).
- Independent of web → can run in parallel. If it depends on the backend API, settle the contract first.
