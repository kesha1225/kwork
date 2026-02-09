# Прокси

Библиотека поддерживает прокси через параметр `proxy=...`.

Реализация основана на `aiohttp-socks`, поэтому для socks-прокси нужно поставить extra-зависимость:

```bash
pip install "kwork[proxy]"
```

## Использование

```python
from kwork import Kwork

api = Kwork(
    login="login",
    password="password",
    proxy="socks5://127.0.0.1:1080",
)
```

`proxy` можно передавать и в `KworkBot`.

## Частые причины

- “Подтвердите, что вы не робот” или нестабильная авторизация из одного IP
- региональные ограничения

## Ошибки установки

Если вы передали `proxy=...`, но не установили `aiohttp-socks`, будет `ImportError` с подсказкой вида:

- `pip install "kwork[proxy]"` (рекомендуется)
- или `pip install aiohttp-socks`

