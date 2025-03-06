import asyncio

from typing import List, Union
from urllib.parse import quote
from aiohttp.abc import AbstractCookieJar

from .logger import logger
from .exception import (
    EmptyQueryError,
    ProxyNotMatchError,
    NoProfileError,
    NoDomainError,
    NoIdError,
    LoginFailed
)
from .util import GET_request, POST_request, GET_request_cookies
from .abs import SearchPaginator, BookItem
from .profile import ZlibProfile
from .const import Extension, Language
from typing import Optional
import json


ZLIB_DOMAIN = "https://z-library.sk/"
LOGIN_DOMAIN = "https://z-library.sk/rpc.php"

ZLIB_TOR_DOMAIN = (
    "http://bookszlibb74ugqojhzhg2a63w5i2atv5bqarulgczawnbmsb6s6qead.onion"
)
LOGIN_TOR_DOMAIN = (
    "http://loginzlib2vrak5zzpcocc3ouizykn6k5qecgj2tzlnab5wcbqhembyd.onion/rpc.php"
)


class AsyncZlib:
    semaphore = True
    onion = False

    __semaphore = asyncio.Semaphore(64)
    _jar: Optional[AbstractCookieJar] = None

    cookies = None
    proxy_list = None

    _mirror = ""
    login_domain = None
    domain = None
    profile = None

    @property
    def mirror(self):
        return self._mirror

    @mirror.setter
    def mirror(self, value):
        if not value.startswith("http"):
            value = "https://" + value
        self._mirror = value

    def __init__(
        self,
        onion: bool = False,
        proxy_list: Optional[list] = None,
        disable_semaphore: bool = False,
    ):
        if proxy_list:
            if type(proxy_list) is list:
                self.proxy_list = proxy_list
                logger.debug("Set proxy_list: %s", str(proxy_list))
            else:
                raise ProxyNotMatchError

        if onion:
            self.onion = True
            self.login_domain = LOGIN_TOR_DOMAIN
            self.domain = ZLIB_TOR_DOMAIN
            self.mirror = self.domain

            if not proxy_list:
                print(
                    "Tor proxy must be set to route through onion domains.\n"
                    "Set up a tor service and use: onion=True, proxy_list=['socks5://127.0.0.1:9050']"
                )
                exit(1)
        else:
            self.login_domain = LOGIN_DOMAIN
            self.domain = ZLIB_DOMAIN

        if disable_semaphore:
            self.semaphore = False

    async def _r(self, url: str):
        if self.semaphore:
            async with self.__semaphore:
                return await GET_request(
                    url, proxy_list=self.proxy_list, cookies=self.cookies
                )
        else:
            return await GET_request(
                url, proxy_list=self.proxy_list, cookies=self.cookies
            )

    async def login(self, email: str, password: str):
        data = {
            "isModal": True,
            "email": email,
            "password": password,
            "site_mode": "books",
            "action": "login",
            "isSingleLogin": 1,
            "redirectUrl": "",
            "gg_json_mode": 1,
        }

        resp, jar = await POST_request(
            self.login_domain, data, proxy_list=self.proxy_list
        )
        resp = json.loads(resp)
        resp = resp['response']
        logger.debug(f"Login response: {resp}")
        if resp.get('validationError'):
            raise LoginFailed(json.dumps(resp, indent=4))
        self._jar = jar

        self.cookies = {}
        for cookie in self._jar:
            self.cookies[cookie.key] = cookie.value
        logger.debug("Set cookies: %s", self.cookies)

        if self.onion and self.domain:
            url = self.domain + "/?remix_userkey=%s&remix_userid=%s" % (
                self.cookies["remix_userkey"],
                self.cookies["remix_userid"],
            )
            resp, jar = await GET_request_cookies(
                url, proxy_list=self.proxy_list, cookies=self.cookies
            )

            self._jar = jar
            for cookie in self._jar:
                self.cookies[cookie.key] = cookie.value
            logger.debug("Set cookies: %s", self.cookies)

            self.mirror = self.domain
            logger.info("Set working mirror: %s" % self.mirror)
        else:
            self.mirror = ZLIB_DOMAIN.strip("/")

            if not self.mirror:
                raise NoDomainError

        self.profile = ZlibProfile(self._r, self.cookies, self.mirror, ZLIB_DOMAIN)
        return self.profile

    async def logout(self):
        self._jar = None
        self.cookies = None

    async def search(
        self,
        q: str = "",
        exact: bool = False,
        from_year: Optional[int] = None,
        to_year: Optional[int] = None,
        lang: List[Union[Language, str]] = [],
        extensions: List[Union[Extension, str]] = [],
        count: int = 10,
    ) -> SearchPaginator:
        if not self.profile:
            raise NoProfileError
        if not q:
            raise EmptyQueryError

        payload = f"{self.mirror}/s/{quote(q)}?"
        if exact:
            payload += "&e=1"
        if from_year:
            assert str(from_year).isdigit()
            payload += f"&yearFrom={from_year}"
        if to_year:
            assert str(to_year).isdigit()
            payload += f"&yearTo={to_year}"
        if lang:
            assert type(lang) is list
            for la in lang:
                if type(la) is str:
                    payload += f"&languages%5B%5D={la}"
                elif type(la) is Language:
                    payload += f"&languages%5B%5D={la.value}"
        if extensions:
            assert type(extensions) is list
            for ext in extensions:
                if type(ext) is str:
                    payload += f"&extensions%5B%5D={ext}"
                elif type(ext) is Extension:
                    payload += f"&extensions%5B%5D={ext.value}"

        paginator = SearchPaginator(
            url=payload, count=count, request=self._r, mirror=self.mirror
        )
        await paginator.init()
        return paginator

    async def get_by_id(self, id: str = ""):
        if not id:
            raise NoIdError

        book = BookItem(self._r, self.mirror)
        book["url"] = f"{self.mirror}/book/{id}"
        return await book.fetch()

    async def full_text_search(
        self,
        q: str = "",
        exact: bool = False,
        phrase: bool = False,
        words: bool = False,
        from_year: Optional[int] = None,
        to_year: Optional[int] = None,
        lang: List[Union[Language, str]] = [],
        extensions: List[Union[Extension, str]] = [],
        count: int = 10,
    ) -> SearchPaginator:
        if not self.profile:
            raise NoProfileError
        if not q:
            raise EmptyQueryError
        if not phrase and not words:
            raise Exception(
                "You should either specify 'words=True' to match words, or 'phrase=True' to match phrase."
            )

        payload = "%s/fulltext/%s?" % (self.mirror, quote(q))
        if phrase:
            check = q.split(" ")
            if len(check) < 2:
                raise Exception(
                    (
                        "At least 2 words must be provided for phrase search. "
                        "Use 'words=True' to match a single word."
                    )
                )
            payload += "&type=phrase"
        else:
            payload += "&type=words"

        if exact:
            payload += "&e=1"
        if from_year:
            assert str(from_year).isdigit()
            payload += f"&yearFrom={from_year}"
        if to_year:
            assert str(to_year).isdigit()
            payload += f"&yearTo={to_year}"
        if lang:
            assert type(lang) is list
            for la in lang:
                if type(la) is str:
                    payload += f"&languages%5B%5D={la}"
                elif type(la) is Language:
                    payload += f"&languages%5B%5D={la.value}"
        if extensions:
            assert type(extensions) is list
            for ext in extensions:
                if type(ext) is str:
                    payload += f"&extensions%5B%5D={ext}"
                elif type(ext) is Extension:
                    payload += f"&extensions%5B%5D={ext.value}"

        paginator = SearchPaginator(
            url=payload, count=count, request=self._r, mirror=self.mirror
        )
        await paginator.init()
        return paginator
