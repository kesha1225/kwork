# Kwork Tutorial

## Содержание

- [Установка](#установка)
- [API-клиент](#api-клиент)
  - [Основные методы](#основные-методы)
  - [Фильтрация проектов](#фильтрация-проектов)
- [Бот](#бот)
  - [Фильтры обработчиков](#фильтры-обработчиков)
  - [Методы ответа](#методы-ответа)
- [Прокси](#прокси)
- [Двухфакторная авторизация](#двухфакторная-авторизация)
- [Примеры](#примеры)

---

## Установка

```bash
pip install kwork
```

Для поддержки socks5-прокси (рекомендуется ставить через extras):

```bash
pip install "kwork[proxy]"
```

Альтернатива (если ставите зависимость напрямую):

```bash
pip install aiohttp-socks
```

---

## API-клиент

```python
import asyncio
from kwork import Kwork

async def main():
    api = Kwork(login="login", password="password")

    try:
        me = await api.get_me()
        print(me.username, me.free_amount)
    finally:
        await api.close()

asyncio.run(main())
```

### Основные методы

| Метод                            | Описание                          |
| -------------------------------- | --------------------------------- |
| `get_me()`                       | Информация о текущем пользователе |
| `get_user(user_id)`              | Профиль пользователя по ID        |
| `get_connects()`                 | Баланс коннектов                  |
| `get_categories()`               | Все категории кворков             |
| `get_projects(categories_ids)`   | Проекты в категориях              |
| `get_all_dialogs()`              | Все диалоги                       |
| `get_dialog_with_user(username)` | Сообщения с пользователем         |
| `send_message(user_id, text)`    | Отправить сообщение               |
| `delete_message(message_id)`     | Удалить сообщение                 |
| `get_notifications()`            | Уведомления                       |

### Фильтрация проектов

```python
projects = await api.get_projects(
    categories_ids=[11, 79],
    price_from=1000,
    price_to=50000,
    hiring_from=50,
)
```

---

## Бот

```python
import asyncio
from kwork import KworkBot
from kwork.schema import Message

bot = KworkBot(login="login", password="password")

@bot.message_handler(on_start=True)
async def welcome(message: Message):
    await message.answer_simulation("Здравствуйте!")

@bot.message_handler(text_contains="бот")
async def bot_request(message: Message):
    await message.answer_simulation("Вам нужен бот?")

@bot.message_handler(text="привет")
async def hello(message: Message):
    await message.answer_simulation("И вам привет!")

@bot.message_handler()
async def fallback(message: Message):
    await message.fast_answer("Спасибо за сообщение!")

asyncio.run(bot.run())
```

### Фильтры обработчиков

| Параметр              | Описание                   |
| --------------------- | -------------------------- |
| `on_start=True`       | Первое сообщение в диалоге |
| `text="..."`          | Точное совпадение текста   |
| `text_contains="..."` | Содержит слово             |
| без параметров        | Все остальные сообщения    |

### Методы ответа

```python
await message.answer_simulation(text)  # с имитацией набора
await message.fast_answer(text)        # мгновенный ответ
```

---

## Прокси

```python
api = Kwork(
    login="login",
    password="password",
    proxy="socks5://127.0.0.1:1080"
)
```

При ошибке "Подтвердите что вы не робот" — используйте прокси.

---

## Двухфакторная авторизация

При ошибке "Необходимо ввести последние 4 цифры номера телефона":

```python
api = Kwork(
    login="login",
    password="password",
    phone_last="1234"
)
```

---

## Примеры

Смотрите папку [`examples/`](../examples/):

| Файл                  | Описание             |
| --------------------- | -------------------- |
| `api.py`              | Базовая работа с API |
| `bot.py`              | Простой бот          |
| `auto_reply_bot.py`   | Бот-автоответчик     |
| `categories.py`       | Категории и проекты  |
| `dialogs.py`          | Работа с диалогами   |
| `projects_monitor.py` | Мониторинг проектов  |
| `web_exchange_offer.py` | Web-авторизация (как в мобилке) + отклик на бирже |
