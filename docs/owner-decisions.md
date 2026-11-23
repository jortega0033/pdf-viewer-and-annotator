# Owner decisions

A dated record of the decisions the owner made for this repository, so the rules do not depend on anyone's memory of a conversation. Changing any entry needs the owner; an agent that finds a decision blocking a ticket stops and says so.

| # | Decision | Date | Implemented in |
|---|---|---|---|
| 1 | The instructions, tooling and playbook live on the default branch (`main`). | 2026-11-22 | `CLAUDE.md`, `.claude/`, `.github/` |
| 2 | Persona agents run automatically during ticket work and carry instructions tailored to this project. | 2026-11-22 | `.claude/agents/`, `.claude/skills/implement-ticket/SKILL.md`, `.claude/agency-agents/README.md` |
| 3 | Every open ticket is about app implementation; tooling is installed, not ticketed. | 2026-11-22 | epic #1, `.github/ISSUE_TEMPLATE/implementation-ticket.md` |
| 4 | Agents may take a ticket up to a ready pull request. Only the owner merges and releases. | 2026-11-22 | `CLAUDE.md` (Git workflow, Delivery workflow), `.claude/skills/next-ticket/SKILL.md`, `docs/RELEASING.md`, `.claude/settings.json` |
| 5 | No scheduler. Ticket work starts only on the owner's go signal (`/next-ticket`), because the repository is used to train AI models. | 2026-11-22 | `.claude/skills/next-ticket/SKILL.md` (`disable-model-invocation: true`), `LOOP.md` |
| 6 | A review gate hook blocks opening or readying a pull request until the gate roles have run after the last code edit. | 2026-11-22 | `.claude/hooks/role_gate.py`, `.claude/settings.json` |
| 7 | Loop Engineering stays at L1, report-only and unscheduled. | 2026-11-22 | `LOOP.md` |
| 8 | Continuous integration runs on Linux and Windows; the default branch requires a pull request and green checks. | 2026-11-22 | `.github/workflows/ci.yml` (branch protection is set on GitHub by the owner's orchestrator) |
| 9 | Permission rules: documented commands are allowed; force pushes, pushes to the default branch, merges, releases and reads of secrets are denied; edits to CI, agent configuration and Loop files ask first. | 2026-11-22 | `.claude/settings.json` |
| 10 | Open decisions on tickets are settled with the ticket's stated default (list below). | 2026-11-22 | epic #1 "Decisions for the owner", `.claude/skills/next-ticket/SKILL.md` |
| 12 | The ten UI rules in `docs/ui-quality.md` are binding, and the `ui-ux-pro-max` and `unslop` skills are installed in the repository and used for UI work and for copy. | 2026-11-22 | `docs/ui-quality.md`, `.claude/skills/ui-ux-pro-max/`, `.claude/skills/unslop/`, `.claude/skills/implement-ticket/SKILL.md` |
| 13 | Visual system: Pipenzo Flow look tokens (docs/design-tokens.md). SDLC kit version: jortega0033/sdlc-kit v1.0.0. | 2026-11-23 | `docs/design-tokens.md`, `pdf_annotator/static/tokens.css` |
| 14 | Accent, selection, focus ring, themes and linking rules for the token system (list below). | 2026-11-23 | `docs/design-tokens.md`, `docs/ui-quality.md` |

Entry 11 (Rust verified in CI only) does not apply: this repository has no Rust code.

## Entry 10: open decisions settled by the ticket default

Source: epic #1, section "Decisions for the owner". Date 2026-11-22.

| Issue | Decision | Default applied |
|---|---|---|
| #1 (decision 1) | Where a chosen file goes | The page sends it to the loopback server, which keeps a copy in the data directory (#8). |
| #1 (decision 2) | What identifies a document | The SHA-256 of its bytes; a changed copy is a different document without notes (#8). |
| #1 (decision 3) | Script, form and link entries | Keep the M1 refusal. #2 removes only the six structure names it reads from the refused list; the other nine still answer `unsupported_feature`. The gated section of #2 is not built. |
| #1 (decision 4) | Limits | The numbers in the tickets are the defaults. |
| #1 (decision 5) | Font metrics | An owned width table for the characters the fixtures use, approximation elsewhere (#3); widths from the file for non-standard fonts (#9). No published standard-font metrics are added. |
| #1 (decision 6) | #9 beyond PRD milestone P2 | Keep it in the batch. |
| #1 (decision 7) | Independent checker for the export | `pdftotext` when installed, otherwise a skip, plus one manual check in a reader (#6). |
| #1 (decision 8) | JavaScript tests | The self-check page from #4; no JavaScript test runner. |

## Entry 14: accent, selection, focus and themes

Date 2026-11-23. Only D1 (the rule itself) is a decision of the owner; the other items are recommendations of the orchestrator adopted under the owner's delegation of the same day.

| Id | Decision | Source |
|---|---|---|
| D1 | Current selection: the yellow accent is used for the primary action, the current-step marker and the current selection (UI rule 8). | Decided by the owner on 2026-11-23. |
| D1 (how) | A selection uses a solid `--primary` fill with `--on-primary` text (not only a yellow border, which has about 1.5:1 against white on light), plus a second sign that is not colour (weight, icon or text) and the existing aria attribute. Never a tint with a same-hue border and never a thick one-sided border. | Recommended by the orchestrator, adopted under the owner's delegation of the same day. |
| D2 | Focus ring: `--focus` is a focus indicator, exempt from the accent limit, including where it is yellow in dark. A ticket that says the focus style stays unchanged means the rule on `main` after the token pull request. | Recommended by the orchestrator, adopted under the owner's delegation of 2026-11-23. |
| D3 | Themes: contrast and no-colour-alone checks cover both the light and the dark block of `tokens.css`. | Recommended by the orchestrator, adopted under the owner's delegation of 2026-11-23. |
| D4 | Linking: a ticket that creates a page or its static allowlist links `tokens.css` before any other stylesheet and serves it (allowlist and its test). | Recommended by the orchestrator, adopted under the owner's delegation of 2026-11-23. |
| D5 | release-dependency-planner: while a plan is open only one yellow primary button shows; "New plan" (`#new-plan`) becomes neutral, in ticket #11. | Recommended by the orchestrator, adopted under the owner's delegation of 2026-11-23. |
