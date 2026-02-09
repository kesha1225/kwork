# Ошибки и ретраи

## Исключения

Все базовые исключения лежат в `source/kwork/exceptions.py`.

- `KworkException` — базовое исключение библиотеки
- `KworkHTTPException` — HTTP-ошибка или неожиданный/некорректный ответ
  - полезные поля: `status`, `method`, `endpoint`, `response_text`, `response_json`, `request_params`, `request_body`
- `KworkRetryExceeded` — исчерпаны попытки ретрая (обычно сетевые ошибки/таймауты)
  - поля: `attempts`, `last_error`
- `KworkBotException` — ошибки уровня бота (например, нет зарегистрированных handler-ов)

## Ретраи (KworkAPI)

Ретраи настраиваются в конструкторе `Kwork`/`KworkClient` (наследуется от `KworkAPI`):

- `retry_max_attempts` (по умолчанию `1`)
- `retry_backoff_base` (экспоненциальная задержка)
- `retry_backoff_max`
- `retry_jitter`
- `retry_statuses` (по умолчанию: `429, 500, 502, 503, 504`)
- `relogin_on_auth_error`
  - если `True`, при `401/403` библиотека может сбросить токен и залогиниться заново (только когда включены ретраи)

Пример:

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

## Таймауты

Параметр `timeout` в конструкторе принимает:

- `float` (секунды)
- `aiohttp.ClientTimeout`
- `None` (без таймаута)

Также `timeout` можно передавать на уровне конкретного запроса (`request(...)`, `request_with_body(...)`, и т.д.).

## Multipart и ретраи

`request_multipart(...)` по умолчанию **не** ретраит, потому что загрузки часто неидемпотентны.
Если ретраи нужны, включайте их явно (`retry=True` и/или `max_attempts=...`) и передавайте файлы как пути/bytes/tuple,
а не file-like объекты (их нельзя безопасно повторить).

## Логи и чувствительные данные

Если включить DEBUG-логирование для `kwork.api`, библиотека логирует параметры запросов/ответов в отредактированном виде:
значения для ключей вроде `password`, `token`, `authorization`, `phone_last` заменяются на `<redacted>`.
