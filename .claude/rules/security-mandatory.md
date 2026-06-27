# Uwitz Security Mandatory Rules

## Core Policy (from CODE_POLICY.md)
- **Security > Privacy > Correctness > Reliability > Maintainability > Performance > Convenience**
- Never sacrifice security for convenience
- Zero Trust: every network is hostile, every client is untrusted
- Every failure must close, not open

## Cryptography
- Never invent or modify standard cryptographic algorithms
- Prefer algorithms with transparent parameters and extensive public review
- Design for post-quantum migration (ML-DSA-87, ML-KEM-768 where feasible)
- Use constant-time operations where applicable

## Secrets
- Never commit secrets, keys, or credentials to the repository
- Never print secrets in logs or output
- Never store secrets in source code
- Never transmit secrets insecurely

## Input & Auth
- Validate every input
- Authenticate every request
- Authorize every action
- Auth failures must return generic errors — never leak whether a user exists vs bad password

## Supply Chain
- Evaluate every dependency for security history, maintenance, audit history, and necessity
- Prefer standard libraries over third-party dependencies

## Privileged Operations
- Any `sudo` command requires explicit user approval with full explanation before execution

## Review Checklist (every PR)
1. Any new secrets or credentials exposed in the diff?
2. Any new dependencies? Check security posture.
3. Any new input paths? Validate and sanitize.
4. Any changes to auth logic? Verify generic error responses.
5. Any hardcoded keys, tokens, or passwords?
