---
name: teamwork-harness
description: Scaffold and validate the four-layer context harness (lean AGENTS.md, modular .agents/rules, verification exit gates) for new or existing projects before invoking /teamwork-preview.
---

# Teamwork Harness Generator

Prepare any project directory for autonomous multi-agent execution with `/teamwork-preview`.

## Core Philosophy
Autonomous multi-agent swarms fail when they spend turns guessing how to build, test, or navigate the codebase. The harness provides an immediate, unpolluted contract so agents act with precision.

## The Four-Layer Harness

### 1. Root `AGENTS.md` (<150 Lines)
Every project root MUST contain an `AGENTS.md` adhering strictly to this schema:
```markdown
# Project Name & Architecture Overview (Max 15 lines)
- Tech Stack: <Language / Framework / Primary DB>
- Architectural Pattern: <Monorepo, Clean Architecture, MVC, Microservices>
- Primary Entrypoints: <Paths to main servers/routers>

# Commands
- Build: `<command>`
- Test Suite: `<exact command, e.g. pytest -xvs / npm test>`
- Targeted Test: `<command to test single file or feature>`
- Linter/Formatter: `<command, e.g. ruff check / eslint>`

# Global Anti-Patterns
- No speculative abstractions or unrequested features (YAGNI).
- Never commit hardcoded secrets or API keys.
- Do not bypass verification commands or write self-certifying mock assertions.
```

### 2. Modular Rules (`.agents/rules/`)
Keep the root `AGENTS.md` lean. Put framework-specific or directory-specific guidelines into `.agents/rules/*.md`:
- Frontend guidelines -> `.agents/rules/frontend.md`
- Database migrations -> `.agents/rules/db.md`
- Security constraints -> `.agents/rules/security.md`

### 3. Objective Programmatic Verification Gate
Every teamwork project MUST have an executable verification command that exits with code `0`:
- Script target: `./verify.sh` or standard command (`npm test`, `pytest`, `cargo test`).
- The exit code is the hard gate before any subagent can mark a task complete.

### 4. Subagent Delegation Contract
When delegating work within the swarm:
- Use `codebase-explorer` for read-only orientation (returns max 30-line architecture summary).
- Use `test-runner-verifier` for test execution (returns only failing assertions and stack traces).
- Use `security-diff-auditor` before opening PRs or merging branches (returns findings-only table).
