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
