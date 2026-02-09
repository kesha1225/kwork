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

📖 **[Полный туториал](docs/tutorial.md)** — API, боты, прокси, примеры

📚 **[Документация (оглавление)](docs/README.md)** — навигация по разделам

## Web-авторизация (kwork.ru)

Некоторые действия в мобильном приложении выполняются через WebView (домен `kwork.ru`), а не через `api.kwork.ru`.
В библиотеке это делается через `getWebAuthToken` (mobile API) + переход по `login-by-token` (web).

```python
import asyncio
from kwork import Kwork

async def main():
    async with Kwork(login="login", password="password") as api:
        await api.web_login(url_to_redirect="/exchange")
        # Отклик на проект/заказ на бирже (web-flow, как в браузере):
        resp = await api.web.submit_exchange_offer(
            project_id=2920487,
            offer_type="custom",
            description="Добрый день! Готов предложить услугу.",
            kwork_duration=3,
            kwork_price=1000,
            kwork_name="<div>Название предложения</div>",
        )
        print(resp["status"], resp["json"] or resp["text"][:200])

asyncio.run(main())
```

Если периодически появляется ошибка `"Подтвердите, что вы не робот"`, это антибот-защита сайта.
Обычно помогает повторить попытку или использовать `proxy=...` (см. `docs/tutorial.md#прокси`).

## Contributors

- [@iamlostshe](https://github.com/iamlostshe)
