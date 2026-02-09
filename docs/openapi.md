# OpenAPI-методы (автоген)

В `kwork` есть автосгенерированный миксин `OpenAPIMethodsMixin` (`source/kwork/openapi_mixin.py`).
Он создаётся из спецификации `docs/openapi.json` скриптом `scripts/generate_openapi_mixin.py`.

Зачем это нужно:

- покрыть “все” эндпоинты без ручного написания сотен методов
- дать стабильные имена методов для автокомплита
- оставить типизацию поверхностей маленькой: все методы принимают `**params` и возвращают `dict`

## Как это выглядит в коде

```python
from kwork import Kwork


async with Kwork(login="login", password="password") as api:
    # Пример: вызов эндпоинта /actor через автоген-обёртку.
    # Параметры передаются как kwargs.
    data = await api.actor()
    print(data["response"]["username"])
```

Что важно:

- автоген-методы обычно возвращают “сырое” `dict`, а не модели из `kwork.schema`
- у каждого метода есть docstring с `HTTP /path`, кратким описанием из OpenAPI и типом авторизации

## Как формируются имена методов

Из имени эндпоинта (пути без `/`) делается `snake_case`.

Примеры:

- `/acceptExtras` -> `accept_extras(...)`
- `/getWebAuthToken` -> `get_web_auth_token(...)`

Разрешение конфликтов имён:

- если имя совпадает с уже существующим методом из `source/kwork/client.py` или `source/kwork/api.py`,
  добавляется суффикс (`_api`, `_api2`, ...).

## Регенерация

```bash
python3 scripts/generate_openapi_mixin.py
```

После этого изменится файл `source/kwork/openapi_mixin.py`.
