from datetime import date
from bs4 import BeautifulSoup as bsoup
from .abs import DownloadsPaginator
from .booklists import Booklists, OrderOptions
from .exception import ParseError
from .logger import logger

class ZlibProfile:
    __r = None
    cookies = {}
    domain = None
    mirror = None

    def __init__(self, request, cookies, mirror, domain):
        self.__r = request
        self.cookies = cookies
        self.mirror = mirror
        self.domain = domain

    async def get_limits(self):
        resp = await self.__r(self.mirror + "/users/downloads")
        soup = bsoup(resp, features="lxml")
        dstats = soup.find("div", {"class": "dstats-info"})
        if not dstats:
            raise ParseError(
                f"Could not parse download limit at url: {self.mirror + '/users/downloads'}"
            )

        dl_info = dstats.find("div", {"class": "d-count"})
        if not dl_info:
            raise ParseError(
                f"Could not parse download limit info at url: {self.mirror + '/users/downloads'}"
            )
        dl_info = dl_info.text.strip().split("/")
        daily = int(dl_info[0])
        allowed = int(dl_info[1])

        dl_reset = dstats.find("div", {"class": "d-reset"})
        if not dl_reset:
            logger.warning(f"Unable to parse the time for daily download reset.")
            dl_reset = ""
        else:
            dl_reset = dl_reset.text.strip()

        return {
            "daily_amount": daily,
            "daily_allowed": allowed,
            "daily_remaining": allowed - daily,
            "daily_reset": dl_reset,
        }


    async def download_history(self, page: int = 1, date_from: date = None, date_to: date = None):
        if date_from:
            assert type(date_from) is date
        if date_to:
            assert type(date_to) is date
        if page:
            assert type(page) is int

        dfrom = date_from.strftime('%y-%m-%d') if date_from else ''
        dto = date_to.strftime('%y-%m-%d') if date_to else ''
        url = self.mirror + '/users/dstats.php?date_from=%s&date_to=%s' % (dfrom, dto)

        paginator = DownloadsPaginator(url, page, self.__r, self.mirror)
        return await paginator.init()

    async def search_public_booklists(self, q: str, count: int = 10, order: OrderOptions = ""):
        if order:
            assert isinstance(order, OrderOptions)
        
        paginator = Booklists(self.__r, self.cookies, self.mirror)
        return await paginator.search_public(q, count=count, order=order)

    async def search_private_booklists(self, q: str, count: int = 10, order: OrderOptions = ""):
        if order:
            assert isinstance(order, OrderOptions)
        
        paginator = Booklists(self.__r, self.cookies, self.mirror)
        return await paginator.search_private(q, count=count, order=order)
