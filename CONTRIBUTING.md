# Contributing

Contributions are welcome! Please follow these guidelines.

## Getting Started

1. Fork the repository
2. Create a branch off `main` for your change
3. Make your changes (one feature or fix per PR)
4. Ensure all checks pass before submitting

## Running Checks

Before submitting a pull request, make sure the following all pass:

```bash
ruff check .
mypy .
pytest
```

Or use the convenience script:

```bash
./scripts/check.sh
```

## Pull Requests

- Open your PR against `main`
- Describe what the PR does and why
- Link to a relevant issue if one exists
- Keep changes focused -- one feature or fix per PR

## Development Setup

This project uses [uv](https://docs.astral.sh/uv/) for dependency management:

```bash
uv sync --dev
```

Requires Python 3.11 or later.

## Security Issues

Please do not open public issues for security vulnerabilities. Instead, use
[GitHub's private security advisory feature](https://github.com/darcuri/wan-router-notifications/security/advisories/new).
See [SECURITY.md](SECURITY.md) for details.
