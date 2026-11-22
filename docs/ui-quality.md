# UI quality rules

These ten rules bind every change to `pdf_annotator/static/` and every user-facing string. Rules 1 and 2 are the owner's; rules 3 to 10 were approved by the owner on 2026-11-22 with the same standing. The record is in [owner-decisions.md](owner-decisions.md).

1. No thick accent border on one side of a card, callout, alert, list item or quote (for example `border-left: 4px solid <accent>`). Use spacing, type weight, an icon or a full hairline border instead.
2. No soft tinted background with a thin border of the same hue as the default way to mark a status, tag, callout or card. One neutral surface and one clear signal (text, icon or a solid chip) is enough.
3. No gradient text and no purple-to-blue gradient as a default accent.
4. No blur or glass panels, and no drop shadow plus large radius on every card.
5. No emoji used as icons or bullets, and no sparkle marks.
6. No pill or badge on things that are not states. No all-caps, letter-spaced micro labels as section decoration.
7. No centred hero with a slogan in an application screen. Screens open on the user's task.
8. One accent colour, used for the primary action and the current selection. Status colours only for status.
9. Dense, aligned layouts on a consistent spacing scale. No card grid where a table or a list is the right form.
10. User-facing copy is plain and specific: no filler, no exclamation marks, and the same word for the same thing everywhere.

## How they are applied

- A ticket that changes the page starts with the `ui-ux-pro-max` skill (`.claude/skills/ui-ux-pro-max/`), run as a design-system search for the product type, and ends with a check of every changed screen against this file. The result goes in the pull request evidence.
- Copy, documentation and pull request text go through the `unslop` skill (`.claude/skills/unslop/`) before the pull request is opened.
- Frontend Developer, Accessibility Auditor and Code Reviewer name this file in their checklists. Code Reviewer runs on every ticket, so the review gate enforces the rules.
- No script enforces them. Rule 1 can be found with a search for `border-left` and `border-right` in `pdf_annotator/static/app.css`; rule 2 cannot be detected reliably from CSS and needs a reader.
- The page is one native HTML, CSS and JavaScript page with no inline style (the CSP forbids it), so every style lives in `pdf_annotator/static/app.css`. The repository's other hard rules (no external fonts, images or scripts) still apply.
