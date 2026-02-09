# kwork

Асинхронная обёртка над API фриланс-биржи [kwork.ru](https://kwork.ru/)

## Установка

```bash
uv add kwork
```

или последняя версия:

```bash
uv add git+https://github.com/kesha1225/pykwork
```

## Быстрый старт

```python
import asyncio
from kwork import Kwork

async def main():
    api = Kwork(
        login="login",
        password="password",
        # Таймаут на запросы (секунды) или aiohttp.ClientTimeout(...)
        timeout=30.0,
        # Ретраи на 5xx/429 и сетевые ошибки (ограниченные попытки)
        retry_max_attempts=3,
    )

    try:
        me = await api.get_me()
        print(f"{me.username} | {me.free_amount} {me.currency}")
    finally:
        await api.close()

asyncio.run(main())
```

📚 **[Документация](docs/README.md)** — один дружелюбный гайд (API-клиент, боты, прокси, web-авторизация и отклик на бирже)

## Contributors

- [@iamlostshe](https://github.com/iamlostshe)
