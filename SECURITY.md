# Security Policy

## Supported Versions

| Version | Supported |
| --- | --- |
| `1.0.x` | Yes |
| `< 1.0.0` | No (upgrade to `1.0.x`) |

## Sensitive Data Handling

Never include secrets, SIM authentication credentials (`K` / `OPc` / `IMSI` / `ICCID`),
private keys, production configurations, raw diagnostics databases, logs, packet
captures, or Tailnet addresses in public issues or pull requests. Redact all
diagnostic outputs before sharing.

## Reporting a Vulnerability

Please report suspected security vulnerabilities privately rather than opening a
public issue:

- Submit a private report via [GitHub Security Advisories](https://github.com/HKUOpenSource/OpenAirKit/security/advisories/new).
- Include the affected platform (`Spark Console`, `Jetson Console`, deployment scripts, or stack tooling), release version, reproduction steps with redacted diagnostics, and any suggested mitigation.

Maintainers aim to acknowledge vulnerability reports within 7 days and coordinate
a fix before public disclosure.
