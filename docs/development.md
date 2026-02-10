# Разработка

## Локальные проверки

```bash
uv run ruff check source/kwork examples
uv run pyright -p pyrightconfig.json
uv run pytest
```

## Документация (MkDocs)

Документация лежит в `docs/` и собирается в статический сайт через MkDocs.

Локальный предпросмотр:

```bash
uv run mkdocs serve
```

Сборка:

```bash
uv run mkdocs build
```
