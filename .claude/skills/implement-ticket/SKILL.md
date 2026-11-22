---
name: implement-ticket
description: Playbook for implementing a GitHub issue in this repository from start to pull request, with the project subagents run at fixed steps. Use whenever asked to implement, start, continue or finish a ticket, an issue or an epic child, for example "implement #12" or "work on the next ticket".
argument-hint: "[issue number]"
---

# Implement a ticket

Use this playbook for every implementation ticket in this repository. `CLAUDE.md` holds the commands, the architecture boundaries, the Git workflow and the evidence rules; where this playbook and `CLAUDE.md` differ, `CLAUDE.md` wins.

The project subagents in `.claude/agents/` are part of the work. Delegate to them at the steps below without waiting to be asked. If a step names a role that is not installed, do that step yourself and say so in the pull request.

## Steps

1. **Read the ticket.** `gh issue view <number>` and the epic it belongs to. Check that every prerequisite issue is closed and that no owner decision named in the ticket is still open. Decisions recorded in `docs/owner-decisions.md` count as settled by their stated default, so do not stop on the epic's "Decisions for the owner" section. If the ticket is blocked, stop and say what blocks it.
2. **Read the rules.** `CLAUDE.md`, then the architecture notes it links to.
3. **Orient and check the approach.** Delegate as the table "Before coding" says. Settle open design questions before writing code.
4. **Branch** as the Git workflow in `CLAUDE.md` says. Never work on the default branch. For a ticket that changes `pdf_annotator/static/`, start with the `ui-ux-pro-max` skill (`python .claude/skills/ui-ux-pro-max/scripts/search.py "<product type>" --design-system`) and read `docs/ui-quality.md`.
5. **Implement** inside the ticket's stated scope. Delegate the work to the implementing role that matches the files being changed (table "While coding"). Do not widen scope; note anything else you find as a follow-up.
6. **Test.** Add or change tests for every acceptance criterion and material edge case, then run the checks listed in `CLAUDE.md`. Record each command and its result. For a UI ticket, check each changed screen against `docs/ui-quality.md` and record the result.
7. **Finalize the diff.** Before any gate runs, add one line to `CHANGELOG.md` under `Unreleased`, and run the `unslop` skill over user-facing copy, documentation and the pull request text, so the gates judge the final diff.
8. **Specialist review.** Run every role in the table "After coding" whose trigger matches the change.
9. **Review gate, always.** Reviewers have no shell, so first write the diff and the local evidence to `.claude/state/review/` in the ticket worktree (`git diff --stat origin/main...HEAD`, `git diff origin/main...HEAD`, the check outputs) and name those files in each request. Run Code Reviewer on the full diff. Fix every material finding, re-run the checks, and have the reviewer look again until no material finding is left.
10. **Acceptance gate, always.** Run Reality Checker with the ticket's acceptance criteria and the recorded local evidence. It checks that the documented checks ran locally and passed and that CI is configured to run them; it is not asked for a CI result, which does not exist yet. Do not open a pull request unless it passes. An acceptance step that needs a person ("by hand in a normal browser", "manual, recorded") is done as far as an agent can (a scripted or headless run, with the evidence) and the rest goes under "Owner checks" in the pull request; Reality Checker accepts that only when the ticket marks the step as manual.
11. **Hand off.**
    - Capture the evidence `CLAUDE.md` asks for and fill in `.github/pull_request_template.md`.
    - After both gates passed on the current diff, push the branch and open a draft pull request that names the issue. A `/next-ticket` run counts as the owner's request to push and open it; otherwise do not push unless the owner asked in the current session. The gate hook blocks `gh pr create` and `gh pr ready` until the gate roles ran after the last code edit.
    - CI runs on the draft pull request. If it fails, fix, re-run the local checks and both gates, and push. Mark the pull request ready only when CI is green (`gh pr checks`, read once when the session is woken, not polled); that is checked here, not by Reality Checker. Only a leaf ticket is work: a `tracking` ticket or one with open sub-issues is a container, and the pull request of a parent's last open sub-issue also says `Closes #<parent>`.
    - Only the owner merges. Never merge, and never push to the default branch.

## Roles

### Before coding

| Role | Access | Delegate to it |
|---|---|---|
| Codebase Onboarding Engineer | read-only reviewer | At the start of a ticket in an unfamiliar area, to trace the relevant code paths before anything is changed |
| Software Architect | read-only reviewer | Before implementing a ticket that adds or changes a module boundary, data model, storage schema, public API or dependency, to check the approach against the architecture notes |

### While coding

| Role | Access | Delegate to it |
|---|---|---|
| Backend Architect | can edit | When a ticket changes server-side code, HTTP routes, validation, persistence or data migrations |
| Database Optimizer | read-only reviewer | When a ticket changes SQL, the schema, indexes or query paths |
| Frontend Developer | can edit | When a ticket changes browser-side code such as pages, components, client state, styling or keyboard interaction |

### After coding

| Role | Access | Delegate to it |
|---|---|---|
| Application Security Engineer | read-only reviewer | After a ticket touches input parsing, file upload or import, sanitization, origin and host checks, or any handling of untrusted data |
| Accessibility Auditor | read-only reviewer | After a ticket changes user-facing UI, keyboard handling, focus order or markup |
| API Tester | can edit | After a ticket adds or changes an HTTP endpoint, status code or request and response contract |

### Gates that run on every ticket

| Role | Access | Delegate to it |
|---|---|---|
| Code Reviewer | read-only reviewer | After implementing or changing code for a ticket, before the work is called done or a pull request is opened |
| Reality Checker | read-only reviewer | After Code Reviewer and before the draft pull request, to check each acceptance criterion against local evidence that was actually produced; CI is checked later by the driver |

## Rules

- Do not change agent configuration (`.claude/agents/`, `.claude/skills/`, `.claude/hooks/`, `.claude/settings.json`) in a ticket, neither by edit nor by shell command.
- The session or role that wrote a change does not count as its reviewer.
- Read-only reviewers cannot run commands. Give them the diff, the acceptance criteria and the recorded command output.
- Where a role's general advice (frameworks, dependencies, cloud services) conflicts with `CLAUDE.md`, `CLAUDE.md` wins.
- In the pull request description, add a section "Agent roles run" listing each role that ran, what it was asked and its verdict, and any step you did yourself because a role was missing.
