# Бот: `KworkBot`

`KworkBot` наследуется от `KworkClient` и слушает события через WebSocket
`wss://notice.kwork.ru/ws/public/{channel}`.

## Минимальный бот

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


@bot.message_handler(text="привет")
async def hello(message: Message) -> None:
    await message.answer_simulation("И вам привет!")


@bot.message_handler()
async def fallback(message: Message) -> None:
    await message.fast_answer("Спасибо за сообщение!")


asyncio.run(bot.run())
```

## Как выбирается обработчик

- обработчики проверяются **в порядке регистрации**
- срабатывает **первый** обработчик, чей фильтр подошёл
- если у обработчика нет параметров (`@bot.message_handler()`), он подходит под “всё остальное”

Доступные фильтры:

- `on_start=True` — только первое сообщение в диалоге
- `text="..."` — точное совпадение текста (без учета регистра)
- `text_contains="..."` — содержит слово (простая проверка по словам)

## Объект `Message`

`message` (класс `kwork.schema.Message`) содержит минимум:

- `from_id` — ID отправителя
- `text` — текст сообщения
- `api` — ссылка на клиента/бота (`KworkClient`), чтобы при необходимости вызывать API вручную

Методы ответа:

```python
await message.answer_simulation("...")  # с задержкой + "typing"
await message.fast_answer("...")        # мгновенно
```

## Остановка и устойчивость

- при сетевых ошибках бот переподключается с задержкой (см. `RECONNECT_DELAY` в `source/kwork/bot.py`)
- при отмене задачи (`asyncio.CancelledError`) бот корректно закрывает `aiohttp`-сессию

