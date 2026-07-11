# Web Implementation-Agent Prompt (Next.js example)

Template for a **web-only** implementation agent, separate from backend/mobile. Fill in `{…}` and hand
to `executor`/`designer`. Never touch the backend or mobile. Adapt the stack line to your project.

## Stack (example)
Next.js (App Router) / Tailwind CSS / a charting lib / an i18n lib / TypeScript / a state store.

## Template
```
Implement {feature/goal} in the web app ({webPath}). Work on the current branch {branch} (do not switch
branches). Do not touch backend/mobile — separate agents own those.

## Acceptance criteria
{Verifiable criteria. e.g. on a specific page, specific data/state is shown}

## Design rules (required)
- **No emoji → vector icons**: use a free icon set (e.g. lucide-react, MIT). Replace emoji in
  sidebar/buttons/tabs.
- **Design tokens**: don't hardcode color/spacing/typography. Define semantic tokens (brand/surface-*,
  etc.) and use them. Extract repeated inline style objects into a shared lib.
- **No magic numbers/strings in logic**: beyond design tokens, extract literals with domain meaning
  (thresholds, status strings, retry counts) into named constants; model a closed set as a union literal
  type or an `as const` object — **avoid TS `enum`** (runtime cost, `isolatedModules`/bundler pitfalls).
- **Responsive**: mobile/tablet/desktop. Fixed-width layouts (sidebars) get breakpoint branches + a
  mobile drawer.
- **Component consistency**: reuse `components/ui` (Card/Tabs/Badge); avoid one-off inline styles.
- **State design**: design empty/loading(skeleton)/error. No silent `catch {}` — surface error+retry to
  the user, and log.

## Accessibility
- Keep `focus-visible` rings (don't just remove outline), aria-*, semantic HTML, keyboard nav, modal
  focus trap, contrast ratios.

## i18n
- Add new strings **symmetrically across all configured locales** (a parity check may enforce this).
- **Never expose raw/internal keys in the UI**: map chart legends/labels via a label map
  (`LABELS[key] ?? key`) so an internal key like 'chest' never renders raw. No hardcoded copy. Don't
  assemble translations with `.replace()`.

## Data & charts
- Call the backend via a single API client and consume its DTOs. Handle loading/empty/error.
- Charts: label axes; put differently-scaled series on dual axes or split; localize legends;
  centralize tooltip config (no duplicated definitions).

## Done criteria
- `npm run build` (or `tsc`) + lint green, no console errors. E2E (e.g. Playwright) passing where
  applicable.
- Report changed/new files & roles and how you verified. **Do NOT commit/PR**. Read the real target
  pages/components first and match conventions.
```

## Notes
- UI change → include a **designer review** (strict) at code-review time (+ quality/security/performance
  in parallel).
- If it depends on the backend API, settle the contract first. Independent of mobile → can run in parallel.
