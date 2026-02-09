# Разработка

## Быстрый старт

Проект использует `uv` и хранит lockfile в `uv.lock`.

Установить dev-зависимости:

```bash
uv sync --group dev
```

## Качество кода

Линтер:

```bash
uv run ruff check .
```

Типизация (используется `basedpyright`):

```bash
uv run basedpyright
```

Юнит-тесты:

```bash
uv run python -m unittest discover -s tests -p "test_*.py"
```

## Локальные интеграционные проверки (с реальным аккаунтом)

См. [`local_tests/README.md`](../local_tests/README.md).

Важно: не коммитьте реальные логины/пароли. Используйте переменные окружения или `local_tests/config_local.py`
(он в `.gitignore`).

## Автоген OpenAPI-методов

Спецификация лежит в `docs/openapi.json`.
Миксин генерируется скриптом:

```bash
python3 scripts/generate_openapi_mixin.py
```

Результат: `source/kwork/openapi_mixin.py`.

