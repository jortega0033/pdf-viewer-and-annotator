# Design tokens

Source: the Pipenzo "Flow look" tokens, `extension/sidepanel/tokens.css` in jortega0033/clip-to-reel-studio at commit a13378ce73e5b27213c9a200fc960ec93afef054 (2026-11-21). The copy is `pdf_annotator/static/tokens.css`; it is served at `/tokens.css` and linked before `app.css`. Do not edit it.

## Resync

Copy the file from the source repository over `pdf_annotator/static/tokens.css`. Nothing else changes.

## Token names by role

- Surfaces: `--bg`, `--bg-raised`, `--surface`, `--bg-sunken`.
- Text: `--fg`, `--muted`, `--faint`, `--on-media`.
- Lines: `--border`, `--hairline`, `--control-border`, `--input-border`.
- Accent (Pipenzo yellow, primary action and current step only): `--primary`, `--primary-press`, `--primary-edge`, `--on-primary`.
- Status: `--ok`, `--ok-bg`, `--warn-fg`, `--warn-bg`, `--danger`, `--danger-bg`, `--info`, `--success`. Red is for danger only.
- Focus and state layers: `--focus`, `--state-hover`, `--state-selected`, `--btn-secondary`, `--btn-secondary-border`, `--ring-accent`, `--scrim`.
- Dark blocks and hero: `--ink`, `--on-ink`, `--on-ink-muted`, `--ink-border`, `--hero-*`.
- Glass and gradients (`--glass*`, `--blur`, `--grad-*`) exist in the file but rule 4 of `ui-quality.md` forbids using them here.
- Type, space, radius, motion: `--font`, `--mono`, `--space-1` to `--space-7`, `--radius-*`, `--dur-*`, `--ease-*`.

## Rule

New UI uses these tokens; no new colour literals (hex, rgb, hsl or named colours) in `app.css` or `app.js`. Script code reads a token with `getComputedStyle(document.documentElement).getPropertyValue('--token')`.

## Light and dark

Dark is the primary design (black page, alpha-layer surfaces). The light block is the matching light theme. The operating system colour scheme chooses between them (`prefers-color-scheme`); there is no toggle.
