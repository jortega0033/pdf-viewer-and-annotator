# Design tokens

Source: the Pipenzo "Flow look" tokens, `extension/sidepanel/tokens.css` in jortega0033/clip-to-reel-studio at commit a13378ce73e5b27213c9a200fc960ec93afef054 (2026-11-21). The copy is `pdf_annotator/static/tokens.css`; it is served at `/tokens.css` and linked before `app.css`. Do not edit it.

## Resync

Copy the file from the source repository over `pdf_annotator/static/tokens.css`. Nothing else changes.

## Token names by role

- Surfaces: `--bg`, `--bg-raised`, `--surface`, `--bg-sunken`.
- Text: `--fg`, `--muted`, `--faint`, `--on-media`.
- Lines: `--border`, `--hairline`, `--control-border`, `--input-border`.
- Accent (Pipenzo yellow: primary action, current-step marker and current selection, see "Accent, selection, focus and themes"): `--primary`, `--primary-press`, `--primary-edge`, `--on-primary`.
- Status: `--ok`, `--ok-bg`, `--warn-fg`, `--warn-bg`, `--danger`, `--danger-bg`, `--info`, `--success`. Red is for danger only.
- Focus and state layers (`--focus` is a focus indicator, not the accent, see below): `--focus`, `--state-hover`, `--state-selected`, `--btn-secondary`, `--btn-secondary-border`, `--ring-accent`, `--scrim`.
- Dark blocks and hero: `--ink`, `--on-ink`, `--on-ink-muted`, `--ink-border`, `--hero-*`.
- Glass and gradients (`--glass*`, `--blur`, `--grad-*`) exist in the file but rule 4 of `ui-quality.md` forbids using them here.
- Type, space, radius, motion: `--font`, `--mono`, `--space-1` to `--space-7`, `--radius-*`, `--dur-*`, `--ease-*`.

## Rule

New UI uses these tokens; no new colour literals (hex, rgb, hsl or named colours) in `app.css` or `app.js`. Script code reads a token with `getComputedStyle(document.documentElement).getPropertyValue('--token')`.

## Light and dark

Dark is the primary design (black page, alpha-layer surfaces). The light block is the matching light theme. The operating system colour scheme chooses between them (`prefers-color-scheme`); there is no toggle.

## Accent, selection, focus and themes

The header comment of `tokens.css` says yellow is used only on the primary button, the current-step node and a few small marks. That comment is narrower than the rules below. The copy must stay identical to the source, so the comment is not edited here; this document takes precedence over it.

- **Accent (D1).** The yellow accent is used for the primary action, the current-step marker and the current selection (UI rule 8 in `ui-quality.md`). Decided by the owner on 2026-11-23.
- **How a selection looks (D1, recommended by the orchestrator and adopted under the owner's delegation of 2026-11-23).** A selection uses a solid `--primary` fill with `--on-primary` text, not only a yellow border (a yellow border has about 1.5:1 against white on light). It also carries a second sign that is not colour (weight, icon or text) and the existing aria attribute. Never a tint with a border of the same hue, and never a thick one-sided border (UI rules 1 and 2).
- **Focus ring (D2, recommended by the orchestrator and adopted under the owner's delegation of 2026-11-23).** `--focus` is a focus indicator and is exempt from the accent limit, including where it is yellow in dark. A ticket that says the focus style stays unchanged means the rule on `main` after the token pull request.
- **Themes (D3, recommended by the orchestrator and adopted under the owner's delegation of 2026-11-23).** Contrast checks and no-colour-alone checks cover both the light block and the dark block of `tokens.css`.

Status: the page does not fully follow this yet. Where it still marks a selection in a neutral colour, the page follows in ticket work.
