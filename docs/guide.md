# Документация `kwork`

`kwork` — асинхронная Python-библиотека для работы с **kwork.ru** (на базе `aiohttp`).

Эта документация одна: здесь собраны клиент, бот, прокси и web-flow для биржи.

## Содержание

- [Установка](#установка)
- [Быстрый старт](#быстрый-старт)
- [API-клиент: `Kwork` / `KworkClient`](#api-клиент-kwork--kworkclient)
- [Проекты (биржа): получить список](#проекты-биржа-получить-список)
- [Отклик на проект (web-flow как в браузере)](#отклик-на-проект-web-flow-как-в-браузере)
- [Бот: `KworkBot`](#бот-kworkbot)
- [Прокси и "Подтвердите, что вы не робот"](#прокси-и-подтвердите-что-вы-не-робот)
- [Ошибки и ретраи](#ошибки-и-ретраи)
- [Примеры](#примеры)
- [Разработка](#разработка)

## Установка

Рекомендуемый способ (через `uv`):

```bash
uv add kwork
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

## API-клиент: `Kwork` / `KworkClient`

```python
from kwork import Kwork  # алиас на KworkClient
```

`KworkClient` объединяет:

- базовый транспорт/ретраи: `KworkAPI` (`source/kwork/api.py`)
- автосгенерированные методы из `docs/openapi.json`: `OpenAPIMethodsMixin`
- дополнительные методы, найденные в APK: `APKExtraMethodsMixin`
- web-клиент для `kwork.ru`: `api.web` + `await api.web_login(...)`
- несколько удобных высокоуровневых методов, например `get_me()`, `get_projects()` и т.д.

### Частые методы

Эти методы возвращают pydantic-модели из `kwork.schema`:

- `get_me()` -> `Actor`
- `get_user(user_id)` -> `User`
- `get_categories()` -> `list[ParentCategory]`
- `get_projects(...)` -> `list[WantWorker]`
- `get_connects()` -> `Connects`

И сырые методы, которые возвращают `dict`:

- `send_message(user_id, text)`
- `get_notifications()`
- `get_worker_orders()`, `get_payer_orders()`

Полный список см. в `source/kwork/client.py`.

### Низкоуровневые запросы

Если удобного метода нет, можно вызвать endpoint напрямую:

```python
data = await api.request("post", "projects", use_token=True, categories="11,79")
```

Запрос с body:

```python
data = await api.request_with_body(
    "inboxCreate",
    use_token=True,
    user_id=123,
    body={"text": "Привет!"},
)
```

Multipart:

```python
data = await api.request_multipart(
    "someUploadEndpoint",
    use_token=True,
    fields={"foo": "bar"},
    files={"file": "/path/to/file.png"},
)
```

## Проекты (биржа): получить список

```python
projects = await api.get_projects(
    categories_ids=[11, 79],
    price_from=1000,
    price_to=50000,
    hiring_from=50,
    page=1,
)
print("projects:", len(projects))
```

## Отклик на проект (web-flow как в браузере)

Почему это отдельный раздел:

- “mobile API” (`api.kwork.ru`) не содержит стабильной публичной ручки “создать отклик на бирже”.
- Официальное приложение/сайт делает отклик через web-страницы `kwork.ru` (WebView + XHR).

В библиотеке это реализовано так же, как в мобильном приложении:

1. `POST /getWebAuthToken` на `api.kwork.ru` (с mobile token) возвращает одноразовую ссылку `login-by-token`
2. переход по ней выставляет web-cookie для `kwork.ru`
3. дальше выполняется browser-like цепочка запросов для `/new_offer?...` и финальный `POST /api/offer/createoffer`

Минимальный пример:

```python
import asyncio
from kwork import Kwork


async def main() -> None:
    async with Kwork(login="login", password="password") as api:
        await api.web_login(url_to_redirect="/exchange")

        resp = await api.web.submit_exchange_offer(
            project_id=3094218,
            offer_type="custom",
            description="Добрый день! Готов предложить услугу.",
            kwork_duration=3,
            kwork_price=1000,
            kwork_name="<div>Название предложения</div>",
        )
        print(resp["status"], resp["json"] or resp["text"][:200])


asyncio.run(main())
```

Пример из репозитория: `examples/web_exchange_offer.py`.

Важно:

- это **web-endpoint**, он может меняться без предупреждения (это не часть OpenAPI `api.kwork.ru`)

## Бот: `KworkBot`

`KworkBot` наследуется от `KworkClient` и слушает события через WebSocket:
`wss://notice.kwork.ru/ws/public/{channel}`.

```python
import asyncio
from kwork import KworkBot
from kwork.schema import Message


bot = KworkBot(login="login", password="password")


@bot.message_handler(on_start=True)
async def welcome(message: Message) -> None:
    await message.answer_simulation("Здравствуйте!")


@bot.message_handler(text_contains="бот")
async def bot_request(message: Message) -> None:
    await message.answer_simulation("Вам нужен бот?")


@bot.message_handler()
async def fallback(message: Message) -> None:
    await message.fast_answer("Спасибо за сообщение!")


asyncio.run(bot.run())
```

## Прокси и "Подтвердите, что вы не робот"

Иногда `kwork.ru`/`api.kwork.ru` может отвечать антибот-сообщением вида:
`"Подтвердите, что вы не робот"`.

Что обычно помогает:

- повторить попытку (иногда это разовая защита)
- использовать другой IP (прокси)

### Как включить прокси

1) Поставь extra-зависимость:

```bash
pip install "kwork[proxy]"
```

2) Передай прокси в клиент/бот:

```python
from kwork import Kwork

api = Kwork(
    login="login",
    password="password",
    proxy="socks5://127.0.0.1:1080",
)
```

## Ошибки и ретраи

Исключения лежат в `source/kwork/exceptions.py`:

- `KworkException` — базовая ошибка
- `KworkHTTPException` — HTTP-ошибка (полезные поля: `status`, `endpoint`, `response_text`, `response_json`)
- `KworkRetryExceeded` — закончились попытки ретрая

Ретраи настраиваются в конструкторе:

```python
from kwork import Kwork

api = Kwork(
    login="login",
    password="password",
    retry_max_attempts=3,
    retry_backoff_base=0.5,
    retry_backoff_max=8.0,
    retry_jitter=0.1,
    relogin_on_auth_error=True,
)
```

## Примеры

Папка `examples/`:

- `examples/api.py` — базовая работа с API
- `examples/dialogs.py` — диалоги/сообщения
- `examples/projects_monitor.py` — мониторинг проектов
- `examples/bot.py`, `examples/auto_reply_bot.py` — боты
- `examples/web_exchange_offer.py` — web-авторизация + отклик на бирже

Запуск web-примера:

```bash
KWORK_LOGIN='...' KWORK_PASSWORD='...' KWORK_PROJECT_ID='3094218' uv run python examples/web_exchange_offer.py
```

## Разработка

Локальные проверки:

```bash
uv run ruff check source/kwork examples
uv run pyright -p pyrightconfig.json
```

