# kwork

[![CI](https://github.com/kesha1225/pykwork/actions/workflows/ci.yml/badge.svg)](https://github.com/kesha1225/pykwork/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/kwork.svg)](https://pypi.org/project/kwork/)
[![Python](https://img.shields.io/pypi/pyversions/kwork.svg)](https://pypi.org/project/kwork/)
[![License](https://img.shields.io/pypi/l/kwork.svg)](LICENSE)
[![Typing](https://img.shields.io/badge/typing-py.typed-informational.svg)](https://peps.python.org/pep-0561/)

Асинхронная, типизированная Python-библиотека для работы с [kwork.ru](https://kwork.ru/) (aiohttp + Pydantic).

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

async def main() -> None:
    async with Kwork(
        login="login",
        password="password",
        timeout=30.0,
        retry_max_attempts=3,
    ) as api:
        me = await api.get_me()
        print(f"{me.username} | {me.free_amount} {me.currency}")

asyncio.run(main())
```

Ещё примеры см. в `examples/` и в [гайде](docs/guide.md).

## Документация

- [Главная](docs/index.md)
- [Быстрый старт](docs/getting-started.md)
- [Гайд (подробно)](docs/guide.md)
- [API-справка](docs/api.md)
- [Разработка](docs/development.md)


## Contributors

- [@iamlostshe](https://github.com/iamlostshe)
