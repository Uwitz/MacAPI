# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.2.x   | :white_check_mark: |
| < 0.2   | :x:                |

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Email security reports to: `security@snyco.dev` (replace with your real
contact). You should receive a response within 72 hours. If you don't,
follow up via the email's read receipt or resend.

## What to include

- A description of the vulnerability and its impact
- Steps to reproduce
- The MacAPI version affected
- Your contact info (optional, for follow-up)

## Scope

In scope:
- TLS / certificate handling bugs
- Authentication / authorization bypasses (OWNER_TOKEN, owner_token body field)
- Password-hash verification bypasses
- macOS Keychain / secret handling
- Cloudflare Tunnel misconfiguration that exposes the password
- Anything that lets a remote attacker unlock the Mac without holding both
  the OWNER_TOKEN and the correct Mac password

Out of scope:
- The fact that Cloudflare Tunnel terminates TLS at the edge and can see
  plaintext passwords (this is documented behavior of Cloudflare Tunnel)
- Physical access to the Mac
- Compromise of the user's iCloud / iPhone

## Disclosure timeline

- Day 0: you report
- Day 1-3: acknowledgment
- Day 7-30: investigation + fix
- After fix: public disclosure (coordinated with you, if you want credit)
