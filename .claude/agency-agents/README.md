# Agency Agents roles used in this repository

The Markdown files in `.claude/agents/` whose names start with `engineering-`, `security-` or `testing-` are copies of role definitions from Agency Agents. They are project-local Claude Code subagents. The file `loop-verifier.md` in the same folder is not from Agency Agents; it belongs to the Loop Engineering setup described in [`LOOP.md`](../../LOOP.md).

## Source and licence

- Upstream: https://github.com/msitarzewski/agency-agents
- Pinned revision: `8ae6164602c95ca78828b148b9052460ee426885` (upstream `main`, committed 2026-11-09)
- Licence: MIT, "Copyright (c) 2025 AgentLand Contributors". The upstream licence text at the pinned revision is kept unchanged in [`LICENSE`](LICENSE) next to this file (SHA-256 `9a45258434d5cedf0af73c9ad4771373701225038d246c49219026c33677f66f`). It covers only the copied role files, not the rest of this repository.
- Fetched with `gh api -H "Accept: application/vnd.github.raw" "repos/msitarzewski/agency-agents/contents/<path>?ref=<revision>"`.

## Installed roles

"Upstream SHA-256" is the hash of the file as fetched at the pinned revision. Reviewer roles have one added frontmatter line, `tools: Read, Grep, Glob`, so they cannot edit files or run commands. Nothing else in any file was changed.

| File in `.claude/agents/` | `name:` | Upstream path | Upstream SHA-256 | Local change |
|---|---|---|---|---|
| `engineering-software-architect.md` | Software Architect | `engineering/engineering-software-architect.md` | `b85121691776147bacde26673e68fbbacd6a7f0816d1ca8e203c264d25ce1d30` | added `tools: Read, Grep, Glob` |
| `engineering-code-reviewer.md` | Code Reviewer | `engineering/engineering-code-reviewer.md` | `7509fcc3ea1dda46511b2801996305bf3d4a125576f9655ff0b63df25602f446` | added `tools: Read, Grep, Glob` |
| `engineering-codebase-onboarding-engineer.md` | Codebase Onboarding Engineer | `engineering/engineering-codebase-onboarding-engineer.md` | `07aa548b45887c3ad768efad5fdbf6e57bea639df4f1b74c7e383142f454e2a1` | added `tools: Read, Grep, Glob` |
| `engineering-database-optimizer.md` | Database Optimizer | `engineering/engineering-database-optimizer.md` | `6d773003e3b9251068ab537be94d6827c118201e0e17c11d789cb29dc245bf99` | added `tools: Read, Grep, Glob` |
| `security-appsec-engineer.md` | Application Security Engineer | `security/security-appsec-engineer.md` | `a19f0bda46f4adca5737365dbc3c7ed93e9d93b71349536d92ff055dcf4e3b83` | added `tools: Read, Grep, Glob` |
| `testing-accessibility-auditor.md` | Accessibility Auditor | `testing/testing-accessibility-auditor.md` | `362935907af23839775b9c6162f38c0c5a740542ab4350cb5c5b5a0d9f9a4268` | added `tools: Read, Grep, Glob` |
| `testing-reality-checker.md` | Reality Checker | `testing/testing-reality-checker.md` | `6d32fcdb114233e13902ec6372d50293b120e85d490b5e81d372c29808f988a1` | added `tools: Read, Grep, Glob` |
| `engineering-backend-architect.md` | Backend Architect | `engineering/engineering-backend-architect.md` | `ac717bde4848d7663fff8a3c7edc711fd119256de6a7ce38c036619372f42c99` | none |
| `engineering-frontend-developer.md` | Frontend Developer | `engineering/engineering-frontend-developer.md` | `1ae4cc10b2e0163bd3ed921ad54080b865cd02e591becd8919b64b73fab06dad` | none |
| `testing-api-tester.md` | API Tester | `testing/testing-api-tester.md` | `ab91de9188d48bd9c417282c33673a37b066215e90e08c0f1b270d036084e3bb` | none |

## Why these roles

| Role | Use in this repository |
|---|---|
| Software Architect (read-only) | Review a ticket's design against the layering in [`docs/architecture.md`](../../docs/architecture.md) before code is written: where a parser stage lives, what the display list carries, how a document and its notes are keyed, how a new route keeps the request guards. |
| Code Reviewer (read-only) | Review a diff for correctness, missed edge cases and broken rules (every length checked before use, revision check on every write, request guards on new routes, no traceback in responses). |
| Codebase Onboarding Engineer (read-only) | Trace a code path and report facts with file and line citations. |
| Application Security Engineer (read-only) | Review everything that reads bytes the person chose: the upload route (size cap before buffering, no path built from request input), the parser (caps on size, count, depth and decompressed output, no allocation from a length declared in the file, loops in reference chains), image decoding, and the export download. This is the main risk area of the planned work. |
| Database Optimizer (read-only) | Review schema changes, migrations and transaction scope in `pdf_annotator/storage.py`. Two planned tickets add tables, and every write must keep the revision compare-and-set. |
| Accessibility Auditor (read-only) | Review keyboard operation, focus, labels, live regions and contrast. The page draws on a canvas, so each ticket that changes rendering must keep the text equivalent, and region notes need a path that does not depend on a pointer. |
| Reality Checker (read-only) | Compare claimed evidence with what was actually run before a ticket or the epic is called done. |
| Backend Architect | Implement work in `pdf_annotator/*.py` (parser, HTTP layer, storage and migrations, export writer). |
| Frontend Developer | Implement work in `pdf_annotator/static/` (canvas rendering, zoom and rotation, region overlay, conflict flow). |
| API Tester | Write the HTTP-level `unittest` cases in `tests/` for new and existing routes. |

Most of these roles are written for larger stacks. Backend Architect, Frontend Developer and API Tester mention frameworks, cloud services and Playwright; Database Optimizer is written around PostgreSQL and MySQL; Application Security Engineer describes scanners and pipelines. In this repository the rules in [`CLAUDE.md`](../../CLAUDE.md) win: Python standard library only, SQLite, native HTML, CSS and JavaScript, `unittest`, no pip or npm dependencies, no external requests, no third-party PDF files.

Roles that were considered and left out:

- PDF Engine Architect (`engineering/engineering-pdf-engine-architect.md`): despite the name it is about compiling HTML to PDF with Playwright browser pools and print layout. This repository reads PDF bytes and never produces pages from HTML, so the role's rules would mislead.
- Universal Document Compiler, Performance Benchmarker, Test Automation Engineer and Evidence Collector: their methods need tools this repository does not allow (browser automation, load tools, external services). Browser checks here are manual and recorded.
- Technical Writer and Minimal Change Engineer: the repository rules in `CLAUDE.md` already cover what they would add.

## Name collision with user-level agents

A developer who has installed Agency Agents in `~/.claude/agents/` already has agents with the same `name:` values. Claude Code gives the project-level definition precedence, so inside this repository the copies here are used, including the read-only tool limits. The upstream names were kept on purpose so that the roles stay recognisable and can be compared with upstream.

A Claude Code session that was already running when these files were added keeps the definitions it loaded at start. Start a new session to pick up the project copies.

## Check that the roles load

From the repository root, in a new session:

```text
claude -p "List the project-level subagents defined in .claude/agents with the tools each one may use. Then run the Reality Checker subagent and ask it which tools it has."
```

The seven reviewer roles and `loop-verifier` must report exactly `Read, Grep, Glob`.

### What was observed, and what was not

Observed on 2026-11-22 with Claude Code 2.1.323, headless (`claude -p`, model requested: haiku, no MCP servers), from the repository root, one run, on a machine that also has a user-level Agency Agents install (303 files, all ten names present there, none with a `tools:` line):

- All eleven names were listed (the ten roles above and `loop-verifier`). Software Architect, Code Reviewer, Codebase Onboarding Engineer, Database Optimizer, Application Security Engineer, Accessibility Auditor, Reality Checker and `loop-verifier` were listed with `Read, Grep, Glob`. Backend Architect, Frontend Developer and API Tester were listed with all tools.
- A launched Reality Checker and a launched Application Security Engineer each reported exactly `Read`, `Grep`, `Glob`. The user-level copies have no `tools:` line, so the tool limits show that the project copies were the ones loaded.
- A launched Backend Architect, asked for the tables in its own example schema, answered `users`, `categories`, `products`. The user-level copy on that machine is a different upstream revision whose example has no `categories` table, so this shows project precedence for that role.
- **Not shown:** which copy of Frontend Developer and API Tester was loaded (they were listed, not launched), behaviour in an interactive session, and behaviour on a machine without a user-level install (there the names must simply be listed).
- The listing gives names and tools only, not the file a definition comes from. The statements above about which copy was loaded rest on the tool limits and the quoted table names.

## Updating

Fetch the same paths at a newer revision, re-apply the `tools:` line to the seven reviewer roles, and update the revision and hashes in this file in the same commit.

## Local change: automatic delegation (2026-11-22)

One sentence beginning "Use proactively" was appended to the `description:` line of every Agency Agents role in `.claude/agents/` (not to `loop-verifier`). Claude Code uses that field to decide when to delegate, so the roles now run during ticket work without being named.

A section headed `## In this repository` was then inserted directly after the frontmatter of every Agency Agents role (again not `loop-verifier`), before the upstream text. It is project-specific text written for this repository: the stack and hard rules that bind the role, the files it owns or reviews, its commands or the output it must be given, its checklist, the parts of the upstream text that do not apply here, and what it hands back. It is not upstream text, and the upstream hashes in the table above do not cover it. The upstream text below the section is unchanged.

This supersedes any statement above that a role file is unmodified or that the `tools:` line is the only local change. To compare a role with the pinned upstream file, first remove the "Use proactively" sentence, the `tools:` line where one was added, and the whole "In this repository" section: from its heading through the line "This section and CLAUDE.md override the generic text below wherever they differ." and the blank line after it. When updating to a newer upstream revision, re-apply all three local changes and check each section against the code again.

The steps at which each role runs are in `.claude/skills/implement-ticket/SKILL.md`.

Verification, 2026-11-22: with the sections in place, one headless run from the repository root with Claude Code 2.1.323 (`claude -p "List every project subagent defined in .claude/agents with its exact name and tools, say for each whether its instructions begin with a section titled In this repository, and say whether a skill named implement-ticket is available. Plain list, no commentary." --model haiku`) exited 0 and listed all eleven names. Code Reviewer, Codebase Onboarding Engineer, Database Optimizer, Software Architect, Application Security Engineer, Accessibility Auditor, Reality Checker and `loop-verifier` were listed with `Read, Grep, Glob`; Backend Architect, Frontend Developer and API Tester with no tool limit. Each of the ten Agency Agents roles was reported as beginning with "In this repository", `loop-verifier` as not, and the skill `implement-ticket` as available. Not shown by this run: a role actually launched with the new section, automatic delegation during a real ticket, and behaviour in an interactive session. The answer is a model's listing, so it is evidence that the files parse and load, not proof of how each role behaves.

## Local change: SDLC kit (2026-11-22)

This pass added, without changing any role's upstream text:

- One checklist line naming `docs/ui-quality.md` in the "In this repository" section of Frontend Developer, Accessibility Auditor and Code Reviewer. UI Designer and UX Architect are not installed in this repository.
- The review gate hook `.claude/hooks/role_gate.py` with `GATE_ROLES` set to Code Reviewer and Reality Checker (both installed here), and `.claude/settings.json`.
- The skills `next-ticket`, `ui-ux-pro-max` and `unslop` under `.claude/skills/`, and the updated `implement-ticket` steps.
- CI (`.github/workflows/ci.yml`), the pull request and ticket templates, `CODEOWNERS`, `dependabot.yml`, `SECURITY.md`, `CHANGELOG.md`, `docs/RELEASING.md`, `docs/ui-quality.md` and `docs/owner-decisions.md`.
