# Клиент: `Kwork` / `KworkClient`

```python
from kwork import Kwork  # алиас на KworkClient
```

`KworkClient` объединяет:

- базовый транспорт/ретраи: `KworkAPI` (`source/kwork/api.py`)
- автосгенерированные методы из `docs/openapi.json`: `OpenAPIMethodsMixin`
- дополнительные эндпоинты из APK: `APKExtraMethodsMixin`
- web-клиент для `kwork.ru`: `.web` / `web_login(...)`
- несколько удобных “ручных” методов (см. ниже)

## Жизненный цикл

Рекомендуемый вариант: `async with ...` (сессия будет закрыта автоматически).

```python
import asyncio
from kwork import Kwork


async def main() -> None:
    async with Kwork(login="login", password="password") as api:
        me = await api.get_me()
        print(me.username)


asyncio.run(main())
```

Если создаёте клиент вручную, не забывайте `await api.close()`.

## Часто используемые методы (высокий уровень)

Эти методы возвращают **pydantic-модели** из `kwork.schema`:

- `get_me()` -> `Actor`
- `get_user(user_id: int)` -> `User`
- `get_categories()` -> `list[ParentCategory]`
- `get_projects(...)` -> `list[WantWorker]`
- `get_connects()` -> `Connects`
- `get_dialogs_page(...)` -> `list[DialogMessage]`
- `get_all_dialogs()` -> `list[DialogMessage]`
- `get_dialog_with_user(username: str)` -> `list[InboxMessage]`
- `get_dialog_with_user_page(...)` -> `(list[InboxMessage], paging_dict)`

И ещё несколько “сырьевых” методов (возвращают `dict`):

- `send_message(user_id: int, text: str)`
- `delete_message(message_id: int)`
- `set_typing(recipient_id: int)`
- `set_offline()`
- `get_channel()` -> `str` (нужен для WebSocket-бота)
- `get_notifications()`
- `get_worker_orders()`, `get_payer_orders()`

Полный список см. в `source/kwork/client.py`.

## Низкоуровневые запросы

Если нужного удобного метода нет, можно вызывать API напрямую.

1) Параметры в query string / form params (без body):

```python
data = await api.request("post", "projects", use_token=True, categories="11,79")
```

2) Запрос с body (обычно `application/x-www-form-urlencoded` по OpenAPI):

```python
data = await api.request_with_body(
    "inboxCreate",
    use_token=True,
    user_id=123,
    body={"text": "Привет!"},
)
```

3) Multipart (загрузка файлов):

```python
data = await api.request_multipart(
    "someUploadEndpoint",
    use_token=True,
    fields={"foo": "bar"},
    files={"file": "/path/to/file.png"},
)
```

Подробнее: [Ошибки и ретраи](errors-and-retries.md).

## Автоген OpenAPI-методов

См. страницу: [OpenAPI-методы](openapi.md).

## Web-сессия (kwork.ru)

См. страницу: [Web-сессия](web.md).

