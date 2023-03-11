from .abs import BooklistPaginator
from .const import OrderOptions


class Booklists:
    __r = None
    cookies = {}
    mirror = None

    def __init__(self, request, cookies, mirror):
        self.__r = request
        self.cookies = cookies
        self.mirror = mirror

    async def search_public(self, q: str = "", count: int = 10, order: OrderOptions = ""):
        url = self.mirror + '/booklists?searchQuery=%s&order=%s' % (q, order.value)
        paginator = BooklistPaginator(url, count, self.__r, self.mirror)
        return await paginator.init()

    async def search_private(self, q: str = "", count: int = 10, order: OrderOptions = ""):
        url = self.mirror + '/booklists/my?searchQuery=%s&order=%s' % (q, order.value)
        paginator = BooklistPaginator(url, count, self.__r, self.mirror)
        return await paginator.init()
