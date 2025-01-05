from .abs import BooklistPaginator
from .const import OrderOptions
from typing import Callable, Optional
from .exception import ParseError


class Booklists:
    __r: Optional[Callable] = None
    cookies = {}
    mirror: Optional[str] = None

    def __init__(self, request, cookies, mirror):
        self.__r = request
        self.cookies = cookies
        self.mirror = mirror

    async def search_public(
        self, q: str = "", count: int = 10, order: OrderOptions | str = ""
    ):
        if not self.__r or not self.mirror:
            raise ParseError(
                "Instance of Booklist does not contain a valid request method."
            )
        if type(order) is OrderOptions:
            val = order.value
        else:
            val = order
        url = self.mirror + f"/booklists?searchQuery={q}&order={val}"
        paginator = BooklistPaginator(url, count, self.__r, self.mirror)
        return await paginator.init()

    async def search_private(
        self, q: str = "", count: int = 10, order: OrderOptions | str = ""
    ):
        if not self.__r or not self.mirror:
            raise ParseError(
                "Instance of Booklist does not contain a valid request method."
            )
        if type(order) is OrderOptions:
            val = order.value
        else:
            val = order
        url = self.mirror + f"/booklists/my?searchQuery={q}&order={val}"
        paginator = BooklistPaginator(url, count, self.__r, self.mirror)
        return await paginator.init()
