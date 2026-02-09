from kwork.api import KworkAPI
from kwork.bot import KworkBot
from kwork.client import KworkClient
from kwork.web_client import KworkWebClient, WebLoginResult

Kwork = KworkClient

__all__ = (
    "Kwork",
    "KworkAPI",
    "KworkBot",
    "KworkClient",
    "KworkWebClient",
    "WebLoginResult",
)
