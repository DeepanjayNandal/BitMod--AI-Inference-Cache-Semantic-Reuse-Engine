# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | Yes                |

## Reporting a Vulnerability

If you discover a security vulnerability in BitMod, please report it responsibly.

**Do not open a public GitHub issue for security vulnerabilities.**

Instead, email **security@bitmod.io** with:

- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will acknowledge receipt within 48 hours and aim to release a fix within 7 days for critical vulnerabilities.

## Security Considerations

BitMod handles API keys and LLM provider credentials. When deploying:

- Never commit `.env` files or `bitmod.yaml` with API keys to version control
- Use environment variables or secrets management for production deployments
- Enable authentication (`BITMOD_AUTH_ENABLED=true`) for any public-facing deployment
- Review CORS origins (`BITMOD_CORS_ORIGINS`) to restrict access
- API keys are stored as SHA-256 hashes — plaintext keys are never persisted
- JWT tokens have configurable expiry (default: 1 hour (3600 seconds))
