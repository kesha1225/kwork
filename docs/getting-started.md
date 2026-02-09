# Быстрый старт

## Установка

Рекомендуемый способ (через `uv`):

```bash
uv add kwork
```

Альтернатива (pip):

```bash
pip install kwork
```

Для socks5-прокси:

```bash
pip install "kwork[proxy]"
```

## Минимальный пример

```python
import asyncio
from kwork import Kwork


async def main() -> None:
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

## Дальше

- [Клиент: `Kwork` / `KworkClient`](client.md)
- [Туториал](tutorial.md)

