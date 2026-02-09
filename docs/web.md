# Web-сессия (kwork.ru): `KworkWebClient`

Некоторые действия в мобильном приложении выполняются через WebView на домене `kwork.ru`,
а не через мобильный API `api.kwork.ru`.

В библиотеке это реализовано так же, как в официальном приложении:

1. `POST /getWebAuthToken` на `api.kwork.ru` (с мобильным токеном) возвращает одноразовый `login-by-token` URL
2. `GET` этого URL на `kwork.ru` выставляет web-cookie (как WebView)

После этого можно делать запросы на `kwork.ru` в рамках cookie jar `aiohttp`.

## Быстрый пример

```python
import asyncio
from kwork import Kwork


async def main() -> None:
    async with Kwork(login="login", password="password") as api:
        # Установить web-cookie (kwork.ru) через официальную мобильную схему.
        await api.web_login(url_to_redirect="/exchange")

        # Пример XHR на kwork.ru (не api.kwork.ru)
        resp = await api.web.create_exchange_offer(
            want_id=2920487,
            offer_type="custom",
            description="Добрый день! Готов предложить услугу.",
            kwork_duration=1,
            kwork_price=500,
            kwork_name="Мое предложение",
        )
        print(resp["status"], (resp["json"] or resp["text"][:200]))


asyncio.run(main())
```

## Что доступно

- `api.web` -> `KworkWebClient` (лениво создаётся и переиспользует `aiohttp`-сессию API)
- `await api.web_login(...)` — удобная обёртка над `api.web.login_via_mobile_web_auth_token(...)`
- `await api.web.request(method, path_or_url, ...)` — низкоуровневые запросы на `kwork.ru`
- `await api.web.create_exchange_offer(...)` — пример конкретного web-эндпоинта

## Ограничения

- Web-эндпоинты могут меняться без предупреждения (это не официально документированное API).
- Некоторые действия на сайте могут требовать дополнительные заголовки/параметры, как в браузере.

