# kwork

Асинхронная Python-библиотека для работы с **kwork.ru**:

- API-клиент для `api.kwork.ru`
- Web-flow для `kwork.ru` (web-куки через официальную mobile-цепочку `/getWebAuthToken`)
- WebSocket-события и боты (`KworkBot`)
- Типизированные модели (`pydantic`)

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

## Навигация

- [Быстрый старт](getting-started.md): установка, логин, типовые операции
- [Гайд (подробно)](guide.md): про клиент, бота, прокси и web-flow
- [API-справка](api.md): автогенерируемая справка по публичным объектам
- [Разработка](development.md): локальные проверки и принципы
