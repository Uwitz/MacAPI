# Uwitz Base Template

This project is the **master template for all Uwitz projects**. Every inheriting project follows the same engineering philosophy and security rules.

## Core Priority Order (from CODE_POLICY.md)

**Security > Privacy > Correctness > Reliability > Maintainability > Performance > Convenience**

- Security must **never** be sacrificed for convenience.
- Assume every environment is hostile unless explicitly proven otherwise.
- Adopt **Zero Trust** architecture and **Zero Knowledge** principles by default.

## Quick Rules

- Never commit secrets, keys, or credentials.
- Never invent or modify cryptography — use standard, well-audited algorithms.
- Prefer post-quantum cryptography (ML-DSA-87, ML-KEM-768) where ecosystem allows.
- Validate every input, authenticate every request, authorize every action.
- Auth failures must return generic errors — never leak whether a user exists vs bad password.
- Encrypt all sensitive data at rest and in transit.
- Any `sudo` command requires explicit user approval with full explanation.
- Minimize dependencies; evaluate each for security history, maintenance, and necessity.
- Document threat models, trust boundaries, and security decisions.

## References

- Full engineering philosophy: `CODE_POLICY.md`
- Agent workflow and project context: `AGENTS.md`
- Workflow handoff file: `WORKFLOW_STATE.md`
