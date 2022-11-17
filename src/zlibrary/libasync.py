import asyncio

from bs4 import BeautifulSoup as bsoup
from typing import List
from urllib.parse import quote

from .logger import logger
from .exception import EmptyQueryError, NoDomainError, ProxyNotMatchError
from .util import GET_request, POST_request
from .abs import SearchPaginator
from .profile import ZlibProfile


ZLIB_DOMAIN = "https://z-lib.org/"
LOGIN_DOMAIN = "https://singlelogin.me/rpc.php"

ZLIB_TOR_DOMAIN = "http://bookszlibb74ugqojhzhg2a63w5i2atv5bqarulgczawnbmsb6s6qead.onion"
LOGIN_TOR_DOMAIN = "http://loginzlib2vrak5zzpcocc3ouizykn6k5qecgj2tzlnab5wcbqhembyd.onion/rpc.php"


class AsyncZlib:
    semaphore = True
    onion = False

    __semaphore = asyncio.Semaphore(64)
    _jar = None

    cookies = None
    proxy_list = None

    mirror = ""
    login_domain = None
    domain = None
    profile = None

    def __init__(self, onion: bool = False, proxy_list: list = None, disable_semaphore: bool = False):
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
                print("Tor proxy must be set to route through onion domains.\n"
                      "Set up tor service and use: onion=True, proxy_list=['socks5://127.0.0.1:9050']")
                exit(1)
        else:
            self.login_domain = LOGIN_DOMAIN
            self.domain = ZLIB_DOMAIN

        if disable_semaphore:
            self.semaphore = False

    async def init(self):
        if self.onion:
            self.mirror = self.domain
            logger.debug("Set working mirror: %s" % self.mirror)
            return

        page = await self._r(self.domain)
        soup = bsoup(page, features='lxml')
        check = soup.find('div', { 'class': 'domain-check-error hidden' })
        if not check:
            raise NoDomainError

        dom = soup.find('div', { 'class': 'domain-check-success' })
        if not dom:
            raise NoDomainError

        self.mirror = "%s" % dom.text.strip()
        if not self.mirror.startswith('http'):
            self.mirror = 'https://' + self.mirror
        logger.debug("Set working mirror: %s" % self.mirror)

    async def _r(self, url: str):
        if self.semaphore:
            async with self.__semaphore:
                return await GET_request(url, proxy_list=self.proxy_list, cookies=self.cookies)
        else:
            return await GET_request(url, proxy_list=self.proxy_list, cookies=self.cookies)

    async def login(self, email: str, password: str):
        data = {
            "isModal": True,
            "email": email,
            "password": password,
            "site_mode": "books",
            "action": "login",
            "isSingleLogin": 1,
            "redirectUrl": "",
            "gg_json_mode": 1
        }

        resp, jar = await POST_request(self.login_domain, data, proxy_list=self.proxy_list)
        self._jar = jar

        self.cookies = {}
        for cookie in self._jar:
            self.cookies[cookie.key] = cookie.value
        logger.debug("Set cookies: %s", self.cookies)

        if self.onion:
            url = self.domain + '/?remix_userkey=%s&remix_userid=%s' % (self.cookies['remix_userkey'], self.cookies['remix_userid'])
            resp, jar = await GET_request(url, proxy_list=self.proxy_list, cookies=self.cookies, save_cookies=True)

            self._jar = jar
            for cookie in self._jar:
                self.cookies[cookie.key] = cookie.value
            logger.debug("Set cookies: %s", self.cookies)

        self.profile = ZlibProfile(self._r, self.cookies, self.mirror)
        return self.profile

    async def logout(self):
        self._jar = None
        self.cookies = None

    async def search(self, q: str = "", exact: bool = False, from_year: int = None, to_year: int = None,
                     lang: List[str] = [], extensions: List[str] = [], count: int = 10) -> SearchPaginator:
        if not q:
            raise EmptyQueryError

        payload = "%s/s/%s?" % (self.mirror, quote(q))
        if exact:
            payload += '&e=1'
        if from_year:
            assert str(from_year).isdigit()
            payload += '&yearFrom=%s' % (from_year)
        if to_year:
            assert str(to_year).isdigit()
            payload += '&yearTo=%s' % (to_year)
        if lang:
            assert type(lang) is list
            for l in lang:
                payload += '&languages%5B%5D={}'.format(l)
        if extensions:
            assert type(extensions) is list
            for ext in extensions:
                payload += '&extensions%5B%5D={}'.format(ext)

        paginator = SearchPaginator(url=payload, count=count, request=self._r, mirror=self.mirror)
        await paginator.init()
        return paginator

    async def full_text_search(self, q: str = "", exact: bool = False, phrase: bool = False,
                               words: bool = False, from_year: int = None, to_year: int = None,
                               lang: List[str] = [], extensions: List[str] = [], count: int = 10) -> SearchPaginator:
        if not q:
            raise EmptyQueryError
        if not phrase and not words:
            raise Exception("You should either specify 'words=True' to match words, or 'phrase=True' to match phrase.")

        payload = "%s/fulltext/%s?" % (self.mirror, quote(q))
        if phrase:
            check = q.split(' ')
            if len(check) < 2:
                raise Exception(("At least 2 words must be provided for phrase search. "
                                 "Use 'words=True' to match a single word."))
            payload += '&type=phrase'
        else:
            payload += '&type=words'

        if exact:
            payload += '&e=1'
        if from_year:
            assert str(from_year).isdigit()
            payload += '&yearFrom=%s' % (from_year)
        if to_year:
            assert str(to_year).isdigit()
            payload += '&yearTo=%s' % (to_year)
        if lang:
            assert type(lang) is list
            for l in lang:
                payload += '&languages%5B%5D={}'.format(l)
        if extensions:
            assert type(extensions) is list
            for ext in extensions:
                payload += '&extensions%5B%5D={}'.format(ext)

        paginator = SearchPaginator(url=payload, count=count, request=self._r, mirror=self.mirror)
        await paginator.init()
        return paginator
