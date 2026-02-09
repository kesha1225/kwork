from typing import Any

from kwork.api import KworkAPI
from kwork.apk_extra_mixin import APKExtraMethodsMixin
from kwork.openapi_mixin import OpenAPIMethodsMixin
from kwork.schema import (
    Actor,
    Connects,
    DialogMessage,
    InboxMessage,
    ParentCategory,
    User,
    WantWorker,
)
from kwork.web_client import KworkWebClient, WebLoginResult


class KworkClient(OpenAPIMethodsMixin, APKExtraMethodsMixin, KworkAPI):
    _web_client: KworkWebClient | None = None

    @property
    def web(self) -> KworkWebClient:
        """
        Web client for kwork.ru that uses the official mobile /getWebAuthToken flow.
        """
        if self._web_client is None:
            self._web_client = KworkWebClient(self)
        return self._web_client

    async def web_login(
        self,
        *,
        url_to_redirect: str | None = "/",
        user_agent: str | None = None,
    ) -> WebLoginResult:
        """
        Establish a web session (kwork.ru cookies) using the official mobile app flow.
        """
        return await self.web.login_via_mobile_web_auth_token(
            url_to_redirect=url_to_redirect,
            user_agent=user_agent,
        )

    async def get_me(self) -> Actor:
        data = await self.request("post", "actor", use_token=True)
        return Actor(**data["response"])

    async def get_user(self, user_id: int) -> User:
        data = await self.request("post", "user", id=user_id)
        return User(**data["response"])

    async def set_typing(self, recipient_id: int) -> dict[str, Any]:
        return await self.request(
            "post",
            "typing",
            use_token=True,
            recipientId=recipient_id,
        )

    async def set_offline(self) -> dict[str, Any]:
        return await self.request("post", "offline", use_token=True)

    async def get_channel(self) -> str:
        data = await self.request("post", "getChannel", use_token=True)
        return data["response"]["channel"]

    async def send_message(self, user_id: int, text: str) -> dict[str, Any]:
        return await self.request_with_body(
            "inboxCreate",
            use_token=True,
            # Avoid duplicate messages on retries; caller can opt in explicitly if desired.
            retry=False,
            body={"text": text},
            user_id=user_id,
        )

    async def delete_message(self, message_id: int) -> dict[str, Any]:
        return await self.request(
            "post",
            "inboxDelete",
            use_token=True,
            id=message_id,
        )

    async def get_dialogs_page(
        self,
        page: int = 1,
        excluded_ids: str | None = None,
    ) -> list[DialogMessage]:
        data = await self.request(
            "post",
            "dialogs",
            use_token=True,
            page=page,
            excludedIds=excluded_ids,
        )
        response = data.get("response") or []
        return [DialogMessage(**d) for d in response]

    async def get_all_dialogs(self) -> list[DialogMessage]:
        dialogs: list[DialogMessage] = []
        page = 1

        while True:
            page_dialogs = await self.get_dialogs_page(page)
            if not page_dialogs:
                break
            dialogs.extend(page_dialogs)
            page += 1

        return dialogs

    async def get_dialog_with_user(self, username: str) -> list[InboxMessage]:
        messages: list[InboxMessage] = []
        page = 1

        while True:
            page_messages, paging = await self.get_dialog_with_user_page(username, page=page)
            if not page_messages:
                break

            messages.extend(page_messages)
            if page >= paging.get("pages", page):
                break
            page += 1

        return messages

    async def get_dialog_with_user_page(
        self,
        username: str,
        *,
        page: int = 1,
    ) -> tuple[list[InboxMessage], dict[str, Any]]:
        """
        Получить одну страницу сообщений диалога с пользователем.

        Возвращает (messages, paging), где paging обычно содержит ключ 'pages'.
        """
        data = await self.request(
            "post",
            "inboxes",
            use_token=True,
            username=username,
            page=page,
        )

        response = data.get("response") or []
        paging = data.get("paging") or {}
        return [InboxMessage(**m) for m in response], paging

    async def get_worker_orders(self) -> dict[str, Any]:
        return await self.request(
            "post",
            "workerOrders",
            use_token=True,
            filter="all",
        )

    async def get_payer_orders(self) -> dict[str, Any]:
        return await self.request(
            "post",
            "payerOrders",
            use_token=True,
            filter="all",
        )

    async def get_notifications(self) -> dict[str, Any]:
        return await self.request("post", "notifications", use_token=True)

    async def get_categories(self) -> list[ParentCategory]:
        data = await self.request("post", "categories")
        return [ParentCategory(**c) for c in data["response"]]

    async def get_connects(self) -> Connects:
        data = await self.request(
            "post",
            "projects",
            use_token=True,
            categories="",
        )
        return Connects(**data["connects"])

    async def get_projects(
        self,
        categories_ids: list[int | str],
        price_from: int | None = None,
        price_to: int | None = None,
        hiring_from: int | None = None,
        kworks_filter_from: int | None = None,
        kworks_filter_to: int | None = None,
        page: int | None = None,
        query: str | None = None,
    ) -> list[WantWorker]:
        """
        Получить список проектов.

        categories_ids: ID рубрик через запятую или 'all' для всех рубрик.
            Пустой список — выборка по любимым рубрикам.
        price_from: Бюджет от (включительно)
        price_to: Бюджет до (включительно)
        hiring_from: Процент найма от
        kworks_filter_from: Количество предложений от (не включительно)
        kworks_filter_to: Количество предложений до (включительно)
        page: Страница выдачи
        query: Поисковая строка
        """
        categories_str = ",".join(str(c) for c in categories_ids)

        data = await self.request(
            "post",
            "projects",
            use_token=True,
            categories=categories_str,
            price_from=price_from,
            price_to=price_to,
            hiring_from=hiring_from,
            kworks_filter_from=kworks_filter_from,
            kworks_filter_to=kworks_filter_to,
            page=page,
            query=query,
        )
        return [WantWorker(**p) for p in data["response"]]
