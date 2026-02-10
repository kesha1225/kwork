# Contributing

## Development setup

This project uses `uv` and targets Python `>=3.12`.

```bash
uv sync --group dev
```

## Quality checks

```bash
uv run ruff check .
uv run basedpyright
uv run pytest
```

## Pull requests

- Keep changes focused and well-scoped.
- Add/adjust tests when behavior changes.
- If you touch public API, update `README.md` / `docs/index.md` / `docs/api.md` accordingly.

