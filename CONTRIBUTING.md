# Contributing to lol-genius

## Getting Started

1. Fork the repo and clone your fork
2. Create a virtual environment: `python -m venv .venv && source .venv/bin/activate`
3. Install in dev mode: `pip install -e ".[test]"`
4. Create a feature branch: `git checkout -b my-feature`

## Development

### Linting

```bash
ruff check .
ruff format .
```

### Testing

```bash
pytest tests/
pytest tests/test_features.py -k "test_rank_to_numeric"
```

Tests require a running PostgreSQL instance. See `docker-compose.yml` for the database setup.

### Migrations

```bash
brew install dbmate
dbmate new add_foo_column
```

Migration files go in `db/migrations/`.

## Pull Requests

- Keep PRs focused — one feature or fix per PR
- Ensure `ruff check .` passes with no errors
- Ensure `pytest tests/` passes
- Write descriptive commit messages

## Architecture Notes

- **No target leakage**: Features must be pre-game knowable. Never use in-game stats as model inputs.
- **Rate limits**: Never bypass the rate limiter in `api/client.py`.
- Named SQL params use `%(name)s` style (psycopg2).
