<!--
Metadata quick wins (for maintainers):
- GitHub repo "About" description: "Async, typed Python client for kwork.ru (aiohttp + Pydantic) with WebSocket bot and web-flow helpers."
- GitHub Topics: kwork, kwork-api, freelance, marketplace, asyncio, aiohttp, websockets, bot, pydantic, typed, python
-->

# kwork

[![CI](https://github.com/kesha1225/pykwork/actions/workflows/ci.yml/badge.svg)](https://github.com/kesha1225/pykwork/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/kwork.svg)](https://pypi.org/project/kwork/)
[![Python](https://img.shields.io/pypi/pyversions/kwork.svg)](https://pypi.org/project/kwork/)
[![License](https://img.shields.io/pypi/l/kwork.svg)](LICENSE)
[![Typing](https://img.shields.io/badge/typing-py.typed-informational.svg)](https://peps.python.org/pep-0561/)

Асинхронная обёртка над API фриланс-биржи [kwork.ru](https://kwork.ru/)

## Доверие и ограничения

- Проект **не является официальным** SDK kwork.ru и не аффилирован с площадкой.
- Часть функций работает через **web-endpoint** `kwork.ru` (а не OpenAPI `api.kwork.ru`) и может ломаться без предупреждения.

## Установка

```bash
uv add kwork
```

или последняя версия:

```bash
uv add git+https://github.com/kesha1225/pykwork
```

Альтернатива (pip):

```bash
pip install kwork
```

Если нужен socks5-прокси:

```bash
pip install "kwork[proxy]"
```

## Быстрый старт

```python
import asyncio
from kwork import Kwork

async def main():
    async with Kwork(
        login="login",
        password="password",
        # Таймаут на запросы (секунды) или aiohttp.ClientTimeout(...)
        timeout=30.0,
        # Ретраи на 5xx/429 и сетевые ошибки (ограниченные попытки)
        retry_max_attempts=3,
    ) as api:
        me = await api.get_me()
        print(f"{me.username} | {me.free_amount} {me.currency}")

asyncio.run(main())
```

📚 **[Документация](docs/index.md)** — полноценная документация

## Практические примеры

### 1) Отклик на проект на бирже

Для отклика на проект библиотека повторяет web-цепочку запросов (как делает сайт/приложение).
Минимальный рабочий пример уже есть в репозитории:

```bash
export KWORK_LOGIN="login"
export KWORK_PASSWORD="password"
export KWORK_PROJECT_ID="3094218"
uv run python examples/web_exchange_offer.py
```

Важно:

- это **web-endpoint** `kwork.ru`, он может меняться без предупреждения
- у `description` на стороне сайта есть минимальная длина (в примере >= 150 символов)
- соблюдай правила/лимиты площадки (иначе легко словить ограничения)


### 2) Автоответчик на входящие сообщения (бот)

Бот слушает события через WebSocket и отвечает по правилам/триггерам.

Запуск готового примера:

```bash
export KWORK_LOGIN="login"
export KWORK_PASSWORD="password"
uv run python examples/auto_reply_bot.py
```


Ещё полезные скрипты:

- `examples/projects_monitor.py` — мониторинг новых проектов по фильтрам (категории/цена)
- `examples/dialogs.py` — список диалогов и непрочитанных сообщений

## Contributors

- [@iamlostshe](https://github.com/iamlostshe)
