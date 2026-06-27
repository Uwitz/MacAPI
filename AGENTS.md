# Project Context

## Project identity

- **Uwitz base project template** — master template for all future Uwitz projects
- **Not a runnable project**: this is a scaffolding/boilerplate source. Downstream projects choose their own language, runtime, and framework.
- **Engineering philosophy defined in** `CODE_POLICY.md`: Security > Privacy > Correctness > Reliability > Maintainability > Performance > Convenience
- **Zero Trust architecture** and **Zero Knowledge principles** are the default design constraints for all inheriting projects
- **Repository**: `UZC/base` (part of the Uwitz monorepo at `/Users/snyco/UZC/`)

## Architecture

- **Template repository** — no services, no running processes, no entry points
- Contains scaffolding files that all new Uwitz projects inherit:
  - `AGENTS.md` — agent instructions for the Uwitz engineering workflow
  - `WORKFLOW_STATE.md` — shared handoff file for multi-agent workflow
  - `CODE_POLICY.md` — Uwitz engineering philosophy, security policy, cryptography policy, and decision-making principles
  - `CLAUDE.md` — auto-loaded AI memory (Claude Code), distills CODE_POLICY.md into concise rules
  - `opencode.json` — OpenCode configuration with security-focused skills enabled
  - `.opencode/agents/` — 8 agent definitions for the Uwitz multi-agent workflow
  - `.gitignore` — security-focused default ignores
  - `.env.example` — env var naming convention template
  - `README.md` — customizable new-project README
  - `src/` — source code directory stub
  - `tests/` — tests directory stub
- **Used as a seed**: new Uwitz projects copy this directory (or its relevant files) and add their own source code, configs, manifests, and CI
- **Sibling projects** that were seeded from this template:
  - `UZC/api` — Rust API gateway (axum, MongoDB, WSS/REST)
  - `UZC/orcus` — Python project
  - `UZC/asterisk` — minimal project (README + WORKFLOW_STATE only)
  - Each has its own `AGENTS.md` with project-specific context, language, security invariants, and commands

## Configuration

- **No project-level config** at template level — config approach is chosen by the downstream project
- **Env var convention** (from `UZC/api` precedent): `UZC_SECTION__KEY` with `__` as nesting separator (figment convention) — not enforced at template level but recommended
- Secrets must never be committed (see `CODE_POLICY.md` §Secrets)
- `.env*` files must be in `.gitignore` from the start

## Build & deploy

- **No build or deploy commands** — this is a template, not a runnable project
- Each downstream project defines its own build system (see sibling projects for examples)
- **CI/CD**: no template-level config — `.gitlab-ci.yml`, Dockerfiles, etc. are added per-project

## Security invariants (from CODE_POLICY.md — do not violate)

These are inherited by every project created from this template:

- **Zero Trust**: every network is hostile, every client is untrusted, every server is potentially compromised, every dependency is a supply-chain risk
- **Zero Knowledge**: servers, operators, and infrastructure should learn as little user data as possible
- **Minimize attack surface**: failure must close, not open; validate every input; authenticate every request; authorize every action
- **Cryptography policy**:
  - Never invent or modify standard cryptographic algorithms
  - Prefer algorithms with transparent parameters, extensive public review, and professional audits
  - Favor post-quantum cryptography (ML-DSA-87, ML-KEM-768) where ecosystem support allows
  - Design for cryptographic agility (future migration)
- **Secrets discipline**: never print, store in source, commit, log, or transmit secrets insecurely
- **Supply chain**: evaluate every dependency for security history, maintenance, audit history, community trust, licensing, and necessity
- **Auth failures**: must return generic errors — never leak whether a user exists vs bad password
- **Encryption**: encrypt all sensitive data and communications by default — use constant-time operations where applicable
- **Audit trail**: document threat models, trust boundaries, security assumptions, cryptographic decisions, auth flows, authz models, and operational procedures
- **Threat model includes**: network access, compromised infrastructure, stolen databases, leaked backups, compromised endpoints, supply-chain access, malicious insiders, and future quantum-capable attackers
- **Privileged operations**: any `sudo` command requires explicit user approval with full explanation before execution

## Known issues

- This is a template repository with no runtime code — no known issues at this level
- Downstream projects may encounter framework- or language-specific issues (documented in their own AGENTS.md)
- Template files intentionally minimal — downstream projects are expected to extend, not replace

## Commands

| Action | Command | Notes |
|---|---|---|
| Initialize a new project | `cp -r /path/to/UZC/base /path/to/new-project` | Then customize AGENTS.md, add source code, remove or fill boilerplate |
| Load philosophy | `cat CODE_POLICY.md` | Read before making architectural decisions |
| Agent workflow | See `WORKFLOW_STATE.md` | Shared handoff between Planner → Debater → Implementor → Reviewer → Tester → Security → Linter → Commit |

## Team workflow rules

All agents participate in one workflow.

Shared handoff file:
- Read `WORKFLOW_STATE.md` before starting work
- Update `WORKFLOW_STATE.md` before finishing work
- Never overwrite another section unnecessarily
- Preserve decisions, assumptions, blockers, and next steps

Workflow order:
1. Planner clarifies the request with the user
2. Planner writes clarified scope and acceptance criteria
3. Debater critiques the plan
4. Implementor makes the change
5. Reviewer reviews the result
6. Tester runs relevant tests
7. security-reviewer – performs security code review
8. Linter checks formatting/linting
9. Commit-message writes the final commit message

Writing rules:
- Keep entries short and structured
- Prefer bullets over long paragraphs
- Record file paths when discussing code changes
- Record exact test commands and results
- Record unresolved questions under "Open Questions"

## Shared workflow rules

All agents must use WORKFLOW_STATE.md as the shared handoff file.

Before starting:
- Read WORKFLOW_STATE.md

After finishing:
- Update only the sections relevant to your role
- Preserve existing content unless it is outdated or clearly incorrect
- Add a short handoff note for the next agent

When working on code, dependencies, libraries, frameworks, or APIs:
- Use context7 before proposing a plan
- Use context7 before implementation if external library behavior is relevant
- Use context7 during review when checking API usage or framework conventions
- Prefer context7 over guessing library behavior from memory
- Record important findings in WORKFLOW_STATE.md

Do not use chat history as the only source of truth.
WORKFLOW_STATE.md is the canonical workflow record.

## Serena usage rules

Serena is the semantic code assistant for this project.
Prefer Serena's MCP tools over raw grep for any code navigation.

When working with this codebase:

- Use Serena's MCP tools for semantic code navigation and edits instead of guessing.
- Prefer Serena for:
  - finding relevant files, modules, and symbols
  - understanding call graphs and relationships
  - making structured, multi-file edits
  - Trace where user input flows through the codebase
- Only fall back to raw grep/edit/apply_patch when Serena tools are clearly not applicable.

Serena tools are exposed via the MCP server. Use them by name whenever code understanding or structured refactors are needed.
Record important Serena findings in WORKFLOWSTATE.md.
