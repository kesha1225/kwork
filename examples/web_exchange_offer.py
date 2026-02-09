import asyncio
import os

from kwork import Kwork


async def main() -> None:
    login = os.environ.get("KWORK_LOGIN")
    password = os.environ.get("KWORK_PASSWORD")
    project_id = os.environ.get("KWORK_PROJECT_ID")
    if not login or not password:
        raise RuntimeError("Set KWORK_LOGIN and KWORK_PASSWORD env vars to run this example.")
    if not project_id:
        raise RuntimeError("Set KWORK_PROJECT_ID env var to run this example.")

    async with Kwork(login=login, password=password) as api:
        ua = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:147.0) "
            "Gecko/20100101 Firefox/147.0"
        )

        await api.web_login(url_to_redirect="/exchange", user_agent=ua)

        result = await api.web.submit_exchange_offer(
            project_id=int(project_id),
            offer_type="custom",
            description="Добрый день! Готов предложить услугу. Добрый день! Готов предложить услугу. Добрый день! Готов предложить услугу. Добрый день! Готов предложить услугу. Добрый день! Готов предложить услугу.",
            kwork_duration=3,
            kwork_price=1000,
            kwork_name="<div>VB cкрипт приема платежей для сайта</div>",
            user_agent=ua,
            raise_on_error=False,
        )

        print("HTTP:", result["status"])
        if result["json"] is not None:
            print("JSON:", result["json"])
        else:
            print("TEXT:", result["text"][:500])


if __name__ == "__main__":
    asyncio.run(main())
