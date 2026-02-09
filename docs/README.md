# Документация `kwork`

`kwork` — асинхронная обёртка над API фриланс-биржи **kwork.ru** (на базе `aiohttp`).

## Навигация

- [Быстрый старт](getting-started.md)
- [Туториал (подробнее, с примерами)](tutorial.md)
- [Клиент: `Kwork` / `KworkClient`](client.md)
- [Бот: `KworkBot`](bot.md)
- [Web-сессия (kwork.ru): `KworkWebClient`](web.md)
- [OpenAPI-методы (автоген)](openapi.md)
- [Прокси](proxy.md)
- [Ошибки и ретраи](errors-and-retries.md)
- [Разработка](development.md)

## Версии и требования

- Python: `>= 3.12` (см. `pyproject.toml`)
- Основные зависимости: `aiohttp`, `pydantic`, `websockets`
- Опционально для socks-прокси: `kwork[proxy]` (через `aiohttp-socks`)

## Где смотреть примеры

Папка [`examples/`](../examples/) содержит рабочие сценарии:

- `examples/api.py` — базовая работа с API
- `examples/dialogs.py` — диалоги/сообщения
- `examples/projects_monitor.py` — мониторинг проектов
- `examples/bot.py`, `examples/auto_reply_bot.py` — боты
- `examples/web_exchange_offer.py` — web-авторизация (как в мобилке) + отклик на бирже

